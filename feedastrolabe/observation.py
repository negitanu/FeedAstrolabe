"""Page registrations, normalized baselines, durable jobs and change events."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import difflib
import fcntl
import hashlib
import html
from pathlib import Path
import unicodedata

from flask import current_app
from .collection import now
from .db import get_db
from .opml import transfer_url
from .preferences import bounded_int, preferences, is_due
from .page_broker import capture_page
from .page_protocol import ObservationError, MAX_TEXT


def page_values(url, selector, settle_ms=1000, poll_interval=900, retention_days=90):
    if not isinstance(url,str) or not isinstance(selector,str):
        raise ValueError('観測 URL と CSS セレクターを文字列で指定してください。')
    try:
        url = transfer_url(url.strip())
    except ValueError:
        raise ValueError('観測 URL は認証情報を含まない公開 HTTP(S) URL を指定してください。') from None
    selector = selector.strip()
    if not 1 <= len(selector) <= 500 or any(ord(c)<32 for c in selector):
        raise ValueError('CSS セレクターは 1〜500 文字で入力してください。')
    return url,selector,bounded_int(settle_ms,0,10000,'描画待機時間'),bounded_int(poll_interval,60,86400,'観測間隔'),bounded_int(retention_days,1,365,'保存期間')


def canonical(url,selector):
    return url+'#feedastrolabe-observer='+hashlib.sha256(selector.encode()).hexdigest()


def add_page(url,selector,folder='',settle_ms=1000,poll_interval=900,retention_days=90):
    from .collection import refresh_lock
    url,selector,settle,interval,retention=page_values(url,selector,settle_ms,poll_interval,retention_days)
    if not isinstance(folder,str):
        raise ValueError('フォルダーは文字列で入力してください。')
    identity=canonical(url,selector)
    db=get_db()
    with refresh_lock(), db:
        if db.execute('SELECT id FROM feeds WHERE url=?',(identity,)).fetchone():
            raise ValueError('同じ URL とセレクターは登録済みです。')
        return db.execute('''INSERT INTO feeds(url,title,folder,created_at,source_type,source_kind,target,selector,settle_ms,poll_interval,retention_days)
          VALUES(?,?,?,?,'page','element',?,?,?,?,?)''',(identity,'ページ観測 · '+selector,folder.strip()[:80],now(),url,selector,settle,interval,retention)).lastrowid


def edit_page(feed_id,selector,settle_ms,retention_days):
    from .subscriptions import update_subscription, find_feed
    old = find_feed(get_db(), feed_id)
    if old['source_type'] != 'page':
        raise ValueError('ページ観測が見つかりません。')
    update_subscription(feed_id, {'selector': selector, 'settle_ms': settle_ms, 'retention_days': retention_days})


def normalize_text(text):
    if not isinstance(text,str) or len(text)>MAX_TEXT:
        raise ObservationError('size')
    value=unicodedata.normalize('NFKC',text)
    lines=[' '.join(line.split()) for line in value.splitlines()]
    value='\n'.join(line for line in lines if line)
    if not value:
        raise ObservationError('selector')
    if len(value)>MAX_TEXT:
        raise ObservationError('size')
    return value


def save_observation(feed,text):
    text=normalize_text(text)
    db=get_db()
    with db:
        current=db.execute("SELECT * FROM feeds WHERE id=? AND source_type='page'",(feed['id'],)).fetchone()
        if current is None or current['revision']!=feed['revision']:
            return False
        sequence=current['observation_seq']
        if current['snapshot'] is not None and text!=current['snapshot']:
            sequence+=1
            before=current['snapshot']
            diff='\n'.join(difflib.unified_diff(before.splitlines(),text.splitlines(),fromfile='変更前',tofile='変更後',lineterm='',n=3))
            # Snapshot bounds also bound diffs, with an explicit display truncation.
            if len(diff)>120000:
                diff=diff[:120000]+'\n…差分表示を省略しました'
            content='<p>指定要素のテキストが変わりました。</p><pre>'+html.escape(diff)+'</pre><h3>現在の内容</h3><pre>'+html.escape(text)+'</pre>'
            db.execute('''INSERT INTO articles(feed_id,guid,title,link,content,search_text,published_at)
              VALUES(?,?,?,?,?,?,?)''',(feed['id'],f'page:{sequence}',f"{current['title']} · 変更 {sequence}",current['target'],content,diff+'\n'+text,now()))
        db.execute('UPDATE feeds SET snapshot=?,observation_seq=?,checked_at=?,success_at=?,error=NULL,failures=0 WHERE id=?',
                   (text,sequence,now(),now(),feed['id']))
        cutoff=(datetime.now(timezone.utc)-timedelta(days=current['retention_days'])).strftime('%Y-%m-%d %H:%M:%S')
        db.execute('DELETE FROM articles WHERE feed_id=? AND published_at<? AND is_starred=0',(feed['id'],cutoff))
    return True


def queue_page(feed_id):
    db=get_db()
    with db:
        db.execute("INSERT OR IGNORE INTO page_jobs(feed_id,requested_at) SELECT id,? FROM feeds WHERE id=? AND source_type='page'", (now(),feed_id))
        return db.execute("SELECT 1 FROM feeds WHERE id=? AND source_type='page'", (feed_id,)).fetchone() is not None


@contextmanager
def observer_lock():
    with (Path(current_app.instance_path)/'observer.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('ページ観測ワーカーが実行中です。') from None
        try:
            yield
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)


def observe_pages():
    db=get_db()
    successful=failed=0
    with observer_lock():
        config=preferences()
        rows=db.execute("SELECT f.*,j.requested_at FROM feeds f LEFT JOIN page_jobs j ON j.feed_id=f.id WHERE f.source_type='page' ORDER BY j.requested_at,f.id").fetchall()
        for row in rows:
            feed=dict(row)
            if not feed['requested_at'] and not is_due(feed,config):
                continue
            # Consume only this job; a refresh queued while capturing survives.
            if feed['requested_at']:
                with db:
                    db.execute('DELETE FROM page_jobs WHERE feed_id=? AND requested_at=?',(feed['id'],feed['requested_at']))
            try:
                text=capture_page(feed)
                successful+=int(save_observation(feed,text))
            except Exception as exc:
                safe=exc if isinstance(exc,ObservationError) else ObservationError('browser')
                current_app.logger.warning('Page %s observation failed: %s',feed['id'],safe)
                with db:
                    db.execute('UPDATE feeds SET checked_at=?,error=?,failures=failures+1 WHERE id=? AND revision=?',(now(),str(safe),feed['id'],feed['revision']))
                failed+=1
    return successful,failed
