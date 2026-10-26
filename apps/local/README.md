# FeedAstrolabe Local

FeedAstrolabe の **Go / Electron によるローカルデスクトップ版**です。RSS / Atom の収集と読書、調査案件・メモ・根拠の保存を、サーバー配備なしで利用できます。日本語 UI と SQLite のライブラリを持ち、元の Python 版とは独立して動きます。

現在の `0.1.0` は、初版の読書・調査に加えて SNS 収集と AI を実装しています。最終目標は元版のフル機能移植です。[移植計画](docs/full-port-plan.md) と [現在の機能差](docs/parity.md) で進捗を追跡しています。

## 起動

Go 1.27 系、Node.js 22.12 以上、npm を用意してください。検証環境は macOS / Apple Silicon、Go 1.27.3、Node.js 22.16.0、Electron 45.0.0 です。

```sh
cd apps/local
npm run setup
npm start
```

`setup` は lockfile に従って依存を導入し、Electron の実行バイナリを取得します。初回は npm、Go のモジュールミラー、Electron の配布先への接続が必要です。`npm start` は Go サービスをビルドしてから Electron を起動します。Python・Docker・Cloudflare・外部 AI は不要です。

### この開発環境のネットワーク互換性

検証環境では Go の TLS 1.3 接続がタイムアウトし、TLS 1.2 で接続できました。同じ現象が出る場合は、明示的に互換モードで起動してください。証明書・ホスト名・公開IPの検証は維持します。既定のTLS設定は変更していません。

```sh
FEEDASTROLABE_LOCAL_TLS12=1 npm start
```

## 操作

- **読む**：すべて・未読・スター・履歴、フォルダー／情報源ごとの記事表示。検索、詳細条件、並び替え、標準／1行／タイル、スクロール追加、選択記事の状態変更。「全て既読」は現在条件の未描画記事も対象です。
- **集める**：サイトの RSS / Atom を発見・プレビューして購読。OPML は追加前に重複を確認できます。Mastodon のタグ／アカウント、Bluesky 検索も登録できます。アプリ起動中は起動時・設定間隔・手動で更新します。
- **調べる**：案件と Markdown メモの版管理、記事の関連付け、取得時点の本文・URL・SHA-256 を持つ根拠を保存します。SNS の反応数・タグ・履歴、OpenRouter／OrcaRouter の話題抽出、明示承認付き Ollama 調査補助を利用できます。
- **まとめる**：案件のメモと根拠を、出典付き Markdown に書き出します。
- **設定**：ライト／ダーク／システム連動、更新間隔、表示、UTC／JST、AI接続と全接続共通の日次予算、設定 JSON、完全バックアップと復元、任意のWeb同期。

左のフォルダーは **名前で記事を表示し、矢印だけで開閉**します。右クリック／「⋯」から名前・移動先・停止／再開・削除を操作します。並べ替えは D&D またはメニューの上下移動、幅変更は境界のドラッグまたはフォーカス後の左右キーです。幅・開閉・順序は保存されます。

記事詳細を開くと既読と履歴を記録します。詳細の閉じる、Escape、一覧の空白部分で閉じられます。中クリックは元記事を既定ブラウザーで開き、既読にしません。検索には ⌘K / Ctrl+K を使えます。[詳しい操作](docs/usage.md) を参照してください。

## SNS・AI

「集める」で SNS を登録し、「調べる」で投稿の順位・関連タグ・履歴を表示します。AI は初期状態で無効、モデル指定なしです。「設定」→「AI接続」で接続先・モデル・費用上限を設定してください。OpenRouter / OrcaRouter のキーは各 `OPENROUTER_API_KEY` / `ORCAROUTER_API_KEY` を起動環境に設定します。キーを画面・チャット・Gitへ貼る必要はありません。`.env` の自動読込みは行いません。

Ollama は別途利用者が用意し、ローカルでは `127.0.0.1:11434`・クラウド無効化・モデルdigest一致を確認します。案件で根拠を選択し、送信本文をプレビューしてから承認します。クラウドは public 案件だけを対象とし、他の非公開案件に関連する根拠も拒否します。[設定・送信範囲・費用・制限](docs/social-ai.md) を参照してください。

実サービスでの有料生成・モデル品質は未検証です。自動テストは合成投稿と模擬HTTP、Electronはローカル模擬Ollamaを利用し、利用者のキー・資料は使用しません。

## データ

標準のライブラリは Electron の `userData/library` 以下の `library.sqlite3` です。macOS の既定では `~/Library/Application Support/FeedAstrolabe Local/library/` を使います。元版の `instance/` は開きません。

保存先を分ける場合は絶対パスを指定します。この場合 Electron のプロファイルも指定先内に作成します。

```sh
FEEDASTROLABE_LOCAL_DATA_DIR="$PWD/.data" npm start
```

「設定」→「完全バックアップ」で全データを保存・復元できます。復元前のデータは `library/backups/pre-restore-*.json` に自動保存します。設定 JSON と OPML は完全バックアップではありません。本アプリの JSON は元版 SQLite と互換ではありません。schema1 は整合バックアップ後に schema2 へ移行し、backup1/2 を復元できます。復元後は AI を無効化し、未完了ジョブを再送しません。

稼働中の SQLite ファイルだけをコピーせず、アプリ内バックアップを使ってください。バックアップは本文や調査メモを含むため、安全な場所に保管してください。[保存と安全性](docs/security.md) を参照してください。

## ビルドと検証

```sh
npm test
npm run test:go
npm run test:desktop
openspec validate --all --strict --no-interactive
npm run pack
```

`pack` は `dist/` に Go 同梱の `.app` を作ります。`npm run dist` は DMG / ZIP を生成します。署名なしで検証しており、公証・Windows / Linux の実機検証は未実施です。配布は対象 OS / CPU 上でビルドしてください。Go と Electron のアーキテクチャは一致させてください。

依存は `go.mod` / `go.sum` / `package-lock.json` に固定しています。仕様駆動の変更は `openspec/changes/create-go-electron-app/` と `openspec/changes/add-social-ai/`、現在の契約は `openspec/specs/`、手順は `.codex/skills/openspec-*/SKILL.md` にあります。[設計と開発](docs/development.md)、[初版検証](docs/verification.md)、[SNS・AI検証](docs/verification-social-ai.md) を参照してください。

## Web との同期（実装中の変更）

「設定」→「Web と同期」で接続先を保存し、「今すぐ同期」を実行します。購読・記事・既読・スター・収集状態を共有し、停止中も単独利用できます。Access認証は「接続先を開く」で行います。[同期の操作・競合・復旧](docs/library-sync.md)を参照してください。記事の安全なHTML表示、情報源別の収集間隔、設定/完全JSON v3も追加しています。

今回のOpenSpecはGoによる全機能移植を含みますが、観測・根拠添付/引用・triage・対象関係・専門情報・通知/公開APIなどは未完了です。Python同梱やWeb接続による代替をフル移植の完了とは扱っていません。進捗は [tasks](openspec/changes/sync-local-web/tasks.md) に記録しています。
