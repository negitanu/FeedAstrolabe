import csv
from urllib.parse import urlencode

import pytest
from feedastrolabe.reader_search import phrase_input
from test_reader import app, client, subscribe
from test_reader_navigation import markup
from test_reader_productivity import productivity_data
from test_task_navigation import live_empty
from test_feed_disclosure import browser, browser_only


def test_csv_phrases_preserve_legacy_literals_and_scope(app, client):
    subscribe(client)
    phrases=['Hello 100%', 'literal, comma', 'a "quote"']
    value=phrase_input('\n'.join(phrases))
    assert next(csv.reader([value],skipinitialspace=True))==phrases
    result=client.get('/?'+urlencode({'any_terms_csv':value,'exclude_csv':'blocked, absent','sources':1}))
    assert result.status_code==200
    tree=markup(result.data)
    assert tree.find('.//input[@name="any_terms_csv"]').get('value')==value
    assert tree.find('.//input[@name="sources"][@value="1"]').get('checked') is not None
    assert tree.find('.//textarea[@name="any_terms"]') is None
    canonical=tree.find('.//form[@class="bulk-read"]')
    assert canonical.find('input[@name="any_terms"]').get('value')=='\n'.join(phrases)
    assert client.get('/?'+urlencode({'any_terms':'Hello 100%\nliteral, comma'})).status_code==200


@pytest.mark.parametrize('values',[
    {'any_terms_csv':'"unterminated'}, {'any_terms_csv':'first\nsecond'},
    {'any_terms_csv':','.join(str(i) for i in range(11))},
    {'exclude_csv':'x'*201}, {'any_terms_csv':'x','any_terms':'y'},
    {'exclude_csv':'x','exclude':'y'},
])
def test_invalid_compact_phrases(client, values):
    assert client.get('/?'+urlencode(values)).status_code==400


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width,theme,script',[
    (1280,'light',True),(1280,'dark',True),(1280,'system',True),
    (390,'light',True),(390,'dark',True),(390,'system',True),
    (1280,'light',False),(390,'dark',False),
])
def test_compact_search_controls(browser,live_empty,productivity_data,width,theme,script,tmp_path):
    from playwright.sync_api import expect
    from feedastrolabe.presentation import THEME_COOKIE
    with browser.new_context(viewport={'width':width,'height':900},is_mobile=width==390,
                             has_touch=width==390,java_script_enabled=script,
                             color_scheme='dark' if theme=='system' else theme) as context:
        context.add_cookies([{'name':THEME_COOKIE,'value':theme,'url':live_empty}])
        page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(live_empty)
        page.locator('.reader-advanced > summary').click()
        any_input=page.locator('[name=any_terms_csv]')
        exclude=page.locator('[name=exclude_csv]')
        assert any_input.evaluate('(el)=>el.tagName')=='INPUT'
        assert abs(any_input.bounding_box()['height']-page.locator('[name=search_in]').bounding_box()['height'])<1
        controls=page.locator('.advanced-fields > .source-field,.advanced-fields > label')
        assert controls.first.get_attribute('class')=='source-field'
        if width==1280:
            boxes=[controls.nth(i).bounding_box() for i in range(6)]
            assert max(box['y'] for box in boxes)-min(box['y'] for box in boxes)<1
            assert all(boxes[i]['x']<boxes[i+1]['x'] for i in range(5))
        any_input.fill('match, other');exclude.fill('blocked')
        dropdown=page.locator('.source-dropdown');summary=dropdown.locator('summary')
        expect(dropdown.locator('.source-options')).to_be_hidden()
        summary.focus();summary.press('Enter')
        expect(dropdown.locator('.source-options')).to_be_visible()
        dropdown.locator('input[value="1"]').check()
        dropdown.locator('input[value="2"]').check()
        if script:
            expect(summary).to_contain_text('2 件を選択')
            dropdown.locator('input[value="2"]').press('Escape')
            expect(dropdown.locator('.source-options')).to_be_hidden()
        else:
            summary.click()
        page.get_by_role('button',name='検索',exact=True).click()
        expect(any_input).to_have_value('match,other')
        expect(exclude).to_have_value('blocked')
        expect(summary).to_contain_text('2 件を選択')
        summary.click()
        expect(dropdown.locator('input[value="1"]')).to_be_checked()
        expect(dropdown.locator('input[value="2"]')).to_be_checked()
        if script:
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(tmp_path/f'compact-search-{width}-{theme}-{script}.png'),full_page=True)
        assert errors==[]
