# Reader / platform / provider refresh 検証記録

実施日: 2026-10-24。対象: OpenSpec `reader-platform-provider-refresh`、アプリ0.15.0、DB schema 18。

## 自動テスト

Python 3.15.1の既定`.venv`で、Playwrightブラウザーテストを有効にした全件実行: **623 passed in 172.24s**。

```sh
PLAYWRIGHT_BROWSERS_PATH=/tmp/feedastrolabe-reader-browsers FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q
.venv/bin/python -m pip check
openspec validate reader-platform-provider-refresh --strict
git diff --check
```

依存関係チェック、OpenSpec strict、差分の空白検査は成功。DB v17 fixtureからの移行、既存データ保持、停止・再開、待機中自動処理の停止、フィード順序・所属・競合・取消、継続取得の改ざん・条件変更・並行挿入／削除、全条件の既読化を検証した。

PC／モバイル、light／dark／system、マウス／タッチ／キーボードで、スクロール追加・通信失敗からの再試行、本文・前後移動・履歴、読み込み済み深部記事の状態変更、フォルダー／フィードD&D、閉じたフォルダーへの移動、幅変更、右クリック編集を確認。AI設定切替と設定ダウンロードもブラウザーで確認した。

1万記事・500フィードのfixtureでは、初期応答0.068秒、382,413 bytes、30カード。全1万記事を重複なく取得した。これはローカルfixtureの測定値であり、本番遅延の保証値ではない。30件は内部取得バッチで、表示件数の上限ではない。

OpenRouter／OrcaRouterはmock契約テストで、正常・不正応答、構造化出力、費用参照、費用不明時の予約維持、生成POSTを再送しないこと、接続設定の独立保持、予約ジョブの接続先固定、共通日次予算を確認した。有料の実生成は行っていない。

設定出力ではCSRF、形式・表示設定の検証、読み取りスナップショット、添付レスポンス、秘密値・秘密ファイル・本文の除外を確認。形式は[`settings-export-v1.schema.json`](../feedastrolabe/static/settings-export-v1.schema.json)に定義する。

## 実行基盤

Python 3.15.1へ更新し、直接・間接・開発依存を再解決して29パッケージのconstraintsを固定した。最新安定版への更新にはMarkdown 3.11.2、Playwright 1.64.1、pluggy 1.7.0、pycparser 3.12、pyee 14.0.0、pypdf 6.21.2を含む。

ベースは公式`python:slim`、アプリ／renderer／cloudflaredは`latest`タグを使用。ビルド時にPython 3.15系を検査し、異なるminorへ更新された場合は停止する。今回の環境では`dhi.io/python:3.15`、`3.15-debian13`、`3.15-debian13-dev`および`dhi.io/cloudflared:latest`を解決できなかったため、公式イメージへfallbackした。DHI全般の利用可否を断定するものではない。

arm64のアプリ／rendererビルドと起動を確認。非root UID10001、read-only、rendererのnetwork noneを保持し、隔離コンテナ内でChromium 156.0.8078.4を起動した。amd64のアプリも別途ビルド・起動し、Python 3.15.1、cryptography 50.0.2、SQLite 3.46.1を確認した。amd64のChromium実行は未実施。

配備したイメージ識別子:

- app: `sha256:5ff39e1e2fcf042fc7c0de64774671f551ab3bbc1984780f53000c320c837391`
- renderer: `sha256:e901295c7e0609ac79ebdd2dea1e6587a28771c2b556debf82b4c1f1f6c1c92f`
- cloudflared: `sha256:faa8e0a1475f137c910be6025f43c8e4092fdd35461b31e19fd1390657a1ff39`

## 稼働環境への反映

移行前のDB・証跡バンドルをprivate data volume内の`/data/backups/before-platform-refresh-20261024-final`へ取得。旧イメージも保持した。worker／observer／webを停止して混在を避け、最新トンネルのpullとアプリのbuild後、`docker compose up -d --wait --wait-timeout 180`で再起動した。

全5サービスrunning、web／renderer healthy、`/healthz`成功、稼働Python 3.15.1とpip check成功。DBは17から18へ移行し、外部キー検査に問題なし。41フィードの所属・購読状態、6,599既存記事の既読／スター状態、フォルダー順序が移行前バンドルと一致した。

実HTTPで全11フォルダー×all／unread／starredの33一覧をDBの正しい記事順序と照合。6,599記事の継続取得を220バッチで完走し、重複なし・全件一致。全41フィードの編集fragment、旧設定URLの転送、両AI設定画面、3テーマ、配信資産のSHA-256一致も確認した。

CSRF付き設定出力を実HTTPで取得し、schema 18、41購読、attachment／no-store、環境の認証キー除外を確認。既存記事や購読を変更する操作、外部AI生成は稼働データで実行していない。

## 追補: 集める画面の重複入口削除（2026-10-24）

上段の情報源ショートカットを削除し、登録入口を作業別グループへ統一した。上段だけにあったMastodonアカウント購読は作業別グループへ移し、全4種類の登録リンクを各1つに保つ。PC／モバイルのRSS登録・SNS登録／収集／編集を含むナビゲーション25テスト成功（13.73秒）。OpenSpec全43項目のstrict検証と差分検査も成功した。

## 追補: 全ハブの重複導線削除（2026-10-24）

「集める・調べる・まとめる・設定」から、上段の重複ショートカット枠と下部見出しへのページ内リンク列を削除した。機能一覧、全画面共通ナビゲーション、設定エクスポートなど固有の操作は維持する。設定検索の表示も実際の対象である案件・ウォッチへ修正した。

関連ナビゲーション25テスト成功（13.91秒）、OpenSpec全43項目strict成功。継続するUI/UX・実装・テスト・Git／データ管理の指示をルートの `AGENT.md` に記録した。

## 追補: ハブと1行記事一覧のレイアウト修正（2026-10-24）

4ハブの本文から上部ナビゲーションと重複するページ名のh1を削除し、mainのアクセシブル名と現在位置の表示を維持した。機能一覧はPCで2列、広い設定画面は3列、モバイルは1列へ揃え、見出し削除後の余白を整理した。1行記事一覧では情報源名の列を最大140pxへ制限し、長い名前を省略して記事タイトルの幅を確保。ページング撤去後の末尾行の罫線・角丸も修正した。

ナビゲーション・表示回帰53テスト成功（46.64秒）。375／900／1280pxの全ハブで列の整列と横はみ出しなしを検証し、PC・モバイルのスクリーンショットを確認。記事表示は320／768／1024／1920pxを検証した。OpenSpec全43項目strictと差分検査も成功。


## コミット分割と既存リモート修正の統合（2026-10-24）

変更をGit管理、実行基盤、入力安全性、SNS／AIバックエンド、記事・購読、画面共通化、設定出力、文書の8単位へ分割した。合計ツリーは分割前の検証済みツリーと完全一致する。中間ツリーは実行基盤20件、XML安全性23件、DB／プロバイダ等6項目、記事・SNS統合168件、画面等48件、設定出力21件と文書の検証を行った。

未取り込みだった既存リモート修正を別の統合コミットで反映。本文に依存しない代替GUID、POSTフォームを優先する一括既読条件、情報源の更新日時、条件外の本文404、検索条件を保持するフィード移動を維持した。既存のキーボード操作と任意のPOST既読化は現在の連続読み込みへ統合し、旧UIの重複ボタンや別のreader.jsは戻していない。通常の本文GETは引き続き状態を変更しない。

最終の全回帰は **635 passed in 183.61s**（ブラウザーテスト有効）。OpenSpec全43項目strict、pip check、差分検査が成功。秘密情報検査は履歴を含む1,659対象と、ステージ済み517対象で成功した。過去メッセージの日本語化はファイルツリー・著者・日時を保持し、復旧用bundleと明示的leaseによるpushを使用する。
