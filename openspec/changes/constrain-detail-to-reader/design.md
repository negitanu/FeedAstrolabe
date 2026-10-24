## Context
詳細はfixed top12px、z-index30で共通ヘッダー(z-index20)を覆っている。赤枠はview-heading上端から画面下までの記事欄。
## Goals / Non-Goals
Goals: 記事欄とヘッダーの境界を尊重し、本文の独立スクロールと一覧幅保持を継続。
Non-Goals: 横幅・記事内容順序・既読処理の変更。
## Decisions
view-heading上端、共通ナビ下端、パンくず下端の最大値をCSS変数へ反映しfixed topに利用する。window/visualViewportのscroll/resize、ResizeObserverでレイアウト変更に追従、requestAnimationFrameでまとめる。z-indexを共通ナビ未満にする。下端12pxを維持し、height/max-heightをviewport高さから上端と下余白を引いた値に明示する。gridの自動最小高さをmin-height:0で解除し、長い画像でも伸びずoverflow:autoとする。JSなしは上部UI高さ相当のfallbackを用いる。
## Risks / Trade-offs
狭い画面で利用可能な高さが小さい → 内部スクロールで閉じると本文を維持する。
