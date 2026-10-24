import json
from pathlib import Path
import pytest
from feedastrolabe import ai_research as a,ai_research_adapters as adapter,connectors as c,research as r,evidence as e,entities as n
from feedastrolabe.db import get_db,connect
from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
from test_reader import app,client
from test_phase_two import authorization


def fixtures(version='1'):
 return {'arxiv':{'records':[{'record_id':'1706.03762v'+version,'version':version,'url':'https://arxiv.org/abs/1706.03762v'+version,'title':'Attention fixture','abstract':'Synthetic public metadata <script>alert(1)</script>','published_at':'2017-06-12T00:00:00Z','updated_at':'2026-10-08T00:00:00Z','authors':['Synthetic Author'],'categories':['cs.CL'],'doi':None,'journal_ref':None,'paper_license':None,'metadata_license':'CC0 1.0','coverage':'returned metadata; only observed revisions'}],'total':1,'start':0},'github-releases':[{'id':1,'tag_name':'v1','html_url':'https://github.com/example/repo/releases/tag/v1','name':'Fixture release','body':'Public metadata only','published_at':'2026-10-08T00:00:00Z','created_at':'2026-10-08T00:00:00Z','draft':False,'prerelease':False}]}


def setup(app,provider='arxiv',target='id:1706.03762'):
 with app.app_context():
  wid=r.create_workspace({'title':'AI sources'});watch=a.save_watch(wid,{'provider':provider,'target':target,'outbound_public':True});return wid,watch


def cache(provider,value,data,date='2026-10-08 00:00:00'):
 version=adapter.validate(provider,value,data);raw=c.dumps(data)
 with get_db() as db:db.execute('INSERT INTO connector_cache VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(provider,input) DO UPDATE SET payload=excluded.payload,response_hash=excluded.response_hash,observed_at=excluded.observed_at,expires_at=excluded.expires_at',(provider,value,raw,e.digest(raw.encode()),adapter.endpoint(provider,value),version,date,c.later(3600)))


def model(wid):
 entity=n.create({'kind':'model','value':'Synthetic Model'});text='Model claim: license is not stated; evaluation reference.'
 with e.storage_lock(),r.transaction() as db:eid=e.save(db,source_key='ai-fixture-claim',title='Fixture claim',text=text,method='fixture')
 e.pin('workspace',wid,eid);qid=e.quotation(wid,{'evidence_id':eid,'start':0,'end':len(text),'quote':text})
 card=a.create_card(wid,{'entity_id':entity,'version':'v1','quotation_id':qid});return card,qid


def test_paper_versions_release_edits_and_idempotent_originals(app,client):
 wid,watch=setup(app)
 with app.app_context():
  cache('arxiv','id:1706.03762||0',fixtures()['arxiv']);assert a.sync(watch)['created']==1;assert not a.sync(watch)['advanced']
  cache('arxiv','id:1706.03762||0',fixtures('2')['arxiv'],date='2026-10-08 01:00:00');assert a.sync(watch)['created']==1
  assert [x[0] for x in get_db().execute('SELECT version FROM ai_versions ORDER BY id')]==['1','2']
  card,qid=model(wid);assert a.card(card)['card']['claims']['license'] is None
  version=get_db().execute('SELECT * FROM ai_versions ORDER BY id DESC').fetchone()
  a.add_link(card,{'kind':'paper','url':'https://arxiv.org/abs/1706.03762v2','version_id':version['id'],'quotation_id':qid,'reviewed':True})
  gh=a.save_watch(wid,{'provider':'github-releases','target':'example/repo','outbound_public':True});data=fixtures()['github-releases'];cache('github-releases','example/repo||0',data);a.sync(gh)
  data[0]['body']='Edited description';cache('github-releases','example/repo||0',data,date='2026-10-08 02:00:00');assert a.sync(gh)['created']==1
  assert get_db().execute('SELECT count(*) FROM ai_versions').fetchone()[0]==4
  from feedastrolabe import triage
  triage.save(wid,{'name':'AI fixture','query':{'any':[{'field':'text','op':'contains','value':'Attention fixture'}]}});triage.process();assert get_db().execute('SELECT count(*) FROM watch_events WHERE included=1').fetchone()[0]>0
 assert client.get(f'/ai-research/watches/{watch}').status_code==200
 assert client.get(f'/ai-research/cards/{card}').status_code==200
 assert client.get(f'/ai-research/watches/{watch}?q=notfound').status_code==200
 assert client.get('/ai-research?q=Synthetic').status_code==200
 assert b'<script>' not in client.get(f'/ai-research/watches/{watch}').data


def test_retry_cursor_only_commits_valid_bounded_page(app,monkeypatch):
 wid,watch=setup(app,target='cat:cs.CL')
 with app.app_context():
  c.configure('arxiv',{'expected_revision':1,'enabled':True});job=a.lookup(watch)
  from feedastrolabe.connector_http import ConnectorError
  monkeypatch.setattr(c,'retrieve',lambda _:(_ for _ in ()).throw(ConnectorError('http-503')));c.process(1)
  assert a.find('ai_watches',watch)['page']==0 and a.sync(watch)['created']==0
  data=fixtures()['arxiv'];data['total']=1001;cache('arxiv','cat:cs.CL||0',data);assert a.sync(watch)['advanced'];assert a.find('ai_watches',watch)['page']==1
  # Invalid or missing next-page data cannot move the committed cursor.
  assert not a.sync(watch)['advanced'];wrong=dict(data,start=0)
  with pytest.raises(ValueError):cache('arxiv','cat:cs.CL||1',wrong)
  assert a.find('ai_watches',watch)['page']==1
  with get_db() as db:db.execute('UPDATE ai_watches SET page=19 WHERE id=?',(watch,))
  data['start']=950;cache('arxiv','cat:cs.CL||19',data);a.sync(watch)
  assert a.find('ai_watches',watch)['truncated'] and a.find('ai_watches',watch)['page']==0


def test_xml_entities_foreign_scope_and_public_queries_rejected():
 raw=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1706.03762v1</id><title>Fixture</title><summary>Text</summary><published>2017-06-12T00:00:00Z</published><updated>2017-06-12T00:00:00Z</updated><author><name>Fixture</name></author><category term="cs.CL"/></entry></feed>'
 assert adapter.atom(raw)['records'][0]['record_id']=='1706.03762v1'
 for bad in [b'<!DOCTYPE feed [<!ENTITY x SYSTEM "file:///etc/passwd">]>'+raw,raw.replace(b'arxiv.org/abs',b'127.0.0.1/abs'),raw.replace(b'v1</id>',b'</id>')]:
  with pytest.raises(ValueError):adapter.atom(bad)
 for provider,value in [('arxiv','cat:cs.CL|x OR all:private|0'),('arxiv','cat:other||0'),('arxiv','id:1706.03762||1'),('arxiv','cat:cs.CL||20'),('github-releases','example/repo|secret|0'),('github-releases','user@github.com/repo||0')]:
  with pytest.raises(ValueError):adapter.contract(provider,value)
 data=fixtures()['github-releases'];data[0]['html_url']='https://github.com/other/repo/releases/tag/v1'
 with pytest.raises(ValueError):adapter.project('github-releases','example/repo||0',data)
 wrong=fixtures()['arxiv'];wrong['records'][0]['record_id']='9999.99999v1'
 with pytest.raises(ValueError):adapter.project('arxiv','id:1706.03762||0',wrong)


def test_sourced_cards_reviewed_links_and_cost_unknowns(app):
 wid,watch=setup(app)
 with app.app_context():
  card,qid=model(wid);assert a.card(card)['card']['claims']['cost'] is None
  base={'entity_id':a.find('ai_cards',card)['entity_id'],'version':'v2','quotation_id':qid}
  with pytest.raises(ValueError):a.create_card(wid,dict(base,cost={'amount':'1','currency':'USD'}))
  second=a.create_card(wid,dict(base,cost={'amount':'1.25','currency':'USD','unit':'million tokens','date':'2026-10-08'}));assert a.card(second)['card']['claims']['cost']['date']=='2026-10-08'
  other=r.create_workspace({'title':'Other'})
  with pytest.raises(ValueError):a.create_card(other,base)
  for body in [{'kind':'model-card','url':'http://127.0.0.1/','quotation_id':qid,'reviewed':True},{'kind':'paper','url':'https://example.com','quotation_id':qid,'reviewed':False}]:
   with pytest.raises(ValueError):a.add_link(card,body)


def test_benchmarks_incompatible_missing_conditions_and_reproduction(app,client):
 wid,watch=setup(app)
 with app.app_context():
  card,qid=model(wid);base={'status':'claimed','result':'0.9','quotation_id':qid,'dataset':'DS','dataset_version':'v1','split':'test','metric':'accuracy','direction':'higher','unit':'fraction','harness':'fixture-v1','settings':'seed=1','hardware':'CPU','context':'512'}
  lhs=a.benchmark(card,base);rhs=a.benchmark(card,dict(base,dataset_version='v2'));assert a.compare(lhs,rhs)['state']=='incompatible' and a.compare(lhs,rhs)['different']==['dataset_version']
  missing=a.benchmark(card,{'status':'unverified','result':1});assert a.compare(lhs,missing)['state']=='qualified' and a.compare(lhs,missing)['ranking'] is None
  with pytest.raises(ValueError):a.benchmark(card,{'status':'reproduced','result':1})
  reproduction=a.benchmark(card,dict(base,status='reproduced',notes='User reports local fixture run'));assert a.compare(lhs,reproduction)['state']=='qualified'
  for result in ('NaN','Infinity',True,'1e101',None):
   with pytest.raises(ValueError):a.benchmark(card,dict(base,result=result))
 assert client.get(f'/ai-research/compare?left={lhs}&right={rhs}').status_code==200


def test_api_consent_revision_archival_and_scopes(app,client,monkeypatch):
 wid,watch=setup(app);write=authorization(app,'write')[2];read=authorization(app,'read')[2]
 with app.app_context():a.save_watch(wid,{'expected_revision':1,'outbound_public':False},watch);c.configure('arxiv',{'expected_revision':1,'enabled':True});monkeypatch.setattr(c,'retrieve',lambda _:pytest.fail('no request'));a.schedule();assert get_db().execute('SELECT count(*) FROM connector_jobs').fetchone()[0]==0
 assert client.post(f'/api/v1/ai-watches/{watch}/lookup',headers=read).status_code==403
 assert client.post(f'/api/v1/ai-watches/{watch}/lookup',headers=write).status_code==409
 assert client.patch(f'/api/v1/ai-watches/{watch}',headers=write,json={'expected_revision':1,'enabled':False}).status_code==409
 assert client.patch(f'/api/v1/ai-watches/{watch}',headers=write,json={'expected_revision':2,'target':'cat:cs.AI'}).status_code==400
 for path in [f'/api/v1/ai-watches/{watch}/versions',f'/api/v1/workspaces/{wid}/ai-cards',f'/api/v1/workspaces/{wid}/ai-watches']:
  assert client.get(path,headers=read).status_code==200
 assert client.get('/ai-research?workspace=').status_code==200 and client.post('/ai-research/watches',data={}).status_code==400
 with app.app_context():r.update_workspace(wid,{'archived':True})
 assert client.post(f'/api/v1/ai-watches/{watch}/lookup',headers=write).status_code==409


def test_actual_v10_migration_bundle_keeps_cards_sources(app,tmp_path):
 prior=tmp_path/'prior';prior.mkdir();db=connect(prior/'feeds.sqlite3');db.executescript(Path('tests/fixtures/v10_schema.sql').read_text());db.close();bundle=tmp_path/'v10bundle';backup_bundle(prior/'feeds.sqlite3',bundle);restore_bundle(bundle,tmp_path/'restore'/'feeds.sqlite3')
 db=connect(tmp_path/'restore'/'feeds.sqlite3');assert db.execute('PRAGMA user_version').fetchone()[0]==19;assert db.execute('SELECT count(*) FROM connector_settings').fetchone()[0]==11;assert db.execute('SELECT sum(enabled) FROM connector_settings').fetchone()[0]==0;db.close()
 wid,watch=setup(app)
 with app.app_context():cache('arxiv','id:1706.03762||0',fixtures()['arxiv']);a.sync(watch);card,qid=model(wid);a.benchmark(card,{'status':'claimed','result':'0.1','quotation_id':qid});e.prune()
 bundle=tmp_path/'v11bundle';backup_bundle(app.config['DATABASE'],bundle);restore_bundle(bundle,tmp_path/'restore2'/'feeds.sqlite3');db=connect(tmp_path/'restore2'/'feeds.sqlite3');assert db.execute('SELECT count(*) FROM ai_versions').fetchone()[0]==1;assert db.execute('SELECT count(*) FROM ai_benchmarks').fetchone()[0]==1;assert not db.execute('PRAGMA foreign_key_check').fetchall();db.close()
