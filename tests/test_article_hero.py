import base64
import pytest

from feedastrolabe import article_hero
from feedastrolabe.db import get_db
from test_reader import app, client, subscribe
from test_feed_disclosure import browser, browser_only
from test_reader_navigation import reading_library, live_sequence, markup

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


@pytest.fixture(autouse=True)
def isolated_hero(monkeypatch):
    article_hero.load_image.cache_clear()
    def unavailable(*args, **kwargs):
        raise ValueError('No external network in tests')
    monkeypatch.setattr(article_hero, 'fetch', unavailable)
    yield
    article_hero.load_image.cache_clear()


@pytest.mark.parametrize('metadata', [
    '<meta property="og:image" content="../hero.png">',
    '<meta name="twitter:image" content="../hero.png">',
    '<meta property="og:image" content="javascript:bad"><meta name="twitter:image" content="../hero.png">',
])
def test_proxy_metadata_relative_and_cache(client, monkeypatch, metadata):
    subscribe(client)
    calls=[]
    def fetch(url, **kwargs):
        calls.append((url, kwargs['accept']))
        return (PNG if url.endswith('.png') else metadata.encode(), {'url':'https://example.com/final/article'})
    monkeypatch.setattr(article_hero,'fetch',fetch)
    first=client.get('/articles/1/hero')
    assert first.status_code==200 and first.data==PNG
    assert first.mimetype=='image/png'
    assert "img-src 'self'" in first.headers['Content-Security-Policy']
    assert first.headers['X-Content-Type-Options']=='nosniff'
    assert calls[1][0]=='https://example.com/hero.png'
    assert calls[0][1]=='text/html'
    assert client.get('/articles/1/hero').data==PNG
    assert len(calls)==2


@pytest.mark.parametrize('payload', [b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'<html>error</html>', b''])
def test_reject_active_or_non_image(client, monkeypatch, payload):
    subscribe(client)
    def fetch(url, **kwargs):
        return (payload if url.endswith('.svg') else b'<meta property="og:image" content="https://example.com/a.svg">', {'url':url})
    monkeypatch.setattr(article_hero,'fetch',fetch)
    assert client.get('/articles/1/hero').status_code==204


def test_absent_missing_failure_and_cache(client, monkeypatch):
    subscribe(client)
    assert client.get('/articles/999/hero').status_code==404
    assert client.get('/articles/2/hero').status_code==204
    calls=[]
    def failing(url, **kwargs):
        calls.append(url)
        raise OSError('unreachable')
    monkeypatch.setattr(article_hero,'fetch',failing)
    assert client.get('/articles/1/hero').status_code==204
    assert client.get('/articles/1/hero').status_code==204
    assert len(calls)==1


def test_blocked_original_uses_existing_network_validation(app, client, monkeypatch):
    from feedastrolabe import fetch as network
    subscribe(client)
    with app.app_context(),get_db() as db:
        db.execute("UPDATE articles SET link='http://127.0.0.1/private' WHERE id=1")
    monkeypatch.setattr(article_hero,'fetch',network.fetch)
    monkeypatch.setattr(network.socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('127.0.0.1',80))])
    monkeypatch.setattr(network,'PinnedHTTP',lambda *args,**kwargs:pytest.fail('private request dispatched'))
    assert client.get('/articles/1/hero').status_code==204


def test_detail_semantic_order_and_single_advance(client):
    subscribe(client)
    detail=markup(client.get('/?article=1').data).find(".//section[@id='article-detail']")
    children=list(detail)
    assert [n.tag for n in children]==['div','img','h2','p','div','hr','div','hr','div','div']
    assert children[1].get('data-article-hero')==''
    assert children[4].get('class')=='article-actions'
    assert children[6].get('class')=='prose'
    assert children[8].get('class')=='detail-features'
    assert len(detail.findall(".//form[@class='read-next']"))==1
    assert children[9].find('nav') is not None


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,scheme',[(1280,'light'),(390,'dark')])
@pytest.mark.parametrize('has_image',[True,False])
def test_hero_order_browser(browser, live_sequence, app, monkeypatch, width, scheme, has_image):
    from playwright.sync_api import expect
    base,_=live_sequence
    with app.app_context(),get_db() as db:
        db.execute("UPDATE articles SET link='https://example.com/original'")
    def fetch(url,**kwargs):
        return (PNG if url.endswith('.png') else b'<meta property="og:image" content="/hero.png">',{'url':url})
    if has_image:monkeypatch.setattr(article_hero,'fetch',fetch)
    with browser.new_context(viewport={'width':width,'height':844},color_scheme=scheme) as context:
        page=context.new_page();page.goto(base)
        page.locator('.article-title').first.click()
        detail=page.locator('#article-detail');expect(detail).to_be_visible()
        img=detail.locator('[data-article-hero]')
        if has_image:
            expect(img).to_be_visible()
            assert img.bounding_box()['width']==min(480,detail.evaluate('(el)=>el.clientWidth-parseFloat(getComputedStyle(el).paddingLeft)-parseFloat(getComputedStyle(el).paddingRight)'))
            assert img.bounding_box()['y']<detail.locator('h2').bounding_box()['y']
        else:
            expect(img).to_be_hidden()
        assert detail.evaluate('(el)=>{const r=el.getBoundingClientRect();return r.top>=document.querySelector(".view-heading").getBoundingClientRect().top-1 && r.bottom<=innerHeight;}')
        assert detail.locator('form.read-next').count()==1
        assert detail.locator('.reading-next form').count()==0
        assert detail.evaluate('(el)=>el.scrollWidth<=el.clientWidth')
        page.screenshot(path=f'/tmp/feedastrolabe-content-order-{width}-{has_image}.png')
        detail.locator('.detail-top a').click();expect(detail).to_have_count(0)


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width', [1280,390])
def test_detail_stays_inside_reader_bounds(browser, live_sequence, width):
    from playwright.sync_api import expect
    base,_=live_sequence
    with browser.new_context(viewport={'width':width,'height':844}) as context:
        page=context.new_page()
        page.goto(base+'/?article=15')
        detail=page.locator('#article-detail')
        expect(detail).to_be_visible()
        def check_bounds():
            page.wait_for_function('''() => {
              const detail=document.querySelector('#article-detail').getBoundingClientRect();
              const heading=document.querySelector('.view-heading').getBoundingClientRect();
              const nav=document.querySelector('.app-navigation').getBoundingClientRect();
              const bar=document.querySelector('.workspace .topbar').getBoundingClientRect();
              return detail.top>=Math.max(heading.top,nav.bottom,bar.bottom)-1 && detail.bottom<=innerHeight;
            }''')
        check_bounds()
        before=page.locator('.article-card').first.bounding_box()['width']
        page.evaluate('scrollTo(0,400)');check_bounds()
        page.set_viewport_size({'width':width,'height':640});check_bounds()
        assert abs(before-page.locator('.article-card').first.bounding_box()['width'])<1
        assert detail.evaluate('(el)=>getComputedStyle(el).overflowY')=='auto'
        page.screenshot(path=f'/tmp/feedastrolabe-detail-bounds-{width}.png')
        # The top navigation must receive pointer events even while detail is open.
        nav=page.get_by_role('link',name='設定',exact=True)
        nav.click()
        expect(page).to_have_url(__import__('re').compile('/settings'))
