from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for, Response
from .db import get_db
from .preferences import bounded_int, preferences, due_at, save_preferences
from .collection import now, RefreshBusy
from .keys import issue_key
from .social import add_social, cooldown
from .observation import add_page, edit_page
from .subscriptions import update_subscription, SubscriptionMissing
from .opml import parse_opml, preview_entries, import_entries, export_opml, MAX_OPML
from .import_preview import sign_plan, load_plan
from .identifiers import single_value

settings = Blueprint('settings', __name__)

def settings_url(anchor=None):
    mapping = {'imports':'imports', 'social':'feeds', 'pages':'feeds', 'subscriptions':'feeds'}
    section = request.form.get('return_section', '')
    section = {'subscriptions':'feeds', 'sources':'feeds'}.get(section, section)
    if section not in ('general','api','imports','feeds'):
        section = mapping.get(anchor, 'general')
    if anchor and anchor.startswith('feed-'):
        return url_for('settings_pages.object_edit', kind='feeds', identifier=int(anchor[5:]))
    return url_for('settings_pages.page', section=section)


def render_settings(issued_token=None):
    from .settings_pages import render_page
    return render_page('api', issued_token=issued_token)


@settings.get('/settings')
def index():
    from .navigation import render_hub
    section = request.args.get('section')
    if section:
        section = {'subscriptions':'feeds','sources':'feeds'}.get(section,section)
        if section not in ('general','feeds','api','imports'):
            abort(404)
        return redirect(url_for('settings_pages.page', section=section))
    return render_hub('settings')


@settings.post('/settings')
def save():
    try:
        save_preferences(request.form)
        flash('設定を保存しました。ワーカーは次の巡回で設定を反映します。', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(settings_url())


@settings.post('/settings/feeds/<int:feed_id>')
def save_feed(feed_id):
    try:
        value = request.form.get('poll_interval', '').strip()
        interval = bounded_int(value, 60, 86400, '個別ポーリング間隔') if value else None
        update_subscription(feed_id, {'poll_interval': interval, 'enabled': request.form.get('enabled') == '1'})
        flash('フィード設定を保存しました。', 'success')
    except SubscriptionMissing:
        abort(404)
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(settings_url(f'feed-{feed_id}'))


@settings.post('/settings/keys')
def create_key():
    try:
        _, token = issue_key(request.form.get('name', ''), request.form.get('scope', 'read'), request.form.get('days', '90'))
    except ValueError as exc:
        flash(str(exc), 'error')
        return redirect(url_for('settings_pages.page',section='api'))
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
    return redirect(url_for('settings_pages.page',section='api'))


@settings.get('/subscriptions.opml')
def export():
    return Response(export_opml(), mimetype='text/x-opml', headers={'Content-Disposition': 'attachment; filename="FeedAstrolabe.opml"'})


@settings.post('/settings/opml')
def import_file():
    file = request.files.get('opml')
    try:
        entries = parse_opml(file.read(MAX_OPML + 1) if file else b'')
        rows, counts = preview_entries(entries)
        return render_template('opml_preview.html', entries=rows, counts=counts, plan=sign_plan(entries))
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(settings_url('imports'))


@settings.post('/settings/opml/confirm')
def confirm_import():
    try:
        entries = load_plan(single_value(request.form, 'plan', ''))
        added, skipped = import_entries(entries)
    except RefreshBusy as exc:
        abort(409, description=str(exc))
    except ValueError as exc:
        abort(400, description=str(exc))
    flash(f'OPML：{added} 件追加、{skipped} 件登録済み・重複。記事はワーカーの巡回時に取得します。', 'success')
    return redirect(settings_url('imports'), code=303)


@settings.post('/settings/social')
def subscribe_social():
    try:
        feed_id = add_social(request.form.get('source_type', ''), request.form.get('source_kind', 'account'), request.form.get('target', ''), request.form.get('instance_url', ''), request.form.get('folder', ''))
        flash('SNS を登録しました。次の巡回で取得します。ライブラリから手動更新もできます。', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
        from .settings_pages import render_source
        return render_source('mastodon',request.form.to_dict(),400)
    return redirect(url_for('settings_pages.object_edit',kind='feeds',identifier=feed_id))


@settings.post('/settings/pages')
def subscribe_page():
    try:
        feed_id = add_page(request.form.get('url',''),request.form.get('selector',''),request.form.get('folder',''),request.form.get('settle_ms','1000'),request.form.get('poll_interval','900'),request.form.get('retention_days','90'))
        flash('ページ観測を登録しました。専用ワーカーの初回観測で基準を保存します。','success')
    except ValueError as exc:
        flash(str(exc),'error')
        from .settings_pages import render_source
        return render_source('page',request.form.to_dict(),400)
    return redirect(url_for('settings_pages.object_edit',kind='feeds',identifier=feed_id))


@settings.post('/settings/pages/<int:feed_id>')
def save_page(feed_id):
    try:
        edit_page(feed_id,request.form.get('selector',''),request.form.get('settle_ms','1000'),request.form.get('retention_days','90'))
        flash('観測設定を保存しました。対象・待機時間を変えると次回に基準を取り直します。既存記事は保持します。','success')
    except SubscriptionMissing:
        abort(404)
    except ValueError as exc:
        flash(str(exc),'error')
    return redirect(settings_url(f'feed-{feed_id}'))


@settings.post('/settings/feeds/<int:feed_id>/url')
def repair_url(feed_id):
    try:
        update_subscription(feed_id, {'url': request.form.get('url', '')})
        flash('取得 URL を保存しました。既存記事は保持し、次の巡回で取得します。', 'success')
    except SubscriptionMissing:
        abort(404)
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(settings_url(f'feed-{feed_id}'))
