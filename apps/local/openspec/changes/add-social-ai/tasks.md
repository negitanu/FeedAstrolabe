## 1. 仕様・永続化

- [x] 1.1 元版SNS/AI契約と公式APIを確認しOpenSpec strict検証、フル移植計画を追加。
- [x] 1.2 schema2の整合移行、案件分類、SNS/AIテーブルとbackup1/2互換・復元後無効化。

## 2. SNS

- [x] 2.1 Mastodonタグ/アカウントとBluesky検索の登録・公開APIアダプター。
- [x] 2.2 定期/手動収集、重複/順位/タグ/履歴、失敗保持、サービス単位429待機。
- [x] 2.3 集める/情報源のSNS設定と調査結果UI、記事一覧との統合。

## 3. AI

- [x] 3.1 プロバイダ別設定・秘密情報分離・共有予算予約・永続ジョブと再送防止。
- [x] 3.2 OpenRouter/OrcaRouter話題抽出、入力制限・出典検証・自動解析。
- [x] 3.3 Ollama local/cloud、選択根拠preview/承認・分類/版再検証・引用・レビュー。
- [x] 3.4 接続設定、SNS解析、案件補助・履歴・レビューのElectron UI。

## 4. 検証

- [x] 4.1 模擬HTTP/DBテスト：SNS失敗と429、秘密/分類、予算/重複/再起動、provider契約、Ollama、復元。
- [x] 4.2 Go race/vet、Electron実操作と既存回帰、配布.appビルド。
- [x] 4.3 本仕様・README・操作・差分・検証記録を整合しstrict・秘密情報・差分確認。
