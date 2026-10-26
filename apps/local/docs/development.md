# 設計と開発

## 構成

- `cmd/feedastrolabe`：起動引数、データ先、トークン、HTTP、親プロセスのEOFとsignal処理。
- `internal/app/store.go`：SQLite schema1、購読・状態・条件検索・並び順。
- `internal/app/fetch.go`：安全なHTTP、RSS / Atom、発見と収集。
- `internal/app/research.go`：案件、メモ版、記事関連付け、根拠、Markdown。
- `internal/app/opml.go` / `backup.go`：データ入出力と原子的な復元。
- `internal/app/server.go`：認証・JSON RPCルーティング。
- `desktop`：Go子プロセス、制限付きIPC、ネイティブ保存・読込ダイアログ。
- `ui`：フレームワーク不要の同梱HTML / CSS / JS。ユーザー・記事由来の文字列はDOMのtextContentに設定。

画面が別のWebサービスへ接続することはありません。収集はGoだけが行います。秘密情報や元版のコード・DBをコピーせず、新規に実装しています。

## OpenSpec

実装開始前に `git init`、`openspec init`、`openspec new change create-go-electron-app` を実行しました。proposal → design / specs → tasks の順に作成し、strict 検証の成功後に実装しています。

```sh
openspec status --change create-go-electron-app
openspec validate --all --strict --no-interactive
```

リポジトリ内にCodex用OpenSpecスキルを保持します。初期化時のグローバル `~/.codex/prompts/` 書込みは権限制限のため行っていません。OpenSpec CLIとリポジトリ内スキルで実行でき、グローバル設定の変更は不要です。

新しい移植機能・仕様変更は別changeを作り、テスト・操作文書・本仕様・機能差を更新します。初版の契約は「元版の完全互換」ではなく `docs/parity.md` の実装済み範囲です。

## 依存と配布

Goはmodernc SQLiteによりCGO不要の単体バイナリです。Electronのnative addonは使いません。`scripts/build.cjs` はGoをビルドし、Electron builderがresources/binへ同梱します。現在のOS / CPU向けに作るため、配布先と一致する環境で実行してください。

```sh
npm run setup
npm test
npm run test:go
npm run test:desktop
go vet ./...
go mod verify
npm audit
openspec validate --all --strict --no-interactive
npm run pack
python3 scripts/check-secrets.py
```

E2Eは一時ディレクトリに専用ライブラリとElectron profileを作り、終了時に削除します。外部APIや実データを必要としません。ネットワーク取得はGoテストで制御したHTTP応答と公開IPポリシーを検証します。スクリーンショットはGit除外の `test-results/` に保存します。

実ネットワークのスモークテストは任意に実行します。公式Goブログへの公開HTTP取得を行い、一時ライブラリだけを使用します。

```sh
FEEDASTROLABE_LOCAL_TLS12=1 npm run test:live
```

Go依存のライセンス表示は `docs/THIRD_PARTY_NOTICES.md` に保存し、配布アプリのresourcesにも含めます。Electron / Chromium側のライセンスはElectronの配布物に同梱されます。

## SNS・AI（0.2.0）

`social.go` / `service_http.go` はSNS定義・固定公開API・順位/履歴・サービス待機を担当します。`ai.go` は設定版・正確な入力・プレビュー承認・共有予約・1件ずつの永続worker・人のレビューを扱い、`ai_http.go` はprovider別の要求・応答検証です。資格情報はGoだけが取得し、rendererへ返しません。

`social_ai_schema.go` のschema2移行は、schema1の整合JSONをmigration-backupsへ保存してから行います。backup2は旧8テーブルを維持して追加テーブルを持ち、backup1は空の追加領域で受け入れます。現在設定とジョブのsnapshotを分け、復元は設定を無効化・未完了jobを失敗化します。

Electron E2Eは新たにSNS/AIを含みます。11434番が利用中なら模擬Ollamaのテストをskipし、既存の利用者ランタイムへは接続しません。新規テスト用の小さなHTTPサーバーだけを使い、モデルのpullや有料AI呼出しはありません。
