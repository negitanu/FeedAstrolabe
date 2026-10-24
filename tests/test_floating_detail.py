import pytest
from feedastrolabe.db import get_db
from test_reader import app, client
from test_reader_navigation import reading_library, live_sequence, markup, content
from test_feed_disclosure import browser, browser_only


def test_detail_header_original_link(app, client, reading_library):
    with app.app_context(), get_db() as db:
        db.execute("UPDATE articles SET link='https://example.com/original' WHERE id=15")
    tree = markup(client.get('/?article=15').data)
    detail = tree.find(".//section[@id='article-detail']")
    title = detail.find('h2/a')
    assert title.get('href') == 'https://example.com/original'
    assert title.get('target') == '_blank'
    assert set(title.get('rel').split()) == {'noopener', 'noreferrer'}
    assert '元記事を開く' not in content(detail)
    assert len(detail.findall(".//nav[@class='article-sequence']")) == 1
    assert detail.find(".//nav[@aria-label='記事の移動']") is None
    with app.app_context(), get_db() as db:
        db.execute("UPDATE articles SET link='' WHERE id=15")
    assert markup(client.get('/?article=15').data).find(".//section/h2/a") is None


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,scheme,read_on_open', [(1280,'light',False),(1280,'dark',True),(390,'dark',False),(390,'light',True)])
def test_floating_geometry_and_middle_click(browser, live_sequence, app, width, scheme, read_on_open):
    from playwright.sync_api import expect
    base, _ = live_sequence
    with app.app_context(), get_db() as db:
        db.execute("UPDATE articles SET link='https://example.com/original'")
    with browser.new_context(viewport={'width':width,'height':844},color_scheme=scheme) as context:
        context.route('https://example.com/**', lambda route: route.fulfill(body='Original'))
        page=context.new_page();page.goto(base)
        csrf=page.locator('input[name=csrf]').first.input_value()
        page.request.post(base+'/reading-prefs',form={'csrf':csrf,'list_density':'compact','mark_read_on_open':'1' if read_on_open else '0'})
        page.goto(base)
        card=page.locator('.article-card').first
        title=card.locator('.article-title')
        with context.expect_page() as opened:
            title.click(button='middle')
        original=opened.value;original.wait_for_load_state()
        assert original.url=='https://example.com/original'
        assert 'article=' not in page.url
        with app.app_context():
            assert get_db().execute('SELECT count(*) FROM articles WHERE is_read=1').fetchone()[0]==0
        original.close()
        before=card.bounding_box();scroll=page.evaluate('scrollY')
        title.click()
        detail=page.locator('#article-detail');expect(detail).to_be_visible()
        after=card.bounding_box()
        assert abs(before['width']-after['width'])<1
        assert abs(before['x']-after['x'])<1
        assert page.evaluate('scrollY')==scroll
        box=detail.bounding_box()
        assert box['x']>=0 and box['x']+box['width']<=width
        assert detail.evaluate('(el)=>getComputedStyle(el).position')=='fixed'
        with context.expect_page() as opened:
            detail.locator('h2 a').click()
        opened.value.close()
        detail.locator('.detail-top a').click();expect(detail).to_have_count(0)
        assert abs(card.bounding_box()['width']-before['width'])<1

from test_reader_platform import streaming_data
from test_folders import folder_data
from test_task_navigation import live_empty


@pytest.mark.browser
@browser_only
def test_middle_click_appended_and_missing_original(browser, live_empty, streaming_data, app):
    from playwright.sync_api import expect
    with app.app_context(), get_db() as db:
        db.execute("UPDATE articles SET link='https://example.com/original'")
    with browser.new_context() as context:
        context.route('https://example.com/**', lambda route: route.fulfill(body='Original'))
        page=context.new_page();page.goto(live_empty+'/folders?folder=Tech')
        page.locator('[data-article-loader]').scroll_into_view_if_needed()
        expect(page.locator('.article-card')).to_have_count(60)
        aid=page.locator('.article-card').nth(45).get_attribute('data-article-id')
        card=page.locator(f'[data-article-id="{aid}"]')
        with context.expect_page() as opened:
            card.locator('.article-title').click(button='middle')
        opened.value.close()
        assert page.locator('#article-detail').count()==0
        with app.app_context(), get_db() as db:
            db.execute("UPDATE articles SET link='' WHERE id=?", (aid,))
        page.goto(live_empty+'/folders?folder=Tech&all=1')
        assert card.get_attribute('data-original-url')==''
        page.evaluate('() => {window.openCalls=0;window.open=()=>{window.openCalls++};}')
        card.locator('.article-title').click(button='middle')
        assert page.evaluate('window.openCalls')==0
        assert page.locator('#article-detail').count()==0
