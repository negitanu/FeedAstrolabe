"""Folder identity, feed overviews and shared persistent display order."""
from .db import get_db
from .preferences import bounded_int


class FolderMissing(LookupError):
    pass


def validate_name(name):
    # Do not strip: empty, leading spaces, case and Unicode are identities.
    if not isinstance(name, str) or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError('フォルダー名が不正です。')
    return name


def ordered_names(names):
    remaining = set(names)
    result = []
    for row in get_db().execute('SELECT folder FROM folder_positions ORDER BY position'):
        if row['folder'] in remaining:
            result.append(row['folder'])
            remaining.remove(row['folder'])
    return result + sorted(remaining)


def current_names():
    return ordered_names(row[0] for row in get_db().execute('SELECT DISTINCT folder FROM feeds'))


def feed_rows():
    return get_db().execute('''
        SELECT f.*, count(a.id) AS article_count,
               coalesce(sum(a.is_read=0),0) AS unread
        FROM feeds f LEFT JOIN articles a ON a.feed_id=f.id
        LEFT JOIN feed_positions p ON p.feed_id=f.id
        GROUP BY f.id ORDER BY p.position IS NULL,p.position,f.title,f.id
    ''').fetchall()


def feed_groups(feeds):
    groups = {}
    for feed in feeds:
        groups.setdefault(feed['folder'], []).append(feed)
    return [dict(name=name, feeds=groups[name],
                 unread=sum(f['unread'] for f in groups[name]),
                 article_count=sum(f['article_count'] for f in groups[name]))
            for name in ordered_names(groups)]


def move_folder(name, move, position=None):
    validate_name(name)
    if move not in ('up', 'down', 'position'):
        raise ValueError('移動方法が不正です。')
    db = get_db()
    with db:
        # Resolve against current membership/order and serialize concurrent edits.
        db.execute('BEGIN IMMEDIATE')
        names = current_names()
        if name not in names:
            raise FolderMissing('フォルダーが見つかりません。')
        current = names.index(name)
        if move == 'position':
            target = bounded_int(position, 1, len(names), '移動先の位置') - 1
        else:
            target = max(0, min(len(names) - 1, current + (-1 if move == 'up' else 1)))
        names.pop(current)
        names.insert(target, name)
        db.execute('DELETE FROM folder_positions')
        db.executemany('INSERT INTO folder_positions(folder,position) VALUES(?,?)',
                       ((folder, index) for index, folder in enumerate(names)))
    return target + 1


def rename_folder(name, new_name):
    """Rename an exact identity and its order under the collection write lock."""
    from .collection import refresh_lock
    validate_name(name)
    validate_name(new_name)
    if not new_name or not new_name.strip():
        raise ValueError('フォルダー名を入力してください。')
    db = get_db()
    with refresh_lock(), db:
        db.execute('BEGIN IMMEDIATE')
        names = current_names()
        if name not in names:
            raise FolderMissing('フォルダーが見つかりません。')
        if new_name != name and new_name in names:
            raise ValueError('同じ名前のフォルダーがあります。別の名前を入力してください。')
        names[names.index(name)] = new_name
        db.execute('UPDATE feeds SET folder=? WHERE folder=?', (new_name, name))
        db.execute('DELETE FROM folder_positions')
        db.executemany('INSERT INTO folder_positions(folder,position) VALUES(?,?)',
                       ((folder, index) for index, folder in enumerate(names)))
    return new_name


def move_feed(feed_id, source, destination, position):
    from .collection import refresh_lock
    validate_name(source)
    validate_name(destination)
    db = get_db()
    with refresh_lock(), db:
        db.execute('BEGIN IMMEDIATE')
        feed = db.execute('SELECT folder FROM feeds WHERE id=?', (feed_id,)).fetchone()
        if feed is None:
            raise FolderMissing('フィードが見つかりません。')
        if feed['folder'] != source:
            raise ValueError('所属フォルダーが変更されています。再読み込みしてください。')
        if destination not in current_names():
            raise FolderMissing('移動先フォルダーが見つかりません。')
        groups = {g['name']:[f['id'] for f in g['feeds']] for g in feed_groups(feed_rows())}
        groups[source].remove(feed_id)
        target = bounded_int(position, 1, len(groups[destination])+1, '移動先の位置')-1
        groups[destination].insert(target, feed_id)
        db.execute('UPDATE feeds SET folder=? WHERE id=?', (destination,feed_id))
        for name in {source,destination}:
            db.executemany('INSERT INTO feed_positions VALUES(?,?) ON CONFLICT(feed_id) DO UPDATE SET position=excluded.position',
                           ((identifier,index) for index,identifier in enumerate(groups[name])))
    return [dict(folder=g['name'],feeds=[f['id'] for f in g['feeds']],unread=g['unread']) for g in feed_groups(feed_rows())]
