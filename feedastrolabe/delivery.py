"""One explicit approval per immutable payload; no ambiguous automatic replay."""
from datetime import datetime,timedelta,timezone
import fcntl,uuid,hmac
from pathlib import Path
from flask import current_app
from .db import get_db
from . import research as r,evidence as e,reports as reports
from .delivery_transport import endpoint,recipient,deliver,DeliveryError

def find(table,identifier,db=None):
 if table not in ('delivery_profiles','delivery_previews','delivery_jobs') or type(identifier) is not int or not 1<=identifier<=2**63-1:raise ValueError('ID が不正です。')
 row=(db or get_db()).execute('SELECT * FROM '+table+' WHERE id=?',(identifier,)).fetchone()
 if not row:raise r.ResearchMissing('通知設定・ジョブが見つかりません。')
 return row

def profile(body,identifier=None):
 v=r.fields(body,{'enabled','expected_revision'} if identifier else {'name','kind','destination','enabled'})
 if identifier and 'enabled' not in v:raise ValueError('enabled は必須です。')
 if type(v.get('enabled',False)) is not bool:raise ValueError('enabled は真偽値です。')
 with r.transaction() as db:
  if identifier:
   old=find('delivery_profiles',identifier,db)
   if set(v)-{'enabled','expected_revision'} or type(v.get('expected_revision')) is not int or v['expected_revision']!=old['revision']:raise r.ResearchConflict('設定版が古い、または変更できない項目です。')
   db.execute('UPDATE delivery_profiles SET enabled=?,revision=revision+1,updated_at=? WHERE id=?',(int(v['enabled']),r.now(),identifier));return identifier
  if db.execute('SELECT count(*) FROM delivery_profiles').fetchone()[0]>=20:raise ValueError('通知設定は20件までです。')
  name=r.text(v.get('name'),'name',100,True);kind=v.get('kind');r.text(v.get('destination'),'destination',2048,True)
  if kind not in ('email','webhook'):raise ValueError('通知形式が不正です。')
  from .assistant import clean
  clean(name);clean(v['destination'])
  target=endpoint(v['destination']) if kind=='webhook' else recipient(v['destination'])
  return db.execute('INSERT INTO delivery_profiles(name,kind,destination,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?)',(name,kind,target,int(v.get('enabled',False)),r.now(),r.now())).lastrowid

def check(pr,db):
 p=find('delivery_profiles',pr['profile_id'],db)
 if not p['enabled'] or p['revision']!=pr['profile_revision']:raise r.ResearchConflict('通知先設定が変更・停止されています。')
 if e.digest(pr['payload'].encode())!=pr['payload_hash']:raise ValueError('通知payload hashが不正です。')
 report=reports.find(pr['report_id']);reports.outbound(report,db)
 expected=reports.encode({'report_id':report['id'],'format':report['format'],'report_hash':report['payload_hash'],'content':report['payload'],'citation_manifest':__import__('json').loads(report['manifest'])})
 if expected!=pr['payload']:raise ValueError('通知payloadとレポートが一致しません。')
 return p

def preview(rid,body):
 v=r.fields(body,{'profile_id'})
 with e.storage_lock(),r.transaction() as db:
  report=reports.find(rid);reports.outbound(report,db);p=find('delivery_profiles',v.get('profile_id'),db)
  if not p['enabled']:raise r.ResearchConflict('通知先を有効化してください。')
  if db.execute('SELECT count(*) FROM delivery_previews').fetchone()[0]>=10000:raise ValueError('プレビュー上限です。')
  wire=reports.encode({'report_id':rid,'format':report['format'],'report_hash':report['payload_hash'],'content':report['payload'],'citation_manifest':__import__('json').loads(report['manifest'])})
  from .assistant import clean
  clean(wire)
  expiry=(datetime.now(timezone.utc)+timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
  return db.execute('INSERT INTO delivery_previews(report_id,profile_id,profile_revision,payload,payload_hash,expires_at,created_at) VALUES(?,?,?,?,?,?,?)',(rid,p['id'],p['revision'],wire,e.digest(wire.encode()),expiry,r.now())).lastrowid

def enqueue(pid,body):
 v=r.fields(body,{'approved','payload_hash'})
 if v.get('approved') is not True:raise ValueError('明示的な承認が必要です。')
 with e.storage_lock(),r.transaction() as db:
  pr=find('delivery_previews',pid,db);check(pr,db)
  if not isinstance(v.get('payload_hash'),str) or not hmac.compare_digest(pr['payload_hash'],v['payload_hash']):raise r.ResearchConflict('プレビューhashが一致しません。')
  previous=db.execute('SELECT id FROM delivery_jobs WHERE preview_id=?',(pid,)).fetchone()
  if previous:return previous['id']
  if pr['expires_at']<=r.now():raise r.ResearchConflict('プレビューの承認期限が切れています。')
  if db.execute("SELECT count(*) FROM delivery_jobs WHERE status IN('queued','retry')").fetchone()[0]>=20:raise r.ResearchConflict('通知待ち上限です。')
  return db.execute("INSERT INTO delivery_jobs(preview_id,idempotency_key,status,next_attempt,created_at) VALUES(?,?,'queued',?,?)",(pid,str(uuid.uuid4()),r.now(),r.now())).lastrowid

def process():
 with (Path(current_app.instance_path)/'delivery.lock').open('a') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'processed':0}
  with r.transaction() as db:
   for old in db.execute("SELECT * FROM delivery_jobs WHERE status='running'").fetchall():
    db.execute("UPDATE delivery_jobs SET status='failed',error='delivery-interrupted-unknown',ended_at=? WHERE id=?",(r.now(),old['id']))
    db.execute('INSERT OR IGNORE INTO delivery_attempts(job_id,attempt,status,error,started_at,ended_at) VALUES(?,?,\'failed\',\'delivery-interrupted-unknown\',?,?)',(old['id'],old['attempts'],old['started_at'],r.now()))
   job=db.execute("SELECT * FROM delivery_jobs WHERE status IN('queued','retry') AND next_attempt<=? ORDER BY id LIMIT 1",(r.now(),)).fetchone()
   if not job:return {'processed':0}
   start=r.now();attempt=job['attempts']+1;db.execute("UPDATE delivery_jobs SET status='running',started_at=?,attempts=? WHERE id=?",(start,attempt,job['id']))
  with e.storage_lock(),r.transaction() as db:
   status='success';error=None;next_time=r.now()
   try:
    pr=find('delivery_previews',job['preview_id'],db);p=check(pr,db);deliver(p,pr['payload'],job['idempotency_key'])
   except DeliveryError as exc:
    error=exc.code;status='retry' if exc.retry and attempt<3 else 'failed';next_time=(datetime.now(timezone.utc)+timedelta(seconds=min(3600,60*2**attempt))).strftime('%Y-%m-%d %H:%M:%S')
   except Exception:status='failed';error='delivery-policy-invalid'
   end=r.now();db.execute('UPDATE delivery_jobs SET status=?,error=?,next_attempt=?,ended_at=? WHERE id=?',(status,error,next_time,end,job['id']))
   db.execute('INSERT INTO delivery_attempts(job_id,attempt,status,error,started_at,ended_at) VALUES(?,?,?,?,?,?)',(job['id'],attempt,status,error,start,end))
  return {'processed':1}
