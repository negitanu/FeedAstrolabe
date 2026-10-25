## Why
記事詳細を読んでも未読のまま残り、別の既読操作が必要になっている。詳細の表示で既読を保存し、不要になった「既読にして次へ」を削除する。

## What Changes
- 詳細表示時のCSRF保護された閲覧POSTで既読も保存し、一覧・件数・詳細の操作を更新する。
- 旧「開いたら既読」設定に依存せず詳細を表示し、中クリックは状態を変更しない。
- 詳細の既読にして次へ／一覧へを削除し、通常の前後移動を残す。

## Capabilities
### New Capabilities
### Modified Capabilities
- `article-reader`: 詳細表示時の既読POST。
- `reader-productivity`: 履歴と既読の同時保存。
- `reader-interactions`: 詳細表示による既読と詳細操作の簡素化。

## Impact
Flaskの閲覧処理、reader templates/JavaScript、回帰テスト、READMEと操作文書。依存追加・DB移行なし。
