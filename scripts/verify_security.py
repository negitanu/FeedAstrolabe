"""HTTP fixture or explicitly opted-in live public CVE acceptance in isolated data."""
import argparse,json,sys,urllib.request,urllib.error
from pathlib import Path
from contextlib import nullcontext
from tempfile import TemporaryDirectory
from threading import Thread
if __file__!='<stdin>':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from werkzeug.serving import make_server
from feedastrolabe import create_app,connectors as c,security_intelligence as s,evidence as e,research as r
from feedastrolabe.db import get_db,connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
FIXTURES={'kev': {'catalogVersion': '2026.10.08', 'dateReleased': '2026-10-08T00:00:00Z', 'count': 1, 'vulnerabilities': [{'cveID': 'CVE-2021-44228', 'vendorProject': 'Apache', 'product': 'Log4j', 'vulnerabilityName': 'Fixture', 'shortDescription': 'Fixture record', 'dateAdded': '2021-12-10', 'dueDate': '2021-12-24', 'requiredAction': 'Vendor says update', 'notes': 'https://example.com/advisory'}]}, 'epss': {'status': 'OK', 'status-code': 200, 'version': '1.0', 'total': 1, 'data': [{'cve': 'CVE-2021-44228', 'epss': '0.95', 'percentile': '0.99', 'date': '2026-10-08'}]}, 'cve': {'dataType': 'CVE_RECORD', 'dataVersion': '5.2', 'cveMetadata': {'cveId': 'CVE-2021-44228', 'state': 'PUBLISHED', 'dateUpdated': '2026-10-08T00:00:00Z'}, 'containers': {'cna': {'providerMetadata': {'shortName': 'Apache'}, 'descriptions': [{'lang': 'en', 'value': 'Fixture <script>alert(1)</script>'}], 'affected': [{'vendor': 'Apache', 'product': 'Log4j', 'versions': [{'version': '2.x', 'status': 'affected'}]}], 'metrics': [{'cvssV3_1': {'version': '3.1', 'baseScore': 10.0, 'vectorString': 'CVSS:3.1/AV:N'}}], 'references': [{'url': 'https://example.com/advisory'}, {'url': 'http://127.0.0.1/private'}], 'solutions': [{'value': 'Vendor says upgrade', 'lang': 'en'}]}, 'adp': [{'providerMetadata': {'shortName': 'ADP'}, 'metrics': [{'cvssV4_0': {'version': '4.0', 'baseScore': 9.5, 'vectorString': 'CVSS:4.0/AV:N'}}]}]}}}
CVE='CVE-2021-44228'

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--serve-port',type=int,default=0);parser.add_argument('--data-dir',type=Path);parser.add_argument('--check-state',action='store_true');parser.add_argument('--live-public',action='store_true');args=parser.parse_args()
 if args.data_dir and not args.data_dir.name.endswith('-verify'):parser.error('Use separate verification data')
 if args.check_state and not args.data_dir:parser.error('Use verification data')
 if args.serve_port and not 1024<=args.serve_port<=65535:parser.error('Use local test port')
 with nullcontext(str(args.data_dir)) if args.data_dir else TemporaryDirectory(prefix='feedastrolabe-security-') as directory:
  app=create_app({'DATA_DIR':directory});marker=Path(directory)/'security-state.json'
  if args.check_state:
   state=json.loads(marker.read_text())
   with app.app_context():
    card=s.card(state['watch_id']);db=get_db();assert db.execute('PRAGMA user_version').fetchone()[0]==9
    assert card['applicability']['status']=='confirmed' and card['watch']['revision']==2
    assert card['signals']['epss']['data']['score']==0.95 and card['signals']['epss']['state']=='stale'
    assert db.execute('SELECT count(*) FROM security_observations').fetchone()[0]==3
    assert db.execute('SELECT count(*) FROM security_references').fetchone()[0]==1
    assert db.execute('SELECT count(*) FROM connector_jobs WHERE error IS NOT NULL').fetchone()[0]==1
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
   print('PASS schema9: dated security originals/review/PoC metadata/last-good stale score retained after recreation');return
  with app.app_context():_,token=issue_key('ephemeral security acceptance','write',1);_,read=issue_key('read acceptance','read',1)
  server=make_server('127.0.0.1',args.serve_port,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  def request(method,path,body=None,key=None):
   req=urllib.request.Request(base+'/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=15) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as response:return response.code,json.load(response)
  old=c.retrieve
  try:
   wid=request('POST','/workspaces',{'title':'セキュリティ：公開脆弱性の出典確認'})[1]['data']['id']
   cid=request('POST','/entities',{'kind':'cve','value':CVE})[1]['data']['id']
   body={'entity_id':cid,'product':'Log4j','version':'2.0','outbound_public':True}
   assert request('POST',f'/workspaces/{wid}/security-watches',body,key=read)[0]==403
   watch=request('POST',f'/workspaces/{wid}/security-watches',body)[1]['data']['watch']['id']
   with app.app_context():
    text='Apache Log4j 2.0 applicability manually reviewed in fixture'
    with e.storage_lock(),r.transaction() as db:eid=e.save(db,source_key='security-http-fixture',title='確認用の固定資料',text=text,method='fixture')
    e.pin('workspace',wid,eid);qid=e.quotation(wid,{'evidence_id':eid,'start':0,'end':len(text),'quote':text})
   for provider in ('kev','epss','cve'):
    assert request('PATCH',f'/connectors/{provider}',{'expected_revision':1,'enabled':True})[0]==200
    value='catalog' if provider=='kev' else CVE
    assert request('POST',f'/connectors/{provider}/jobs',{'input':value})[0]==400
    assert request('POST',f'/connectors/{provider}/jobs',{'input':value,'public_identifier':True})[0]==202
    if not args.live_public:
     data=FIXTURES[provider];c.retrieve=lambda url:(data,json.dumps(data).encode())
    with app.app_context():assert c.process(1)['processed']==1;s.sync(cid)
   card=request('GET',f'/security-watches/{watch}')[1]['data']
   if args.live_public:
    for provider,signal in card['signals'].items():
     print(provider,signal['state'],'source version',signal['source_version'],'date',signal['observed_at'],'error',signal['error'])
    assert all(signal['state']=='current' for signal in card['signals'].values())
    assert card['signals']['kev']['data']['listed']
    assert card['signals']['epss']['data']['available']
    print('PASS: 3 opt-in actual public provider GETs for published CVE; identifier only, no user records transmitted')
   else:
    assert card['applicability']['status']=='possible' and card['signals']['epss']['data']['score']==0.95
    assert request('POST',f'/security-watches/{watch}/reviews',{'expected_revision':1,'status':'confirmed','quotation_id':qid,'reason':'固定資料を照合'})[0]==201
    assert request('POST',f'/security-watches/{watch}/reviews',{'expected_revision':1,'status':'unknown','reason':'stale'})[0]==409
    assert request('POST',f'/workspaces/{wid}/security-references',{'entity_id':cid,'url':'https://example.com/reviewed-poc','kind':'poc','quotation_id':qid,'reviewed':True})[0]==201
    with app.app_context():
     with get_db() as db:db.execute("UPDATE connector_cache SET expires_at='2000-01-01 00:00:00' WHERE provider='epss'");db.execute("UPDATE connector_state SET last_request=NULL WHERE provider='epss'")
     from feedastrolabe.connector_http import ConnectorError
     c.retrieve=lambda url:(_ for _ in ()).throw(ConnectorError('http-503'))
     c.enqueue('epss',{'input':CVE,'public_identifier':True});c.process(1)
     assert s.card(watch)['signals']['epss']['state']=='stale'
     bundle=Path(directory)/'bundle';backup_bundle(app.config['DATABASE'],bundle);restored=Path(directory)/'restored'/'feeds.sqlite3';restore_bundle(bundle,restored)
     db=connect(restored);assert db.execute('SELECT status FROM security_reviews').fetchone()[0]=='confirmed';db.close()
    marker.write_text(json.dumps({'workspace_id':wid,'entity_id':cid,'watch_id':watch}))
    print('PASS actual HTTP: consent/read scopes/dated signals/qualified product match/quoted review/409/stale last-good/bundle')
   for path in ['/security',f'/security?workspace={wid}',f'/security/watches/{watch}']:
    with urllib.request.urlopen(base+path) as response:assert response.status==200 and b'<script' not in response.read()
   if args.serve_port:
    print('UI fixture: '+base+f'/security/watches/{watch}',flush=True)
    try:thread.join()
    except KeyboardInterrupt:pass
  finally:server.shutdown();thread.join(timeout=5);c.retrieve=old
if __name__=='__main__':main()
