"""Bounded public-API topic samples and reproducible engagement snapshots."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
import re
import unicodedata
from urllib.parse import quote, urlencode

from .collection import now, refresh_lock
from .db import get_db
from .preferences import bounded_int
from .social import entries, numeric_id, source_values
from .social_http import SocialError, request_json

BLUESKY = 'https://api.bsky.app'
POST_URI = re.compile(r'at://(did:[a-z]+:[A-Za-z0-9:._%-]{1,256})/app\.bsky\.feed\.post/([A-Za-z0-9._~-]{1,128})\Z')


def text_value(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit or any(unicodedata.category(c).startswith('C') for c in value):
        raise ValueError(f'{label}は {limit} 文字以下で入力してください。')
    return value.strip()


def tag_value(value):
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize('NFKC', value).removeprefix('#').casefold()
    return value if 1 <= len(value) <= 64 and all(c.isalnum() or c == '_' for c in value) else None


def topic_values(source_type, target, instance_url):
    target = text_value(target, 200, '検索条件')
    if not isinstance(instance_url, str):
        raise ValueError('サーバーは文字列で指定してください。')
    if source_type == 'mastodon':
        parts = target.replace('、', ',').split(',')
        tags = [tag_value(v.strip()) for v in parts]
        if not 1 <= len(tags) <= 3 or not all(tags):
            raise ValueError('Mastodon はハッシュタグをカンマ区切りで 1〜3 個指定してください。')
        _, _, origin = source_values('mastodon', 'account', 'validation', instance_url)
        target = ','.join(sorted(set(tags)))
    elif source_type == 'bluesky':
        if instance_url.strip():
            raise ValueError('Bluesky の取得先は固定です。サーバー欄は空欄にしてください。')
        origin = BLUESKY
    else:
        raise ValueError('SNS 調査は Mastodon または Bluesky を指定してください。')
    digest = hashlib.sha256((source_type + '\n' + origin + '\n' + target).encode()).hexdigest()
    return 'social-topic:' + digest, target, origin


def add_topic(source_type, target, instance_url='', name='', folder='', poll_interval=1800, window_hours=24):
    url, target, origin = topic_values(source_type, target, instance_url)
    name = text_value(name, 120, '分野名')
    if not isinstance(folder, str) or len(folder.strip()) > 80 or any(ord(c) < 32 for c in folder):
        raise ValueError('フォルダーは 80 文字以下で指定してください。')
    interval = bounded_int(poll_interval, 900, 86400, '収集間隔（秒）')
    window = bounded_int(window_hours, 1, 168, '対象期間（時間）')
    db = get_db()
    with refresh_lock(), db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM feeds WHERE url=?', (url,)).fetchone():
            raise ValueError('この調査条件は登録済みです。')
        feed_id = db.execute('''INSERT INTO feeds(url,title,folder,created_at,source_type,source_kind,target,instance_url,poll_interval)
          VALUES(?,?,?,?,?,'topic',?,?,?)''', (url, name, folder.strip(), now(), source_type, target, origin, interval)).lastrowid
        db.execute('INSERT INTO social_topics(feed_id,window_hours) VALUES(?,?)', (feed_id, window))
    return feed_id


def publication(value):
    try:
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value.astimezone(timezone.utc) if value.tzinfo else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def counter(row, name):
    value = row.get(name, 0)
    if type(value) is not int or not 0 <= value <= 2**31-1:
        raise SocialError('SNS の反応数の形式が不正です。')
    return value


def collect_rows(feed, start, end):
    rows = []
    if feed['source_type'] == 'mastodon':
        for tag in feed['target'].split(','):
            data, _ = request_json(feed['instance_url'] + '/api/v1/timelines/tag/' + quote(tag, safe='') + '?limit=40')
            if not isinstance(data, list) or len(data) > 40:
                raise SocialError('Mastodon のハッシュタグ応答が不正です。')
            rows.extend(data)
    else:
        for sort in ('top', 'latest'):
            params = {'q': feed['target'], 'sort': sort, 'since': start.isoformat(), 'until': end.isoformat(), 'limit': 100}
            data, _ = request_json(BLUESKY + '/xrpc/app.bsky.feed.searchPosts?' + urlencode(params))
            if not isinstance(data, dict) or not isinstance(data.get('posts'), list) or len(data['posts']) > 100:
                raise SocialError('Bluesky の検索応答が不正です。')
            rows.extend(data['posts'])
    return rows


def sample(feed, rows, start, end):
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SocialError('SNS 投稿の形式が不正です。')
        if feed['source_type'] == 'mastodon':
            if row.get('visibility') not in ('public', 'unlisted') or row.get('reblog'):
                continue
            numeric_id(row.get('id'))
            date = publication(row.get('created_at'))
            if date is None or not start <= date <= end:
                continue
            if not isinstance(row.get('content'), str) or len(row['content']) > 100000 or not isinstance(row.get('url', ''), str):
                raise SocialError('Mastodon 投稿本文の形式が不正です。')
            item = entries(feed, [row])[0]
            metrics = tuple(counter(row, n) for n in ('favourites_count', 'reblogs_count', 'replies_count'))
            tags = row.get('tags', [])
            if not isinstance(tags, list) or len(tags) > 100:
                raise SocialError('Mastodon タグの形式が不正です。')
            tags = [tag_value(t.get('name')) for t in tags if isinstance(t, dict)]
        else:
            record, author = row.get('record'), row.get('author')
            uri = row.get('uri')
            match = POST_URI.fullmatch(uri) if isinstance(uri, str) else None
            if not match or not isinstance(author, dict) or author.get('did') != match[1] or not isinstance(record, dict):
                raise SocialError('Bluesky 投稿 ID の形式が不正です。')
            if record.get('$type') != 'app.bsky.feed.post' or not isinstance(record.get('text'), str) or len(record['text']) > 100000:
                raise SocialError('Bluesky 投稿本文の形式が不正です。')
            date = publication(record.get('createdAt'))
            if date is None or not start <= date <= end:
                continue
            text = record['text']
            content = '<p>' + html.escape(text).replace('\n', '<br>') + '</p>'
            link = 'https://bsky.app/profile/' + quote(match[1], safe=':') + '/post/' + quote(match[2], safe='')
            published = date.strftime('%Y-%m-%d %H:%M:%S')
            item = (feed['id'], 'bluesky:' + uri, text[:160] or 'Bluesky 投稿', link, content, text, published, published)
            metrics = tuple(counter(row, n) for n in ('likeCount', 'repostCount', 'replyCount'))
            # Extract actual tag facets and explicit tags, never arbitrary embeds.
            tags = record.get('tags', [])
            facets = record.get('facets', [])
            if not isinstance(tags, list) or len(tags) > 100 or not isinstance(facets, list) or len(facets) > 1000:
                raise SocialError('Bluesky タグの形式が不正です。')
            tags = [tag_value(t) for t in tags]
            for facet in facets:
                if not isinstance(facet, dict) or not isinstance(facet.get('features', []), list) or len(facet.get('features', [])) > 100:
                    raise SocialError('Bluesky タグの形式が不正です。')
                tags.extend(tag_value(f.get('tag')) for f in facet.get('features', []) if isinstance(f, dict) and f.get('$type') == 'app.bsky.richtext.facet#tag')
        likes, reposts, replies = metrics
        value = {'item': item, 'likes': likes, 'reposts': reposts, 'replies': replies, 'score': likes + 2*reposts + replies, 'tags': {t for t in tags if t}}
        # A post may occur in several tags/search orders. Count it once.
        result[item[1]] = value
    return sorted(result.values(), key=lambda v: (v['score'], v['item'][6], v['item'][1]), reverse=True)


def refresh_topic(feed):
    db = get_db()
    topic = db.execute('SELECT window_hours FROM social_topics WHERE feed_id=?', (feed['id'],)).fetchone()
    if not topic:
        raise SocialError('SNS 調査設定が見つかりません。')
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=topic['window_hours'])
    posts = sample(feed, collect_rows(feed, start, end), start, end)
    tags = Counter(t for p in posts for t in p['tags'])
    hashtags = [{'tag': tag, 'posts': count} for tag, count in sorted(tags.items(), key=lambda v: (-v[1], v[0]))[:12]]
    identifiers = []
    new_count = 0
    with db:
        db.execute('BEGIN IMMEDIATE')
        for post in posts:
            item = post['item']
            existing = db.execute('SELECT id FROM articles WHERE feed_id=? AND guid=?', item[:2]).fetchone()
            new_count += int(existing is None)
            db.execute('''INSERT INTO articles(feed_id,guid,title,link,content,search_text,published_at,source_published_at)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(feed_id,guid) DO UPDATE SET
              title=excluded.title,link=excluded.link,content=excluded.content,search_text=excluded.search_text,source_published_at=excluded.source_published_at''', item)
            identifiers.append(db.execute('SELECT id FROM articles WHERE feed_id=? AND guid=?', item[:2]).fetchone()[0])
        timestamp = end.strftime('%Y-%m-%d %H:%M:%S')
        run_id = db.execute('''INSERT INTO social_runs(feed_id,collected_at,window_start,sample_count,new_count,hashtags)
          VALUES(?,?,?,?,?,?)''', (feed['id'], timestamp, start.strftime('%Y-%m-%d %H:%M:%S'), len(posts), new_count, json.dumps(hashtags, ensure_ascii=False))).lastrowid
        for rank, (post, article_id) in enumerate(zip(posts[:40], identifiers[:40]), 1):
            db.execute('INSERT INTO social_results(run_id,article_id,rank,score,likes,reposts,replies) VALUES(?,?,?,?,?,?,?)',
                       (run_id, article_id, rank, post['score'], post['likes'], post['reposts'], post['replies']))
        db.execute('DELETE FROM social_runs WHERE feed_id=? AND id NOT IN (SELECT id FROM social_runs WHERE feed_id=? ORDER BY id DESC LIMIT 30)', (feed['id'], feed['id']))
        db.execute('UPDATE feeds SET checked_at=?,success_at=?,error=NULL,failures=0,retry_at=NULL WHERE id=?', (timestamp, timestamp, feed['id']))
    from .evidence import capture_articles
    capture_articles(identifiers, feed['id'])


def topic_report(feed_id):
    db = get_db()
    row = db.execute('SELECT f.*,s.window_hours,s.ai_enabled,s.ai_criteria,s.ai_revision FROM social_topics s JOIN feeds f ON f.id=s.feed_id WHERE f.id=?', (feed_id,)).fetchone()
    if row is None:
        raise LookupError('SNS 調査が見つかりません。')
    feed = dict(row)
    from .preferences import due_at, preferences
    from .social import cooldown
    due = due_at(feed, preferences())
    retry = cooldown(feed)
    feed['next_poll'] = max(filter(None, [due.strftime('%Y-%m-%d %H:%M:%S') if due else None, retry]), default=None)
    feed['enabled'] = bool(feed['enabled'])
    runs = [dict(r) for r in db.execute('SELECT * FROM social_runs WHERE feed_id=? ORDER BY id DESC LIMIT 30', (feed_id,))]
    for run in runs:
        run['hashtags'] = json.loads(run['hashtags'])
    results = [dict(r) for r in db.execute('''SELECT r.*,a.title,a.link,a.published_at,a.is_read,a.is_starred
      FROM social_results r JOIN articles a ON a.id=r.article_id WHERE r.run_id=? ORDER BY r.rank''', (runs[0]['id'],))] if runs else []
    from .social_ai import report
    return {'topic': feed, 'latest': runs[0] if runs else None, 'results': results, 'history': runs, 'analysis':report(feed_id)}
