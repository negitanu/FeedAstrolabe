import csv,io,json,uuid,hmac,hashlib
from pathlib import Path
import pytest
from feedastrolabe import reports as p,delivery as d,operations as o,research as r,evidence as e,delivery_transport as t
from feedastrolabe.db import get_db,connect,init_database
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle,validate_bundle
from feedastrolabe.maintenance import restore
from test_reader import app,client,subscribe,post
from test_phase_two import authorization

def case(app,text='Public fixture: example.com AS15169 CVE-2021-44228.',classification='public',title='Public fixture'):
 with app.app_context():
  wid=r.create_workspace({'title':title,'classification':classification})
  with e.storage_lock(),r.transaction() as db:eid=e.save(db,source_key=uuid.uuid4().hex,title='=unsafe spreadsheet title',text=text,method='fixture',source_url='https://example.com/source')
  e.pin('workspace',wid,eid);return wid,eid

def setup_delivery(app,monkeypatch):
 wid,eid=case(app);monkeypatch.setattr(d,'endpoint',lambda x:x)
 with app.app_context():
  rid=p.create(wid,{'format':'json'});pid=d.profile({'name':'Fixture only','kind':'webhook','destination':'https://example.com/hook','enabled':True});prid=d.preview(rid,{'profile_id':pid});pr=d.find('delivery_previews',prid);jid=d.enqueue(prid,{'approved':True,'payload_hash':pr['payload_hash']});return wid,eid,rid,pid,prid,jid

def test_classification_shared_sources_csv_secrets_and_immutable_manifest(app):
 wid,eid=case(app);other,otherid=case(app,classification='restricted',text='nonpublic specimen',title='SECRET CASE')
 with app.app_context():
  rid=p.create(other,{'format':'json'});data=json.loads(p.find(rid)['payload']);assert data['records']==[] and 'SECRET CASE' not in p.find(rid)['payload'] and data['manifest']['excluded_count']==1
  e.pin('workspace',other,eid);default=p.create(wid,{'format':'json'});assert json.loads(p.find(default)['payload'])['records']==[]
  with pytest.raises(ValueError):p.create(wid,{'format':'json','evidence_ids':[otherid]})
  csv_id=p.create(wid,{'format':'csv','include_nonpublic':True});rows=list(csv.reader(io.StringIO(p.find(csv_id)['payload'])));assert rows[1][2].startswith("'=")
  for value in ['=1+1',' +command','-2','@SUM(1)','\tdata','\rdata']:assert p.cell(value).startswith("'")
  local=p.find(csv_id);assert json.loads(local['manifest'])['sources'][0]['text_hash']==e.find(eid)['text_hash']
  with pytest.raises(ValueError):p.outbound(local,get_db())
 bad,bid=case(app,text='pass'+'word='+('x'*20))
 with app.app_context():
  with pytest.raises(ValueError):p.create(bad,{'format':'markdown'})
  assert get_db().execute('SELECT count(*) FROM report_sources WHERE evidence_id=?',(bid,)).fetchone()[0]==0

def test_stix_subset_sco_sdo_mapping_and_source_note(app):
 from feedastrolabe import entities
 wid,eid=case(app)
 with app.app_context():
  entities.extract();rid=p.create(wid,{'format':'stix'});bundle=json.loads(p.find(rid)['payload']);assert bundle['type']=='bundle'
  objects=bundle['objects'];kinds={x['type'] for x in objects};assert {'domain-name','autonomous-system','vulnerability','note'}<=kinds
  ids={x['id'] for x in objects};note=next(x for x in objects if x['type']=='note');assert set(note['object_refs'])<=ids;assert 'not independently verified' in note['content']
  for obj in objects:
   assert obj['spec_version']=='2.1' and uuid.UUID(obj['id'].split('--')[1]).version==4
   if obj['type'] in ('note','vulnerability'):assert obj['created']==obj['modified']
  assert next(x for x in objects if x['type']=='autonomous-system')['number']==15169

def test_delivery_hash_approval_retry_stable_idempotency_and_success_no_resend(app,monkeypatch):
 wid,eid,rid,pid,prid,jid=setup_delivery(app,monkeypatch);sent=[]
 def send(profile,wire,key):
  sent.append((wire,key))
  if len(sent)<3:raise t.DeliveryError('delivery-http-503',True)
 monkeypatch.setattr(d,'deliver',send)
 with app.app_context():
  pr=d.find('delivery_previews',prid)
  with pytest.raises(r.ResearchConflict):d.enqueue(prid,{'approved':True,'payload_hash':'f'*64})
  with pytest.raises(ValueError):d.enqueue(prid,{'approved':False,'payload_hash':pr['payload_hash']})
  assert d.enqueue(prid,{'approved':True,'payload_hash':pr['payload_hash']})==jid
  for attempt in range(3):
   d.process();assert d.find('delivery_jobs',jid)['attempts']==attempt+1
   with get_db() as db:db.execute('UPDATE delivery_jobs SET next_attempt=? WHERE id=?',('2000-01-01',jid))
  assert d.find('delivery_jobs',jid)['status']=='success';assert d.process()=={'processed':0};assert len(sent)==3 and len({x[1] for x in sent})==1 and all(x[0]==pr['payload'] for x in sent)
  assert get_db().execute('SELECT count(*) FROM delivery_attempts').fetchone()[0]==3

def test_policy_change_ambiguous_interruption_and_max_attempts_stop(app,monkeypatch):
 wid,eid,rid,pid,prid,jid=setup_delivery(app,monkeypatch)
 with app.app_context():
  r.update_workspace(wid,{'classification':'restricted'});monkeypatch.setattr(d,'deliver',lambda *x:pytest.fail('policy changed must not send'));d.process();assert d.find('delivery_jobs',jid)['error']=='delivery-policy-invalid'
 wid,eid,rid,pid,prid,jid=setup_delivery(app,monkeypatch)
 with app.app_context():
  def ambiguous(*args):raise t.DeliveryError('delivery-ambiguous-transport')
  monkeypatch.setattr(d,'deliver',ambiguous);d.process();assert d.find('delivery_jobs',jid)['status']=='failed';d.process();assert d.find('delivery_jobs',jid)['attempts']==1
 wid,eid,rid,pid,prid,jid=setup_delivery(app,monkeypatch)
 with app.app_context():
  with get_db() as db:db.execute("UPDATE delivery_jobs SET status='running',attempts=1,started_at='2026-10-08' WHERE id=?",(jid,))
  monkeypatch.setattr(d,'deliver',lambda *x:pytest.fail('no interrupted replay'));d.process();assert d.find('delivery_jobs',jid)['error']=='delivery-interrupted-unknown'
 wid,eid,rid,pid,prid,jid=setup_delivery(app,monkeypatch)
 with app.app_context():
  def rejected(*args):raise t.DeliveryError('delivery-http-429',True)
  monkeypatch.setattr(d,'deliver',rejected)
  for _ in range(4):
   d.process()
   with get_db() as db:db.execute("UPDATE delivery_jobs SET next_attempt='2000-01-01' WHERE id=?",(jid,))
  assert d.find('delivery_jobs',jid)['status']=='failed' and d.find('delivery_jobs',jid)['attempts']==3

def test_signed_fixed_webhook_credentials_redirect_and_public_pin(app,tmp_path,monkeypatch):
 file=tmp_path/'delivery-credentials';config={'destinations':['https://example.com/hook'],'webhook_secret':'x'*40};file.write_text(json.dumps(config));file.chmod(0o600);app.config['DELIVERY_CONFIG_FILE']=str(file)
 with app.app_context():
  assert t.configuration()==config;file.chmod(0o644)
  with pytest.raises(t.DeliveryError):t.configuration()
  file.chmod(0o600);link=tmp_path/'link';link.symlink_to(file);app.config['DELIVERY_CONFIG_FILE']=str(link)
  with pytest.raises(t.DeliveryError):t.configuration()
  app.config['DELIVERY_CONFIG_FILE']=str(file)
  for url in ['http://example.com/','https://127.0.0.1/hook','https://example.com/?x=1','https://example.com/#a','https://user:pass@example.com/','https://example.com:8080/','https://example.com/'+('z'*32),'https://hooks.slack.com/services/fixture','https://example.com/path%0a']:
   with pytest.raises(ValueError):t.endpoint(url)
  sent=[];pin=[]
  class Conn:
   def request(self,method,path,body=None,headers=None):sent.append((method,path,body,headers))
   def getresponse(self):return type('Res',(),{'status':302})()
   def close(self):pass
  monkeypatch.setattr(t,'public_address',lambda host,port:pin.append((host,port)) or ('public',))
  monkeypatch.setattr(t,'PinnedHTTP',lambda *x:Conn())
  with pytest.raises(t.DeliveryError,match='302'):t.deliver({'kind':'webhook','destination':'https://example.com/hook'},'{}','fixture-id')
  headers=sent[0][3];assert headers['Idempotency-Key']=='fixture-id';assert headers['X-FeedAstrolabe-Signature']=='sha256='+hmac.new(('x'*40).encode(),b'{}',hashlib.sha256).hexdigest();assert pin and all(x==('example.com',443) for x in pin)
  with pytest.raises(t.DeliveryError,match='not-allowed'):t.deliver({'kind':'webhook','destination':'https://other.example/hook'},'{}','fixture-id')

def test_email_exact_recipient_tls_only_message_id_and_no_credential_audit(app,tmp_path,monkeypatch):
 file=tmp_path/'email-credentials';file.write_text(json.dumps({'destinations':['recipient@example.com'],'smtp':{'host':'smtp.example.com','port':465,'sender':'sender@example.com','username':'fixture','password':'x'*40}}));file.chmod(0o600);app.config['DELIVERY_CONFIG_FILE']=str(file)
 for target in ['a@example.com\r\nBcc: b@example.com','a@example.com,b@example.com','Name <a@example.com>']:
  with pytest.raises(ValueError):t.recipient(target)
 sent=[]
 class SMTP:
  def __init__(self,*args,**kwargs):assert args==('smtp.example.com',465) and kwargs['context'].check_hostname
  def login(self,*args):pass
  def send_message(self,message,**kwargs):sent.append((message,kwargs));return {}
  def close(self):pass
 monkeypatch.setattr(t.smtplib,'SMTP_SSL',SMTP);monkeypatch.setattr(t,'public_address',lambda *x:('public',))
 with app.app_context():t.deliver({'kind':'email','destination':'recipient@example.com'},'fixture exact payload','fixture-job')
 assert sent[0][0]['Message-ID']=='<fixture-job@feedastrolabe.local>' and sent[0][1]['to_addrs']==['recipient@example.com'] and 'x'*40 not in sent[0][0].as_string()

def test_health_staleness_safe_history_scheduled_backup_retention_and_offline_guard(app,tmp_path):
 wid,eid=case(app)
 with app.app_context():
  run=o.start('worker');o.end(run,7);health=o.health();assert not health['workers'][0]['stale'] and health['workers'][1]['stale'] and health['ci']['active'] is False
  with get_db() as db:db.execute("UPDATE worker_health SET heartbeat_at='2000-01-01'")
  assert o.health()['workers'][0]['stale'];o.schedule();assert get_db().execute('SELECT count(*) FROM backup_jobs').fetchone()[0]==0
  o.config({'expected_revision':1,'backup_enabled':True,'generations':1});o.schedule();job1=get_db().execute('SELECT * FROM backup_jobs').fetchone();o.process();row=get_db().execute('SELECT * FROM backup_jobs WHERE id=?',(job1['id'],)).fetchone();assert row['status']=='success';bundle=o.path_for(row['generation']);assert validate_bundle(bundle)
  source=Path(app.config['DATABASE']);before=get_db().execute('SELECT count(*) FROM evidence').fetchone()[0]
  with pytest.raises((ValueError,BlockingIOError)):restore_bundle(bundle,source)
  with pytest.raises(ValueError,match='稼働中'):restore(bundle/'feeds.sqlite3',source)
  assert get_db().execute('SELECT count(*) FROM evidence').fetchone()[0]==before
  restore_bundle(bundle,tmp_path/'offline'/'feeds.sqlite3');db=connect(tmp_path/'offline'/'feeds.sqlite3');assert db.execute('SELECT text FROM evidence').fetchone()[0]==e.find(eid)['text'];db.close()
  o.enqueue();o.process();assert not bundle.exists() and get_db().execute('SELECT retired_at FROM backup_jobs WHERE id=?',(job1['id'],)).fetchone()[0]
  new=get_db().execute('SELECT * FROM backup_jobs ORDER BY id DESC LIMIT 1').fetchone();bad=o.path_for(new['generation']);blob=next((bad/'evidence-blobs').iterdir());blob.unlink()
  destination=tmp_path/'offline'/'feeds.sqlite3';original=destination.read_bytes()
  with pytest.raises(ValueError):restore_bundle(bad,destination)
  assert destination.read_bytes()==original

def test_backup_quota_corruption_and_config_revision(app,tmp_path):
 wid,eid=case(app)
 with app.app_context():
  o.config({'expected_revision':1,'quota_bytes':1048576})
  with pytest.raises(r.ResearchConflict):o.config({'expected_revision':1,'generations':3})
  jid=o.enqueue();o.process();assert get_db().execute('SELECT status FROM backup_jobs WHERE id=?',(jid,)).fetchone()[0]=='failed'
  assert not list(o.root().iterdir())

def test_bounded_atomic_settings_bulk_opml_scope_and_csrf(app,client):
 subscribe(client);read=authorization(app,'read')[2];write=authorization(app,'write')[2]
 for data,status in [({'ids':[1],'is_read':True},403),({'ids':list(range(1,102)),'is_read':True},400),({'ids':[1,1],'is_read':True},400),({'ids':[1,99999],'is_read':True},404),({'ids':[True],'is_read':True},400)]:
  response=client.post('/api/v1/articles/bulk-state',headers=read if status==403 else write,json=data);assert response.status_code==status
 with app.app_context():assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0]==0
 assert client.post('/api/v1/articles/bulk-state',headers=write,json={'ids':[1,2],'is_read':True,'is_starred':True}).status_code==200
 assert client.patch('/api/v1/settings',headers=read,json={'poll_interval':600}).status_code==403
 before=client.get('/api/v1/settings',headers=read).json
 assert client.patch('/api/v1/settings',headers=write,json={'poll_interval':600,'page_size':1}).status_code==400
 assert client.get('/api/v1/settings',headers=read).json==before
 assert client.patch('/api/v1/settings',headers=write,json={'poll_interval':600,'polling_enabled':False}).json['data']['polling_enabled']==0
 xml=b'<opml version="2.0"><body><outline xmlUrl="https://example.com/new" text="New"/></body></opml>';headers={**write,'Content-Type':'application/xml'}
 assert client.post('/api/v1/opml',headers=read,data=xml).status_code==403
 assert client.post('/api/v1/opml',headers=headers,data=xml).json['data']['added']==1
 assert client.post('/api/v1/opml',headers=headers,data=xml).json['data']['skipped']==1
 assert client.post('/api/v1/opml',headers=headers,data=xml.replace(b'https://example.com/new',b'http://127.0.0.1/')).status_code==400
 assert client.post('/api/v1/opml',headers=headers,data=b'<!DOCTYPE opml [<!ENTITY x SYSTEM "file:///etc/passwd">]><opml><body/></opml>').status_code==400
 assert b'https://example.com/new' in client.get('/api/v1/opml',headers=read).data
 assert client.post('/operations/backups').status_code==400
 assert client.get('/operations').status_code==200

def test_v12_schema_reports_retention_and_bundle_integrity(app,tmp_path):
 prior=tmp_path/'prior';prior.mkdir();db=connect(prior/'feeds.sqlite3');db.executescript(Path('tests/fixtures/v12_schema.sql').read_text());db.close();backup_bundle(prior/'feeds.sqlite3',tmp_path/'v12bundle');restore_bundle(tmp_path/'v12bundle',tmp_path/'restored'/'feeds.sqlite3');db=connect(tmp_path/'restored'/'feeds.sqlite3');assert db.execute('PRAGMA user_version').fetchone()[0]==13 and db.execute('SELECT backup_enabled FROM operations_config').fetchone()[0]==0;db.close()
 wid,eid=case(app)
 with app.app_context():
  rid=p.create(wid,{'format':'markdown'});with_db=get_db()
  with with_db:with_db.execute("UPDATE evidence SET captured_at='2000-01-01' WHERE id=?",(eid,));with_db.execute('DELETE FROM workspace_evidence')
  e.prune();assert e.find(eid)
  bundle=tmp_path/'reportsbundle';backup_bundle(app.config['DATABASE'],bundle)
 restore_bundle(bundle,tmp_path/'restored2'/'feeds.sqlite3');db=connect(tmp_path/'restored2'/'feeds.sqlite3');assert db.execute('SELECT payload_hash FROM reports WHERE id=?',(rid,)).fetchone()[0] and not db.execute('PRAGMA foreign_key_check').fetchall();db.close()


def test_export_metadata_secrets_malformed_payloads_and_expired_notification(app,client,monkeypatch):
 wid,eid=case(app)
 with app.app_context():
  with get_db() as db:db.execute('UPDATE evidence SET source_url=? WHERE id=?',('https://example.com/?api'+'_key='+('z'*32),eid))
  for format in ('csv','manifest','markdown','json','stix'):
   with pytest.raises(ValueError):p.create(wid,{'format':format})
 wid,eid,rid,pid,prid,jid=setup_delivery(app,monkeypatch)
 with app.app_context():
  new=d.preview(rid,{'profile_id':pid})
  with get_db() as db:db.execute("UPDATE delivery_previews SET expires_at='2000-01-01' WHERE id=?",(new,))
  with pytest.raises(r.ResearchConflict):d.enqueue(new,{'approved':True,'payload_hash':d.find('delivery_previews',new)['payload_hash']})
  with pytest.raises(ValueError):d.profile({'expected_revision':1},pid)
 headers=authorization(app,'write')[2]
 assert client.post(f'/api/v1/workspaces/{wid}/reports',headers=headers,json={'format':[]}).status_code==400
 assert client.patch(f'/api/v1/delivery-profiles/{pid}',headers=headers,json={'expected_revision':1}).status_code==400
