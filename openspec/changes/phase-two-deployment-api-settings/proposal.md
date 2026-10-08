## Why

第一段階のリーダーをコンテナで再現可能に運用し、Cloudflare Zero Trust を経由したアクセスに対応させる。さらに記事を他のツールから取得できる API と、通常運用に必要な設定・購読移行機能を追加する。

## What Changes

- 非 root コンテナ、Web/worker、永続ボリューム、healthcheck、ローカル検証用 Compose override。
- Cloudflare Tunnel の設定、origin の Access JWT 検証と公開運用手順。
- Bearer API キーによるフィード／記事取得・購読追加・閲覧状態変更 API、読み取り専用／書き込み権限、有効期限、失効、レート制限。
- ポーリング間隔、収集一時停止、失敗時のバックオフ、フィード別設定。
- 一覧件数と初期ビューの設定、OPML インポート／エクスポート。
- version 1 DB からデータを保持したマイグレーションとバックアップコマンド。
- 公開ドメインと Cloudflare 資格情報が未確定の間はローカル検証まで実行する。

## Capabilities

### New Capabilities

- `container-deployment`: 再現可能なコンテナ起動、永続化、復旧、Cloudflare Access の認証境界。
- `reader-api`: API キーと JSON API、検索、ページ送り、購読・状態操作。
- `reader-settings`: 更新頻度・一時停止・表示設定とワーカーへの反映。
- `subscription-transfer`: 安全な OPML の入出力と購読の移行。

### Modified Capabilities

- `article-reader`: ページ件数を設定可能とし、既定の 30 件表示を維持する。

既存の手動操作と既定の 15 分更新は維持する。

## Impact

SQLite schema version 2、Flask blueprint、JWT 検証用 PyJWT/cryptography、OPML 用 defusedxml、Docker/Compose を追加。外部公開には Cloudflare のチームドメイン・AUD・Tunnel token・Access policy が必要。
