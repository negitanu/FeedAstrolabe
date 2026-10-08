import json
from pathlib import Path
import pytest
from feedastrolabe import create_app,network_adapters as a,network_intelligence as n,connectors as c,research as r,evidence as e,entities as entities
from feedastrolabe.db import get_db,connect,init_database
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
from test_reader import app,client,post
from test_phase_two import authorization
from test_entities import capture,context
from test_security import configure


def fixtures():
 return {
 'dns':{'Status':0,'AD':True,'TC':False,'Question':[{'name':'example.com.','type':1}],'Answer':[{'name':'example.com.','type':1,'TTL':300,'data':'1.1.1.1'}]},
 'rdap-bootstrap':{'version':'1.0','publication':'2026-10-08T00:00:00Z','services':[[['com'],['https://rdap.verisign.com/com/v1/']]]},
 'rdap':{'objectClassName':'domain','ldhName':'EXAMPLE.COM','handle':'example-id','status':['active'],'events':[{'eventAction':'registration','eventDate':'1995-08-14T00:00:00Z'}],'nameservers':[{'ldhName':'ns.example.com'}],'entities':[{'vcardArray':['vcard', [['fn',{},'text','personal contact']]]}],'links':[{'href':'http://127.0.0.1/private','rel':'related'}]},
 'routing':{'status':'ok','version':'1.1','time':'2026-10-08T00:00:00Z','data':{'asns':[15169],'prefix':'8.8.8.0/24'}},
 'rpki':{'status':'ok','version':'0.3','time':'2026-10-08T00:00:00Z','data':{'prefix':'8.8.8.0/24','resource':'15169','status':'valid','description':'Prefix-origin pair valid at source'}},
 'ct':[{'id':1,'issuer_name':'Fixture CA','common_name':'example.com','name_value':'example.com\n*.example.com','not_before':'2026-10-01T00:00:00','not_after':'2027-01-01T00:00:00','entry_timestamp':'2026-10-01T00:00:00'}]
 }


def setup(app,provider='dns',**options):
 with app.app_context():
  wid=r.create_workspace({'title':'Passive infrastructure'});kind='ip' if provider in ('routing','rpki') else 'domain';value='8.8.8.8' if kind=='ip' else 'example.com'
  eid=entities.create({'kind':kind,'value':value});body={'entity_id':eid,'provider':provider,'outbound_public':True}
  if provider=='rpki':body.update(prefix='8.8.8.0/24',origin='AS15169')
  body.update(options);watch=n.save_watch(wid,body);return wid,eid,watch


def cache(provider,value,payload,observed='2026-10-08 00:00:00'):
 raw=json.dumps(payload).encode();a.validate(provider,value,payload)
 with get_db() as db:db.execute('INSERT INTO connector_cache VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(provider,input) DO UPDATE SET payload=excluded.payload,response_hash=excluded.response_hash,observed_at=excluded.observed_at,expires_at=excluded.expires_at',(provider,value,c.dumps(payload),e.digest(raw),'https://dns.google/resolve','fixture-protocol',observed,c.later(3600)))


def test_dns_history_field_changes_ttl_scope_and_last_good(app,client):
 wid,eid,watch=setup(app)
 with app.app_context():
  first=fixtures()['dns'];cache('dns','example.com|A',first);oid=n.sync(watch);assert n.sync(watch)==oid
  assert n.card(watch)['ttl_expired'] and n.card(watch)['state']=='stale'
  first['Answer'][0]['TTL']=200;cache('dns','example.com|A',first,observed='2026-10-08 01:00:00');n.sync(watch)
  assert get_db().execute('SELECT count(*) FROM network_events').fetchone()[0]==0
  first['Answer'][0]['data']='8.8.8.8';cache('dns','example.com|A',first,observed='2026-10-08 02:00:00');n.sync(watch)
  event=get_db().execute('SELECT * FROM network_events').fetchone();assert set(json.loads(event['changes']))=={'rrset'}
  assert event['previous_id']!=event['current_id'] and get_db().execute('SELECT count(*) FROM network_observations').fetchone()[0]==3
  failed=dict(first,Status=2)
  with pytest.raises(ValueError):cache('dns','example.com|A',failed)
  assert n.card(watch)['observation']['normalized']['rrset'][0]['data']=='8.8.8.8'
  absent=dict(first,Status=3,Answer=[]);cache('dns','example.com|A',absent,observed='2026-10-08 03:00:00');n.sync(watch)
  assert n.card(watch)['observation']['normalized']['absence']=='nxdomain'
 assert client.get(f'/network/watches/{watch}').status_code==200


def test_public_inputs_pair_strictness_and_no_wildcard_or_private_probe(app):
 with app.app_context():
  for provider,value in [('dns','intranet.local|A'),('dns','*.example.com|A'),('dns','example.com|ANY'),('routing','ip|127.0.0.1'),('rdap','ip|10.0.0.1'),('rdap','ip|::ffff:8.8.8.8'),('ct','example.com&output=html'),('rpki','10.0.0.0/8|AS15169'),('rpki','8.8.8.1/24|AS15169'),('rpki','8.8.8.0/24|AS4294967296'),('rpki','8.8.8.0/24'),('routing','ip|224.0.0.1')]:
   with pytest.raises(ValueError):a.contract(provider,value)
  assert a.contract('rpki','8.8.8.0/24|AS15169')['prefix']=='8.8.8.0/24'
  wid=r.create_workspace({'title':'public'});entity=entities.create({'kind':'ip','value':'8.8.8.8'})
  with pytest.raises(ValueError):n.save_watch(wid,{'entity_id':entity,'provider':'rpki','prefix':'1.1.1.0/24','origin':'AS13335'})


def test_rdap_reviewed_bootstrap_longest_authority_and_no_referral_follow(app,monkeypatch):
 wid,eid,watch=setup(app,'rdap')
 with app.app_context():
  configure('rdap');configure('rdap-bootstrap')
  result=n.lookup(watch);assert result['job_id'] is None and result['bootstrap_job_id']
  boot=fixtures()['rdap-bootstrap'];cache('rdap-bootstrap','dns',boot)
  assert a.endpoint('rdap','domain|example.com')=='https://rdap.verisign.com/com/v1/domain/example.com'
  unreviewed={'version':'1.0','publication':'now','services':[[['com'],['https://127.0.0.1/rdap/']]]}
  with pytest.raises(ValueError):a.authority(a.contract('rdap','domain|example.com'),unreviewed)
  longer=fixtures()['rdap-bootstrap'];longer['services'].append([['example.com'],['https://unreviewed.example/']])
  with pytest.raises(ValueError):a.authority(a.contract('rdap','domain|example.com'),longer)
  cache('rdap','domain|example.com',fixtures()['rdap']);n.sync(watch)
  normalized=n.card(watch)['observation']['normalized'];assert normalized['referrals_followed'] is False and 'entities' not in normalized
  assert n.lookup(watch)['job_id']


def test_ct_issuance_ris_coverage_rpki_pair_and_caps(app):
 with app.app_context():
  ct=a.project('ct','example.com',fixtures()['ct']);assert 'serving endpoint not verified' in ct['interpretation']
  empty=a.project('ct','example.com',[]);assert empty['absence']=='not-seen-in-this-query'
  data=fixtures()['routing'];data['data']={'asns':[],'prefix':None}
  assert a.project('routing','ip|8.8.8.8',data)['absence']=='not-visible-at-RIS'
  rpki=fixtures()['rpki'];rpki['data']['status']='unknown';assert a.project('rpki','8.8.8.0/24|AS15169',rpki)['status']=='unknown'
  rpki['data']['resource']='13335'
  with pytest.raises(ValueError):a.project('rpki','8.8.8.0/24|AS15169',rpki)
  many=[dict(fixtures()['ct'][0],id=i) for i in range(300)];bounded=a.project('ct','example.com',many);assert bounded['truncated'] and len(bounded['certificates'])==200
  wrong=fixtures()['dns'];wrong['Question'][0]['name']='wrong.example.com'
  with pytest.raises(ValueError):a.project('dns','example.com|A',wrong)


def test_consent_scoped_api_revision_archival_and_watchlists(app,client,monkeypatch):
 wid,eid,watch=setup(app,outbound_public=False)
 write=authorization(app,'write')[2];read=authorization(app,'read')[2]
 with app.app_context():
  configure('dns');monkeypatch.setattr(c,'retrieve',lambda _:pytest.fail('must not send'))
  n.schedule();assert get_db().execute('SELECT count(*) FROM connector_jobs').fetchone()[0]==0
 assert client.post(f'/api/v1/network-watches/{watch}/lookup',headers=write).status_code==409
 assert client.post(f'/api/v1/network-watches/{watch}/lookup',headers=read).status_code==403
 assert client.patch(f'/api/v1/network-watches/{watch}',headers=write,json={'expected_revision':1,'outbound_public':True}).status_code==200
 assert client.patch(f'/api/v1/network-watches/{watch}',headers=write,json={'expected_revision':1,'enabled':False}).status_code==409
 assert client.patch(f'/api/v1/network-watches/{watch}',headers=write,json={'expected_revision':2,'entity_id':eid}).status_code==400
 with app.app_context():
  cache('dns','example.com|A',fixtures()['dns']);n.sync(watch)
  from feedastrolabe import triage
  condition=triage.save(wid,{'name':'DNS changed','query':{'any':[{'field':'text','op':'contains','value':'1.1.1.1'}]},'enabled':True})
  triage.process();assert get_db().execute('SELECT count(*) FROM watch_events WHERE included=1').fetchone()[0]>=1
  r.update_workspace(wid,{'archived':True})
 assert client.post(f'/api/v1/network-watches/{watch}/lookup',headers=write).status_code==409
 for path in [f'/api/v1/network-watches/{watch}/observations',f'/api/v1/network-watches/{watch}/events',f'/api/v1/workspaces/{wid}/network-watches']:
  assert client.get(path,headers=read).status_code==200
 assert client.post('/network/watches',data={}).status_code==400 and client.get('/network?workspace=').status_code==200


def test_retention_keeps_latest_quotes_notes_and_fixed_evidence(app):
 wid,eid,watch=setup(app,retention_days=7)
 with app.app_context():
  records=[]
  for index in range(3):
   data=fixtures()['dns'];data['Answer'][0]['data']=str(index)+'.1.1.1';cache('dns','example.com|A',data,observed=f'2000-01-0{index+1} 00:00:00');records.append(n.sync(watch))
  db=get_db();first=db.execute('SELECT evidence_id FROM network_observations WHERE id=?',(records[0],)).fetchone()[0];item=e.find(first)
  e.quotation(wid,{'evidence_id':first,'start':0,'end':5,'quote':item['text'][:5]})
  with db:db.execute("UPDATE network_events SET created_at='2000-01-01 00:00:00'")
  assert n.prune(watch)==1
  remaining=[row[0] for row in db.execute('SELECT id FROM network_observations ORDER BY id')];assert remaining==[records[0],records[-1]]
  assert db.execute('SELECT count(*) FROM evidence').fetchone()[0]==3 and db.execute('SELECT count(*) FROM workspace_evidence').fetchone()[0]==3


def test_v9_migration_v10_bundle_and_prior_contracts(app,tmp_path):
 prior=tmp_path/'v9';prior.mkdir();db=connect(prior/'feeds.sqlite3');db.executescript(Path('tests/fixtures/v9_schema.sql').read_text());db.close()
 bundle=tmp_path/'v9-bundle';backup_bundle(prior/'feeds.sqlite3',bundle);restore_bundle(bundle,tmp_path/'restore'/'feeds.sqlite3')
 db=connect(tmp_path/'restore'/'feeds.sqlite3');assert db.execute('PRAGMA user_version').fetchone()[0]==10;assert db.execute('SELECT count(*) FROM connector_settings').fetchone()[0]==9;assert db.execute('SELECT sum(enabled) FROM connector_settings').fetchone()[0]==0;db.close()
 wid,eid,watch=setup(app)
 with app.app_context():
  cache('dns','example.com|A',fixtures()['dns']);n.sync(watch)
 bundle2=tmp_path/'v10-bundle';backup_bundle(app.config['DATABASE'],bundle2);restore_bundle(bundle2,tmp_path/'restore2'/'feeds.sqlite3')
 db=connect(tmp_path/'restore2'/'feeds.sqlite3');assert db.execute('SELECT count(*) FROM network_observations').fetchone()[0]==1;assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
