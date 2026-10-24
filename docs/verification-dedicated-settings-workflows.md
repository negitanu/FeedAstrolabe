# 専用設定画面・初回利用フローの検証

実施日：2026-10-24（Asia/Tokyo）。対象：`dedicated-settings-workflows`。

## 変更の目的

設定索引からOpenRouterを選ぶとSNS画面へ移動してしまう問題を、アンカーの修正ではなく専用設定画面への分離で解消した。登録・結果閲覧・設定・レポート作成・稼働状況を分け、各画面の見出しと現在位置を一致させた。

## 検証範囲

- 全11種類の設定について、専用URL・主見出し・現在位置・目的のフォームとCSRF、他機能のフォームが混在しないこと。
- 設定の索引を全作業領域から開けること、旧カテゴリURLからのリダイレクト、不明な設定の404。
- 106件の案件、105件のタグ、情報源と各種ウォッチの個別設定。ページ送りや100件の上限に依存せず到達すること。HTMLを含む名称のエスケープと名前検索。
- OpenRouterの保存、無効入力の保持、部分更新の防止、古い版での更新拒否、保存時に生成を実行しないこと。
- 全体・情報源・案件・保存検索・脆弱性・ネットワーク・AI研究ウォッチの保存先と値。ウォッチリストの戻り先引数の衝突も回帰テストを追加して修正。
- SNS・Mastodon・ページ観測の登録エラーで、入力と現在の作業領域を維持すること。
- 案件から要約・レポートへの案件の引き継ぎ。OPML取り消し先とAPIキー発行後の戻り先。
- Chromium、375pxと1280px、JavaScript無効：11種類すべての全体設定を「設定→項目」の2クリックで開き、見出しの表示と横はみ出しがないことを確認。OpenRouterの保存も実操作。
- 同条件のブラウザーで個別情報源・案件を2クリックで開くこと。削除確認の開閉まで3クリック、案件保存後も同じ設定に留まること。
- Chromium、375pxと1280px：空の状態からRSS登録→記事閲覧→SNS登録→投稿収集→分野設定を変更→結果へ戻る一連の操作。
- PC・スマートフォンのOpenRouter専用画面とSNS結果をスクリーンショットで確認。

外部コンテンツ取得・AI応答・通知送信は既存のフィクスチャを使う。実サービスへの送信成功や、実際の初見利用者によるユーザビリティ評価を保証するテストではない。

## 最終実行

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/feedastrolabe-navigation-browsers \
FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q --tb=short
openspec validate dedicated-settings-workflows --strict --no-interactive
git diff --check
.venv/bin/python -m compileall -q feedastrolabe
```

最終ソースで **514 passed in 85.56s**。ブラウザーテストを有効にした全件実行で、失敗・スキップなし。OpenSpec厳格検証、差分の空白チェック、Pythonコンパイルも成功。

## コンテナへの反映

`docker compose up --build -d --wait` が成功。web・worker・observer・rendererを再構築して再作成し、既存のtunnelと合わせて5サービスの稼働を確認した。ヘルスチェックを定義しているweb・rendererはhealthy。

再起動後のwebコンテナ内から実際のHTTP配信へGETし、設定索引、全11設定、4種類の情報源登録、レポートの計17画面でHTTP 200・主見出し・現在の領域を確認。設定ページのフォーム送信先とSNS登録フォームの不在も確認した。`/healthz` は200。確認のための本番データの登録・設定保存・外部送信は行っていない。

この配信確認はコンテナのHTTPサーバーが対象。Cloudflare経由の外部ブラウザー認証は今回の検証範囲には含めない。
