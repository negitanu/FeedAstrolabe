import hmac
import os
from pathlib import Path
import secrets
import time

import click
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

from .db import close_db, get_db, init_database
from .collection import add_feed, refresh_feeds, sanitize
from .fetch import normalize_url
from .preferences import preferences
from .subscriptions import update_subscription, delete_subscription, SubscriptionMissing
from .access import configure_access, verify_access
from .api import api
from .settings import settings
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
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o700)
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
    app.teardown_appcontext(close_db)

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
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def filters():
        source = request.values
        view = source.get('view', preferences()['default_view'])
        if view not in ('all', 'unread', 'starred'):
            view = 'all'
        feed_id = source.get('feed', type=int)
        if feed_id is not None and feed_id < 1:
            feed_id = None
        query = source.get('q', '').strip()[:200]
        clauses, params = [], []
        if view == 'unread':
            clauses.append('a.is_read=0')
        if view == 'starred':
            clauses.append('a.is_starred=1')
        if feed_id:
            clauses.append('a.feed_id=?')
            params.append(feed_id)
        if query:
            clauses.append("(a.title LIKE ? ESCAPE '!' OR a.search_text LIKE ? ESCAPE '!')")
            escaped = query.replace('!', '!!').replace('%', '!%').replace('_', '!_')
            params.extend(['%' + escaped + '%'] * 2)
        from .research import find, ResearchMissing, WORKSPACE_ARTICLES
        scopes = {}
        for name, kind in [('workspace','workspace'),('tag','tag')]:
            value = source.get(name, '')
            scopes[name] = None
            if value:
                try:
                    if not value.isdecimal() or len(value)>19:
                        raise ValueError('ID は正の整数で指定してください。')
                    scopes[name] = int(value)
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
        return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), params, dict(view=view, feed=feed_id, q=query, **scopes)

    def return_to():
        target = request.form.get('next', '/')
        # Only application-owned paths; never accept a scheme, authority or backslash.
        if not target.startswith('/') or target.startswith('//') or chr(92) in target or any(ord(c) < 32 for c in target):
            target = '/'
        return redirect(target)

    @app.get('/')
    def index():
        from .research import tag_rows, options
        db = get_db()
        where, params, selected = filters()
        total = db.execute('SELECT count(*) FROM articles a' + where, params).fetchone()[0]
        page_size = preferences()['page_size']
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(pages, max(1, request.args.get('page', 1, type=int)))
        articles = db.execute('SELECT a.*,f.title AS feed_title FROM articles a JOIN feeds f ON f.id=a.feed_id' + where + ' ORDER BY a.published_at DESC,a.id DESC LIMIT ? OFFSET ?', params + [page_size, (page - 1) * page_size]).fetchall()
        feeds = db.execute('SELECT f.*,sum(CASE WHEN a.is_read=0 THEN 1 ELSE 0 END) AS unread FROM feeds f LEFT JOIN articles a ON a.feed_id=f.id GROUP BY f.id ORDER BY f.folder,f.title').fetchall()
        counts = db.execute('SELECT count(*) AS total,coalesce(sum(is_read=0),0) AS unread,coalesce(sum(is_starred),0) AS starred FROM articles').fetchone()
        article_id = request.args.get('article', type=int)
        article = db.execute('SELECT a.*,f.title AS feed_title FROM articles a JOIN feeds f ON f.id=a.feed_id WHERE a.id=?', (article_id,)).fetchone() if article_id else None
        if article_id and article is None:
            abort(404)
        selected_feed = next((f for f in feeds if f['id'] == selected['feed']), None)
        title = selected_feed['title'] if selected_feed else {'all': 'すべての記事', 'unread': '未読の記事', 'starred': 'スター付き'}[selected['view']]
        return render_template('index.html', articles=articles, feeds=feeds, counts=counts, article=article,
                               selected=selected, selected_feed=selected_feed, title=title, total=total, page=page, pages=pages,
                               safe_content=sanitize(article['content']) if article else '', next_path=request.full_path.rstrip('?'),
                               research_workspaces=options('workspace',selected['workspace']),
                               research_tags=options('tag',selected['tag']),
                               article_tags=tag_rows('article',article_id) if article else [])

    @app.post('/feeds')
    def subscribe():
        try:
            url = normalize_url(request.form.get('url', '').strip())
            add_feed(url, request.form.get('folder', '').strip()[:80])
            flash('フィードを登録しました。', 'success')
        except Exception as exc:
            app.logger.warning('Subscription failed: %s', exc)
            flash(str(exc)[:500], 'error')
        return redirect(url_for('index'))

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
        try:
            succeeded, failed = refresh_feeds(request.form.get('feed', type=int))
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
        return return_to()

    @app.post('/articles/read-all')
    def read_all():
        where, params, _ = filters()
        db = get_db()
        with db:
            db.execute('UPDATE articles SET is_read=1 WHERE id IN (SELECT a.id FROM articles a' + where + ')', params)
        flash('表示条件に一致する記事を既読にしました。', 'success')
        return return_to()

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

    @app.cli.command('worker')
    @click.option('--interval', default=None, type=click.IntRange(min=60, max=86400), help='Override global interval; per-feed overrides still apply.')
    @click.option('--once', is_flag=True)
    def worker(interval, once):
        """Refresh periodically; stop with Ctrl-C."""
        while True:
            try:
                result = refresh_feeds(due_only=True, interval_override=interval)
                from .security_intelligence import schedule
                from .connectors import process as connector_process
                from .network_intelligence import schedule as network_schedule
                from .ai_research import schedule as ai_schedule
                schedule();network_schedule();ai_schedule();connector_process();schedule();network_schedule();ai_schedule()
                from .assistant import process as assistant_process
                assistant_process()
                from .triage import process
                process()
                from .entities import extract
                extract()
                if once or any(result):
                    click.echo('success={}, failed={}'.format(*result))
            except ValueError as exc:
                click.echo(str(exc), err=True)
            if once:
                break
            time.sleep(10)

    @app.cli.command('observer-worker')
    @click.option('--once', is_flag=True)
    def observer_worker(once):
        """Observe scheduled and queued public pages with a separate renderer."""
        from .observation import observe_pages
        while True:
            try:
                result=observe_pages()
                if once or any(result):
                    click.echo('observed={}, failed={}'.format(*result))
            except ValueError as exc:
                click.echo(str(exc),err=True)
            if once:
                break
            time.sleep(10)

    return app
