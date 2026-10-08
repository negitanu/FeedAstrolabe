"""HTTP fixture or explicitly opted-in live public network acceptance in isolated data."""
import argparse,json,sys,urllib.request,urllib.error
from pathlib import Path
from contextlib import nullcontext
from tempfile import TemporaryDirectory
from threading import Thread
if __file__!='<stdin>':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from werkzeug.serving import make_server
from feedastrolabe import create_app,connectors as c,network_intelligence as s,evidence as e,research as r
from feedastrolabe.db import get_db,connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle

from feedastrolabe import entities,network_adapters as a
FIXTURES={'dns': {'Status': 0, 'AD': True, 'TC': False, 'Question': [{'name': 'example.com.', 'type': 1}], 'Answer': [{'name': 'example.com.', 'type': 1, 'TTL': 300, 'data': '1.1.1.1'}]}, 'rdap-bootstrap': {'version': '1.0', 'publication': '2026-10-08T00:00:00Z', 'services': [[['com'], ['https://rdap.verisign.com/com/v1/']]]}, 'rdap': {'objectClassName': 'domain', 'ldhName': 'EXAMPLE.COM', 'handle': 'example-id', 'status': ['active'], 'events': [{'eventAction': 'registration', 'eventDate': '1995-08-14T00:00:00Z'}], 'nameservers': [{'ldhName': 'ns.example.com'}], 'entities': [{'vcardArray': ['vcard', [['fn', {}, 'text', 'personal contact']]]}], 'links': [{'href': 'http://127.0.0.1/private', 'rel': 'related'}]}, 'routing': {'status': 'ok', 'version': '1.1', 'time': '2026-10-08T00:00:00Z', 'data': {'asns': [15169], 'prefix': '8.8.8.0/24'}}, 'rpki': {'status': 'ok', 'version': '0.3', 'time': '2026-10-08T00:00:00Z', 'data': {'prefix': '8.8.8.0/24', 'resource': '15169', 'status': 'valid', 'description': 'Prefix-origin pair valid at source'}}, 'ct': [{'id': 1, 'issuer_name': 'Fixture CA', 'common_name': 'example.com', 'name_value': 'example.com\n*.example.com', 'not_before': '2026-10-01T00:00:00', 'not_after': '2027-01-01T00:00:00', 'entry_timestamp': '2026-10-01T00:00:00'}]}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--serve-port',type=int,default=0);parser.add_argument('--data-dir',type=Path);parser.add_argument('--check-state',action='store_true');parser.add_argument('--live-public',action='store_true');args=parser.parse_args()
 if args.data_dir and not args.data_dir.name.endswith('-verify'):parser.error('Use separate verification data')
 if args.check_state and not args.data_dir:parser.error('Use verification data')
 with nullcontext(str(args.data_dir)) if args.data_dir else TemporaryDirectory(prefix='feedastrolabe-network-') as directory:
  app=create_app({'DATA_DIR':directory});marker=Path(directory)/'network-state.json'
  if args.check_state:
   state=json.loads(marker.read_text())
   with app.app_context():
    db=get_db();assert db.execute('PRAGMA user_version').fetchone()[0]==13
    card=s.card(state['dns']);assert card['observation']['normalized']['rrset'][0]['data']=='8.8.8.8' and card['state']=='stale'
    assert db.execute('SELECT count(*) FROM network_events').fetchone()[0]==1
    assert db.execute('SELECT count(*) FROM network_observations').fetchone()[0]==6
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
   print('PASS schema13 network originals/change links/last-good stale/consent after recreation');return
  with app.app_context():_,token=issue_key('ephemeral network acceptance','write',1);_,read=issue_key('network read acceptance','read',1)
  server=make_server('127.0.0.1',args.serve_port,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  def request(method,path,body=None,key=None):
   req=urllib.request.Request(base+'/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=15) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as response:return response.code,json.load(response)
  old=c.retrieve
  try:
   wid=request('POST','/workspaces',{'title':'ネットワーク：公開識別子の受動観測'})[1]['data']['id']
   domain=request('POST','/entities',{'kind':'domain','value':'example.com'})[1]['data']['id']
   ip=request('POST','/entities',{'kind':'ip','value':'8.8.8.8'})[1]['data']['id'];watches={}
   for provider in ('dns','rdap-bootstrap','rdap','routing','rpki','ct'):
    assert request('PATCH',f'/connectors/{provider}',{'expected_revision':1,'enabled':True})[0]==200
    if provider=='rdap-bootstrap':
     assert request('POST',f'/connectors/{provider}/jobs',{'input':'dns','public_identifier':True})[0]==202
    else:
     body={'entity_id':ip if provider in ('routing','rpki') else domain,'provider':provider,'outbound_public':False}
     if provider=='rpki':body.update(prefix='8.8.8.0/24',origin='AS15169')
     assert request('POST',f'/workspaces/{wid}/network-watches',body,key=read)[0]==403
     watch=request('POST',f'/workspaces/{wid}/network-watches',body)[1]['data']['watch']['id'];watches[provider]=watch
     assert request('POST',f'/network-watches/{watch}/lookup')[0]==409
     assert request('PATCH',f'/network-watches/{watch}',{'expected_revision':1,'outbound_public':True})[0]==200
     assert request('POST',f'/network-watches/{watch}/lookup')[0]==202
    if not args.live_public:
     data=FIXTURES[provider];c.retrieve=lambda url:(data,json.dumps(data).encode())
    with app.app_context():
     assert c.process(1)['processed']==1
     if provider!='rdap-bootstrap':s.sync(watches[provider])
   if args.live_public:
    with app.app_context():
     for provider,watch in watches.items():
      card=s.card(watch);print(provider,card['state'],'version',card['observation']['source_version'] if card['observation'] else None,'error',card['last_job']['error'] if card['last_job'] else None)
    print('Completed 6 isolated actual public GET attempts; provider failures remain unknown, never converted to absence')
   else:
    watch=watches['dns']
    with app.app_context():
     data=FIXTURES['dns'];data['Answer'][0]['data']='8.8.8.8'
     with get_db() as db:db.execute("UPDATE connector_cache SET expires_at='2000-01-01 00:00:00' WHERE provider='dns'");db.execute("UPDATE connector_state SET last_request=NULL WHERE provider='dns'")
     c.retrieve=lambda url:(data,json.dumps(data).encode());s.lookup(watch);c.process(1);s.sync(watch)
     with get_db() as db:db.execute("UPDATE connector_cache SET expires_at='2000-01-01 00:00:00' WHERE provider='dns'");db.execute("UPDATE connector_state SET last_request=NULL WHERE provider='dns'")
     from feedastrolabe.connector_http import ConnectorError
     c.retrieve=lambda url:(_ for _ in ()).throw(ConnectorError('http-503'));s.lookup(watch);c.process(1)
     assert s.card(watch)['state']=='stale'
     bundle=Path(directory)/'bundle';backup_bundle(app.config['DATABASE'],bundle);restore_bundle(bundle,Path(directory)/'restore'/'feeds.sqlite3')
    assert len(request('GET',f'/network-watches/{watch}/events')[1]['data'])==1
    marker.write_text(json.dumps(watches));print('PASS actual HTTP: consent/scopes/dated network records/change links/stale last-good/bundle')
   for path in ['/network',f'/network?workspace={wid}',f'/network/watches/{watches["dns"]}']:
    with urllib.request.urlopen(base+path) as response:assert response.status==200
   if args.serve_port:
    print('UI fixture: '+base+f'/network/watches/{watches["dns"]}',flush=True)
    try:thread.join()
    except KeyboardInterrupt:pass
  finally:server.shutdown();thread.join(timeout=5);c.retrieve=old
if __name__=='__main__':main()
