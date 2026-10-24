## Why
フォルダーの順序を直接操作できず、暗い環境での配色にも対応していない。重複するラベルと説明が操作の優先順位を隠している。

## What Changes
- マウス・タッチによるフォルダーのドラッグ並べ替えと既存のキーボード操作を併設する。
- ライト・ダーク・システム連動を全画面に提供する。
- 配色と画面部品を整理し、装飾ラベルと重複説明を削減する。
- 操作・配色・既存機能の回帰検証後にコンテナを再構築する。

## Capabilities
### New Capabilities
- `direct-folder-ordering`: ドラッグ操作による永続的なフォルダー並べ替え。
- `adaptive-appearance`: システム連動を含む全画面のテーマ。
- `quiet-interface`: 共通レイアウトと簡潔なラベル。

### Modified Capabilities

## Impact
Flask settings routes, shared Jinja templates, CSS modules, progressive JavaScript, browser regression tests and documentation. Existing folder ordering schema and data are retained.
