# 記事詳細の表示順・アイキャッチ（2026-10-24）

OpenSpec: `article-detail-content-order`。既存の `floating-article-detail` のフロート動作とタイトル元記事リンクは継続する。

## 表示

任意のアイキャッチ、タイトル、時刻、既読にして次へ・既読／未読・保存、横線、記事説明、横線、案件・タグ・根拠保存、前の記事・件数・次の記事の順。既読にして次へは上側のみ。

画像は元ページOGP/Twitter Cardを既存のfetch経由で取得し、同一オリジンの画像エンドポイントから配信する。本文応答は外部通信を待たない。幅480px、max-width100%。画像取得・デコード失敗時は空欄を残さない。SVG/HTMLを配信せず、公開アドレス検証・DNS固定・リダイレクト/時間/サイズ制限・既存CSPを維持。最大16件のメモリキャッシュで5分区切りに更新する。DB移行・追加依存なし。

## 成功した検証

- `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest tests/test_article_hero.py tests/test_reader_navigation.py tests/test_fetch.py -q --tb=short`: **63 passed**。
- 相対画像URL、Twitter Card、危険スキーム、SVG/HTML拒否、画像なし/取得失敗、キャッシュ、プライベートアドレス拒否、既存fetchのリダイレクト等を検証。
- PC1280px/light・モバイル390px/darkの画像あり/なし、幅制限、本文先行配置、既読操作の単一化、閉じる、前後移動を実Chromiumで検証。
- スクリーンショット `/tmp/feedastrolabe-content-order-390-False.png` を目視確認。
- `openspec validate --all --strict`: **45 passed**。
- `pip check`: No broken requirements found。`git diff --check` 成功。
- `docker compose up -d --build --wait web worker observer` 成功、依存rendererを含めhealthy。
- 稼働webコンテナ内の実HTTP: `/healthz` **200**。指定の「モビリティ領域」記事で説明が調査機能に先行することを確認。実OGP画像は **200 image/webp、45,966 bytes**。

## 未実施

全サイトのOGP互換性、外部Cloudflare認証、今回と無関係な有料AI呼び出しは未検証。画像がない／拒否されるサイトでは記事情報だけを表示する。
