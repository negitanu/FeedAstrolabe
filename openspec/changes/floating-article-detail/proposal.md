## Why
記事詳細を開くたびに一覧が縮み、元記事を開く操作も分散している。リスト位置を保持したまま本文と元記事へアクセスできるようにする。
## What Changes
- 中クリックで元記事を別タブに開く。
- 右側に重なる詳細パネルを表示し一覧幅を維持する。
- 詳細タイトルを別タブへの元記事リンクにし、元記事ボタンと上側の移動ナビを削除する。
## Capabilities
### New Capabilities
### Modified Capabilities
- `reader-interactions`: 元記事アクセスとフロート詳細。
## Impact
Jinja templates, reader JavaScript/CSS, browser tests and reader documentation. No DB or dependency changes.
