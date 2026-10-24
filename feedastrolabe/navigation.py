"""Task-oriented navigation shared by every server-rendered UI screen."""
from flask import Blueprint, abort, render_template, request, url_for, redirect
from .db import get_db

navigation = Blueprint('navigation', __name__, url_prefix='/navigate')

AREAS = (('read', '読む'), ('collect', '集める'), ('research', '調べる'),
         ('publish', 'まとめる'), ('settings', '設定'))


def link(title, description, endpoint, **values):
    return dict(title=title, description=description, href=url_for(endpoint, **values))


def settings_groups():
    from .settings_pages import PAGES
    categories = [('読む・収集する', ['appearance', 'general', 'imports']),
                  ('AI・連携', ['ai', 'models', 'connectors', 'api']),
                  ('管理・保守', ['tags', 'notifications', 'backup', 'environment'])]
    return [(title, [link(PAGES[key], '', 'settings_pages.page', section=key) for key in keys]) for title, keys in categories]


def task_groups(area):
    if area == 'collect':
        return [
            ('RSS / Atom を読む', [
                link('1. 情報源を登録', 'フィードURLとフォルダーを指定します。', 'settings_pages.source', kind='rss'),
                link('2. 収集を設定', '間隔・一時停止・URLを管理します。', 'index'),
                link('3. 記事を読む', '更新後の記事を未読一覧で確認します。', 'index', view='unread'),
            ]),
            ('SNS の話題を追う', [
                link('1. 分野を登録', 'Blueskyの検索語、Mastodonのタグを指定します。', 'settings_pages.source', kind='sns'),
                link('2. 収集結果を確認', '分野を選び、今すぐ収集・注目投稿・履歴を確認します。', 'social_research.index'),
                link('3. 重要トピックを抽出（任意）', 'AI接続のプロバイダ・モデル・予算を設定します。', 'settings_pages.page', section='ai'),
            ]),
            ('ページの変化を追う', [
                link('1. ページ観測を登録', 'URL・比較箇所・保存期間を指定します。', 'settings_pages.source', kind='page'),
                link('2. 観測条件を確認', '初回は比較基準を保存します。稼働状況も確認できます。', 'index'),
                link('3. 変更記事を読む', '2回目以降の変化を記事一覧で確認します。', 'index'),
            ]),
            ('Mastodon アカウントを読む', [
                link('アカウントを購読', 'サーバーとユーザー名を指定します。', 'settings_pages.source', kind='mastodon'),
            ]),
        ]
    if area == 'research':
        return [
            ('調査を進める', [
                link('1. 案件を作る・開く', '目的と問いを定め、情報源・記事・メモをまとめます。', 'research.index'),
                link('2. 根拠を確認', '記事や添付資料を固定し、引用を残します。', 'evidence.index'),
                link('3. 対象と関係を整理', '識別子・組織・製品と、その関係を記録します。', 'entities.index'),
                link('4. 重複を整理', '重複候補を比較し、採用する根拠を判断します。', 'triage.groups'),
            ]),
            ('専門分野を追跡する', [
                link('セキュリティ', '案件とCVE対象を指定して、脆弱性を追跡します。', 'security.index'),
                link('ネットワーク', '案件と公開識別子を指定して、DNS・登録情報・経路を観測します。', 'network.index'),
                link('AI 研究', '案件に論文・公開リリース・モデル版を記録します。', 'ai.index'),
                link('連携を有効にする', '各ウォッチの作成後、必要な公開情報サービスを有効にします。', 'settings_pages.page', section='connectors'),
            ]),
        ]
    return [
        ('調査結果を届ける', [
            link('1. 案件と根拠を確認', '固定した資料・引用・メモをそろえます。', 'research.index'),
            link('2. 要約・翻訳・比較（任意）', 'モデル設定後に入力をプレビューし、承認して生成します。', 'assistant.index'),
            link('3. レポートを作成', '案件から引用付きの出力を作り、内容を確認します。', 'operations.reports_page'),
            link('4. 通知先を設定', '宛先を登録・有効化した後、レポート画面で送信内容を確認・承認します。', 'settings_pages.page', section='notifications'),
        ]),
        ('運用を確認する', [
            link('収集・実行状況', 'ヘルス情報と実行履歴を確認します。', 'operations.index'),
            link('バックアップ', '定期設定・手動予約・保存世代を確認します。', 'settings_pages.page', section='backup'),
        ]),
    ]


def individual_settings():
    """All editable objects, without the feature lists' pagination limits."""
    db = get_db()
    groups = []
    definitions = [
        ('調査案件', 'SELECT id,title AS label FROM workspaces ORDER BY id DESC', 'workspaces'),
        ('保存検索・ウォッチリスト', 'SELECT id,name AS label FROM watchlists ORDER BY id DESC', 'watchlists'),
        ('脆弱性ウォッチ', 'SELECT w.id,e.canonical AS label FROM security_watches w JOIN entities e ON e.id=w.entity_id ORDER BY w.id DESC', 'security'),
        ('ネットワーク観測', 'SELECT id,input AS label FROM network_watches ORDER BY id DESC', 'network'),
        ('AI 研究ウォッチ', 'SELECT id,target AS label FROM ai_watches ORDER BY id DESC', 'ai'),
    ]
    query = request.args.get('q', '').strip().casefold()
    if len(query) > 200:
        abort(400)
    for title, sql, kind in definitions:
        groups.append((title, [link(row['label'], 'この項目の設定を変更', 'settings_pages.object_edit', kind=kind, identifier=row['id']) for row in db.execute(sql) if not query or query in row['label'].casefold()]))
    return groups


@navigation.get('/<area>')
def hub(area):
    if area not in dict(AREAS) or area == 'read':
        abort(404)
    if area == 'settings':
        return redirect(url_for('settings.index'))
    return render_hub(area)


def render_hub(area):
    descriptions = {
        'collect': '情報源を選び、登録・収集・結果の確認まで進めます。',
        'research': '案件を起点に、根拠を集めて問いを検証します。',
        'publish': '根拠をそろえ、要約・レポート・通知まで進めます。',
        'settings': '変更したい項目を選んでください。各項目から入力欄へ直接移動できます。',
    }
    return render_template('navigation_hub.html', area=area, title=dict(AREAS)[area], page_title=dict(AREAS)[area],
                           description=descriptions[area],
                           groups=settings_groups() if area == 'settings' else task_groups(area),
                           individual=individual_settings() if area == 'settings' else [])


@navigation.get('/tags')
def tags():
    return redirect(url_for('settings_pages.page', section='tags'))


def navigation_context():
    endpoint = request.endpoint or ''
    area = 'research'
    if endpoint == 'navigation.hub':
        area = (request.view_args or {}).get('area', 'research')
    elif endpoint == 'settings_pages.source':
        area = 'collect'
    elif endpoint.startswith(('settings.', 'settings_pages.', 'navigation.tags')):
        area = 'settings'
    elif endpoint in ('index', 'folder_detail'):
        area = 'read'
    elif endpoint.startswith('social_research.'):
        area = 'collect'
    elif endpoint.startswith(('operations.', 'assistant.')):
        area = 'publish'
    choices = {}
    if endpoint in ('security.index','network.index','ai.index'):
        choices['workspace_choices'] = get_db().execute('SELECT id,title FROM workspaces WHERE archived=0 ORDER BY title,id').fetchall()
        kinds = {'security.index': ('cve',), 'network.index': ('domain','ip','asn'), 'ai.index': ('model',)}[endpoint]
        choices['entity_choices'] = get_db().execute('SELECT id,display_name,kind FROM entities WHERE merged_into IS NULL AND kind IN (' + ','.join('?' for _ in kinds) + ') ORDER BY display_name,id', kinds).fetchall()
    page_names = {'research.index':'調査案件','research.detail':'調査案件','evidence.index':'根拠','entities.index':'対象と関係','security.index':'セキュリティ情報','network.index':'ネットワーク観測','ai.index':'AI研究','assistant.index':'出典付き調査補助','operations.index':'稼働状況と履歴','operations.reports_page':'レポート','social_research.index':'SNS トレンド調査'}
    return dict(**choices, current_page_name=page_names.get(endpoint, '詳細'), app_navigation=[dict(key=key, title=title, href=url_for('index') if key == 'read' else url_for('settings.index') if key == 'settings' else url_for('navigation.hub', area=key)) for key, title in AREAS], active_area=area)
