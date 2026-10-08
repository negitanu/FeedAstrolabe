"""Private content-addressed evidence. Lock order: evidence.lock, then SQLite."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import fcntl
import hashlib
import html
import os
from pathlib import Path
import re
import secrets

import bleach
from flask import current_app
from .db import get_db
from . import research as r

MAX_FILE=10*1024*1024
MAX_TEXT=160000
HASH=re.compile(r'^[a-f0-9]{64}$')


def digest(data):
    return hashlib.sha256(data).hexdigest()


@contextmanager
def storage_lock(data_dir=None):
    root=Path(data_dir or current_app.instance_path)
    with (root/'evidence.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        yield


def blob_path(hash_value,data_dir=None):
    if not isinstance(hash_value,str) or not HASH.fullmatch(hash_value):
        raise ValueError('根拠のハッシュが不正です。')
    root=Path(data_dir or current_app.instance_path)/'evidence-blobs'
    if root.is_symlink():
        raise ValueError('根拠保存先が不正です。')
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=root/hash_value
    if path.is_symlink():
        raise ValueError('根拠ファイルが不正です。')
    return path


def read_blob(hash_value,size=None,data_dir=None):
    path=blob_path(hash_value,data_dir)
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as handle:
            value=handle.read(MAX_FILE+1)
    except OSError:
        raise ValueError('根拠ファイルが欠損または不正です。') from None
    if len(value)>MAX_FILE or (size is not None and len(value)!=size) or digest(value)!=hash_value:
        raise ValueError('根拠ファイルの整合性検証に失敗しました。')
    return value


def find(identifier,db=None):
    if type(identifier) is not int or not 1<=identifier<=2**63-1:
        raise ValueError('根拠 ID は正の整数で指定してください。')
    row=(db or get_db()).execute('SELECT e.*,b.size FROM evidence e JOIN evidence_blobs b ON b.hash=e.blob_hash WHERE e.id=?',(identifier,)).fetchone()
    if row is None:
        raise r.ResearchMissing('根拠が見つかりません。')
    return row


def save(db,*,source_key,title,text,method,source_url='',publisher='',source_guid='',feed_id=None,article_id=None,published_at=None,observed_at=None,raw=None,mime='text/plain',filename=''):
    if not isinstance(text,str) or len(text)>MAX_TEXT:
        raise ValueError('根拠テキストの上限を超えています。')
    encoded=text.encode('utf-8');raw=encoded if raw is None else raw
    if len(raw)>MAX_FILE:
        raise ValueError('添付の上限10MiBを超えています。')
    blob_hash,text_hash=digest(raw),digest(encoded)
    previous=db.execute('SELECT * FROM evidence WHERE source_key=? ORDER BY version DESC LIMIT 1',(source_key,)).fetchone()
    if previous and previous['blob_hash']==blob_hash and previous['text_hash']==text_hash and previous['title']==title and previous['source_url']==source_url and previous['method']==method and previous['publisher']==publisher and previous['source_guid']==source_guid and previous['published_at']==published_at and previous['mime']==mime and previous['filename']==filename:
        return previous['id']
    path=blob_path(blob_hash)
    exists=db.execute('SELECT size FROM evidence_blobs WHERE hash=?',(blob_hash,)).fetchone()
    if exists:
        read_blob(blob_hash,exists['size'])
    else:
        quota=db.execute('SELECT quota_bytes FROM evidence_settings').fetchone()[0]
        # Include orphan files left by interrupted transactions in physical quota.
        used=0
        for child in path.parent.iterdir():
            if child.is_symlink() or not child.is_file() or not HASH.fullmatch(child.name):
                raise ValueError('根拠保存先に不正なファイルがあります。')
            used+=child.stat().st_size
        if not path.exists() and used+len(raw)>quota:
            raise ValueError('根拠ライブラリの容量上限に達しました。')
        if path.exists():
            read_blob(blob_hash,len(raw))
        else:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            try:
                with os.fdopen(fd,'wb') as handle:
                    handle.write(raw);handle.flush();os.fsync(handle.fileno())
            except BaseException:
                path.unlink(missing_ok=True);raise
        db.execute('INSERT INTO evidence_blobs(hash,size) VALUES(?,?)',(blob_hash,len(raw)))
    version=previous['version']+1 if previous else 1
    return db.execute('''INSERT INTO evidence(source_key,version,feed_id,article_id,source_url,publisher,source_guid,title,method,published_at,observed_at,captured_at,blob_hash,text_hash,text,mime,filename) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(source_key,version,feed_id,article_id,source_url,publisher,source_guid,title,method,published_at,observed_at,r.now(),blob_hash,text_hash,text,mime,filename)).lastrowid


def article_capture(identifier,method='article-backfill-now'):
    with storage_lock(),r.transaction() as db:
        article=r.find('article',identifier,db);feed=r.find('feed',article['feed_id'],db)
        return save(db,source_key=digest((feed['url']+'\0'+article['guid']).encode()),title=article['title'],text=html.unescape(bleach.clean(article['content'],tags=[],strip=True)),method=method,source_url=article['link'] or (feed['target'] if feed['source_type']=='page' else feed['url']),publisher=feed['title'],source_guid=article['guid'],feed_id=feed['id'],article_id=identifier,published_at=article['source_published_at'],observed_at=feed['checked_at'])


def capture_articles(identifiers,feed_id):
    try:
        for identifier in identifiers:
            article_capture(identifier,'feed-derived')
        with get_db() as db:
            db.execute('DELETE FROM evidence_capture_errors WHERE feed_id=?',(feed_id,))
    except (ValueError,OSError):
        record_capture_error(feed_id)


def record_capture_error(feed_id):
    with get_db() as db:
        db.execute("INSERT INTO evidence_capture_errors(feed_id,message,occurred_at) SELECT id,?,? FROM feeds WHERE id=? ON CONFLICT(feed_id) DO UPDATE SET message=excluded.message,occurred_at=excluded.occurred_at",('根拠保存に失敗しました。容量・本文サイズ・保存先を確認してください。',r.now(),feed_id))


def capture_page(feed,text,article_id=None):
    try:
        with storage_lock(),r.transaction() as db:
            actual=db.execute('SELECT id FROM feeds WHERE id=?',(feed['id'],)).fetchone()
            if article_id and not db.execute('SELECT id FROM articles WHERE id=?',(article_id,)).fetchone():
                article_id=None
            return save(db,source_key=digest((feed['url']+'\0page-selected').encode()),title=feed['title'],text=text,method='page-selected-text',source_url=feed['target'],publisher=feed['title'],source_guid=feed['selector'],feed_id=feed['id'] if actual else None,article_id=article_id,observed_at=r.now())
    except (ValueError,OSError):
        record_capture_error(feed['id'])


def pin(kind,identifier,evidence_id,remove=False):
    if kind not in ('workspace','note'):
        raise ValueError('関連種別が不正です。')
    with storage_lock(),r.transaction() as db:
        parent=r.find(kind,identifier,db);item=find(evidence_id,db)
        if not remove:read_blob(item['blob_hash'],item['size'])
        r.editable(identifier if kind=='workspace' else parent['workspace_id'],db)
        if kind=='note' and parent['archived']:
            raise r.ResearchConflict('アーカイブ済みのメモです。')
        table=kind+'_evidence';column=kind+'_id'
        if remove:db.execute(f'DELETE FROM {table} WHERE {column}=? AND evidence_id=?',(identifier,evidence_id))
        else:db.execute(f'INSERT OR IGNORE INTO {table}({column},evidence_id) VALUES(?,?)',(identifier,evidence_id))


def quotation(workspace_id,body):
    values=r.fields(body,{'evidence_id','start','end','quote','note_id'})
    for name in ('evidence_id','start','end'):
        value=values.get(name)
        if type(value) is not int or not 0<=value<=2**63-1:
            raise ValueError('引用 ID と位置は整数で指定してください。')
    quote=r.text(values.get('quote'),'quote',10000,True,True)
    with storage_lock(),r.transaction() as db:
        r.editable(workspace_id,db);item=find(values['evidence_id'],db)
        read_blob(item['blob_hash'],item['size'])
        note_id=values.get('note_id')
        if note_id is not None:
            note=r.find('note',note_id,db)
            if note['workspace_id']!=workspace_id or note['archived']:
                raise ValueError('引用先のメモがこの案件に属していません。')
        start,end=values['start'],values['end']
        if start>=end or end>len(item['text']) or item['text'][start:end]!=quote or digest(item['text'].encode())!=item['text_hash']:
            raise ValueError('引用位置と本文が一致しません。')
        existing=db.execute('SELECT id FROM quotations WHERE workspace_id=? AND evidence_id=? AND start=? AND end=? AND note_id IS ?',(workspace_id,item['id'],start,end,note_id)).fetchone()
        if existing:return existing['id']
        return db.execute('INSERT INTO quotations(workspace_id,note_id,evidence_id,text_hash,start,end,quote,created_at) VALUES(?,?,?,?,?,?,?,?)',(workspace_id,note_id,item['id'],item['text_hash'],start,end,quote,r.now())).lastrowid


def prune():
    with storage_lock(),r.transaction() as db:
        days=db.execute('SELECT retention_days FROM evidence_settings').fetchone()[0]
        cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        cursor=db.execute('''DELETE FROM evidence WHERE captured_at<? AND NOT EXISTS(SELECT 1 FROM workspace_evidence w WHERE w.evidence_id=evidence.id) AND NOT EXISTS(SELECT 1 FROM note_evidence n WHERE n.evidence_id=evidence.id) AND NOT EXISTS(SELECT 1 FROM quotations q WHERE q.evidence_id=evidence.id) AND NOT EXISTS(SELECT 1 FROM watch_events w WHERE w.evidence_id=evidence.id) AND NOT EXISTS(SELECT 1 FROM duplicate_members d WHERE d.evidence_id=evidence.id)''',(cutoff,))
        count=cursor.rowcount
        db.execute('DELETE FROM evidence_blobs WHERE NOT EXISTS(SELECT 1 FROM evidence e WHERE e.blob_hash=evidence_blobs.hash)')
    # DB commit precedes orphan removal; interrupted cleanup is retryable.
    with storage_lock():
        known={row[0] for row in get_db().execute('SELECT hash FROM evidence_blobs')}
        root=blob_path('0'*64).parent
        for child in root.iterdir():
            if child.is_symlink() or not child.is_file() or not HASH.fullmatch(child.name):
                raise ValueError('根拠保存先が不正です。')
            if child.name not in known:child.unlink()
    return count
