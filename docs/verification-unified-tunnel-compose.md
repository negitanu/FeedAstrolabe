# 単一ComposeとTunnel標準化（2026-10-19）

以下は統合時の検証記録です。Tunnel認証は後続の `tunnel-token-dotenv` 変更で `.env` の `TUNNEL_TOKEN` 方式へ移行しました。さらに `minimal-tunnel-settings` でAccess検証をCloudflare側に委ねる方式を標準とし、Accessのローカル3設定は任意になりました。現在の手順は[公開手順](deployment.md)を参照してください。

## 変更

- 基本設定・Cloudflare・localhost公開・観測・X・Ollama cloud・通知に分かれていた7ファイルを削除し、ルートの `compose.yml` 一つへ統合しました。
- `docker compose up --build -d --wait` の既定対象はweb、worker、observer、renderer、tunnelの5サービスです。追加ファイルやprofileを必要としません。
- WebのCloudflare Access設定は必須。Tunnel tokenはtunnelだけにマウントし、host portは全サービスで非公開です。readerは明示的なbridge、rendererはnetwork_mode none・IPCソケットだけを共有し、既存のresource／non-root／read-only／capabilities制限を維持します。
- プロジェクト名feedastrolabe、reader-data／renderer-ipcのキーを保持し、既存のnamed volumeを再利用します。独自のプロジェクト名で運用していた場合は引き続き同じ名前を指定します。
- 任意連携は `.env` のコンテナ内ファイルパスで指定します。private volumeのアプリUID/GID10001・0600ファイルを使い、空欄なら追加の資格情報ファイルを要求しません。旧host secretからの移行、所有者を保つ標準入力での配置方法、シェル環境変数の優先順位も説明書へ記載しました。
- コンテナ検証は統合Composeを使い、認証のlocal設定とTunnel無効化を検証中の一時ファイルだけへ置きます。運用者の.env／資格情報パスを使わず、専用イメージ・*-verifyプロジェクト・ボリュームで実行します。host portは検証でも公開しません。
- 秘密情報のworktree検査が削除済みtrackedファイルを読み込んで失敗しないようにし、削除した候補は検査対象から除外します。index／historyの検査は維持します。

## 検証

- Compose CLI v5.6.0で `.env.example` を使う `docker compose config --quiet` が成功。
- 新規10テストで、既定のファイル探索、5サービス、Access必須設定、ポート非公開、bridge／renderer隔離、volume名、任意連携の未設定／設定、検証用の設定分離・後片付け、本番project名拒否、埋め込み検証コードの構文を確認しました。
- 全回帰テストは実ブラウザー有効で372テスト成功、スキップなし。最初の実行ではmacOS側のheadless shellが欠けていたため、一時キャッシュへ公式ブラウザーを取得し、`PLAYWRIGHT_BROWSERS_PATH=/private/tmp/feedastrolabe-compose-playwright FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q --tb=short` で再実行しました。
- `scripts/verify_container.py --project feedastrolabe-compose-verify` 成功。非root・read-only、実HTTP APIと失効、bundle backup／restore、Web／worker再作成後の既読・スター・案件・メモの保持を確認しました。
- `scripts/verify_observer.py --project feedastrolabe-compose-observer-verify` 成功。実Chromiumとtext／Markdown／PDF解析のIPC、rendererのネットワーク禁止・DBなし、baseline／変更／無変化／復帰イベント、実API、調査・根拠・運用機能、全サービス再作成後の状態保持を確認しました。
- 両検証ともTunnelは起動せず、ホストポートも公開せず、終了時に検証コンテナとネットワークを停止・削除しました。検証用ボリュームは受入スクリプトの仕様どおり保持しています。
- OpenSpec全24項目strict、git diff --check、追跡対象と新規候補の秘密情報パターン検査が成功。Gitleaksのscripts／docs検査でも検出はありませんでした。

README・運用ドキュメント・スクリプト・テストから、削除したCompose名の実行参照を除去しました。過去の検証記録にあるlocalhost接続先は当時の記録です。

稼働中の本番サービス、実資格情報、公開Tunnelは変更していません。実ホスト名・Access利用者・service tokenでの外部受入確認は [公開手順](deployment.md#公開後の受入確認) に従って実施してください。
