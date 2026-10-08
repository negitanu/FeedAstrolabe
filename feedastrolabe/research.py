"""Shared research organization; all writes validate inside an atomic transaction."""
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
import sqlite3

import bleach
import markdown
from .db import get_db


class ResearchMissing(ValueError):
    pass


class ResearchConflict(ValueError):
    pass


KINDS = {'workspace': 'workspaces', 'note': 'notes', 'article': 'articles', 'feed': 'feeds', 'tag': 'tags'}
WORKSPACE_FIELDS = {'title', 'purpose', 'questions', 'status', 'classification', 'archived'}
NOTE_FIELDS = {'title', 'body', 'label', 'archived'}
WORKSPACE_ARTICLES = """(EXISTS(SELECT 1 FROM workspace_articles wa WHERE wa.workspace_id=? AND wa.article_id=a.id)
 OR EXISTS(SELECT 1 FROM workspace_feeds wf WHERE wf.workspace_id=? AND wf.feed_id=a.feed_id))"""


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def find(kind, identifier, db=None):
    if type(identifier) is not int or not 1 <= identifier <= 2**63-1:
        raise ValueError('ID は正の整数で指定してください。')
    row = (db or get_db()).execute(f'SELECT * FROM {KINDS[kind]} WHERE id=?', (identifier,)).fetchone()
    if row is None:
        raise ResearchMissing('対象が見つかりません。')
    return row


def record(row):
    result = dict(row)
    if 'archived' in result:
        result['archived'] = bool(result['archived'])
    return result


@contextmanager
def transaction():
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise


def editable(workspace_id, db):
    row = find('workspace', workspace_id, db)
    if row['archived']:
        raise ResearchConflict('アーカイブ済みです。編集するには案件を再開してください。')
    return row


def text(value, name, maximum, required=False, multiline=False):
    if not isinstance(value, str):
        raise ValueError(name + ' は文字列で指定してください。')
    value = value if multiline else value.strip()
    if len(value) > maximum or (required and not value) or any(ord(c) < 32 and (not multiline or c not in '\n\r\t') for c in value):
        raise ValueError(f'{name} は{"1" if required else "0"}〜{maximum}文字で、制御文字は使用できません。')
    return value


def fields(body, allowed):
    if not isinstance(body, dict) or not body or set(body) - allowed:
        raise ValueError('空のデータや未対応の項目は保存できません。')
    return dict(body)


def validate(body, note=False):
    values = fields(body, NOTE_FIELDS if note else WORKSPACE_FIELDS)
    for name in values:
        value = values[name]
        if name in ('title', 'purpose', 'questions', 'body'):
            values[name] = text(value, name, {'title':120,'purpose':10000,'questions':10000,'body':100000}[name], name=='title',name!='title')
        elif name == 'archived':
            if type(value) is not bool:
                raise ValueError('archived は真偽値で指定してください。')
        else:
            choices = {'label':('fact','source-claim','hypothesis'), 'status':('active','paused','completed'), 'classification':('public','internal','restricted')}
            if value not in choices[name]:
                raise ValueError(name + ' の値が無効です。')
    return values


def create_workspace(body):
    values = validate(body)
    if 'title' not in values:
        raise ValueError('title は必須です。')
    timestamp = now()
    with transaction() as db:
        cursor = db.execute('INSERT INTO workspaces(' + ','.join(values) + ',created_at,updated_at) VALUES(' + ','.join('?' for _ in range(len(values)+2)) + ')', list(values.values()) + [timestamp,timestamp])
        return cursor.lastrowid


def update_workspace(identifier, body):
    values = validate(body)
    with transaction() as db:
        current = find('workspace', identifier, db)
        if current['archived'] and values != {'archived':False}:
            raise ResearchConflict('アーカイブ済みです。先に案件を再開してください。')
        db.execute('UPDATE workspaces SET ' + ','.join(k+'=?' for k in values) + ',updated_at=? WHERE id=?', list(values.values()) + [now(),identifier])


def save_revision(db, identifier):
    db.execute('INSERT INTO note_revisions(note_id,revision,title,body,label,archived,created_at) SELECT id,revision,title,body,label,archived,updated_at FROM notes WHERE id=?', (identifier,))


def create_note(workspace_id, body):
    values = validate(body, note=True)
    if 'title' not in values:
        raise ValueError('title は必須です。')
    with transaction() as db:
        editable(workspace_id, db)
        timestamp = now()
        cursor = db.execute('INSERT INTO notes(' + ','.join(values) + ',workspace_id,revision,created_at,updated_at) VALUES(' + ','.join('?' for _ in range(len(values)+4)) + ')', list(values.values()) + [workspace_id,1,timestamp,timestamp])
        save_revision(db, cursor.lastrowid)
        return cursor.lastrowid


def update_note(identifier, body):
    values = fields(body, NOTE_FIELDS | {'expected_revision'})
    revision = values.pop('expected_revision', None)
    if type(revision) is not int or not 1 <= revision <= 2**63-2:
        raise ValueError('expected_revision は正の整数で指定してください。')
    values = validate(values, note=True)
    with transaction() as db:
        current = find('note', identifier, db)
        editable(current['workspace_id'], db)
        if current['revision'] != revision:
            raise ResearchConflict('別の編集が保存されています。最新版と入力内容を確認してください。')
        if current['archived'] and values != {'archived':False}:
            raise ResearchConflict('アーカイブ済みのメモです。先に再開してください。')
        db.execute('UPDATE notes SET ' + ','.join(k+'=?' for k in values) + ',revision=revision+1,updated_at=? WHERE id=? AND revision=?', list(values.values())+[now(),identifier,revision])
        save_revision(db, identifier)


def save_tag(body, identifier=None):
    values = fields(body, {'name'})
    name = text(values.get('name'), 'name', 80, True)
    with transaction() as db:
        if identifier is not None:
            find('tag', identifier, db)
        try:
            if identifier is None:
                return db.execute('INSERT INTO tags(name) VALUES(?)', (name,)).lastrowid
            db.execute('UPDATE tags SET name=? WHERE id=?', (name,identifier))
            return identifier
        except sqlite3.IntegrityError as exc:
            raise ResearchConflict('同名のタグが登録済みです。') from exc


def associate(kind, identifier, target_kind, target_id, remove=False):
    mapping = {('workspace','feed'):('workspace_feeds','workspace_id','feed_id'),
               ('workspace','article'):('workspace_articles','workspace_id','article_id'),
               ('workspace','tag'):('workspace_tags','workspace_id','tag_id'),
               ('article','tag'):('article_tags','article_id','tag_id'),
               ('note','tag'):('note_tags','note_id','tag_id')}
    table, left, right = mapping[(kind,target_kind)]
    with transaction() as db:
        parent = find(kind, identifier, db)
        find(target_kind, target_id, db)
        if kind == 'workspace':
            editable(identifier, db)
        elif kind == 'note':
            editable(parent['workspace_id'], db)
            if parent['archived']:
                raise ResearchConflict('アーカイブ済みのメモです。')
        if not remove and target_kind == 'tag':
            exists = db.execute(f'SELECT 1 FROM {table} WHERE {left}=? AND {right}=?', (identifier,target_id)).fetchone()
            if not exists and db.execute(f'SELECT count(*) FROM {table} WHERE {left}=?', (identifier,)).fetchone()[0] >= 100:
                raise ValueError('関連タグは1件あたり100個までです。')
        if remove:
            db.execute(f'DELETE FROM {table} WHERE {left}=? AND {right}=?', (identifier,target_id))
        else:
            db.execute(f'INSERT OR IGNORE INTO {table}({left},{right}) VALUES(?,?)', (identifier,target_id))


def tag_rows(kind, identifier):
    table = {'workspace':'workspace_tags','article':'article_tags','note':'note_tags'}[kind]
    return get_db().execute(f'SELECT t.* FROM tags t JOIN {table} x ON x.tag_id=t.id WHERE x.{kind}_id=? ORDER BY t.name,t.id', (identifier,)).fetchall()


def render_note(body):
    # Escape raw HTML before Markdown; sanitize generated links and omit all images.
    rendered = markdown.markdown(escape(body, quote=False), extensions=['fenced_code','tables'])
    return bleach.clean(rendered, tags={'p','br','hr','h1','h2','h3','h4','h5','h6','em','strong','blockquote','ul','ol','li','pre','code','a','table','thead','tbody','tr','th','td'}, attributes={'a':['href','title']}, protocols=['http','https'], strip=True)


def options(kind, selected_id=None):
    """Keep an explicitly selected older filter visible within 100 options."""
    table = {'workspace':'workspaces', 'tag':'tags'}[kind]
    order = 'name,id' if kind == 'tag' else 'id DESC'
    rows = get_db().execute(f'SELECT * FROM {table} ORDER BY {order} LIMIT 100').fetchall()
    if selected_id is not None and all(row['id'] != selected_id for row in rows):
        rows = [find(kind,selected_id)] + rows[:99]
    return rows
