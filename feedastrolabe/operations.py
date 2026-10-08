"""Safe worker metrics and disabled-by-default verified generation backups."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
import fcntl,uuid,shutil
from flask import current_app
from .db import get_db
from . import research as r,evidence as e
from .evidence_backup import backup_bundle,validate_bundle,file_hash

@contextmanager
def offline_lock(root):
 with (Path(root)/'runtime.lock').open('a') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Web・ワーカー稼働中は復元できません。全サービスを停止してください。') from None
  yield

def start(name):
 if name not in ('worker','observer'):raise ValueError('worker name invalid')
 with r.transaction() as db:
  timestamp=r.now();db.execute("UPDATE worker_runs SET status='interrupted',ended_at=?,error='worker-interrupted' WHERE name=? AND status='running'",(timestamp,name))
  db.execute('INSERT INTO worker_health(name,started_at,heartbeat_at,status) VALUES(?,?,?,\'running\') ON CONFLICT(name) DO UPDATE SET started_at=excluded.started_at,heartbeat_at=excluded.heartbeat_at,ended_at=NULL,status=\'running\',error=NULL',(name,timestamp,timestamp))
  return db.execute("INSERT INTO worker_runs(name,started_at,status) VALUES(?,?,'running')",(name,timestamp)).lastrowid

def end(run,processed=0,error=None):
 with r.transaction() as db:
  row=db.execute('SELECT * FROM worker_runs WHERE id=?',(run,)).fetchone();status='failed' if error else 'idle';timestamp=r.now()
  db.execute('UPDATE worker_runs SET status=?,ended_at=?,processed=?,error=? WHERE id=?',(status,timestamp,min(100000,max(0,processed)),error,run));db.execute('UPDATE worker_health SET heartbeat_at=?,ended_at=?,status=?,error=? WHERE name=?',(timestamp,timestamp,status,error,row['name']))
  db.execute('DELETE FROM worker_runs WHERE id NOT IN(SELECT id FROM worker_runs ORDER BY id DESC LIMIT 1000)')

def health():
 db=get_db();cutoff=(datetime.now(timezone.utc)-timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
 workers=[]
 for name in ('worker','observer'):
  row=db.execute('SELECT * FROM worker_health WHERE name=?',(name,)).fetchone();data=dict(row) if row else {'name':name,'status':'unknown','heartbeat_at':None}
  data['stale']=row is None or row['heartbeat_at']<cutoff;workers.append(data)
 counts={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('reports','delivery_jobs','backup_jobs','assistant_jobs','connector_jobs')}
 return {'workers':workers,'counts':counts,'ci':{'status':'workflow-permission-required','template':'.github/ci-template.yaml','active':False},'restore':'offline-only: stop Web/worker/observer, verify bundle, then restore-bundle CLI','schema':db.execute('PRAGMA user_version').fetchone()[0]}

def config(body):
 v=r.fields(body,{'backup_enabled','interval_seconds','generations','quota_bytes','expected_revision'})
 with r.transaction() as db:
  old=dict(db.execute('SELECT * FROM operations_config').fetchone())
  if type(v.get('expected_revision')) is not int or v['expected_revision']!=old['revision']:raise r.ResearchConflict('設定版が古いです。')
  enabled=v.get('backup_enabled',bool(old['backup_enabled']))
  if type(enabled) is not bool:raise ValueError('backup_enabled は真偽値です。')
  values={}
  for key,low,high in [('interval_seconds',3600,604800),('generations',1,30),('quota_bytes',1048576,107374182400)]:
   value=v.get(key,old[key])
   if type(value) is not int or not low<=value<=high:raise ValueError(key+' の上限・下限を確認してください。')
   values[key]=value
  db.execute('UPDATE operations_config SET backup_enabled=?,interval_seconds=?,generations=?,quota_bytes=?,revision=revision+1 WHERE id=1',(int(enabled),values['interval_seconds'],values['generations'],values['quota_bytes']))

def enqueue():
 with r.transaction() as db:
  old=db.execute("SELECT id FROM backup_jobs WHERE status IN('queued','running') ORDER BY id LIMIT 1").fetchone()
  if old:return old['id']
  if db.execute('SELECT count(*) FROM backup_jobs').fetchone()[0]>=10000:raise ValueError('バックアップ履歴上限です。')
  return db.execute("INSERT INTO backup_jobs(status,generation,created_at) VALUES('queued',?,?)",('backup-'+uuid.uuid4().hex,r.now())).lastrowid

def schedule():
 row=get_db().execute('SELECT * FROM operations_config').fetchone()
 if not row['backup_enabled']:return
 cutoff=(datetime.now(timezone.utc)-timedelta(seconds=row['interval_seconds'])).strftime('%Y-%m-%d %H:%M:%S')
 if row['last_attempt'] is None or row['last_attempt']<=cutoff:enqueue()

def root():
 path=Path(current_app.instance_path)/'backups'
 if path.is_symlink():raise ValueError('バックアップ保存先がリンクです。')
 path.mkdir(mode=0o700,exist_ok=True);path.chmod(0o700);return path

def path_for(generation):
 import re
 if not isinstance(generation,str) or not re.fullmatch(r'backup-[a-f0-9]{32}',generation):raise ValueError('世代 ID が不正です。')
 path=root()/generation
 if path.is_symlink():raise ValueError('世代がリンクです。')
 return path

def size(path):
 total=0
 for item in path.rglob('*'):
  if item.is_symlink():raise ValueError('バックアップにリンクがあります。')
  if item.is_file():total+=item.stat().st_size
 return total

def process():
 with (Path(current_app.instance_path)/'backup.lock').open('a') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'processed':0}
  with r.transaction() as db:
   db.execute("UPDATE backup_jobs SET status='failed',error='backup-interrupted',ended_at=? WHERE status='running'",(r.now(),))
   job=db.execute("SELECT * FROM backup_jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
   if not job:return {'processed':0}
   settings=dict(db.execute('SELECT * FROM operations_config').fetchone());db.execute("UPDATE backup_jobs SET status='running' WHERE id=?",(job['id'],));db.execute('UPDATE operations_config SET last_attempt=? WHERE id=1',(r.now(),))
  status='success';error=None;bytes_used=None;manifest_hash=None
  try:
   path=path_for(job['generation']);existing=[x for x in root().iterdir()]
   if any(x.is_symlink() or not x.is_dir() or not x.name.startswith('backup-') for x in existing):raise ValueError('不明なバックアップ保存物です。')
   # Reserve both a generation and total physical quota before copying.
   source=Path(current_app.config['DATABASE']);estimate=source.stat().st_size+get_db().execute('SELECT coalesce(sum(size),0) FROM evidence_blobs').fetchone()[0]+1048576
   if estimate>2*1024**3 or sum(size(x) for x in existing)+estimate>settings['quota_bytes']:raise ValueError('バックアップ容量上限です。')
   backup_bundle(source,path);validate_bundle(path);bytes_used=size(path);manifest_hash=file_hash(path/'manifest.json')
   if bytes_used>2*1024**3 or sum(size(x) for x in root().iterdir())>settings['quota_bytes']:raise ValueError('バックアップ容量上限です。')
   # Retire only app-owned, recorded, still-verified generations. Unknown/corrupt files stay for inspection.
   prior=get_db().execute("SELECT * FROM backup_jobs WHERE status='success' AND retired_at IS NULL ORDER BY id DESC").fetchall()
   for old in prior[max(0,settings['generations']-1):]:
    oldpath=path_for(old['generation']);validate_bundle(oldpath)
    if file_hash(oldpath/'manifest.json')!=old['manifest_hash']:raise ValueError('世代マニフェストhash不一致です。')
    shutil.rmtree(oldpath)
    with get_db() as db:db.execute('UPDATE backup_jobs SET retired_at=? WHERE id=?',(r.now(),old['id']))
  except Exception:status='failed';error='backup-integrity-or-quota'
  with r.transaction() as db:db.execute('UPDATE backup_jobs SET status=?,error=?,size_bytes=?,manifest_hash=?,ended_at=? WHERE id=?',(status,error,bytes_used,manifest_hash,r.now(),job['id']))
  return {'processed':1}
