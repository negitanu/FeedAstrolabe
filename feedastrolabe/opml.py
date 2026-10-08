import ipaddress
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring
from .collection import now, refresh_lock
from .db import get_db
from .fetch import normalize_url

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


def import_opml(data):
    if not data or len(data) > MAX_OPML:
        raise ValueError('OPML は 1 MiB 以下のファイルを指定してください。')
    try:
        root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        raise ValueError('安全な OPML XML を指定してください。') from None
    if root.tag != 'opml' or root.find('body') is None:
        raise ValueError('OPML の body が見つかりません。')
    entries = []
    # An explicit stack bounds deep nesting without Python recursion.
    stack = [(child, '') for child in root.find('body')]
    while stack:
        node, folder = stack.pop()
        if node.tag != 'outline':
            continue
        if node.get('xmlUrl'):
            entries.append((transfer_url(node.get('xmlUrl')), (node.get('title') or node.get('text') or node.get('xmlUrl'))[:1000], folder[:80]))
            if len(entries) > 100:
                raise ValueError('一度にインポートできるフィードは 100 件までです。')
        else:
            name = node.get('text') or node.get('title') or ''
            next_folder = '/'.join(v for v in (folder, name) if v)[:80]
            stack.extend((child, next_folder) for child in node)
    db = get_db()
    added = skipped = 0
    with refresh_lock(), db:
        for url, title, folder in entries:
            cursor = db.execute('INSERT OR IGNORE INTO feeds(url,title,folder,created_at) VALUES(?,?,?,?)', (url, title, folder, now()))
            if cursor.rowcount:
                added += 1
            else:
                skipped += 1
    return added, skipped


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
