## Why
本文より先に調査機能があり、記事の説明へ到達しづらい。画像と記事情報を先に、調査操作と前後移動を後に配置する。
## What Changes
- 取得可能なOGP/Twitter画像を固定幅で最上部に表示する。
- タイトル、時刻、既読・保存操作、横線、説明、横線、調査・根拠保存、末尾ナビの順にする。
- 末尾の重複した既読にして次へを削除する。
## Capabilities
### New Capabilities
### Modified Capabilities
- `reader-interactions`: 記事詳細の表示順序と任意画像。
## Impact
記事テンプレート、CSS、画像読み込みJS、画像取得エンドポイント、テストと操作文書。DB移行・追加依存なし。
