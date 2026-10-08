import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for, Response
from .db import get_db
from .preferences import bounded_int, preferences, due_at, save_preferences
from .collection import now
from .keys import issue_key
from .social import add_social, cooldown
from .opml import import_opml, export_opml, MAX_OPML

settings = Blueprint('settings', __name__)


def render_settings(issued_token=None):
    db = get_db()
    config = preferences()
    feeds = []
    for row in db.execute('SELECT * FROM feeds ORDER BY folder,title'):
        feed = dict(row)
        due = due_at(feed, config)
        feed['provider_retry'] = cooldown(feed) if feed['source_type'] != 'rss' else None
        feed['next_poll'] = due.strftime('%Y-%m-%d %H:%M:%S UTC') if due else '次の巡回で取得'
        feeds.append(feed)
    keys = db.execute('SELECT id,name,prefix,scope,created_at,expires_at,revoked_at,last_used_at FROM api_keys ORDER BY id DESC').fetchall()
    return render_template('settings.html', config=config, feeds=feeds, keys=keys, issued_token=issued_token, access_mode=current_app.config['ACCESS_MODE'], x_configured=bool(current_app.config.get('X_TOKEN_FILE') or os.environ.get('FEEDASTROLABE_X_TOKEN_FILE')))


@settings.get('/settings')
def index():
    return render_settings()


@settings.post('/settings')
def save():
    try:
        save_preferences(request.form)
        flash('設定を保存しました。ワーカーは次の巡回で設定を反映します。', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('settings.index'))


@settings.post('/settings/feeds/<int:feed_id>')
def save_feed(feed_id):
    try:
        value = request.form.get('poll_interval', '').strip()
        interval = bounded_int(value, 60, 86400, '個別ポーリング間隔') if value else None
        db = get_db()
        with db:
            result = db.execute('UPDATE feeds SET poll_interval=?,enabled=? WHERE id=?', (interval, int(request.form.get('enabled') == '1'), feed_id))
            if not result.rowcount:
                abort(404)
        flash('フィード設定を保存しました。', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('settings.index'))


@settings.post('/settings/keys')
def create_key():
    try:
        _, token = issue_key(request.form.get('name', ''), request.form.get('scope', 'read'), request.form.get('days', '90'))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('settings.index'))
    # Plaintext stays only in this response, never in a cookie, flash or DB.
    return render_settings(token)


@settings.post('/settings/keys/<int:key_id>/revoke')
def revoke_key(key_id):
    db = get_db()
    with db:
        result = db.execute('UPDATE api_keys SET revoked_at=? WHERE id=? AND revoked_at IS NULL', (now(), key_id))
        if not result.rowcount:
            abort(404)
    flash('API キーを失効させました。', 'success')
    return redirect(url_for('settings.index'))


@settings.get('/subscriptions.opml')
def export():
    return Response(export_opml(), mimetype='text/x-opml', headers={'Content-Disposition': 'attachment; filename="FeedAstrolabe.opml"'})


@settings.post('/settings/opml')
def import_file():
    file = request.files.get('opml')
    try:
        added, skipped = import_opml(file.read(MAX_OPML + 1) if file else b'')
        flash(f'OPML：{added} 件追加、{skipped} 件登録済み。記事はワーカーの巡回時に取得します。', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('settings.index'))


@settings.post('/settings/social')
def subscribe_social():
    try:
        add_social(request.form.get('source_type', ''), request.form.get('source_kind', 'account'), request.form.get('target', ''), request.form.get('instance_url', ''), request.form.get('folder', ''))
        flash('SNS を登録しました。次の巡回で取得します。ライブラリから手動更新もできます。', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('settings.index', _anchor='social'))
