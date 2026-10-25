import hmac
import os
from pathlib import Path
import secrets
import time

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from .operations_api import api as operations_api
from .operations_ui import ui as operations_ui
from .db import close_db, get_db, init_database
from .collection import add_feed, refresh_feeds, sanitize
from .fetch import normalize_url
from .preferences import preferences
from .display_time import display_time
from .identifiers import DatabaseIDConverter, optional_id, single_value
from .reader_navigation import article_navigation
from .reader_order import order_sql, VISITED
from .navigation import navigation, navigation_context
from .settings_pages import ui as settings_pages
from .subscriptions import update_subscription, delete_subscription, SubscriptionMissing
from .access import configure_access, verify_access
from .api import api
from .settings import settings
from .social_ui import ui as social_ui
from .research_api import research_api
from .research_ui import research_ui
from .evidence_api import api as evidence_api
from .evidence_ui import ui as evidence_ui
from .triage_api import api as triage_api
from .triage_ui import ui as triage_ui
from .assistant_api import api as assistant_api
from .assistant_ui import ui as assistant_ui
from .ai_research_api import api as ai_api
from .ai_research_ui import ui as ai_ui
from .network_api import api as network_api
from .network_ui import ui as network_ui
from .security_api import api as security_api
from .security_ui import ui as security_ui
from .entities_api import api as entities_api
from .entities_ui import ui as entities_ui
from werkzeug.exceptions import HTTPException, SecurityError


def create_app(test_config=None):
    data_dir = Path(os.environ.get('FEEDASTROLABE_DATA_DIR', Path(__file__).resolve().parent.parent / 'instance')).resolve()
    if test_config and test_config.get('DATA_DIR'):
        data_dir = Path(test_config['DATA_DIR']).resolve()
    app = Flask(__name__, instance_path=str(data_dir))
    app.url_map.converters['int'] = DatabaseIDConverter
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o700)
    import fcntl,weakref
    runtime_handle=(data_dir/'runtime.lock').open('a')
    fcntl.flock(runtime_handle,fcntl.LOCK_SH)
    app.extensions['runtime_lock']=runtime_handle
    weakref.finalize(app,runtime_handle.close)
    key_path = data_dir / 'secret.key'
    # Atomic initialization so Web and worker startup cannot produce different keys.
    import fcntl
    with (data_dir / 'init.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not key_path.exists():
            fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as handle:
                handle.write(secrets.token_hex(32))
        key = key_path.read_text().strip()
        init_database(str(data_dir / 'feeds.sqlite3'))
    app.config.update(SECRET_KEY=key, DATABASE=str(data_dir / 'feeds.sqlite3'), MAX_CONTENT_LENGTH=12*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'])
    if test_config:
        app.config.update(test_config)
    configure_access(app)
    app.before_request(verify_access)
    app.register_blueprint(api)
    app.register_blueprint(settings)
    app.register_blueprint(settings_pages)
    from .discovery import ui as discovery_ui
    app.register_blueprint(discovery_ui)
    from .article_hero import hero
    app.register_blueprint(hero)
    app.register_blueprint(navigation)
    app.context_processor(navigation_context)
    from .presentation import presentation_context, script_nonce
    app.context_processor(presentation_context)
    app.register_blueprint(social_ui)
    app.register_blueprint(research_api)
    app.register_blueprint(research_ui)
    app.register_blueprint(evidence_api)
    app.register_blueprint(evidence_ui)
    app.register_blueprint(triage_api)
    app.register_blueprint(triage_ui)
    app.register_blueprint(entities_api)
    app.register_blueprint(entities_ui)
    app.register_blueprint(security_api)
    app.register_blueprint(security_ui)
    app.register_blueprint(network_api)
    app.register_blueprint(network_ui)
    app.register_blueprint(ai_api)
    app.register_blueprint(ai_ui)
    app.register_blueprint(assistant_api)
    app.register_blueprint(assistant_ui)
    app.register_blueprint(operations_api)
    app.register_blueprint(operations_ui)
    app.teardown_appcontext(close_db)
    app.add_template_filter(display_time, 'display_time')
    from .reader_search import phrase_input
    app.add_template_filter(phrase_input, 'phrase_input')

    @app.before_request
    def csrf_protect():
        if request.path.startswith('/api/'):
            return
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        if request.method == 'POST' and not hmac.compare_digest(session['csrf'].encode(), request.form.get('csrf', '').encode()):
            abort(400, description='操作トークンが無効です。ページを再読み込みしてください。')

    @app.after_request
    def security_headers(response):
        script_policy = "'nonce-" + g.sidebar_nonce + "'" if hasattr(g, 'sidebar_nonce') else "'none'"
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src " + script_policy + "; style-src 'self'; img-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def reading_prefs():
        density = session.get('list_density', 'comfortable')
        if density not in ('comfortable', 'compact'):
            density = 'comfortable'
        return {'list_density': density, 'mark_read_on_open': bool(session.get('mark_read_on_open')),
                'scan_after_read': bool(session.get('scan_after_read', False))}

    app.context_processor(lambda: {'reading': reading_prefs()})

    def filters():
        source = request.form if request.method == 'POST' else request.args
        view = single_value(source, 'view', preferences()['default_view'] if request.method == 'GET' else 'all')
        if view not in ('all', 'unread', 'starred', 'history'):
            abort(400, description='表示条件が不正です。')
        feed_id = optional_id(source, 'feed')
        from .folders import validate_name
        folder_name = None
        if 'folder' in source or request.endpoint == 'folder_detail':
            try:
                folder_name = validate_name(single_value(source, 'folder'))
            except ValueError as exc:
                abort(400, description=str(exc))
            if get_db().execute('SELECT 1 FROM feeds WHERE folder=?', (folder_name,)).fetchone() is None:
                abort(404, description='フォルダーが見つかりません。')
        sort = single_value(source, 'sort', None)
        from .reader_order import ordering
        ordering({'sort': sort, 'view': view})
        query = single_value(source, 'q', '').strip()
        if len(query) > 200:
            abort(400, description='検索語は 200 文字以下で指定してください。')
        clauses, params = [], []
        if view == 'unread':
            clauses.append('a.is_read=0')
        if view == 'starred':
            clauses.append('a.is_starred=1')
        if view == 'history':
            clauses.append('EXISTS(SELECT 1 FROM article_visits v WHERE v.article_id=a.id)')
        if feed_id:
            clauses.append('a.feed_id=?')
            params.append(feed_id)
        if folder_name is not None:
            clauses.append('EXISTS(SELECT 1 FROM feeds f WHERE f.id=a.feed_id AND f.folder=?)')
            params.append(folder_name)
        from .reader_search import conditions
        extra_clauses, extra_params, search = conditions(source, query)
        clauses.extend(extra_clauses)
        params.extend(extra_params)
        from .research import find, ResearchMissing, WORKSPACE_ARTICLES
        scopes = {}
        for name, kind in [('workspace','workspace'),('tag','tag')]:
            scopes[name] = optional_id(source, name)
            if scopes[name] is not None:
                try:
                    find(kind, scopes[name])
                except ResearchMissing as exc:
                    abort(404,description=str(exc))
                except ValueError as exc:
                    abort(400,description=str(exc))
        if scopes['workspace']:
            clauses.append(WORKSPACE_ARTICLES)
            params.extend([scopes['workspace']]*2)
        if scopes['tag']:
            clauses.append('EXISTS(SELECT 1 FROM article_tags t WHERE t.article_id=a.id AND t.tag_id=?)')
            params.append(scopes['tag'])
        return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), params, dict(view=view, feed=feed_id, folder=folder_name, q=query, sort=sort, **scopes, **search)

    def return_to():
        target = request.form.get('next', '/')
        # Only application-owned paths; never accept a scheme, authority or backslash.
        if not target.startswith('/') or target.startswith('//') or chr(92) in target or any(ord(c) < 32 for c in target):
            target = '/'
        return redirect(target)

    @app.get('/articles/more', endpoint='article_more')
    @app.get('/folders', endpoint='folder_detail')
    @app.get('/')
    def index():
        from .research import tag_rows, options
        from .folders import feed_rows, feed_groups
        db = get_db()
        where, params, selected = filters()
        article_id = optional_id(request.args, 'article')
        reconcile_ids = []
        raw_reconcile = request.headers.get('X-Reader-Reconcile-Ids')
        if raw_reconcile is not None:
            parts = raw_reconcile.split(',')
            if not 1 <= len(parts) <= 100 or any(not p.isascii() or not p.isdecimal() or len(p)>19 or not 1<=int(p)<=2**63-1 for p in parts):
                abort(400)
            reconcile_ids = [int(p) for p in parts]
            if len(set(reconcile_ids)) != len(reconcile_ids):
                abort(400)

        if selected['feed'] is not None and db.execute('SELECT 1 FROM feeds WHERE id=?',(selected['feed'],)).fetchone() is None:
            abort(404)
        total = db.execute('SELECT count(*) FROM articles a' + where, params).fetchone()[0]
        article = db.execute(f'SELECT a.*,f.title AS feed_title,{VISITED} AS visited_at FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?', (article_id,)).fetchone() if article_id else None
        if article_id and (article is None or (selected['folder'] is not None and
                db.execute('SELECT folder FROM feeds WHERE id=?', (article['feed_id'],)).fetchone()[0] != selected['folder'])):
            abort(404)
        detail_where = where
        if (article is not None and selected['view'] == 'unread'
                and not request.headers.get('X-Reader-Reconcile') and not reconcile_ids
                and db.execute('SELECT 1 FROM article_visits WHERE article_id=?', (article_id,)).fetchone()):
            # Reopening an automatically read detail must retain the unread list scope.
            detail_where = where.replace('a.is_read=0', '(a.is_read=0 OR a.id=?)', 1)
        detail_params = [article_id, *params] if detail_where != where else params
        if article is not None:
            clause = (detail_where + ' AND a.id=?') if detail_where else ' WHERE a.id=?'
            if db.execute('SELECT 1 FROM articles a'+clause,[*detail_params,article_id]).fetchone() is None:
                if request.headers.get('X-Reader-Detail') == '1' and (request.headers.get('X-Reader-Reconcile') == str(article_id) or article_id in reconcile_ids):
                    article = None
                    article_id = None
                else:
                    abort(404)
        navigation = article_navigation(detail_where, detail_params, article_id, selected) if article else None
        from .reader_stream import batch
        cursor = single_value(request.args, 'cursor') if 'cursor' in request.args else None
        if request.endpoint == 'article_more' and cursor is None:
            abort(400)
        all_results = single_value(request.args, 'all', '0')
        if all_results not in ('0','1'):
            abort(400)
        articles, continuation = batch(where,params,selected,cursor,all_results=='1' and request.endpoint!='article_more')

        def reader_url(**changes):
            values = {**selected, **changes}
            endpoint = 'folder_detail' if values.get('folder') is not None else 'index'
            return url_for(endpoint, **values)

        more_url = url_for('article_more', **selected, cursor=continuation) if continuation else None
        next_path = reader_url(article=article_id) if article_id else reader_url()
        if request.endpoint == 'article_more':
            return {'html':render_template('article_cards.html', articles=articles, article=None,
                    reader_url=reader_url, next_path=next_path, selected=selected), 'next':more_url}
        feeds = feed_rows()
        folder_groups = feed_groups(feeds)
        selected_folder = next((group for group in folder_groups if group['name'] == selected['folder']), None)
        count_where = ' WHERE feed_id IN (SELECT id FROM feeds WHERE folder=?)' if selected['folder'] is not None else ''
        count_params = (selected['folder'],) if selected['folder'] is not None else ()
        counts = db.execute('SELECT count(*) AS total,coalesce(sum(is_read=0),0) AS unread,coalesce(sum(is_starred),0) AS starred FROM articles' + count_where, count_params).fetchone()
        counts = dict(counts)
        counts['history'] = db.execute('SELECT count(*) FROM article_visits v JOIN articles ON articles.id=v.article_id' + count_where, count_params).fetchone()[0]
        selected_feed = next((f for f in feeds if f['id'] == selected['feed']), None)
        title = selected_feed['title'] if selected_feed else {'all': 'すべての記事', 'unread': '未読の記事', 'starred': 'スター付き', 'history': '最近読んだ記事'}[selected['view']]
        if selected_folder is not None:
            title = (selected['folder'] or '未分類') + ' の記事'

        script_nonce()
        if request.headers.get('X-Reader-Detail') == '1' and request.headers.get('X-Reader-Reconcile'):
            try:
                reconcile = int(request.headers['X-Reader-Reconcile'])
                if reconcile < 1 or reconcile > 2**63-1:
                    raise ValueError()
            except ValueError:
                abort(400)
            articles = db.execute(f'SELECT a.*,f.title AS feed_title,{VISITED} AS visited_at FROM articles a JOIN feeds f ON f.id=a.feed_id' + where +
                       (' AND ' if where else ' WHERE ') + 'a.id=?', [*params,reconcile]).fetchall()
        if request.headers.get('X-Reader-Detail') == '1' and reconcile_ids:
            marks = ','.join('?' for _ in reconcile_ids)
            articles = db.execute(f'SELECT a.*,f.title AS feed_title,{VISITED} AS visited_at FROM articles a JOIN feeds f ON f.id=a.feed_id' + where +
                       (' AND ' if where else ' WHERE ') + 'a.id IN ('+marks+')', [*params,*reconcile_ids]).fetchall()
        template = 'reader_detail_fragment.html' if request.headers.get('X-Reader-Detail') == '1' else 'index.html'
        return render_template(template, articles=articles, feeds=feeds, counts=counts, article=article,
                               folder_groups=folder_groups, selected_folder=selected_folder, reader_url=reader_url,
                               article_navigation=navigation,
                               sidebar_nonce=g.sidebar_nonce,
                               selected=selected, selected_feed=selected_feed, title=title, total=total, more_url=more_url,
                               safe_content=sanitize(article['content']) if article else '', next_path=next_path,
                               research_workspaces=options('workspace',selected['workspace']),
                               research_tags=options('tag',selected['tag']),
                               article_tags=tag_rows('article',article_id) if article else [])

    @app.post('/feeds')
    def subscribe():
        try:
            url = normalize_url(request.form.get('url', '').strip())
            feed_id = add_feed(url, request.form.get('folder', '').strip()[:80])
            flash('フィードを登録しました。', 'success')
        except Exception as exc:
            app.logger.warning('Subscription failed: %s', exc)
            flash(str(exc)[:500], 'error')
            if request.form.get('source_origin') == 'rss':
                from .settings_pages import render_source
                return render_source('rss',request.form.to_dict(),400)
            return redirect(url_for('index'))
        return redirect(url_for('index',feed=feed_id) if request.form.get('source_origin') == 'rss' else url_for('index'))

    @app.post('/feeds/<int:feed_id>/folder')
    def folder(feed_id):
        try:
            update_subscription(feed_id, {'folder': request.form.get('folder', '')})
            flash('フォルダーを変更しました。', 'success')
        except SubscriptionMissing:
            abort(404)
        except ValueError as exc:
            flash(str(exc), 'error')
        return return_to()

    @app.post('/feeds/<int:feed_id>/delete')
    def delete_feed(feed_id):
        try:
            delete_subscription(feed_id)
            flash('フィードと記事を削除しました。', 'success')
        except SubscriptionMissing:
            abort(404)
        except ValueError as exc:
            flash(str(exc), 'error')
        return redirect(url_for('index'))

    @app.post('/refresh')
    def refresh():
        feed_id = optional_id(request.form, 'feed')
        if feed_id is not None and get_db().execute('SELECT 1 FROM feeds WHERE id=?', (feed_id,)).fetchone() is None:
            abort(404, description='購読が見つかりません。')
        try:
            succeeded, failed = refresh_feeds(feed_id)
            flash(f'更新完了：{succeeded} 件成功、{failed} 件失敗。ページ観測は専用ワーカーに予約しました。', 'error' if failed else 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
        return return_to()

    @app.post('/articles/<int:article_id>/<action>')
    def article_action(article_id, action):
        columns = {'read': 'is_read', 'star': 'is_starred'}
        if action not in columns or request.form.get('value') not in ('0', '1'):
            abort(400)
        db = get_db()
        with db:
            result = db.execute(f'UPDATE articles SET {columns[action]}=? WHERE id=?', (int(request.form['value']), article_id))
            if not result.rowcount:
                abort(404)
        if action == 'read' and request.form['value'] == '1' and reading_prefs()['scan_after_read']:
            where, params, selected = filters()
            unread_where = where + (' AND ' if where else ' WHERE ') + 'a.is_read=0'
            nxt = db.execute('SELECT a.id FROM articles a'+unread_where+' ORDER BY '+order_sql(selected)+' LIMIT 1',params).fetchone()
            return redirect(url_for('folder_detail' if selected['folder'] is not None else 'index',**selected,article=nxt['id'] if nxt else None))
        return return_to()

    @app.post('/articles/<int:article_id>/visit')
    def visit_article(article_id):
        from datetime import datetime, timezone
        db = get_db()
        if db.execute('SELECT 1 FROM articles WHERE id=?', (article_id,)).fetchone() is None:
            abort(404)
        where, params, selected = filters()
        with db:
            db.execute('UPDATE articles SET is_read=1 WHERE id=?', (article_id,))
            db.execute('INSERT INTO article_visits(article_id,visited_at) VALUES(?,?) ON CONFLICT(article_id) DO UPDATE SET visited_at=excluded.visited_at',
                       (article_id, datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')))
        if request.headers.get('X-Reader-State') == '1':
            count_where = ' WHERE feed_id IN (SELECT id FROM feeds WHERE folder=?)' if selected['folder'] is not None else ''
            count_params = (selected['folder'],) if selected['folder'] is not None else ()
            counts = dict(db.execute('SELECT count(*) AS total,coalesce(sum(is_read=0),0) AS unread,coalesce(sum(is_starred),0) AS starred FROM articles' + count_where, count_params).fetchone())
            counts['history'] = db.execute('SELECT count(*) FROM article_visits v JOIN articles ON articles.id=v.article_id' + count_where, count_params).fetchone()[0]
            total = db.execute('SELECT count(*) FROM articles a' + where, params).fetchone()[0]
            return {'counts': counts, 'total': total}
        if request.headers.get('X-Reader-Visit') == '1':
            return '', 204
        return return_to()

    @app.post('/articles/<int:article_id>/open')
    def open_article(article_id):
        where, params, selected = filters()
        db = get_db()
        clause = (where + ' AND a.id=?') if where else ' WHERE a.id=?'
        if db.execute('SELECT 1 FROM articles a'+clause,[*params,article_id]).fetchone() is None:
            abort(404)
        return redirect(url_for('folder_detail' if selected['folder'] is not None else 'index',**selected,article=article_id))

    @app.post('/reading-prefs')
    def save_reading_prefs():
        density = request.form.get('list_density', 'comfortable')
        if density not in ('comfortable','compact'):
            abort(400,description='表示密度が不正です。')
        session['list_density'] = density
        session['mark_read_on_open'] = request.form.get('mark_read_on_open') == '1'
        session['scan_after_read'] = request.form.get('scan_after_read') == '1'
        return return_to()

    @app.post('/articles/bulk-state')
    def selected_state():
        from .reader_state import bulk_state
        from .research_ui import errors
        single_value(request.form, 'csrf')
        action = single_value(request.form, 'action')
        operations = {'read': ('is_read', True), 'unread': ('is_read', False),
                      'star': ('is_starred', True), 'unstar': ('is_starred', False)}
        if action not in operations:
            abort(400, description='一括操作を選択してください。')
        values = request.form.getlist('ids')
        if len(values)>100 or any(not p.isascii() or not p.isdecimal() or len(p)>19 or not 1<=int(p)<=2**63-1 for p in values):
            abort(400, description='記事 ID は1〜100件の正の整数で指定してください。')
        where, params, _ = filters()
        column, value = operations[action]
        with errors():
            bulk_state({'ids': [int(p) for p in values], column: value}, where, params)
        flash(f'{len(values)} 件の記事を更新しました。', 'success')
        return return_to()

    @app.post('/articles/read-all')
    def read_all():
        where, params, _ = filters()
        db = get_db()
        with db:
            db.execute('UPDATE articles SET is_read=1 WHERE id IN (SELECT a.id FROM articles a' + where + ')', params)
        flash('表示条件に一致する記事を既読にしました。', 'success')
        return return_to()

    @app.post('/articles/<int:article_id>/read-next')
    def read_next(article_id):
        where, params, selected = filters()
        db = get_db()
        with db:
            # Keep successor selection and the state change in one snapshot.
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM articles WHERE id=?', (article_id,)).fetchone() is None:
                abort(404)
            navigation = article_navigation(where, params, article_id, selected)
            if navigation is None:
                abort(409, description='この記事は現在の表示条件に含まれていません。一覧を開き直してください。')
            successor = navigation['next']
            db.execute('UPDATE articles SET is_read=1 WHERE id=?', (article_id,))
            if successor:
                target = url_for('folder_detail' if selected['folder'] is not None else 'index', **selected, article=successor['id'], _anchor='article-detail')
            else:
                target = url_for('folder_detail' if selected['folder'] is not None else 'index', **selected)
        if not successor:
            flash('この記事を既読にしました。表示条件に一致する次の記事はありません。', 'success')
        return redirect(target, code=303)

    @app.get('/healthz')
    def health():
        get_db().execute('SELECT 1').fetchone()
        return {'status': 'ok'}

    @app.errorhandler(HTTPException)
    def error_page(error):
        if isinstance(error, SecurityError):
            return error.get_response()
        if request.path.startswith('/api/'):
            response = app.json.response({'error': {'code': error.code, 'message': error.description}})
            response.status_code = error.code
            if error.code == 401:
                response.headers['WWW-Authenticate'] = 'Bearer'
            if error.code == 429:
                response.headers['Retry-After'] = str(60 - int(time.time()) % 60)
            return response
        return render_template('error.html', error=error), error.code

    @app.cli.command('prune-evidence')
    def prune_evidence():
        from .evidence import prune
        click.echo('pruned={}'.format(prune()))

    @app.cli.command('refresh')
    def refresh_command():
        """Refresh all subscriptions once."""
        try:
            click.echo('success={}, failed={}'.format(*refresh_feeds()))
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

    @app.cli.command('connector-jobs')
    def connector_jobs_once():
        from .connectors import process
        from .security_intelligence import schedule
        from .network_intelligence import schedule as network_schedule
        from .ai_research import schedule as ai_schedule
        schedule();network_schedule();ai_schedule();click.echo(process());schedule();network_schedule();ai_schedule()

    @app.cli.command('assistant-jobs')
    def assistant_jobs_once():
        from .assistant import process
        click.echo(process())

    @app.cli.command('extract-entities')
    def extract_entities_once():
        """Extract one bounded fixed-evidence batch; no network access."""
        from .entities import extract
        click.echo(extract())

    @app.cli.command('triage')
    def triage_once():
        """Run one bounded matching/grouping batch without outbound notifications."""
        from .triage import process
        click.echo(process())

    @app.cli.command('operation-jobs')
    def operation_jobs():
        from . import operations,delivery
        operations.schedule();click.echo({'delivery':delivery.process(),'backup':operations.process()})

    @app.cli.command('worker')
    @click.option('--interval', default=None, type=click.IntRange(min=60, max=86400), help='Override global interval; per-feed overrides still apply.')
    @click.option('--once', is_flag=True)
    def worker(interval, once):
        """Refresh periodically; stop with Ctrl-C."""
        from . import operations,delivery
        while True:
            run=operations.start('worker');failure=None;result=(0,0)
            try:
                result = refresh_feeds(due_only=True, interval_override=interval)
                from .security_intelligence import schedule
                from .connectors import process as connector_process
                from .network_intelligence import schedule as network_schedule
                from .ai_research import schedule as ai_schedule
                schedule();network_schedule();ai_schedule();connector_process();schedule();network_schedule();ai_schedule()
                from .assistant import process as assistant_process
                assistant_process()
                from . import social_ai
                social_ai.schedule();social_ai.process()
                delivery.process();operations.schedule();operations.process()
                from .triage import process
                process()
                from .entities import extract
                extract()
                if once or any(result):
                    click.echo('success={}, failed={}'.format(*result))
            except Exception:
                failure='worker-cycle-failed';click.echo(failure,err=True)
            finally:
                operations.end(run,sum(result),failure)
            if once:
                break
            time.sleep(10)

    @app.cli.command('observer-worker')
    @click.option('--once', is_flag=True)
    def observer_worker(once):
        """Observe scheduled and queued public pages with a separate renderer."""
        from .observation import observe_pages
        from . import operations
        while True:
            run=operations.start('observer');failure=None;result=(0,0)
            try:
                result=observe_pages()
                if once or any(result):
                    click.echo('observed={}, failed={}'.format(*result))
            except Exception:
                failure='observer-cycle-failed';click.echo(failure,err=True)
            finally:
                operations.end(run,sum(result),failure)
            if once:
                break
            time.sleep(10)

    return app
