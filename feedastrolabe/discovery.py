"""Bounded RSS alternate discovery and session-bound subscription previews."""
import hashlib
import hmac
from http.client import HTTPException
from html.parser import HTMLParser

import bleach
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadData, URLSafeTimedSerializer

from . import collection
from .fetch import fetch, normalize_url, safe_link
from .folders import validate_name
from .identifiers import single_value

ui = Blueprint('discovery', __name__)
MAX_CANDIDATES = 8
MAX_AGE = 900


class Alternates(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.candidates = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if (tag != 'link' or 'alternate' not in (values.get('rel') or '').lower().split()
                or (values.get('type') or '').split(';')[0].strip().lower() not in
                ('application/rss+xml', 'application/atom+xml')):
            return
        url = safe_link(values.get('href', ''), self.base)
        if url and len(self.candidates) < MAX_CANDIDATES:
            self.candidates.setdefault(url, (values.get('title') or url)[:200])


def preview(url):
    body, meta = fetch(normalize_url(url), accept='text/html,application/rss+xml,application/atom+xml,application/xml')
    if body is None:
        raise ValueError('プレビューする内容を取得できませんでした。')
    final = normalize_url(meta['url'])
    try:
        parsed = collection.parse_feed(body)
    except ValueError:
        parser = Alternates(final)
        parser.feed(body.decode('utf-8', errors='replace'))
        if not parser.candidates:
            raise ValueError('RSS / Atom が見つかりませんでした。フィードの URL を直接入力してください。') from None
        return {'candidates': [{'url': u, 'title': t} for u, t in parser.candidates.items()]}
    clean = lambda value: bleach.clean(str(value), tags=[], strip=True)[:1000]
    return {'preview': {'url': final, 'title': clean(parsed.feed.get('title', final)),
                        'articles': [{'title': clean(e.get('title', '無題')),
                                      'summary': clean(e.get('summary', ''))[:300]}
                                     for e in sorted(parsed.entries[:2000], key=lambda e: e.get('published_parsed') or e.get('updated_parsed') or (0,)*9, reverse=True)[:5]]}, 'plan': sign(final)}


def signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='rss-discovery-v1')


def binding():
    return hashlib.sha256(session['csrf'].encode()).hexdigest()


def sign(url):
    return signer().dumps({'v': 1, 'session': binding(), 'url': url})


def load(token):
    try:
        if not isinstance(token, str) or len(token) > 8192:
            raise ValueError()
        data = signer().loads(token, max_age=MAX_AGE)
        if (set(data) != {'v', 'session', 'url'} or data['v'] != 1
                or not hmac.compare_digest(data['session'], binding())):
            raise ValueError()
        return normalize_url(data['url'])
    except (BadData, ValueError, TypeError, KeyError):
        raise ValueError('プレビューの有効期限が切れたか無効です。もう一度探索してください。') from None


def render(data=None, status=200):
    from .settings_pages import SOURCES
    return render_template('source_new.html', source_kind='rss', page_title=SOURCES['rss'][0],
                           description=SOURCES['rss'][1], active_area='collect',
                           submitted=request.form, **(data or {})), status


@ui.post('/sources/discover')
def discover():
    try:
        url = single_value(request.form, 'url', '').strip()
        validate_name(single_value(request.form, 'folder', ''))
        return render(preview(url))
    except (ValueError, OSError, HTTPException) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else '取得できませんでした。接続先を確認してください。', 'error')
        return render(status=400)


@ui.post('/sources/confirm')
def confirm():
    try:
        url = load(single_value(request.form, 'plan', ''))
        folder = validate_name(single_value(request.form, 'folder', ''))
        identifier = collection.add_feed(url, folder)
        flash('フィードを登録しました。', 'success')
        return redirect(url_for('index', feed=identifier), code=303)
    except (ValueError, OSError, HTTPException) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else '登録できませんでした。もう一度確認してください。', 'error')
        return render(status=400)
