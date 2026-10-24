# 詳細パネルの高さ制限（2026-10-24）

OpenSpec: `constrain-detail-to-reader`。

詳細パネル上端をview-heading上端・共通ナビ下端・パンくず下端の最大値に設定する。scroll/resize、visualViewport、ResizeObserverで追従し、height/max-heightを残りの画面高へ明示的に制限。min-height:0により画像を含む長い本文でも伸びない。共通ナビより低いz-indexを使用する。既存の一覧幅・表示順序・内部スクロールを維持。

検証:
- 実Chromiumで `tests/test_article_hero.py tests/test_reader_navigation.py`: **38 passed**。
- 画像ありの上下端チェック追加後 `tests/test_article_hero.py`: **15 passed**。
- PC1280px/mobile390px、画像あり/なし、直接詳細URL、scroll/resize、一覧幅保持、詳細表示中の設定ナビクリック、閉じる・前後移動を確認。
- 長い画像で自動高さが伸びる回帰を検出し、明示height/max-heightで修正して再検証。
- `/tmp/feedastrolabe-detail-bounds-1280.png` と `/tmp/feedastrolabe-content-order-1280-True.png` でヘッダー非干渉を目視確認。
- OpenSpec全件strict: **46 passed**。pip check成功。git diff --check成功。

DB移行・依存変更なし。外部Cloudflare認証は今回の変更では未検証。

稼働反映: Docker Hubのタグ/digest照会がTLS timeoutになったため、既存ローカルappイメージに更新ソースをCOPYしてネットワーク不要で再構築。非rootなど元イメージの設定と依存を維持。`docker compose up -d --no-build --no-deps --wait web worker observer`で反映し全対象healthy。rendererはUIに関係しないため既存のまま。実HTTPでhealthと一覧が200、更新された高さ制限CSS・位置計算JSの配信を確認。通常のDockerfile/compose設定には変更なし。
