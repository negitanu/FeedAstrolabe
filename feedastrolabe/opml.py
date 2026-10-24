import ipaddress
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring
from .collection import now, refresh_lock
from .db import get_db
from .fetch import normalize_url
from .xml_safety import validate_xml

MAX_OPML = 1024 * 1024


def transfer_url(value):
    url = normalize_url(value)
    host = urlsplit(url).hostname.lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local')):
        raise ValueError('OPML にローカル URL は登録できません。')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return url
    if not address.is_global:
        raise ValueError('OPML にプライベート IP は登録できません。')
    return url


def parse_opml(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_OPML:
        raise ValueError('OPML は 1 MiB 以下のファイルを指定してください。')
    try:
        validate_xml(data, max_bytes=MAX_OPML, max_elements=10000)
        root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ValueError('安全な OPML XML を指定してください。') from None
    if root.tag != 'opml' or root.find('body') is None:
        raise ValueError('OPML の body が見つかりません。')
    entries = []
    # An explicit stack bounds deep nesting without Python recursion.
    stack = [(child, '') for child in reversed(root.find('body'))]
    while stack:
        node, folder = stack.pop()
        if node.tag != 'outline':
            continue
        if node.get('xmlUrl'):
            entries.append({'url': node.get('xmlUrl'), 'title': (node.get('title') or node.get('text') or node.get('xmlUrl'))[:1000], 'folder': folder[:80]})
            if len(entries) > 100:
                raise ValueError('一度にインポートできるフィードは 100 件までです。')
        else:
            name = node.get('text') or node.get('title') or ''
            next_folder = '/'.join(v for v in (folder, name) if v)[:80]
            stack.extend((child, next_folder) for child in reversed(node))
    return validate_entries(entries)


def validate_entries(entries):
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError('一度にインポートできるフィードは 100 件までです。')
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'url', 'title', 'folder'}:
            raise ValueError('購読のデータが不正です。')
        if any(not isinstance(entry[name], str) or len(entry[name]) > limit
               for name, limit in [('url', 2048), ('title', 1000), ('folder', 80)]):
            raise ValueError('購読のデータが不正です。')
        try:
            url = transfer_url(entry['url'])
            if len(url) > 2048:
                raise ValueError()
        except ValueError:
            raise ValueError('認証情報を含まない公開 HTTP(S) URL を指定してください。') from None
        result.append({**entry, 'url': url})
    return result


def preview_entries(entries):
    existing = {row['url'] for row in get_db().execute('SELECT url FROM feeds')}
    seen = set()
    rows = []
    counts = {'new': 0, 'existing': 0, 'duplicate': 0}
    for entry in entries:
        status = 'duplicate' if entry['url'] in seen else 'existing' if entry['url'] in existing else 'new'
        rows.append({**entry, 'status': status})
        counts[status] += 1
        seen.add(entry['url'])
    return rows, counts


def import_entries(entries):
    entries = validate_entries(entries)
    db = get_db()
    added = skipped = 0
    with refresh_lock(), db:
        db.execute('BEGIN IMMEDIATE')
        for entry in entries:
            cursor = db.execute('INSERT OR IGNORE INTO feeds(url,title,folder,created_at) VALUES(?,?,?,?)', (entry['url'], entry['title'], entry['folder'], now()))
            if cursor.rowcount:
                added += 1
            else:
                skipped += 1
    return added, skipped


def import_opml(data):
    return import_entries(parse_opml(data))


def export_opml():
    root = ET.Element('opml', version='2.0')
    ET.SubElement(ET.SubElement(root, 'head'), 'title').text = 'FeedAstrolabe subscriptions'
    body = ET.SubElement(root, 'body')
    folders = {}
    for feed in get_db().execute("SELECT * FROM feeds WHERE source_type='rss' ORDER BY folder,title"):
        folder = feed['folder']
        parent = body
        if folder:
            if folder not in folders:
                folders[folder] = ET.SubElement(body, 'outline', text=folder, title=folder)
            parent = folders[folder]
        ET.SubElement(parent, 'outline', type='rss', text=feed['title'], title=feed['title'], xmlUrl=feed['url'])
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
