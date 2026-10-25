## Why
詳細検索の語句欄と情報源一覧が高さを取り、他の入力欄と揃わない。1行の語句入力と閉じた状態でコンパクトな情報源選択にする。
## What Changes
- 追加・除外語句を1行のカンマ区切り入力へ変更。
- 情報源をチェック項目付きプルダウンに変更し複数選択を維持。
- 既存の改行区切りURL・検索条件・JavaScript無効時の操作を維持。
## Capabilities
### New Capabilities
### Modified Capabilities
- `reader-productivity`: 詳細検索の入力と情報源選択。
## Impact
reader search parser、テンプレート、CSS、テストと操作文書。依存追加・DB移行なし。
