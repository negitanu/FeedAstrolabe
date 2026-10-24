import json
from pathlib import Path
import pytest
from feedastrolabe import create_app,connectors as c,security_intelligence as s,security_adapters as a,connector_http as h,evidence as e,research as r,entities as n
from feedastrolabe.db import get_db,connect,init_database
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
from test_reader import app,client,post
from test_phase_two import authorization
from test_entities import capture,context

CVE='CVE-2021-44228'

def payloads():
 return {
 'kev':{'catalogVersion':'2026.10.08','dateReleased':'2026-10-08T00:00:00Z','count':1,'vulnerabilities':[{'cveID':CVE,'vendorProject':'Apache','product':'Log4j','vulnerabilityName':'Fixture','shortDescription':'Fixture record','dateAdded':'2021-12-10','dueDate':'2021-12-24','requiredAction':'Vendor says update','notes':'https://example.com/advisory'}]},
 'epss':{'status':'OK','status-code':200,'version':'1.0','total':1,'data':[{'cve':CVE,'epss':'0.95','percentile':'0.99','date':'2026-10-08'}]},
 'cve':{'dataType':'CVE_RECORD','dataVersion':'5.2','cveMetadata':{'cveId':CVE,'state':'PUBLISHED','dateUpdated':'2026-10-08T00:00:00Z'},'containers':{'cna':{'providerMetadata':{'shortName':'Apache'},'descriptions':[{'lang':'en','value':'Fixture <script>alert(1)</script>'}],'affected':[{'vendor':'Apache','product':'Log4j','versions':[{'version':'2.x','status':'affected'}]}],'metrics':[{'cvssV3_1':{'version':'3.1','baseScore':10.0,'vectorString':'CVSS:3.1/AV:N'}}],'references':[{'url':'https://example.com/advisory'},{'url':'http://127.0.0.1/private'}],'solutions':[{'value':'Vendor says upgrade','lang':'en'}]},'adp':[{'providerMetadata':{'shortName':'ADP'},'metrics':[{'cvssV4_0':{'version':'4.0','baseScore':9.5,'vectorString':'CVSS:4.0/AV:N'}}]}]}}
 }


def configure(provider):
 c.configure(provider,{'expected_revision':c.setting(provider)['revision'],'enabled':True})


def run(provider,monkeypatch,data=None):
 data=payloads()[provider] if data is None else data
 monkeypatch.setattr(c,'retrieve',lambda url:(data,json.dumps(data).encode()))
 job=c.enqueue(provider,{'input':'catalog' if provider=='kev' else CVE,'public_identifier':True});result=c.process(1)
 assert result['processed']==1
 return job


def setup(app):
 with app.app_context():
  eid=capture(app,'Apache Log4j 2.0 deployed, reviewed applicability')
  wid,qid=context(app,eid);cid=n.create({'kind':'cve','value':CVE})
  watch=s.save_watch(wid,{'entity_id':cid,'product':'Log4j','version':'2.0','outbound_public':True})
  return wid,qid,cid,watch


def test_consent_registered_inputs_cache_budget_and_daily_reset(app,monkeypatch):
 setup(app)
 with app.app_context():
  with pytest.raises(r.ResearchConflict):c.enqueue('epss',{'input':CVE,'public_identifier':True})
  configure('epss')
  for body in [{'input':CVE},{'input':'https://evil.example','public_identifier':True},{'input':CVE,'public_identifier':True,'token':'fixture'}]:
   with pytest.raises(ValueError):c.enqueue('epss',body)
  job=run('epss',monkeypatch);assert c.enqueue('epss',{'input':CVE,'public_identifier':True})==job
  assert get_db().execute('SELECT requests FROM connector_state WHERE provider=\'epss\'').fetchone()[0]==1
  with get_db() as db:db.execute("UPDATE connector_cache SET expires_at='2000-01-01 00:00:00'")
  nextjob=c.enqueue('epss',{'input':CVE,'public_identifier':True});assert c.enqueue('epss',{'input':CVE,'public_identifier':True})==nextjob
  assert c.process()['processed']==0  # min60 seconds
  with get_db() as db:db.execute("UPDATE connector_state SET last_request=NULL,requests=100")
  assert c.process()['processed']==0
  with get_db() as db:db.execute("UPDATE connector_state SET budget_day='2000-01-01'")
  assert c.process()['processed']==1
  assert get_db().execute('SELECT requests FROM connector_state WHERE provider=\'epss\'').fetchone()[0]==1


def test_signals_evidence_stale_unknown_and_qualified_match(app,client,monkeypatch):
 wid,qid,cid,wid2=setup(app)
 with app.app_context():
  assert s.card(wid2)['signals']['epss']['data'] is None
  for provider in a.PROVIDERS:configure(provider);run(provider,monkeypatch)
  assert s.sync(cid)==3 and s.sync(cid)==0
  card=s.card(wid2);assert card['applicability']['status']=='possible'
  assert card['signals']['kev']['data']['listed'] is True
  assert card['signals']['epss']['data']['score']==0.95
  assert len(card['signals']['cve']['data']['severity'])==2
  assert len(card['signals']['cve']['data']['references'])==1
  with get_db() as db:
   db.execute("UPDATE connector_cache SET expires_at='2000-01-01 00:00:00' WHERE provider='epss'");db.execute("UPDATE connector_state SET last_request=NULL WHERE provider='epss'")
  monkeypatch.setattr(c,'retrieve',lambda url:(_ for _ in ()).throw(h.ConnectorError('http-503')))
  job=c.enqueue('epss',{'input':CVE,'public_identifier':True});c.process(1)
  old=s.card(wid2)['signals']['epss'];assert old['state']=='stale' and old['data']['score']==0.95 and old['error']=='http-503'
  assert get_db().execute('SELECT status FROM connector_jobs WHERE id=?',(job,)).fetchone()[0]=='queued'
  with get_db() as db:db.execute("UPDATE evidence SET captured_at='2000-01-01 00:00:00'")
  e.prune();assert get_db().execute('SELECT count(*) FROM security_observations').fetchone()[0]==3
 response=client.get(f'/security/watches/{wid2}');assert response.status_code==200 and '<script>' not in response.text and '&lt;script&gt;' in response.text


def test_missing_epss_is_unknown_not_zero_and_wrong_records_preserve_cache(app,monkeypatch):
 wid,qid,cid,watch=setup(app)
 with app.app_context():
  configure('epss');empty=payloads()['epss'];empty.update(total=0,data=[]);run('epss',monkeypatch,empty);s.sync(cid)
  data=s.observations(cid)['epss']['data'];assert data['score'] is None and data['available'] is False
  for change in [{'epss':'NaN'},{'epss':'1.1'},{'cve':'CVE-2026-0001'}]:
   bad=payloads()['epss'];bad['data'][0].update(change)
   with pytest.raises(ValueError):a.validate('epss',CVE,bad)
  with pytest.raises(ValueError):a.validate('kev','catalog',dict(payloads()['kev'],count=2))
  bad=payloads()['cve'];bad['dataVersion']='6.0'
  with pytest.raises(ValueError):a.validate('cve',CVE,bad)


def test_manual_review_quote_scope_atomic_history_and_watch_edit(app,client):
 wid,qid,cid,watch=setup(app);other,otherquote=context(app,capture(app,'other claim'))
 with app.app_context():
  for body in [{'expected_revision':1,'status':'confirmed','reason':'confirmed'}, {'expected_revision':1,'status':'confirmed','reason':'confirmed','quotation_id':otherquote}]:
   with pytest.raises(ValueError):s.review(watch,body)
  assert s.watch(watch)['revision']==1
  s.review(watch,{'expected_revision':1,'status':'confirmed','quotation_id':qid,'reason':'fixed quote confirms','author':'reviewer'})
  assert s.card(watch)['applicability']['status']=='confirmed'
  with pytest.raises(r.ResearchConflict):s.review(watch,{'expected_revision':1,'status':'unknown','reason':'stale'})
  s.review(watch,{'expected_revision':2,'status':'possible','reason':'more checks needed'})
  assert get_db().execute('SELECT count(*) FROM security_reviews').fetchone()[0]==2
  s.save_watch(wid,{'expected_revision':3,'version':'3.0'},watch)
  assert s.card(watch)['applicability']['status']=='unknown'
  r.update_workspace(wid,{'archived':True})
  with pytest.raises(r.ResearchConflict):s.review(watch,{'expected_revision':4,'status':'unknown','reason':'archived'})
 write=authorization(app,'write')[2];read=authorization(app,'read')[2]
 assert client.post(f'/api/v1/security-watches/{watch}/reviews',headers=read,json={}).status_code==403
 assert client.get(f'/api/v1/security-watches/{watch}',headers=read).status_code==200
 assert client.post('/security/watches',data={}).status_code==400
 assert client.patch('/api/v1/connectors/epss',headers=write,json={'expected_revision':1,'enabled':'yes'}).status_code==400
 assert client.get('/security?workspace=').status_code==200


def test_poc_reference_is_quoted_metadata_only_and_no_private_url(app,monkeypatch):
 wid,qid,cid,watch=setup(app)
 monkeypatch.setattr(c,'retrieve',lambda _:pytest.fail('reference must not fetch'))
 with app.app_context():
  body={'entity_id':cid,'url':'https://example.com/poc','kind':'poc','quotation_id':qid,'reviewed':True}
  first=s.reference(wid,body);assert s.reference(wid,body)==first
  for changed in [{'reviewed':False},{'url':'http://127.0.0.1/poc'},{'url':'javascript:alert(1)'}]:
   with pytest.raises(ValueError):s.reference(wid,dict(body,**changed))


def test_safe_transport_redirect_rate_limit_dns_and_credential_confinement(monkeypatch):
 seen=[]
 class Response:
  status=302
  def getheaders(self):return [('Location','http://127.0.0.1/secret'),('Retry-After','3600')]
 class Connection:
  sock=None
  def __init__(self,*args):seen.append(args)
  def request(self,method,path,headers):seen.append(headers);assert not any(k.lower() in ('authorization','cookie') for k in headers)
  def getresponse(self):return Response()
  def close(self):pass
 monkeypatch.setattr(h,'public_address',lambda host,port:('fixture',))
 monkeypatch.setattr(h,'PinnedHTTP',Connection)
 with pytest.raises(h.ConnectorError,match='redirect-rejected'):h.retrieve(a.endpoint('epss',CVE))
 assert len(seen)==2
 Response.status=429
 with pytest.raises(h.ConnectorError) as info:h.retrieve(a.endpoint('epss',CVE))
 assert info.value.code=='rate-limited' and info.value.retry_at
 monkeypatch.setattr(h,'public_address',lambda *_:(_ for _ in ()).throw(ValueError('private target')))
 before=len(seen)
 with pytest.raises(h.ConnectorError,match='transport-or-format'):h.retrieve(a.endpoint('epss',CVE))
 assert len(seen)==before


def test_retry_exhaustion_idempotent_parallel_queue_and_config_conflict(app,monkeypatch):
 setup(app)
 with app.app_context():
  configure('epss');monkeypatch.setattr(c,'retrieve',lambda _:(_ for _ in ()).throw(h.ConnectorError('rate-limited',c.later(3600))))
  job=c.enqueue('epss',{'input':CVE,'public_identifier':True})
  for count in range(3):
   if count:
    with get_db() as db:
     db.execute('UPDATE connector_state SET last_request=NULL,cooldown_until=NULL');db.execute("UPDATE connector_jobs SET next_attempt='2000-01-01 00:00:00'")
   assert c.process(1)['processed']==1
  row=get_db().execute('SELECT * FROM connector_jobs WHERE id=?',(job,)).fetchone();assert row['attempts']==3 and row['status']=='failed'
  with pytest.raises(r.ResearchConflict):c.configure('epss',{'expected_revision':1,'enabled':False})


def test_v8_migration_and_v9_bundle_preserves_security_assessment(app,tmp_path,monkeypatch):
 prior=tmp_path/'v8';prior.mkdir();db=connect(prior/'feeds.sqlite3');db.executescript(Path('tests/fixtures/v8_schema.sql').read_text());db.close()
 bundle=tmp_path/'v8-bundle';backup_bundle(prior/'feeds.sqlite3',bundle);restored=tmp_path/'restore'/'feeds.sqlite3';restore_bundle(bundle,restored)
 db=connect(restored);assert db.execute('PRAGMA user_version').fetchone()[0]==18;assert db.execute('SELECT sum(enabled) FROM connector_settings').fetchone()[0]==0;db.close()
 wid,qid,cid,watch=setup(app)
 with app.app_context():
  configure('epss');run('epss',monkeypatch);s.sync(cid);s.review(watch,{'expected_revision':1,'status':'confirmed','quotation_id':qid,'reason':'fixture'})
 bundle2=tmp_path/'v9-bundle';backup_bundle(app.config['DATABASE'],bundle2);restore_bundle(bundle2,tmp_path/'restore2'/'feeds.sqlite3')
 db=connect(tmp_path/'restore2'/'feeds.sqlite3');assert db.execute('SELECT status FROM security_reviews').fetchone()[0]=='confirmed';assert db.execute('SELECT count(*) FROM security_observations').fetchone()[0]==1;assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()


def test_concurrent_queue_and_cache_quota_keep_last_good(app,monkeypatch):
 from concurrent.futures import ThreadPoolExecutor
 setup(app)
 with app.app_context():configure('epss')
 def enqueue():
  with app.app_context():return c.enqueue('epss',{'input':CVE,'public_identifier':True})
 with ThreadPoolExecutor(max_workers=4) as pool:ids=list(pool.map(lambda _:enqueue(),range(8)))
 assert len(set(ids))==1
 with app.app_context():
  db=get_db();large=json.dumps({'fixture':'x'*(4*1024*1024)})
  with db:
   for index in range(4):db.execute('INSERT INTO connector_cache VALUES(?,?,?,?,?,?,?,?)',('cve',f'CVE-2026-{1000+index}',large,e.digest(large.encode()),'https://cveawg.mitre.org/api/cve/fixture','5.2',r.now(),c.later(86400)))
  data=payloads()['epss'];monkeypatch.setattr(c,'retrieve',lambda url:(data,json.dumps(data).encode()))
  assert c.process(1)['processed']==1
  assert db.execute('SELECT error FROM connector_jobs WHERE id=?',(ids[0],)).fetchone()[0]=='cache-quota'
  assert db.execute("SELECT count(*) FROM connector_cache WHERE provider='epss'").fetchone()[0]==0
