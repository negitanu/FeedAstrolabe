"""Real HTTP API acceptance in isolated data, explicitly fixture-only outbound transport."""
import argparse,json,sys,uuid,urllib.request,urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from werkzeug.serving import make_server
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from feedastrolabe import create_app,research as r,evidence as e,reports as p,delivery as d,operations as o
from feedastrolabe.db import get_db,connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import validate_bundle,restore_bundle

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--data-dir');parser.add_argument('--serve-port',type=int);parser.add_argument('--check-state',action='store_true');args=parser.parse_args()
 with TemporaryDirectory(prefix='feedastrolabe-operations-') as temporary:
  directory=args.data_dir or temporary;app=create_app({'DATA_DIR':directory,'TESTING':True});marker=Path(directory)/'verification.json'
  if args.check_state:
   state=json.loads(marker.read_text())
   with app.app_context():
    assert get_db().execute('PRAGMA user_version').fetchone()[0]==17
    report=p.find(state['report']);assert e.digest(report['payload'].encode())==report['payload_hash']
    job=d.find('delivery_jobs',state['job']);assert job['status']=='success' and job['attempts']==1
    assert get_db().execute('SELECT count(*) FROM delivery_attempts WHERE job_id=?',(job['id'],)).fetchone()[0]==1
    row=get_db().execute('SELECT * FROM backup_jobs WHERE id=?',(state['backup'],)).fetchone();assert row['status']=='success';validate_bundle(o.path_for(row['generation']))
    assert get_db().execute('SELECT processed FROM worker_runs ORDER BY id DESC LIMIT 1').fetchone()[0]==3
    assert not get_db().execute('PRAGMA foreign_key_check').fetchall()
   print('PASS schema17 report/citation payload hashes, delivery success/audit/idempotency, verified backup generation and safe worker metrics after recreation');return
  server=make_server('127.0.0.1',args.serve_port or 0,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  with app.app_context():_,write=issue_key('Operations HTTP fixture','write',1);_,read=issue_key('Operations read fixture','read',1)
  def request(method,path,body=None,key=write):
   headers={'Authorization':'Bearer '+key};raw=None
   if body is not None:raw=json.dumps(body).encode();headers['Content-Type']='application/json'
   req=urllib.request.Request(base+'/api/v1'+path,data=raw,headers=headers,method=method)
   try:
    with urllib.request.urlopen(req) as response:return response.status,json.loads(response.read())
   except urllib.error.HTTPError as exc:return exc.code,json.loads(exc.read())
  oldendpoint=d.endpoint;oldsend=d.deliver
  try:
   assert request('PATCH','/settings',{'poll_interval':900},read)[0]==403
   assert request('PATCH','/settings',{'poll_interval':600,'polling_enabled':False})[1]['data']['poll_interval']==600
   wid=request('POST','/workspaces',{'title':'運用検証用の公開案件','classification':'public'})[1]['data']['id']
   with app.app_context():
    with e.storage_lock(),r.transaction() as db:eid=e.save(db,source_key='operations-fixture',title='=CSV formula fixture',text='Public source: example.com AS15169. <script>ignored</script>',method='fixture')
    e.pin('workspace',wid,eid)
   assert request('POST',f'/workspaces/{wid}/reports',{'format':'json'},read)[0]==403
   report=request('POST',f'/workspaces/{wid}/reports',{'format':'json'})[1]['data'];rid=report['id'];assert report['payload_hash']==e.digest(report['payload'].encode())
   d.endpoint=lambda value:value
   profile=request('POST','/delivery-profiles',{'name':'検証用通知先（実送信なし）','kind':'webhook','destination':'https://example.com/fixture-hook','enabled':True})[1]['data']['id']
   preview=request('POST',f'/reports/{rid}/delivery-previews',{'profile_id':profile})[1]['data'];prid=preview['id']
   assert request('POST',f'/delivery-previews/{prid}/jobs',{'approved':False,'payload_hash':preview['payload_hash']})[0]==400
   assert request('POST',f'/delivery-previews/{prid}/jobs',{'approved':True,'payload_hash':'f'*64})[0]==409
   approval={'approved':True,'payload_hash':preview['payload_hash']};job=request('POST',f'/delivery-previews/{prid}/jobs',approval)[1]['data']['id']
   sent=[];d.deliver=lambda profile,wire,key:sent.append((wire,key))
   with app.app_context():d.process();assert sent[0][0]==preview['payload'];d.process();assert len(sent)==1
   assert request('POST',f'/delivery-previews/{prid}/jobs',approval)[1]['data']['id']==job
   assert request('GET',f'/delivery-jobs/{job}')[1]['data']['status']=='success'
   assert request('POST','/articles/bulk-state',{'ids':list(range(1,102)),'is_read':True})[0]==400
   assert request('POST','/operations/backups',key=read)[0]==403
   backup=request('POST','/operations/backups')[1]['data']['id']
   with app.app_context():
    run=o.start('worker');o.end(run,3);o.process();row=get_db().execute('SELECT * FROM backup_jobs WHERE id=?',(backup,)).fetchone();assert row['status']=='success';path=o.path_for(row['generation']);validate_bundle(path)
    try:restore_bundle(path,Path(app.config['DATABASE']));raise AssertionError('Online restore must fail')
    except ValueError:pass
    restore_bundle(path,Path(directory)/'restored'/'feeds.sqlite3');restored=connect(Path(directory)/'restored'/'feeds.sqlite3');assert restored.execute('SELECT payload_hash FROM reports WHERE id=?',(rid,)).fetchone()[0]==report['payload_hash'];restored.close()
   marker.write_text(json.dumps({'report':rid,'preview':prid,'job':job,'backup':backup}))
   print('PASS actual HTTP: scoped settings/bulk bounds/report hash/citations/exact notification approval/success no resend/backup verified/offline restore guard; outbound transport fixture ONLY',flush=True)
   if args.serve_port:
    print('UI fixture: '+base+'/operations/previews/'+str(prid),flush=True)
    try:thread.join()
    except KeyboardInterrupt:pass
  finally:server.shutdown();thread.join(timeout=5);d.endpoint=oldendpoint;d.deliver=oldsend
if __name__=='__main__':main()
