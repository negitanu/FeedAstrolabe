# 第二段階の検証記録

検証日: 2026-10-08

## 実装と検証済み

- Python テスト: 73 件成功。DB マイグレーション、設定と収集スケジュール、API キーの発行・失効・期限・権限・レート制限、API ページング、OPML、Cloudflare Access JWT の検証を含む。
- OpenSpec: `openspec validate --all --strict --no-interactive` 成功（仕様 3 件、変更 2 件）。
- 依存関係: `pip check` 成功。
- Docker: Web/worker のビルド・起動、非 root 実行、実 HTTP API、キー失効、バックアップ・復元、再作成後の永続性を確認。
- 既存データ移行: 1 購読と既存 23 記事の既読・スター状態が一致。移行前のバックアップを保存。
- UI: 設定画面を通常幅と幅 390px で確認。コンテナの設定画面と OpenAPI へのリンクを確認。
- Cloudflare: Compose 構成の検証、cloudflared イメージの取得、署名・issuer・audience・期限・Host の拒否と認証基盤障害時の拒否をテスト。

ローカル起動先: http://127.0.0.1:5010

## 外部接続の未完了項目

実際の Cloudflare ドメイン、Access アプリケーション、許可ユーザー、Tunnel の設定は未提供。実 Tunnel 接続と外部からの許可・拒否確認は未実施。OpenSpec のタスク 4.3 を未完了として残す。

設定と受入確認は [デプロイ手順](deployment.md)、API は [API 手順](api.md) を参照。
