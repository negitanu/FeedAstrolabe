import pytest

from feedastrolabe import collection
from feedastrolabe.db import get_db
from feedastrolabe.fetch import MAX_BYTES
from feedastrolabe.opml import parse_opml
from feedastrolabe.xml_safety import validate_xml
from test_reader import app, client, post, subscribe, RSS, ATOM, META

DECLARATIONS = [
    '<!DOCTYPE rss [<!ENTITY fixture "expanded fixture text">]>',
    '<!DOCTYPE rss [<!ENTITY fixture SYSTEM "file:///private/fixture-sensitive">]>',
    '<!DOCTYPE rss SYSTEM "https://example.com/private-dtd">',
    '<!DOCTYPE rss [<!ENTITY a "1234567890"><!ENTITY fixture "&a;&a;&a;&a;">]>',
]


@pytest.mark.parametrize('declaration', DECLARATIONS)
@pytest.mark.parametrize('encoding', ['UTF-8', 'UTF-16'])
def test_feed_declarations_rejected_before_feedparser(monkeypatch, declaration, encoding):
    body = (f'<?xml version="1.0" encoding="{encoding}"?>'+declaration+
            '<rss version="2.0"><channel><title>fixture</title><item><title>&fixture;</title></item></channel></rss>').encode(encoding)
    monkeypatch.setattr(collection.feedparser, 'parse', lambda *args: pytest.fail('Unsafe XML must not reach feedparser'))
    with pytest.raises(ValueError, match='安全な XML') as caught:
        collection.parse_feed(body)
    assert 'fixture-sensitive' not in str(caught.value)
    assert 'private-dtd' not in str(caught.value)


@pytest.mark.parametrize('body', [b'<rss><channel></rss>', b'junk<!DOCTYPE rss><rss/>',
                                  b'<rss><channel><title>&undefined;</title></channel></rss>',
                                  b'<rss version="2.0"><channel>'+b'<x/>'*100000+b'</channel></rss>',
                                  b'<rss>'+b'<x>'*64+b'</x>'*64+b'</rss>',
                                  b'x'*(MAX_BYTES+1), 'https://example.com/feed'])
def test_feed_shape_and_size_rejected_before_feedparser(monkeypatch, body):
    monkeypatch.setattr(collection.feedparser, 'parse', lambda *args: pytest.fail('Rejected XML must not reach feedparser'))
    with pytest.raises(ValueError):
        collection.parse_feed(body)


@pytest.mark.parametrize('encoding', ['UTF-8', 'UTF-16', 'ISO-8859-1'])
def test_valid_feed_encodings_and_builtin_references(encoding):
    body = (f'<?xml version="1.0" encoding="{encoding}"?>'
            '<rss version="2.0"><channel><title>News &amp; updates</title><item>'
            '<guid>safe</guid><title>Caf&#233; &#x26; news</title>'
            '<description><![CDATA[<p>Safe <b>body</b></p>]]></description>'
            '</item></channel></rss>').encode(encoding)
    parsed = collection.parse_feed(body)
    assert parsed.feed.title == 'News & updates'
    assert parsed.entries[0].title == 'Café & news'
    assert len(collection.parse_feed(ATOM).entries) == 1


def test_xml_exact_structure_limits():
    validate_xml(b'<x>'*64+b'</x>'*64, max_bytes=1000, max_elements=64)
    validate_xml(b'<x><y/><y/><y/></x>', max_bytes=1000, max_elements=4)
    for body, elements in [(b'<x>'*65+b'</x>'*65, 100), (b'<x><y/><y/><y/><y/></x>', 4)]:
        with pytest.raises(ValueError, match='安全な XML'):
            validate_xml(body, max_bytes=1000, max_elements=elements)


def test_literal_doctype_text_in_cdata_is_safe():
    body = b'<rss version="2.0"><channel><title>XML notes</title><item><title>safe</title><description><![CDATA[Example: <!DOCTYPE sample>]]></description></item></channel></rss>'
    assert len(collection.parse_feed(body).entries) == 1


@pytest.mark.parametrize('body', [b'<opml><body>'+b'<outline/>'*9999+b'</body></opml>',
                                  b'<opml><body>'+b'<outline>'*63+b'</outline>'*63+b'</body></opml>'])
def test_opml_structure_limits_reject_without_writes(app, body):
    with app.app_context():
        with pytest.raises(ValueError):
            parse_opml(body)
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0] == 0


def test_unsafe_refresh_preserves_content_and_other_feed_progress(app, client, monkeypatch, caplog):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    post(client, '/articles/1/read', {'value': '1'})
    post(client, '/articles/1/star', {'value': '1'})
    with app.app_context():
        before = [tuple(row) for row in get_db().execute('SELECT * FROM articles WHERE feed_id=1 ORDER BY id')]
    unsafe = ('<!DOCTYPE rss [<!ENTITY external SYSTEM "file:///private/fixture-sensitive">]>'
              '<rss version="2.0"><channel><title>&external;</title></channel></rss>').encode()
    monkeypatch.setattr(collection, 'fetch', lambda url, *args: (unsafe if url.endswith('/feed') else RSS, META))
    result = post(client, '/refresh', follow_redirects=True)
    assert '1 件成功、1 件失敗' in result.get_data(as_text=True)
    assert 'fixture-sensitive' not in result.get_data(as_text=True)
    assert 'fixture-sensitive' not in caplog.text
    with app.app_context():
        db = get_db()
        assert [tuple(row) for row in db.execute('SELECT * FROM articles WHERE feed_id=1 ORDER BY id')] == before
        assert '安全な XML' in db.execute('SELECT error FROM feeds WHERE id=1').fetchone()[0]
        assert db.execute('SELECT error FROM feeds WHERE id=2').fetchone()[0] is None
