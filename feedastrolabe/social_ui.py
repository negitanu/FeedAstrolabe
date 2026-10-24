"""Public social research views; mutation routes use the global CSRF guard."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from .collection import refresh_feeds, RefreshBusy
from .db import get_db
from .preferences import bounded_int, preferences
from .social_research import add_topic, topic_report
from .subscriptions import update_subscription, SubscriptionMissing
from .api import integer_arg
from . import social_ai, research as r
from .openrouter_http import micro_usd

ui = Blueprint('social_research', __name__, url_prefix='/social-research')


@ui.get('')
def index():
    before = integer_arg('before_id', None) if 'before_id' in request.args else None
    rows = get_db().execute('''SELECT f.*,t.window_hours,
      (SELECT sample_count FROM social_runs WHERE feed_id=f.id ORDER BY id DESC LIMIT 1) AS sample_count
      FROM social_topics t JOIN feeds f ON f.id=t.feed_id WHERE (? IS NULL OR f.id<?) ORDER BY f.id DESC LIMIT 21''', (before, before)).fetchall()
    return render_template('social_research.html', topics=rows[:20], next_before=rows[19]['id'] if len(rows)>20 else None, report=None, config=preferences(), ai_config=social_ai.configuration())


@ui.get('/<int:feed_id>')
def detail(feed_id):
    try:
        report = topic_report(feed_id)
    except LookupError as exc:
        abort(404, description=str(exc))
    return render_template('social_research.html', report=report, config=preferences(), ai_config=social_ai.configuration())


@ui.post('/ai/config')
def ai_configure():
    try:
        body = {'expected_revision':bounded_int(request.form.get('expected_revision'),1,2**63-1,'設定版'),
                'provider':request.form.get('provider',social_ai.settings()['provider']), 'model':request.form.get('model',''), 'enabled':request.form.get('enabled')=='1'}
        for field in ('max_output_tokens','daily_calls'):
            body[field] = bounded_int(request.form.get(field),1,10000,field)
        for field in ('input_rate','output_rate','max_cost','daily_cost'):
            body[field] = micro_usd(request.form.get(field))
        social_ai.configure(body)
        flash('AI接続設定を保存しました。', 'success')
    except (ValueError,r.ResearchConflict) as exc:
        flash(str(exc) if not isinstance(exc,social_ai.RouterError) else '料金は0〜100 USDの数値で指定してください。', 'error')
        from .settings_pages import render_page
        return render_page('ai', submitted=request.form.to_dict(), status=400)
    return redirect(url_for('settings_pages.page',section='ai'))


@ui.post('/<int:feed_id>/ai/settings')
def ai_topic_configure(feed_id):
    try:
        social_ai.topic_configure(feed_id, {'expected_revision':bounded_int(request.form.get('expected_revision'),1,2**63-1,'設定版'),
                                          'ai_enabled':request.form.get('ai_enabled')=='1','ai_criteria':request.form.get('ai_criteria','')})
        flash('重要トピックの抽出設定を保存しました。', 'success')
    except r.ResearchMissing:
        abort(404)
    except (ValueError,r.ResearchConflict) as exc:
        flash(str(exc),'error')
    return redirect(url_for('settings_pages.object_edit',kind='feeds',identifier=feed_id))


@ui.post('/<int:feed_id>/ai/jobs')
def ai_enqueue(feed_id):
    try:
        social_ai.enqueue(feed_id)
        flash('重要トピックの抽出を予約しました。ワーカーが実行します。同じ収集回・設定の解析は再送しません。','success')
    except r.ResearchMissing:
        abort(404)
    except (ValueError,r.ResearchConflict) as exc:
        flash(str(exc),'error')
    return redirect(url_for('social_research.detail',feed_id=feed_id,_anchor='important-topics'))


@ui.post('')
def create():
    try:
        minutes = bounded_int(request.form.get('interval_minutes', 30), 15, 1440, '収集間隔（分）')
        feed_id = add_topic(request.form.get('source_type'), request.form.get('target'), request.form.get('instance_url', ''),
                            request.form.get('name'), request.form.get('folder', ''), minutes*60, request.form.get('window_hours', 24))
    except (ValueError, RefreshBusy) as exc:
        flash(str(exc), 'error')
        from .settings_pages import render_source
        return render_source('sns',request.form.to_dict(),400)
    flash('SNS 調査を登録しました。ワーカーの次の巡回で収集します。', 'success')
    return redirect(url_for('social_research.detail', feed_id=feed_id))


@ui.post('/<int:feed_id>/settings')
def configure(feed_id):
    try:
        topic_report(feed_id)
        minutes = bounded_int(request.form.get('interval_minutes'), 15, 1440, '収集間隔（分）')
        update_subscription(feed_id, {'name': request.form.get('name'), 'folder': request.form.get('folder', ''),
                                     'poll_interval': minutes*60, 'window_hours': request.form.get('window_hours'), 'enabled': request.form.get('enabled') == '1'})
        flash('調査設定を保存しました。', 'success')
    except (LookupError, SubscriptionMissing):
        abort(404)
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('settings_pages.object_edit', kind='feeds', identifier=feed_id))


@ui.post('/<int:feed_id>/refresh')
def refresh(feed_id):
    try:
        topic_report(feed_id)
        succeeded, failed = refresh_feeds(feed_id)
        flash('収集しました。' if succeeded else '取得に失敗しました。下のエラーを確認してください。' if failed else 'API の再試行予定まで待機中です。', 'success' if succeeded else 'error' if failed else 'info')
    except LookupError:
        abort(404)
    except RefreshBusy as exc:
        flash(str(exc), 'error')
    return redirect(url_for('social_research.detail', feed_id=feed_id))
