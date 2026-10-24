"""Dedicated configuration and registration screens; GET never runs collection."""
from flask import Blueprint, abort, current_app, render_template, request, url_for
from .db import get_db
from .preferences import preferences, due_at
from .social import cooldown
from . import research as r
from .research_ui import errors

ui = Blueprint('settings_pages', __name__)

PAGES = {
    'appearance': '外観',
    'general': '収集と表示',
    'api': 'API キー',
    'imports': '購読の移行（OPML）',
    'ai': 'AI接続',
    'models': '調査補助のモデル',
    'connectors': '公開情報サービス',
    'notifications': '通知先',
    'backup': 'バックアップと復元',
    'tags': '共有タグ',
    'environment': '接続情報・実行環境',
}

SOURCES = {
    'rss': ('RSS / Atom を追加', 'ニュースサイトなどが公開するRSS/AtomのURLを入力します。通常のWebページのURLは「固定ページを観測」で登録してください。'),
    'sns': ('SNS の調査分野を追加', 'Blueskyの検索語、またはMastodonのハッシュタグを指定します。投稿の収集にはAPIキーは不要です。'),
    'page': ('固定ページを観測', '公開ページの一部分を定期比較します。初回は基準の保存、2回目以降の変化が記事になります。'),
    'mastodon': ('Mastodon アカウントを購読', 'Mastodonの公開アカウントを購読します。サーバーURLとローカルユーザー名を入力してください。'),
}


def schedules(identifier=None):
    db = get_db()
    config = preferences()
    sql = 'SELECT * FROM feeds' + (' WHERE id=?' if identifier is not None else '') + ' ORDER BY folder,title,id'
    result = []
    for row in db.execute(sql, (identifier,) if identifier is not None else ()):
        feed = dict(row)
        feed.update(next_poll=due_at(feed, config),
                    provider_retry=cooldown(feed) if feed['source_type'] in ('bluesky', 'mastodon') else None,
                    queued=db.execute('SELECT 1 FROM page_jobs WHERE feed_id=?', (feed['id'],)).fetchone() is not None)
        result.append(feed)
    return result


def render_page(section, *, issued_token=None, submitted=None, status=200):
    if section not in PAGES:
        abort(404)
    from . import social_ai
    from .connector_registry import PROVIDERS
    db = get_db()
    title = PAGES[section]
    data = dict(page_title=title, section=section, active_area='settings',
                settings_links=list(PAGES.items()),
                parts=[section], issued_token=issued_token, submitted=submitted or {},
                work_url=url_for('navigation.hub', area='collect'), work_label='情報源を集める',
                access_mode=current_app.config['ACCESS_MODE'])
    if section == 'appearance':
        data.update(work_url=url_for('index'), work_label='記事を読む')
    elif section == 'general':
        data['config'] = preferences()
        data.update(work_url=url_for('index'), work_label='記事を読む')
    elif section == 'api':
        data.update(keys=db.execute('SELECT id,name,prefix,scope,expires_at,revoked_at,last_used_at FROM api_keys ORDER BY id DESC').fetchall(), parts=['issued_key', 'api', 'keys'])
    elif section == 'ai':
        from .identifiers import single_value
        try:
            selected_provider = (submitted or {}).get('provider') or single_value(request.args,'provider',None)
            ai_config = social_ai.configuration(selected_provider)
        except ValueError as exc:
            abort(400,description=str(exc))
        data.update(ai_config=ai_config, parts=['ai'], work_url=url_for('social_research.index'), work_label='SNS の収集結果を見る')
    elif section == 'models':
        data.update(profiles=db.execute('SELECT * FROM assistant_profiles ORDER BY id DESC').fetchall(), work_url=url_for('assistant.index'), work_label='資料の要約・比較に進む')
    elif section == 'connectors':
        data.update(settings=db.execute('SELECT s.*,z.last_request,z.cooldown_until,z.requests,z.budget_day FROM connector_settings s JOIN connector_state z ON z.provider=s.provider ORDER BY s.provider').fetchall(), providers=PROVIDERS, work_url=url_for('navigation.hub', area='research'), work_label='調査に戻る')
    elif section == 'notifications':
        data.update(profiles=db.execute('SELECT * FROM delivery_profiles ORDER BY id DESC').fetchall(), work_url=url_for('operations.reports_page'), work_label='レポートを作る・送る')
    elif section == 'backup':
        data.update(config=dict(db.execute('SELECT * FROM operations_config').fetchone()), backups=db.execute('SELECT * FROM backup_jobs ORDER BY id DESC LIMIT 100').fetchall(), work_url=url_for('operations.index'), work_label='実行状況を見る')
    elif section == 'tags':
        data.update(tags=db.execute('SELECT * FROM tags ORDER BY name,id').fetchall(), work_url=url_for('research.index'), work_label='案件を開く')
    return render_template('settings_page.html', **data), status


@ui.get('/settings/<section>')
def page(section):
    if section in ('folders','feeds'):
        from flask import redirect
        return redirect(url_for('index'), code=303)
    if section == 'openrouter':
        from flask import redirect
        return redirect(url_for('settings_pages.page',section='ai',provider='openrouter'),code=303)
    return render_page(section)


@ui.get('/settings/items/<kind>/<int:identifier>')
def object_edit(kind, identifier):
    data = dict(active_area='settings', settings_links=list(PAGES.items()),
                section='feeds' if kind == 'feeds' else '', submitted={})
    db = get_db()
    with errors():
        if kind == 'feeds':
            from .social_research import topic_report
            feeds = schedules(identifier)
            if not feeds:
                abort(404)
            feed = feeds[0]
            data.update(page_title=feed['title'] + ' の設定', feeds=feeds, config=preferences(), parts=['feeds'], work_url=url_for('index', feed=identifier), work_label='この情報源の記事を読む')
            if feed['source_kind'] == 'topic':
                data.update(topic=topic_report(identifier)['topic'], parts=['topic', 'topic_ai', 'feeds'], work_url=url_for('social_research.detail', feed_id=identifier), work_label='この分野の収集結果を見る')
        elif kind == 'workspaces':
            item = r.find('workspace', identifier)
            data.update(item=item, page_title=item['title'] + ' の設定', parts=['workspace'], work_url=url_for('research.detail', workspace_id=identifier), work_label='この案件に戻る')
        elif kind == 'watchlists':
            from . import triage
            item = triage.record(triage.find(identifier))
            data.update(item=item, workspace=r.find('workspace', item['workspace_id']), page_title=item['name'] + ' の設定', parts=['watchlist'], work_url=url_for('triage.index', workspace_id=item['workspace_id']), work_label='照合結果を見る')
        elif kind in ('security', 'network', 'ai'):
            from . import security_intelligence, network_intelligence, ai_research
            card = {'security': security_intelligence.card, 'network': network_intelligence.card, 'ai': ai_research.watch_card}[kind](identifier)
            label = card['entity']['canonical'] if kind == 'security' else card['watch']['input'] if kind == 'network' else card['watch']['target']
            data.update(card=card, page_title=label + ' の設定', parts=['ai_watch' if kind=='ai' else kind], work_url=url_for({'security':'security.detail','network':'network.detail','ai':'ai.watch'}[kind], watch_id=identifier), work_label='観測結果を見る')
        else:
            abort(404)
    template = 'object_editor.html' if request.headers.get('X-Context-Editor') == '1' else 'settings_page.html'
    return render_template(template, **data)


@ui.get('/sources/new/<kind>')
def source(kind):
    return render_source(kind)


def render_source(kind, submitted=None, status=200):
    if kind not in SOURCES:
        abort(404)
    title, description = SOURCES[kind]
    return render_template('source_new.html', page_title=title, description=description, source_kind=kind, submitted=submitted or {}, active_area='collect'), status


def object_redirect(kind, object_id, fallback, **values):
    """Only fixed application destinations; the form never supplies a URL."""
    if request.form.get('settings_origin') == '1':
        return url_for('settings_pages.object_edit', kind=kind, identifier=object_id)
    return url_for(fallback, **values)


@ui.post('/settings/openrouter')
@ui.post('/settings/ai')
def save_openrouter():
    from .social_ui import ai_configure
    return ai_configure()


@ui.post('/settings/folders')
@ui.post('/folders/order')
def save_folder_order():
    from flask import flash, redirect
    from .folders import move_folder, FolderMissing
    from .identifiers import single_value
    try:
        position = move_folder(single_value(request.form, 'folder'), single_value(request.form, 'move'),
                               single_value(request.form, 'position'))
    except FolderMissing as exc:
        if request.accept_mimetypes.best == 'application/json':
            return {'error': str(exc)}, 404
        abort(404, description=str(exc))
    except ValueError as exc:
        if request.accept_mimetypes.best == 'application/json':
            return {'error': str(exc)}, 400
        abort(400, description=str(exc))
    if request.accept_mimetypes.best == 'application/json':
        from .folders import current_names
        return {'position': position, 'folders': current_names()}
    flash('フォルダーの表示順を保存しました。', 'success')
    return redirect(url_for('index'), code=303)


@ui.post('/settings/appearance')
def save_appearance():
    from flask import flash, redirect
    from .identifiers import single_value
    from .presentation import THEMES, THEME_COOKIE
    try:
        theme = single_value(request.form, 'theme')
        if theme not in THEMES:
            raise ValueError('外観を選択してください。')
    except ValueError as exc:
        flash(str(exc), 'error')
        return render_page('appearance', status=400)
    flash('外観を保存しました。', 'success')
    response = redirect(url_for('settings_pages.page', section='appearance'), code=303)
    response.set_cookie(THEME_COOKIE, theme, max_age=31536000, httponly=True,
                        secure=current_app.config.get('SESSION_COOKIE_SECURE', False), samesite='Lax')
    return response


@ui.post('/folders/rename')
def rename_folder():
    from .folders import rename_folder as rename, FolderMissing
    from .identifiers import single_value
    from .collection import RefreshBusy
    try:
        name = rename(single_value(request.form, 'folder'), single_value(request.form, 'name'))
    except FolderMissing as exc:
        return {'error': str(exc)}, 404
    except RefreshBusy as exc:
        return {'error': str(exc)}, 409
    except ValueError as exc:
        return {'error': str(exc)}, 400
    return {'name': name}


@ui.route('/feeds/<int:feed_id>/subscription', methods=['GET','POST'])
def subscription(feed_id):
    from .subscriptions import find_feed, update_subscription, SubscriptionMissing
    from .identifiers import single_value
    from .collection import RefreshBusy
    try:
        feed = find_feed(get_db(), feed_id)
        if request.method == 'POST':
            value = single_value(request.form, 'enabled')
            if value not in ('0','1'):
                raise ValueError('購読状態が不正です。')
            update_subscription(feed_id, {'enabled':value == '1'})
            feed = find_feed(get_db(), feed_id)
        return {'enabled':bool(feed['enabled']), 'resumable':feed['source_type'] != 'x'}
    except SubscriptionMissing as exc:
        return {'error':str(exc)}, 404
    except RefreshBusy as exc:
        return {'error':str(exc)}, 409
    except ValueError as exc:
        return {'error':str(exc)}, 400


@ui.post('/feeds/<int:feed_id>/order')
def feed_order(feed_id):
    from .folders import move_feed, FolderMissing
    from .identifiers import single_value
    from .collection import RefreshBusy
    try:
        groups = move_feed(feed_id, single_value(request.form,'source'), single_value(request.form,'folder'), single_value(request.form,'position'))
        return {'groups':groups}
    except FolderMissing as exc:
        return {'error':str(exc)}, 404
    except RefreshBusy as exc:
        return {'error':str(exc)}, 409
    except ValueError as exc:
        return {'error':str(exc)}, 400


