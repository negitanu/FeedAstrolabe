# 依存・Dockerfile統合と容量削減（2026-10-19）

## 変更

- 5つの依存ファイルを `requirements.txt` 一つへ統合しました。29パッケージの固定バージョンは変更せず、重複指定を除去しました。
- 既存の `pyproject.toml` に標準のdependency groupsを追加し、`app`、`renderer`、`test` の導入対象を選べるようにしました。バージョン指定はrequirements.txtだけにあります。全開発依存は `pip install -r requirements.txt`、用途別はpip 25.1以上で `pip install -c requirements.txt --group app` などで導入します。
- 2つのDockerfileを単一の `Dockerfile` へ統合しました。共通runtimeからapp／rendererを構築し、既定targetはappです。Composeのweb／worker／observerはapp、rendererはrenderer targetを選択します。
- appにはブラウザー・テスト依存を含めません。rendererは実装が使用するheadless shellを `--only-shell chromium` で導入し、フルChromiumを省きます。必要なOSライブラリー・フォント・FFmpegは保持します。
- bytecodeの事前生成を省き、pip／APTのキャッシュを残しません。アプリソースは依存導入後にコピーし、ソース修正時に依存層を再利用できます。ビルドコンテキストは依存定義とアプリソースだけを許可します。
- README・観測の導入手順・CIテンプレートを更新しました。過去の検証記録にある旧ファイル名には統合済みの注記を追加しました。

## 容量の実測

Docker Engine 29.8.2／Compose 5.6.0、Linux arm64で比較しました。変更前後とも同じdigestで固定したPython 3.14 slimを使用しています。値は `docker image inspect` のSizeで、圧縮配布量やDocker全体の共有層を考慮したディスク使用量とは異なります。

- app：248,264,500 → 235,036,314 bytes（236.8 → 224.1 MiB）、5.33%削減。
- renderer：1,914,317,096 → 1,295,685,794 bytes（1825.6 → 1235.7 MiB）、32.32%削減。

比較元は `feedastrolabe-compose-verify:local` と `feedastrolabe-compose-observer-verify-renderer:local`、比較先は `feedastrolabe-slim-observer-verify:local` と `feedastrolabe-slim-observer-verify-renderer:local` です。比較元のタグは上書きしていません。

## 検証

- 旧固定ファイルの和集合と新requirements.txtを照合し、全29依存のバージョン一致を確認しました。`pip install --dry-run -c requirements.txt --group test` も成功しました。
- 実イメージのimportlib.metadataを照合し、appは従来の実行依存20個のみ、rendererはそれにブラウザー依存4個を加えた24個のみであることを確認しました（pip自体を除く）。両方でpytestなどのテスト依存はなく、appにはPlaywrightもありません。両方の `pip check` が成功しました。
- rendererには `chromium_headless_shell-1243` と `ffmpeg-1011` があり、フルChromiumのディレクトリーはありません。実ブラウザーの動作は後述の受入検証で確認しました。
- `scripts/verify_container.py --project feedastrolabe-slim-app-verify` 成功。非root・read-only、実HTTP APIとキー失効、bundle backup／restore、Web／worker再作成後の既読・スター保持を確認しました。
- `scripts/verify_observer.py --project feedastrolabe-slim-observer-verify` 成功。実JavaScript描画、text／Markdown／PDF解析のIPC、baseline／変更／無変化／復帰イベント、API・調査・根拠・運用機能、全サービス再作成後の状態保持を確認しました。ネットワークなし・DBなし・非root・リソース制限も維持しています。
- Composeの役割別target選択テストを追加しました。`PLAYWRIGHT_BROWSERS_PATH=/private/tmp/feedastrolabe-compose-playwright FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q --tb=short` は373テスト成功、スキップなしでした。
- OpenSpec全25項目strict、git diff --check、追跡対象と新規候補の秘密情報パターン検査、Gitleaksのscripts／docs検査に成功しました。

受入検証では専用のイメージ・プロジェクト・ボリュームを使用し、Tunnelとホストポートを有効にせず、終了時に検証コンテナとネットワークを削除しました。検証ボリュームは受入スクリプトの仕様どおり保持しています。本番サービスの再起動や公開Tunnelの変更は行っていません。

導入方式の根拠：[pip dependency groups](https://pip.pypa.io/en/stable/cli/pip_install/)、[PEP 735](https://peps.python.org/pep-0735/)、[Playwright headless shell](https://playwright.dev/python/docs/browsers)。
