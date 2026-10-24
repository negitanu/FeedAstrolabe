"""Optional original-page hero images, served through the existing safe fetcher."""
from functools import lru_cache
from html.parser import HTMLParser
from http.client import HTTPException
import time

from flask import Blueprint, Response, abort

from .db import get_db
from .fetch import fetch, safe_link

hero = Blueprint('article_hero', __name__)


class ImageMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.og = []
        self.twitter = []

    def handle_starttag(self, tag, attrs):
        if tag != 'meta':
            return
        values = dict(attrs)
        name = (values.get('property') or values.get('name') or '').lower()
        value = values.get('content') or ''
        if name in ('og:image', 'og:image:url'):
            self.og.append(value)
        elif name in ('twitter:image', 'twitter:image:src'):
            self.twitter.append(value)


def image_type(body):
    if body.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if body.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if body.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if body.startswith(b'RIFF') and body[8:12] == b'WEBP':
        return 'image/webp'
    return None


@lru_cache(maxsize=16)
def load_image(original, cache_period):
    # Five-minute cache buckets also bound negative results; at most 16 x 5 MiB.
    try:
        body, meta = fetch(original, accept='text/html')
        if not body:
            return None
        parser = ImageMetadata()
        parser.feed(body.decode('utf-8', errors='replace'))
        url = next((url for value in parser.og + parser.twitter
                    if (url := safe_link(value, meta['url']))), '')
        if not url:
            return None
        body, _ = fetch(url, accept='image/png,image/jpeg,image/gif,image/webp')
        mime = image_type(body) if body else None
        return (body, mime) if mime else None
    except (ValueError, OSError, HTTPException):
        # Missing/blocked images must never prevent reading the article.
        return None


@hero.get('/articles/<int:article_id>/hero')
def image(article_id):
    article = get_db().execute('SELECT link FROM articles WHERE id=?', (article_id,)).fetchone()
    if article is None:
        abort(404)
    original = safe_link(article['link'])
    result = load_image(original, int(time.monotonic() // 300)) if original else None
    if result is None:
        return Response(status=204)
    body, mime = result
    return Response(body, mimetype=mime)
