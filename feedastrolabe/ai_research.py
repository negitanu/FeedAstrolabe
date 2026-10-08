"""Transactional metadata cursors, immutable sourced cards and condition comparisons."""
import json
from decimal import Decimal,InvalidOperation
from .db import get_db
from . import research as r,evidence as e,entities as n,triage as t,connectors as c,ai_research_adapters as a
from .security_intelligence import quote
from .security_adapters import link


def find(table,identifier,db=None):
 if table not in ('ai_watches','ai_cards','ai_versions','ai_benchmarks'):raise ValueError('research-table')
 t.positive_id(identifier);row=(db or get_db()).execute('SELECT * FROM '+table+' WHERE id=?',(identifier,)).fetchone()
 if row is None:raise r.ResearchMissing('研究記録が見つかりません。')
 return row


def input_for(watch):return watch['target']+'|'+watch['term']+'|'+str(watch['page'])


def save_watch(workspace_id,body,identifier=None):
 values=r.fields(body,{'enabled','outbound_public','interval_seconds'}|({'expected_revision'} if identifier else {'provider','target','term'}))
 if identifier:t.positive_id(values.get('expected_revision'))
 with r.transaction() as db:
  r.editable(workspace_id,db);old=find('ai_watches',identifier,db) if identifier else None
  if old and (old['workspace_id']!=workspace_id or old['revision']!=values['expected_revision']):raise r.ResearchConflict('ウォッチが更新されています。')
  def val(key,default=None):return values.get(key,old[key] if old else default)
  provider=val('provider');target=r.text(val('target'),'target',200,True);term=r.text(val('term',''),'term',80);a.contract(provider,target+'|'+term+'|0')
  enabled=val('enabled',True);consent=val('outbound_public',False);interval=val('interval_seconds',86400)
  if old:
   if 'enabled' not in values:enabled=bool(enabled)
   if 'outbound_public' not in values:consent=bool(consent)
  if type(enabled) is not bool or type(consent) is not bool or type(interval) is not int or not 3600<=interval<=604800:raise ValueError('研究ウォッチの設定が不正です。')
  if identifier:
   db.execute('UPDATE ai_watches SET enabled=?,outbound_public=?,interval_seconds=?,revision=revision+1,updated_at=? WHERE id=?',(enabled,consent,interval,r.now(),identifier));return identifier
  if db.execute('SELECT count(*) FROM ai_watches WHERE workspace_id=?',(workspace_id,)).fetchone()[0]>=100:raise ValueError('研究ウォッチは100件までです。')
  if db.execute('SELECT id FROM ai_watches WHERE workspace_id=? AND provider=? AND target=? AND term=?',(workspace_id,provider,target,term)).fetchone():raise r.ResearchConflict('同じ研究ウォッチがあります。')
  return db.execute('INSERT INTO ai_watches(workspace_id,provider,target,term,enabled,outbound_public,interval_seconds,next_check,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(workspace_id,provider,target,term,enabled,consent,interval,r.now(),r.now(),r.now())).lastrowid


def lookup(identifier):
 w=find('ai_watches',identifier);r.editable(w['workspace_id'],get_db())
 if not w['enabled'] or not w['outbound_public']:raise r.ResearchConflict('公開検索条件の送信許可と有効化が必要です。')
 return c.enqueue(w['provider'],{'input':input_for(w),'public_identifier':True})


def sync(identifier):
 w=find('ai_watches',identifier);value=input_for(w);db=get_db();cache=db.execute('SELECT * FROM connector_cache WHERE provider=? AND input=?',(w['provider'],value)).fetchone()
 if not cache or cache['expires_at']<=r.now():return {'created':0,'advanced':False}
 signature=e.digest((value+cache['response_hash']+cache['observed_at']).encode())
 if signature==w['last_cache_signature']:return {'created':0,'advanced':False}
 projection=a.project(w['provider'],value,json.loads(cache['payload']));created=0
 with e.storage_lock(),r.transaction() as tx:
  current=find('ai_watches',identifier,tx)
  if current['page']!=w['page'] or current['last_cache_signature']==signature:return {'created':0,'advanced':False}
  for record in projection['records']:
   text=c.dumps(record);hash=e.digest(text.encode())
   if tx.execute('SELECT 1 FROM ai_versions WHERE watch_id=? AND record_id=? AND projection_hash=?',(identifier,record['record_id'],hash)).fetchone():continue
   if tx.execute('SELECT count(*) FROM ai_versions WHERE watch_id=?',(identifier,)).fetchone()[0]>=10000:raise ValueError('研究の版履歴は10000件までです。')
   eid=e.save(tx,source_key='ai:'+w['provider']+':'+record['record_id'],title=record['title'],text=text,method='public-research-metadata',source_url=record['url'],publisher=a.PROVIDERS[w['provider']]['name'],source_guid=record['record_id'],published_at=record['published_at'],observed_at=cache['observed_at'])
   tx.execute('INSERT INTO ai_versions(watch_id,record_id,version,projection_hash,response_hash,payload,source_url,source_version,observed_at,evidence_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,record['record_id'],record['version'],hash,cache['response_hash'],text,cache['source_url'],cache['source_version'],cache['observed_at'],eid))
   tx.execute('INSERT OR IGNORE INTO workspace_evidence VALUES(?,?)',(w['workspace_id'],eid));created+=1
  more=projection['more'] and w['page']<19
  tx.execute('UPDATE ai_watches SET page=?,last_cache_signature=?,truncated=?,next_check=?,last_success_at=? WHERE id=?',(w['page']+1 if more else 0,signature,projection['truncated'],r.now() if more else c.later(w['interval_seconds']),cache['observed_at'],identifier))
 return {'created':created,'advanced':True}


def schedule():
 rows=get_db().execute("SELECT s.* FROM ai_watches s JOIN workspaces w ON w.id=s.workspace_id WHERE s.enabled=1 AND w.archived=0 ORDER BY coalesce(s.last_processed_at,''),s.id LIMIT 20").fetchall()
 for row in rows:
  # A paused consent never advances the collection cursor or submits a follow-on query.
  if row['outbound_public'] and row['next_check']<=r.now() and c.setting(row['provider'])['enabled']:
   try:lookup(row['id']);sync(row['id'])
   except (ValueError,r.ResearchConflict):pass
  with r.transaction() as db:db.execute('UPDATE ai_watches SET last_processed_at=? WHERE id=?',(r.now(),row['id']))
 return {'watches':len(rows)}


def watch_card(identifier):
 w=find('ai_watches',identifier);job=get_db().execute('SELECT * FROM connector_jobs WHERE provider=? AND input=? ORDER BY id DESC LIMIT 1',(w['provider'],input_for(w))).fetchone()
 latest=get_db().execute('SELECT observed_at FROM ai_versions WHERE watch_id=? ORDER BY id DESC LIMIT 1',(identifier,)).fetchone()
 stale=bool(w['last_success_at'] and (w['last_success_at']<=c.later(-w['interval_seconds']) or (job and job['error'])))
 return {'state':'unknown' if not w['last_success_at'] else 'stale' if stale else 'observed-scope','watch':dict(w),'last_job':dict(job) if job else None,'last_observed_at':latest[0] if latest else None,'coverage':'latest revisions observed; bounded dynamic pagination, not exhaustive history','provider':a.PROVIDERS[w['provider']]}


CLAIMS={'license','use_constraints','hardware','context','cost'}
CONDITIONS={'dataset','dataset_version','split','metric','unit','direction','harness','settings','hardware','context'}

def optional_strings(body,fields,maximum):
 result={}
 for field in fields:
  value=body.get(field)
  result[field]=None if value is None or value=='' else r.text(value,field,maximum,True,True)
 return result


def create_card(workspace_id,body):
 v=r.fields(body,{'entity_id','version','quotation_id','author'}|CLAIMS);version=r.text(v.get('version'),'version',300,True);claims=optional_strings(v,CLAIMS-{'cost'},4000);claims['cost']=None
 if v.get('cost') is not None:
  cost=r.fields(v['cost'],{'amount','currency','unit','date'})
  if set(cost)!={'amount','currency','unit','date'}:raise ValueError('費用はamount/currency/unit/dateが必要です。')
  amount=r.text(cost['amount'],'amount',100,True)
  try:
   number=Decimal(amount)
   if not number.is_finite() or number<0 or number>Decimal('1e100'):raise ValueError('cost-amount')
  except InvalidOperation:raise ValueError('cost-amount') from None
  import re
  from datetime import date
  if not isinstance(cost['currency'],str) or not re.fullmatch(r'[A-Z]{3}',cost['currency']):raise ValueError('cost-currency')
  date.fromisoformat(r.text(cost['date'],'date',10,True))
  claims['cost']={'amount':str(number),'currency':cost['currency'],'unit':r.text(cost['unit'],'unit',100,True),'date':cost['date']}
 with e.storage_lock(),r.transaction() as db:
  r.editable(workspace_id,db);entity=n.find(v.get('entity_id'),db)
  if entity['kind']!='model':raise ValueError('手動登録したモデル対象が必要です。')
  quote(workspace_id,v.get('quotation_id'),db)
  if db.execute('SELECT count(*) FROM ai_cards WHERE workspace_id=?',(workspace_id,)).fetchone()[0]>=1000:raise ValueError('モデル版カードは1000件までです。')
  return db.execute('INSERT INTO ai_cards(workspace_id,entity_id,version,quotation_id,claims,author,created_at) VALUES(?,?,?,?,?,?,?)',(workspace_id,entity['id'],version,v['quotation_id'],c.dumps(claims),r.text(v.get('author','local-user'),'author',100,True),r.now())).lastrowid


def add_link(identifier,body):
 v=r.fields(body,{'kind','url','version_id','quotation_id','reviewed','author'});url=link(v.get('url'))
 if not url or v.get('kind') not in ('paper','repository','model-card') or v.get('reviewed') is not True:raise ValueError('明示レビュー済みの公開URLが必要です。')
 with e.storage_lock(),r.transaction() as db:
  card=find('ai_cards',identifier,db);r.editable(card['workspace_id'],db);quote(card['workspace_id'],v.get('quotation_id'),db);vid=v.get('version_id')
  if vid is not None:
   version=find('ai_versions',vid,db);watch=find('ai_watches',version['watch_id'],db)
   if watch['workspace_id']!=card['workspace_id'] or json.loads(version['payload'])['url']!=url:raise ValueError('同じ案件の明示された版URLが必要です。')
  old=db.execute('SELECT id FROM ai_links WHERE card_id=? AND kind=? AND url=? AND quotation_id=?',(identifier,v['kind'],url,v['quotation_id'])).fetchone()
  if old:return old['id']
  if db.execute('SELECT count(*) FROM ai_links WHERE card_id=?',(identifier,)).fetchone()[0]>=100:raise ValueError('参照は100件までです。')
  return db.execute('INSERT INTO ai_links(card_id,kind,url,version_id,quotation_id,author,created_at) VALUES(?,?,?,?,?,?,?)',(identifier,v['kind'],url,vid,v['quotation_id'],r.text(v.get('author','local-user'),'author',100,True),r.now())).lastrowid


def benchmark(identifier,body):
 v=r.fields(body,{'status','result','notes','quotation_id','author'}|CONDITIONS);conditions=optional_strings(v,CONDITIONS,4000);status=v.get('status')
 if status not in ('claimed','reproduced','unverified'):raise ValueError('評価の出典状態が不正です。')
 if conditions['direction'] not in (None,'higher','lower'):raise ValueError('metric方向はhigher/lowerです。')
 try:
  value=v.get('result');assert isinstance(value,(str,int,float)) and not isinstance(value,bool) and len(str(value))<=100;number=Decimal(str(value));assert number.is_finite() and abs(number)<=Decimal('1e100')
 except (InvalidOperation,AssertionError):raise ValueError('有限の数値結果が必要です。') from None
 notes=r.text(v.get('notes',''),'notes',10000,multiline=True)
 if status=='reproduced' and not notes.strip():raise ValueError('再現には実行条件・結果のメモが必要です。')
 with e.storage_lock(),r.transaction() as db:
  card=find('ai_cards',identifier,db);r.editable(card['workspace_id'],db);qid=v.get('quotation_id')
  if status=='claimed' and qid is None:raise ValueError('情報源の主張には引用が必要です。')
  if qid is not None:quote(card['workspace_id'],qid,db)
  if db.execute('SELECT count(*) FROM ai_benchmarks WHERE card_id=?',(identifier,)).fetchone()[0]>=1000:raise ValueError('評価は1000件までです。')
  return db.execute('INSERT INTO ai_benchmarks(card_id,status,conditions,result,notes,quotation_id,author,created_at) VALUES(?,?,?,?,?,?,?,?)',(identifier,status,c.dumps(conditions),str(number),notes,qid,r.text(v.get('author','local-user'),'author',100,True),r.now())).lastrowid


def decoded(row):
 result=dict(row)
 for field in ('claims','conditions','payload'):
  if field in result:result[field]=json.loads(result[field])
 return result


def card(identifier):
 item=find('ai_cards',identifier)
 return {'card':decoded(item),'entity':dict(n.find(item['entity_id'])),'quotation':dict(get_db().execute('SELECT * FROM quotations WHERE id=?',(item['quotation_id'],)).fetchone()),'links':[dict(x) for x in get_db().execute('SELECT * FROM ai_links WHERE card_id=? ORDER BY id DESC',(identifier,))]}


def compare(left,right):
 lhs=find('ai_benchmarks',left);rhs=find('ai_benchmarks',right);lc=find('ai_cards',lhs['card_id']);rc=find('ai_cards',rhs['card_id'])
 if lc['workspace_id']!=rc['workspace_id']:raise ValueError('比較は同じ案件内だけです。')
 l=json.loads(lhs['conditions']);rr=json.loads(rhs['conditions']);unknown=sorted(k for k in CONDITIONS if l[k] is None or rr[k] is None);different=sorted(k for k in CONDITIONS if l[k] is not None and rr[k] is not None and l[k]!=rr[k]);provenance_diff=lhs['status']!=rhs['status']
 return {'left':decoded(lhs),'right':decoded(rhs),'state':'incompatible' if different else 'qualified' if unknown or provenance_diff else 'same-recorded-conditions','different':different,'unknown':unknown,'provenance_differs':provenance_diff,'ranking':None,'qualification':'Exact recorded conditions only; user reproduction is user-reported, not independently verified.'}
