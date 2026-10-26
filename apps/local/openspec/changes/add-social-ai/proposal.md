## Why

Go / Electron 版を元版のフル機能移植へ進める。次の縦断機能としてSNS収集・分析とAI接続・出典付き調査補助を実装し、元版の安全性・予算・履歴を保つ。

## What Changes

- Mastodonタグ/アカウント、Blueskyキーワードを購読として登録し、公開投稿・反応・関連タグ・直近30収集履歴を保存。
- OpenRouter / OrcaRouter の個別設定、上限価格・UTC共有予算、出典付き話題抽出、自動解析、プロバイダ固定の永続ジョブ。
- Ollamaローカル/クラウドの調査補助。案件の公開区分、選択根拠の正確な入力プレビューと承認、モデルdigest確認、固定引用と人のレビュー版。
- schema2/backup2。既存schema1/backup1から移行。設定exportに秘密情報を含めず、復元後AIは無効・予約は再送しない。
- フル移植の残作業を依存順と元仕様への対応付きで管理する。

## Capabilities

### New Capabilities
- `social-collection`: SNS購読、定期/手動収集、順位・タグ・履歴、429待機。
- `ai-processing`: 接続設定、予算・永続ジョブ、話題抽出、Ollama調査補助と送信保護。

### Modified Capabilities
- `local-data`: 新しいデータと安全な復元・設定エクスポートの追加（ADDED requirements）。

## Impact

Goコレクター・DB・RPC、Electron許可リスト、既存5機能内のUI、バックアップ形式、検証。元版DBや秘密情報は読み込まない。有料生成・実モデルの受入は資格情報を作成/転用せず模擬HTTPで検証する。
