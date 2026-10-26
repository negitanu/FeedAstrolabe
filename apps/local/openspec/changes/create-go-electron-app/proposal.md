## Why

FeedAstrolabe の読む・収集・調査ワークフローを、サーバー配備不要のデスクトップアプリとして利用する。元版から独立したデータと Git 履歴を持つ Go / Electron 実装を作る。

## What Changes

- Go / SQLite の購読・記事・フォルダー・検索・履歴・既読・スター・定期収集。
- 日本語 Electron UI、スクロール追加、詳細パネル、テーマ、D&D、幅・開閉の保存。
- RSS/Atom 発見・プレビュー、OPML 入出力、購読停止・再開。
- 調査案件、版管理メモ、記事関連付け、取得時点の根拠、Markdownレポート。
- 設定JSON、完全バックアップJSON、復元、Electronパッケージング。
- 元版の高度な外部連携（SNS、JSページ観測、AI、脅威/ネットワーク情報、対象グラフ、通知、公開API）との未移植差分を明記。初版はローカルのリーダーと調査の実用経路を完成させる。

## Capabilities

### New Capabilities
- `desktop-runtime`: Electron 隔離、Go 子プロセス、認証、終了と配布。
- `reader-library`: フィード収集、購読整理、検索・履歴・状態、OPML。
- `research-workspace`: 調査案件・メモ版・根拠・レポート。
- `local-data`: 設定、バックアップ、永続化と復元。

### Modified Capabilities

なし（新規リポジトリ）。

## Impact

新規 Go モジュール、SQLite driver、Electron、Playwright による検証。元版のコード・DB・設定は変更しない。バックアップ形式は本アプリ専用で元版SQLiteとは互換ではない。
