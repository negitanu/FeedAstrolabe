"""Persisted explicit-consent jobs. Lock order evidence/connector then database."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import fcntl,json
from flask import current_app
from .db import get_db
from . import research as r,evidence as e,triage as t
from .connector_registry import PROVIDERS,endpoint,validate,contract
from .connector_http import retrieve,ConnectorError


def dumps(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def later(seconds):return (datetime.now(timezone.utc)+timedelta(seconds=seconds)).strftime('%Y-%m-%d %H:%M:%S')

def setting(provider,db=None):
    if provider not in PROVIDERS:raise ValueError('provider-policy')
    return (db or get_db()).execute('SELECT * FROM connector_settings WHERE provider=?',(provider,)).fetchone()

def configure(provider,body):
    values=r.fields(body,{'enabled','ttl_seconds','daily_budget','expected_revision'});t.positive_id(values.get('expected_revision'))
    with r.transaction() as db:
        old=setting(provider,db)
        if old['revision']!=values['expected_revision']:raise r.ResearchConflict('連携設定が更新されています。')
        enabled=values.get('enabled',bool(old['enabled']))
        if type(enabled) is not bool:raise ValueError('enabled must be boolean')
        ttl=values.get('ttl_seconds',old['ttl_seconds']);budget=values.get('daily_budget',old['daily_budget'])
        if type(ttl) is not int or not 3600<=ttl<=604800 or type(budget) is not int or not 1<=budget<=1000:raise ValueError('連携の保存時間・取得上限が不正です。')
        db.execute('UPDATE connector_settings SET enabled=?,ttl_seconds=?,daily_budget=?,revision=revision+1 WHERE provider=?',(enabled,ttl,budget,provider))
    return dict(setting(provider))


def enqueue(provider,body):
    values=r.fields(body,{'input','public_identifier'});value=values.get('input');contract(provider,value)
    if values.get('public_identifier') is not True:raise ValueError('公開識別子を送信する明示的確認が必要です。')
    with r.transaction() as db:
        if not setting(provider,db)['enabled']:raise r.ResearchConflict('連携は停止しています。')
        pending=db.execute("SELECT id FROM connector_jobs WHERE provider=? AND input=? AND status IN('queued','running')",(provider,value)).fetchone()
        if pending:return pending['id']
        cache=db.execute('SELECT expires_at FROM connector_cache WHERE provider=? AND input=?',(provider,value)).fetchone()
        if cache and cache['expires_at']>r.now():
            last=db.execute("SELECT id FROM connector_jobs WHERE provider=? AND input=? AND status='success' ORDER BY id DESC LIMIT 1",(provider,value)).fetchone()
            if last:return last['id']
        if db.execute("SELECT count(*) FROM connector_jobs WHERE status IN('queued','running')").fetchone()[0]>=100 or db.execute('SELECT count(*) FROM connector_jobs').fetchone()[0]>=10000:raise ValueError('連携ジョブの上限に達しました。')
        return db.execute("INSERT INTO connector_jobs(provider,input,status,next_attempt,created_at) VALUES(?,?,'queued',?,?)",(provider,value,r.now(),r.now())).lastrowid


def process(limit=3):
    if type(limit) is not int or not 1<=limit<=3:raise ValueError('batch-limit')
    root=Path(current_app.instance_path)
    with (root/'connector.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {'processed':0,'busy':True}
        db=get_db()
        # Only this process holds the lock, so any prior running job was interrupted.
        with r.transaction() as tx:tx.execute("UPDATE connector_jobs SET status='queued',next_attempt=? WHERE status='running'",(r.now(),))
        processed=0
        for _ in range(limit):
            with r.transaction() as tx:
                now=r.now();today=now[:10]
                job=tx.execute("""SELECT j.* FROM connector_jobs j JOIN connector_settings s ON s.provider=j.provider JOIN connector_state z ON z.provider=j.provider WHERE j.status='queued' AND j.next_attempt<=? AND s.enabled=1 AND (z.cooldown_until IS NULL OR z.cooldown_until<=?) AND (z.last_request IS NULL OR z.last_request<=?) AND (z.budget_day IS NULL OR z.budget_day!=? OR z.requests<s.daily_budget) ORDER BY j.id LIMIT 1""",(now,now,later(-60),today)).fetchone()
                if job is None:break
                cache=tx.execute('SELECT * FROM connector_cache WHERE provider=? AND input=?',(job['provider'],job['input'])).fetchone()
                if cache and cache['expires_at']>now:
                    tx.execute("UPDATE connector_jobs SET status='success',finished_at=? WHERE id=?",(now,job['id']));processed+=1;continue
                if job['attempts']>=3:
                    tx.execute("UPDATE connector_jobs SET status='failed',error='retry-exhausted',finished_at=? WHERE id=?",(now,job['id']));continue
                tx.execute("UPDATE connector_jobs SET status='running',attempts=attempts+1 WHERE id=?",(job['id'],))
                tx.execute('UPDATE connector_state SET last_request=?,budget_day=?,requests=CASE WHEN budget_day=? THEN requests+1 ELSE 1 END WHERE provider=?',(now,today,today,job['provider']))
            try:
                url=endpoint(job['provider'],job['input']);payload,raw=retrieve(url);version=validate(job['provider'],job['input'],payload);serialized=dumps(payload);digest=e.digest(raw)
                with r.transaction() as tx:
                    previous=tx.execute('SELECT length(CAST(payload AS BLOB)) FROM connector_cache WHERE provider=? AND input=?',(job['provider'],job['input'])).fetchone()
                    total=tx.execute('SELECT coalesce(sum(length(CAST(payload AS BLOB))),0) FROM connector_cache').fetchone()[0]
                    if total-(previous[0] if previous else 0)+len(serialized.encode())>16*1024*1024:raise ConnectorError('cache-quota')
                    settings=setting(job['provider'],tx)
                    tx.execute('INSERT INTO connector_cache VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(provider,input) DO UPDATE SET payload=excluded.payload,response_hash=excluded.response_hash,source_url=excluded.source_url,source_version=excluded.source_version,observed_at=excluded.observed_at,expires_at=excluded.expires_at',(job['provider'],job['input'],serialized,digest,url,version,r.now(),later(settings['ttl_seconds'])))
                    tx.execute("UPDATE connector_jobs SET status='success',error=NULL,finished_at=? WHERE id=?",(r.now(),job['id']))
            except Exception as exc:
                code=exc.code if isinstance(exc,ConnectorError) else 'provider-format'
                retry=exc.retry_at if isinstance(exc,ConnectorError) else None
                with r.transaction() as tx:
                    attempts=job['attempts']+1;next_at=max(retry or later(min(3600,60*2**attempts)),later(60))
                    tx.execute("UPDATE connector_jobs SET status=?,next_attempt=?,error=?,finished_at=? WHERE id=?",('failed' if attempts>=3 else 'queued',next_at,code,r.now() if attempts>=3 else None,job['id']))
                    tx.execute('UPDATE connector_state SET cooldown_until=? WHERE provider=?',(next_at,job['provider']))
            processed+=1
        return {'processed':processed,'busy':False}
