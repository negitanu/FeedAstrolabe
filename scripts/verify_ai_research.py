"""HTTP fixture or explicitly opted-in live public network acceptance in isolated data."""
import argparse,json,sys,urllib.request,urllib.error
from pathlib import Path
from contextlib import nullcontext
from tempfile import TemporaryDirectory
from threading import Thread
if __file__!='<stdin>':sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from werkzeug.serving import make_server
from feedastrolabe import create_app,connectors as c,ai_research as s,evidence as e,research as r
from feedastrolabe.db import get_db,connect
from feedastrolabe.keys import issue_key
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle


from feedastrolabe import entities
FIXTURES={'arxiv': {'records': [{'record_id': '1706.03762v1', 'version': '1', 'url': 'https://arxiv.org/abs/1706.03762v1', 'title': 'Attention fixture', 'abstract': 'Synthetic public metadata <script>alert(1)</script>', 'published_at': '2017-06-12T00:00:00Z', 'updated_at': '2026-10-08T00:00:00Z', 'authors': ['Synthetic Author'], 'categories': ['cs.CL'], 'doi': None, 'journal_ref': None, 'paper_license': None, 'metadata_license': 'CC0 1.0', 'coverage': 'returned metadata; only observed revisions'}], 'total': 1, 'start': 0}, 'github-releases': [{'id': 1, 'tag_name': 'v1', 'html_url': 'https://github.com/example/repo/releases/tag/v1', 'name': 'Fixture release', 'body': 'Public metadata only', 'published_at': '2026-10-08T00:00:00Z', 'created_at': '2026-10-08T00:00:00Z', 'draft': False, 'prerelease': False}]}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--serve-port',type=int,default=0);parser.add_argument('--data-dir',type=Path);parser.add_argument('--check-state',action='store_true');parser.add_argument('--live-public',action='store_true');args=parser.parse_args()
 if args.data_dir and not args.data_dir.name.endswith('-verify'):parser.error('Use separate verification data')
 if args.check_state and not args.data_dir:parser.error('Use verification data')
 with nullcontext(str(args.data_dir)) if args.data_dir else TemporaryDirectory(prefix='feedastrolabe-ai-') as directory:
  app=create_app({'DATA_DIR':directory});marker=Path(directory)/'ai-state.json'
  if args.check_state:
   state=json.loads(marker.read_text())
   with app.app_context():
    db=get_db();assert db.execute('PRAGMA user_version').fetchone()[0]==12
    assert db.execute('SELECT count(*) FROM ai_versions').fetchone()[0]==3
    assert s.card(state['card'])['card']['claims']['license'] is None
    assert s.compare(state['left'],state['right'])['state']=='incompatible'
    assert db.execute('SELECT count(*) FROM ai_links').fetchone()[0]==1
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
   print('PASS schema12 immutable paper/release versions, quoted model/link/evaluation conditions after recreation');return
  with app.app_context():_,token=issue_key('ephemeral AI metadata acceptance','write',1);_,read=issue_key('AI read acceptance','read',1)
  server=make_server('127.0.0.1',args.serve_port,app);thread=Thread(target=server.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(server.server_port)
  def request(method,path,body=None,key=None):
   req=urllib.request.Request(base+'/api/v1'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+(key or token),'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=15) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as response:return response.code,json.load(response)
  old=c.retrieve
  try:
   wid=request('POST','/workspaces',{'title':'AI研究：論文と版の出典確認'})[1]['data']['id'];watches={}
   for provider,target in [('arxiv','id:1706.03762'),('github-releases','pallets/flask' if args.live_public else 'example/repo')]:
    assert request('PATCH',f'/connectors/{provider}',{'expected_revision':1,'enabled':True})[0]==200
    body={'provider':provider,'target':target,'outbound_public':False}
    assert request('POST',f'/workspaces/{wid}/ai-watches',body,key=read)[0]==403
    watch=request('POST',f'/workspaces/{wid}/ai-watches',body)[1]['data']['watch']['id'];watches[provider]=watch
    assert request('POST',f'/ai-watches/{watch}/lookup')[0]==409
    assert request('PATCH',f'/ai-watches/{watch}',{'expected_revision':1,'outbound_public':True})[0]==200
    assert request('POST',f'/ai-watches/{watch}/lookup')[0]==202
    if not args.live_public:
     data=FIXTURES[provider];c.retrieve=lambda url:(data,json.dumps(data).encode())
    with app.app_context():assert c.process(1)['processed']==1;s.sync(watch)
   if args.live_public:
    with app.app_context():
     for provider,watch in watches.items():
      db=get_db();job=db.execute('SELECT status,error FROM connector_jobs WHERE provider=? ORDER BY id DESC LIMIT 1',(provider,)).fetchone();count=db.execute('SELECT count(*) FROM ai_versions WHERE watch_id=?',(watch,)).fetchone()[0]
      print(provider,dict(job),'observed versions',count)
    print('Completed 2 opt-in public metadata GET attempts, no user research/credentials/content sent')
   else:
    with app.app_context():
     data=FIXTURES['arxiv'];row=data['records'][0];row.update(record_id='1706.03762v2',version='2',url='https://arxiv.org/abs/1706.03762v2')
     with get_db() as db:db.execute("UPDATE connector_cache SET expires_at='2000-01-01 00:00:00' WHERE provider='arxiv'");db.execute("UPDATE connector_state SET last_request=NULL WHERE provider='arxiv'")
     c.retrieve=lambda url:(data,json.dumps(data).encode());s.lookup(watches['arxiv']);c.process(1);s.sync(watches['arxiv'])
     assert get_db().execute('SELECT count(*) FROM ai_versions').fetchone()[0]==3
     text='Synthetic model source. License is not stated. Dataset revision affects comparison.'
     with e.storage_lock(),r.transaction() as db:eid=e.save(db,source_key='ai-http-fixture',title='確認用モデル資料',text=text,method='fixture')
     e.pin('workspace',wid,eid);qid=e.quotation(wid,{'evidence_id':eid,'start':0,'end':len(text),'quote':text})
    entity=request('POST','/entities',{'kind':'model','value':'確認用モデル'})[1]['data']['id']
    card=request('POST',f'/workspaces/{wid}/ai-cards',{'entity_id':entity,'version':'fixture-v1','quotation_id':qid})[1]['data']['card']['id']
    assert request('POST',f'/ai-cards/{card}/links',{'kind':'paper','url':'https://arxiv.org/abs/1706.03762v2','quotation_id':qid,'reviewed':True})[0]==201
    conditions={'status':'claimed','result':'0.9','quotation_id':qid,'dataset':'Fixture DS','dataset_version':'v1','split':'test','metric':'accuracy','unit':'fraction','direction':'higher','harness':'fixture-v1','settings':'seed=1','hardware':'CPU','context':'512'}
    left=request('POST',f'/ai-cards/{card}/benchmarks',conditions)[1]['data']['id'];conditions['dataset_version']='v2';right=request('POST',f'/ai-cards/{card}/benchmarks',conditions)[1]['data']['id']
    assert request('GET',f'/ai-benchmarks/{left}/compare/{right}')[1]['data']['state']=='incompatible'
    with app.app_context():backup_bundle(app.config['DATABASE'],Path(directory)/'bundle');restore_bundle(Path(directory)/'bundle',Path(directory)/'restore'/'feeds.sqlite3')
    marker.write_text(json.dumps({'card':card,'left':left,'right':right}));print('PASS actual HTTP: public consent/read scopes/paper revision/quoted model/license unknown/reviewed link/incompatible conditions/bundle')
   for path in ['/ai-research',f'/ai-research/watches/{watches["arxiv"]}']+([] if args.live_public else [f'/ai-research/cards/{card}',f'/ai-research/compare?left={left}&right={right}']):
    with urllib.request.urlopen(base+path) as response:assert response.status==200 and b'<script>' not in response.read()
   if args.serve_port:
    print('UI fixture: '+base+f'/ai-research/watches/{watches["arxiv"]}',flush=True)
    try:thread.join()
    except KeyboardInterrupt:pass
  finally:server.shutdown();thread.join(timeout=5);c.retrieve=old
if __name__=='__main__':main()
