"""User-facing contracts: destination identity, isolated forms and complete workflows."""
from threading import Thread
from urllib.parse import urlsplit

import pytest
from werkzeug.serving import make_server

from feedastrolabe import research, triage, entities, network_intelligence, ai_research, security_intelligence
from feedastrolabe.db import get_db
from feedastrolabe.social_research import add_topic
from test_reader import app, client, post, subscribe
from test_reader_navigation import markup
from test_feed_disclosure import browser, browser_only, live_reader

# Deliberately independent expectations: a valid href/anchor alone is not acceptance.
SETTINGS = {
    'appearance': ('外観', '/settings/appearance'),
    'general': ('収集と表示', '/settings'),
    'api': ('API キー', '/settings/keys'),
    'imports': ('購読の移行（OPML）', '/settings/opml'),
    'ai': ('AI接続', '/settings/ai'),
    'models': ('調査補助のモデル', '/assistant/profiles'),
    'connectors': ('公開情報サービス', '/security/connectors/arxiv'),
    'notifications': ('通知先', '/operations/profiles'),
    'backup': ('バックアップと復元', '/operations/config'),
    'tags': ('共有タグ', '/workspaces/tags'),
    'environment': ('接続情報・実行環境', None),
}


def tree_for(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    return markup(response.data)


def assert_identity(tree, heading, area='設定'):
    assert [''.join(h.itertext()) for h in tree.findall('.//h1')] == [heading]
    nav = tree.find(".//nav[@aria-label='アプリ全体']")
    assert [''.join(a.itertext()) for a in nav.findall('a')] == ['読む', '集める', '調べる', 'まとめる', '設定']
    current = [a for a in nav.findall('a') if a.get('aria-current')]
    assert len(current) == 1 and ''.join(current[0].itertext()) == area


@pytest.mark.parametrize('section', SETTINGS)
def test_setting_identity_and_no_cross_feature_forms(client, section):
    heading, action = SETTINGS[section]
    hub = tree_for(client, '/settings')
    assert hub.find(f".//a[@href='/settings/{section}']") is not None
    tree = tree_for(client, '/settings/' + section)
    assert_identity(tree, heading)
    assert tree.find(f".//nav[@aria-label='設定項目']/a[@href='/settings/{section}'][@aria-current='page']") is not None
    if action:
        assert tree.find(f".//form[@action='{action}']") is not None
    for other, (_, wrong_action) in SETTINGS.items():
        if other != section and wrong_action:
            assert tree.find(f".//form[@action='{wrong_action}']") is None
    for form in tree.findall('.//form'):
        if form.get('method') == 'post':
            assert form.find(".//input[@name='csrf']") is not None
    assert tree.find(".//form[@action='/social-research']") is None


def test_work_screens_do_not_embed_global_settings(client):
    for path, forbidden in [('/social-research','/settings/openrouter'),('/assistant','/assistant/profiles'),
                            ('/security','/security/connectors/arxiv'),('/operations','/operations/config')]:
        tree = tree_for(client, path)
        assert tree.find(f".//form[@action='{forbidden}']") is None
    for path in ['/','/workspaces','/evidence','/entities','/security','/network','/ai-research',
                 '/assistant','/operations','/operations/reports','/social-research',
                 '/navigate/collect','/navigate/research','/navigate/publish']:
        tree = tree_for(client, path)
        assert tree.find(".//nav[@aria-label='アプリ全体']/a[@href='/settings']") is not None
    for path in ('/navigate/collect', '/navigate/research', '/navigate/publish', '/settings'):
        hub = tree_for(client, path)
        assert hub.find(".//h1") is None
        assert hub.find(".//section[@class='first-use']") is None
        assert hub.find(".//nav[@aria-label='このページの項目']") is None
        assert hub.find(".//div[@class='navigation-groups']") is not None
    collect = tree_for(client, '/navigate/collect')
    assert collect.find(".//section[@class='first-use']") is None
    for kind in ('rss', 'sns', 'page', 'mastodon'):
        assert len(collect.findall(f".//a[@href='/sources/new/{kind}']")) == 1
    for old, new in [('/navigate/settings','/settings'),('/settings?section=general','/settings/general'),
                     ('/navigate/tags','/settings/tags')]:
        assert client.get(old).location == new
    assert client.get('/settings?section=unknown').status_code == 404
    assert client.get('/settings/unknown').status_code == 404


def test_all_individual_settings_are_dedicated_and_unpaginated(app, client):
    subscribe(client)
    with app.app_context():
        topic = add_topic('bluesky', 'AI', name='SNS テスト')
        wid = research.create_workspace({'title': '<script>bad()</script>'})
        triage.save(wid, {'name': '条件', 'query': {'any': [{'field':'text','op':'contains','value':'Hello'}]}})
        domain = entities.create({'kind':'domain','value':'example.com'})
        network_intelligence.save_watch(wid, {'entity_id':domain,'provider':'dns','outbound_public':False})
        ai_research.save_watch(wid, {'provider':'arxiv','target':'id:1706.03762','outbound_public':False})
        cve = entities.create({'kind':'cve','value':'CVE-2026-1234'})
        security_intelligence.save_watch(wid, {'entity_id':cve,'outbound_public':False})
        for i in range(105):
            research.create_workspace({'title':f'案件 {i}'})
        with get_db() as db:
            for i in range(105):db.execute('INSERT INTO tags(name) VALUES(?)',(f'tag {i}',))
    response = client.get('/settings')
    assert b'<script>bad()' not in response.data
    tree = markup(response.data)
    links = [a for a in tree.findall('.//a') if a.get('href','').startswith('/settings/items/')]
    assert len([a for a in links if '/workspaces/' in a.get('href')]) == 106
    for a in links:
        href = a.get('href')
        assert not urlsplit(href).fragment
        detail = tree_for(client, href)
        expected = ''.join(a.find('strong').itertext()).removesuffix(' →') + ' の設定'
        assert_identity(detail, expected)
        assert detail.find(".//input[@name='settings_origin']") is not None
    topic_tree = tree_for(client, f'/settings/items/feeds/{topic}')
    assert topic_tree.find(".//input[@name='ai_criteria']") is not None
    assert topic_tree.find(".//input[@name='window_hours']") is not None
    assert len(topic_tree.findall(".//input[@name='folder']")) == 1
    assert len(tree_for(client,'/settings/tags').findall(".//input[@name='name']")) == 106
    assert client.get('/settings/items/not-a-kind/1').status_code == 404
    assert client.get('/settings/items/feeds/99999').status_code == 404
    filtered=tree_for(client,'/settings?q=SNS')
    assert len([a for a in filtered.findall('.//a') if a.get('href','').startswith('/settings/items/')]) == 0


def router_values(**changes):
    return {'expected_revision':'1','model':'vendor/fixture-model','max_output_tokens':'512',
            'daily_calls':'10','max_cost':'0.1','daily_cost':'1','input_rate':'1','output_rate':'3', **changes}


def test_openrouter_save_errors_stay_in_setting_and_do_not_send(app, client, monkeypatch):
    from feedastrolabe import social_ai
    monkeypatch.setattr(social_ai,'generate',lambda *args: pytest.fail('saving must not generate'))
    assert client.post('/settings/openrouter',data=router_values()).status_code == 400
    invalid=post(client,'/settings/openrouter',router_values(daily_calls='0',model='vendor/keep-me'))
    assert invalid.status_code == 400
    tree=markup(invalid.data)
    assert_identity(tree,'AI接続')
    assert tree.find(".//input[@name='model']").get('value') == 'vendor/keep-me'
    assert tree.find(".//input[@name='daily_calls']").get('value') == '0'
    with app.app_context():assert social_ai.configuration()['revision'] == 1
    saved=post(client,'/settings/openrouter',router_values())
    assert saved.location == '/settings/ai'
    tree=tree_for(client,saved.location)
    assert tree.find(".//input[@name='model']").get('value') == 'vendor/fixture-model'
    stale=post(client,'/settings/openrouter',router_values(model='vendor/stale'))
    assert stale.status_code == 400
    with app.app_context():assert social_ai.configuration()['model'] == 'vendor/fixture-model'


def test_save_continuity_and_workspace_handoff(app, client):
    response=post(client,'/settings',{'poll_interval':'900','polling_enabled':'1','page_size':'30',
        'default_view':'all','display_timezone':'Asia/Tokyo','api_rate_limit':'60'})
    assert response.location == '/settings/general'
    assert post(client,'/workspaces/tags',{'return_to':'settings-tags','name':'navigation tag'}).location == '/settings/tags'
    subscribe(client)
    assert post(client,'/settings/feeds/1',{'poll_interval':'600','enabled':'1'}).location == '/settings/items/feeds/1'
    with app.app_context():wid=research.create_workspace({'title':'引き継ぐ案件'})
    response=post(client,f'/workspaces/{wid}/edit',{'settings_origin':'1','title':'編集後','purpose':'目的',
        'questions':'問い','status':'active','classification':'internal'})
    assert response.location == f'/settings/items/workspaces/{wid}'
    for path in [f'/operations/reports?workspace={wid}',f'/assistant?workspace={wid}']:
        options=tree_for(client,path).findall(".//select[@name='workspace_id']/option")
        assert [o.get('value') for o in options if 'selected' in o.attrib] == [str(wid)]


def test_each_watch_save_returns_to_its_own_setting(app, client):
    import json
    with app.app_context():
        wid = research.create_workspace({'title':'保存先の検証'})
        rule = triage.save(wid, {'name':'検索条件', 'query':{'any':[]}})
        domain = entities.create({'kind':'domain','value':'example.com'})
        network = network_intelligence.save_watch(wid, {'entity_id':domain,'provider':'dns','outbound_public':False})
        ai = ai_research.save_watch(wid, {'provider':'arxiv','target':'id:1706.03762','outbound_public':False})
        cve = entities.create({'kind':'cve','value':'CVE-2026-1234'})
        security = security_intelligence.save_watch(wid, {'entity_id':cve,'outbound_public':False})
    for kind, identifier, action, values in [
        ('watchlists', rule, f'/triage/watchlists/{rule}/update', {'name':'保存後の条件','kind':'watchlist','query':json.dumps({'any':[]}),'exclusion':json.dumps({'any':[]}),'priority':'normal','reason':''}),
        ('network', network, f'/network/watches/{network}/update', {'interval_seconds':'7200','retention_days':'90'}),
        ('ai', ai, f'/ai-research/watches/{ai}/update', {'interval_seconds':'7200'}),
        ('security', security, f'/security/watches/{security}/update', {'product':'保存後の製品','version':'1.0'}),
    ]:
        response = post(client, action, {'settings_origin':'1','expected_revision':'1','enabled':'on',**values})
        assert response.status_code == 302
        assert response.location == f'/settings/items/{kind}/{identifier}'
        tree = tree_for(client, response.location)
        assert tree.find(".//*[@role='status']") is not None
        assert tree.find(".//input[@name='expected_revision']").get('value') == '2'


@pytest.mark.parametrize('kind,path,values,field,value', [
    ('sns','/social-research', {'provider':'bluesky','query':'AI','name':'残す名前','interval_minutes':'1'}, 'name','残す名前'),
    ('mastodon','/settings/social', {'source_type':'mastodon','target':'alice','instance_url':'http://example.com'}, 'target','alice'),
    ('page','/settings/pages', {'url':'http://127.0.0.1','selector':'#news'}, 'selector','#news'),
])
def test_source_validation_preserves_context(client,kind,path,values,field,value):
    response = post(client, path, values)
    assert response.status_code == 400
    tree = markup(response.data)
    assert tree.find(f".//input[@name='{field}']").get('value') == value
    current = tree.find(".//nav[@aria-label='アプリ全体']/a[@aria-current]")
    assert ''.join(current.itertext()) == '集める'
    assert tree.find(".//*[@role='alert']") is not None


@pytest.fixture
def live_empty(app):
    server=make_server('127.0.0.1',0,app)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield 'http://127.0.0.1:'+str(server.server_port)
    finally:server.shutdown();thread.join(timeout=5);server.server_close()


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[375,1280])
def test_every_global_setting_in_two_clicks_and_correct_screen(browser,live_empty,width,tmp_path):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':900},java_script_enabled=False) as context:
        page=context.new_page()
        for section,(heading,_) in SETTINGS.items():
            page.goto(live_empty+'/assistant')
            page.get_by_role('navigation',name='アプリ全体').get_by_role('link',name='設定',exact=True).click() # 1
            page.locator('main .destination-card[href="/settings/'+section+'"]').click() # 2
            expect(page).to_have_url(live_empty+'/settings/'+section)
            expect(page.get_by_role('heading',level=1)).to_have_text(heading)
            expect(page.get_by_role('heading',level=1)).to_be_in_viewport()
            expect(page.get_by_role('navigation',name='アプリ全体').locator('[aria-current]')).to_have_text('設定')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.goto(live_empty+'/settings/ai')
        page.get_by_label('モデルID',exact=True).fill('vendor/browser-model')
        page.get_by_role('button',name='保存').click()
        expect(page).to_have_url(live_empty+'/settings/ai')
        expect(page.get_by_role('status')).to_contain_text('保存しました')
        expect(page.get_by_label('モデルID',exact=True)).to_have_value('vendor/browser-model')
        page.screenshot(path=str(tmp_path/f'openrouter-focused-{width}.png'),full_page=True)


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[375,1280])
def test_first_use_rss_and_sns_complete_workflow(browser,live_empty,app,monkeypatch,width,tmp_path):
    from playwright.sync_api import expect
    from feedastrolabe import social_research, discovery
    from test_reader import RSS, META
    monkeypatch.setattr(discovery,'fetch',lambda *a,**kw:(RSS,META))
    from test_social_research import bpost
    monkeypatch.setattr(social_research,'request_json',lambda *args:({'posts':[bpost()]},{}))
    with browser.new_context(viewport={'width':width,'height':900}) as context:
        page=context.new_page();page.goto(live_empty)
        page.get_by_role('link',name='情報源を選んで始める →',exact=True).click()
        page.locator('a.destination-card[href="/sources/new/rss"]').click()
        expect(page.get_by_role('heading',level=1)).to_have_text('RSS / Atom を追加')
        page.get_by_label('Webサイト / RSS / Atom URL',exact=True).fill('https://example.com/feed')
        page.get_by_label('フォルダー',exact=True).fill('ニュース')
        page.get_by_role('button',name='候補を探す',exact=True).click()
        expect(page.get_by_role('heading',name='最新の記事',exact=True)).to_be_visible()
        page.get_by_role('button',name='購読して記事を読む',exact=True).click()
        expect(page).to_have_url(live_empty+'/?feed=1')
        page.locator('.article-title').filter(has_text='First story').click()
        expect(page.locator('#article-detail')).to_contain_text('Hello')
        page.get_by_role('navigation',name='アプリ全体').get_by_role('link',name='集める',exact=True).click()
        page.locator('a.destination-card[href="/sources/new/sns"]').click()
        expect(page.get_by_role('heading',level=1)).to_have_text('SNS の調査分野を追加')
        page.get_by_label('分野名',exact=True).fill('AI 調査')
        page.get_by_label('検索語／ハッシュタグ',exact=True).fill('AI')
        page.get_by_role('button',name='調査を登録',exact=True).click()
        expect(page.get_by_role('heading',level=1)).to_have_text('AI 調査')
        page.get_by_role('button',name='↻ 今すぐ収集',exact=True).click()
        expect(page.locator('.social-results li')).to_have_count(1)
        page.get_by_role('link',name='この分野の設定 →',exact=True).click()
        expect(page.get_by_role('dialog').get_by_role('heading',level=2).first).to_have_text('AI 調査 の設定')
        page.get_by_label('対象期間（時間）',exact=True).fill('48')
        page.get_by_role('button',name='設定を保存',exact=True).click()
        expect(page.get_by_role('dialog').get_by_role('heading',level=2).first).to_have_text('AI 調査 の設定')
        expect(page.get_by_label('対象期間（時間）',exact=True)).to_have_value('48')
        expect(page.locator('[data-editor-feedback]')).to_have_text('保存しました。')
        with page.expect_navigation():
            page.get_by_role('dialog').get_by_role('button',name='閉じる',exact=True).click()
        expect(page.locator('main')).to_contain_text('過去 48 時間')
        page.screenshot(path=str(tmp_path/f'first-use-results-{width}.png'),full_page=True)


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[375,1280])
def test_individual_settings_and_delete_disclosure_in_three_clicks(browser,live_empty,app,width):
    from playwright.sync_api import expect
    with app.app_context():
        topic = add_topic('bluesky','AI',name='編集する分野')
        wid = research.create_workspace({'title':'編集する案件'})
    with browser.new_context(viewport={'width':width,'height':900},java_script_enabled=False) as context:
        page=context.new_page()
        for kind,identifier,heading in [('feeds',topic,'編集する分野 の設定'),('workspaces',wid,'編集する案件 の設定')]:
            page.goto(live_empty+'/operations/reports')
            if kind=='feeds':
                page.goto(live_empty+'/?feed='+str(identifier))
                page.get_by_role('link',name='この情報源の設定 →',exact=True).click()
            else:
                page.get_by_role('navigation',name='アプリ全体').get_by_role('link',name='設定',exact=True).click()
                page.locator('main a[href="/settings/items/'+kind+'/'+str(identifier)+'"]').click()
            expect(page.get_by_role('heading',level=1)).to_have_text(heading)
            expect(page.get_by_role('heading',level=1)).to_be_in_viewport()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            if kind=='feeds':
                expect(page.get_by_label('対象期間（時間）',exact=True)).to_be_visible()
                page.get_by_text('このフィードを削除…',exact=True).click() # 3
                expect(page.get_by_role('button',name='フィードと記事を削除する',exact=True)).to_be_visible()
            else:
                page.get_by_role('button',name='案件を保存',exact=True).click()
                expect(page).to_have_url(live_empty+'/settings/items/workspaces/'+str(wid))
                expect(page.get_by_role('status')).to_contain_text('保存しました')


@pytest.mark.browser
@browser_only
@pytest.mark.parametrize('width',[375,900,1280])
def test_hub_layout_without_duplicate_page_heading(browser,live_empty,width,tmp_path):
    from playwright.sync_api import expect
    with browser.new_context(viewport={'width':width,'height':900}) as context:
        page=context.new_page()
        for area,path in [('collect','/navigate/collect'),('research','/navigate/research'),('publish','/navigate/publish'),('settings','/settings')]:
            page.goto(live_empty+path)
            expect(page.locator('main h1')).to_have_count(0)
            expect(page.locator('main')).to_have_attribute('aria-label',{'collect':'集める','research':'調べる','publish':'まとめる','settings':'設定'}[area])
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            groups=page.locator('main>.navigation-groups>.navigation-group')
            boxes=[group.bounding_box() for group in groups.all()]
            columns=1 if width<=700 else 3 if area=='settings' and width>1000 else 2
            for index,box in enumerate(boxes):
                assert box['width']>0 and box['x']>=0 and box['x']+box['width']<=width
                if index and index%columns:
                    assert abs(box['y']-boxes[index-1]['y'])<1
            page.screenshot(path=str(tmp_path/f'hub-{area}-{width}.png'),full_page=True)
