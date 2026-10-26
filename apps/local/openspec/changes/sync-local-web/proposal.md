## Why

Web と Go / Electron local のライブラリが独立しており、端末間で閲覧・収集を継続できない。local の未移植機能も今回の変更で移植し、同期なしでも全機能を利用する。

## What Changes

- バージョン付きの双方向同期。購読、記事、既読、スター、収集設定・結果を対応付け、オフライン更新と再送を保持する。
- 設定から接続・同期・停止を行い、同期停止後も独立運用を継続する。
- 外部認証は Cloudflared / Entra ID に委譲し、同期専用のアカウント・APIキーを要求しない。既存公開APIとローカルIPCの保護は維持する。
- local に不足する調査・根拠・分類・観測・triage・対象関係・専門情報・通知・運用・公開APIを Go で移植する。Python基盤同梱案は採用しない。

## Capabilities

### New Capabilities
- `library-sync`: 永続変更履歴と再送可能な双方向同期。
- `native-feature-parity`: Web版の業務機能をGo / Electronで独立実行。

### Modified Capabilities

なし。既存のWeb利用・公開APIの契約を維持する。

## Impact

Web の同期モジュール・DB初期化・API、local のDB・RPC・Electron通信・設定・業務機能、両側のテストと文書。実データ・秘密情報は扱わない。
