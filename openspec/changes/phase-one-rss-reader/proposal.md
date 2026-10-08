## Why

複数の RSS/Atom を一箇所で読み、記事の既読状態と保存状態を継続して管理したい。後続のコンテナ運用、SNS、固定ページ観測に向けて、まずローカルで動く個人用リーダーを完成させる。

## What Changes

- 日本語のレスポンシブ Web UI、フィード追加・削除・フォルダー分類。
- RSS/Atom の手動・定期取得、重複排除、条件付き HTTP リクエスト、取得エラーの表示。
- 記事一覧・本文表示、未読・スター・フィード・検索による絞り込み、ページ送り。
- SQLite 永続化と Git 管理、検証手順、四段階のロードマップ。
- 第一段階は localhost の個人利用。外部公開、SNS、Playwright 観測は後続の独立した変更とする。

## Capabilities

### New Capabilities
- `feed-collection`: RSS/Atom の登録、分類、削除、取得と重複排除。
- `article-reader`: 記事閲覧、検索、既読・スター操作と永続化。
- `local-operation`: ローカル起動、定期更新、永続データと安全な入力処理。

### Modified Capabilities

なし（新規プロジェクト）。

## Impact

Flask、SQLite、feedparser、bleach、Waitress を導入。Web プロセスと別の更新ワーカーを起動する。既存システムへの影響なし。
