# 第九段階の検証（2026-10-08）

OpenSpec change: `phase-nine-entities-relations`。対象の正規化・出典付き言及／候補確認・手動訂正、引用付き関係の不変版、監査、取り消せる手動統合、案件内のグラフ／タイムラインを実装。schema v7→v8。

- `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：最終版206件成功、33.18秒。`tests/test_entities.py`8テストでIPv6の異なる元表記、IDNA2008 non-transitionalによるsharp-s区別、CVE可変連番、ASN境界、malformed識別子、同名組織を自動統合しないこと、別名、固定位置／ハッシュ、訂正・却下の再抽出保持、409、readキー／CSRF／巨大ID、他案件引用・不正期間の原子的拒否、確信度の旧版、統合／取消監査・cycle、並行再処理、200対象のgraph上限、500言及上限と省略、v7移行／v7・v8 bundle復元、意味的に壊れた固定位置のbackup拒否を確認。追加の画面回帰で空の任意フィルター・未指定案件リンク・日本語表示と内部select値・手動登録を確認。画面修正後も実4サービスを再作成してhealthy、実ライブラリの未指定案件から対象詳細への遷移をCUAで確認。
- `scripts/verify_entities.py --serve-port 5012`：一時ライブラリの実HTTPでIPv6の1対象・2原文、引用付き2ドメイン関係、同時編集409、手動組織言及の訂正保持、merge／undo／remerge、scope graph、v8 bundle復元を確認。CUAで更新済み日本語の対象詳細・関係一覧を確認し、390px幅の対象詳細はscrollWidth=390、script要素0。
- `scripts/verify_observer.py --project feedastrolabe-entity-final-verify`：新しいidna依存を含む4コンテナを構築。Linux text／Markdown／PDFの実IPC、実Chromium JS観測、隔離renderer、既存triageの状態保持を回帰検証。検証専用DBの対象・原言及・統合／取消監査・引用判断の版・再抽出冪等性が4サービスの強制再作成後も保持。サービスを停止し独立volume保持。利用者DBにfixtureを追加しない。
- writer停止後 `/data/pre-phase-nine/` に検証済みschema7 bundle（DB600）を作成し、4サービスをschema8へ更新／再作成、すべてhealthy。移行前の全購読ID／URL・記事ID／feed／GUID／既読／スター、案件／メモ／タグ／引用／根拠／条件版／通知／重複グループをEXCEPT比較し不一致0、FK正常。実ライブラリは購読1件／記事33件／案件0件。新着記事の増加は旧記事の保持と区別して検証。
- OpenAPI 0.9の全ローカル参照と83ルート／メソッドを実装に照合。pip check成功、OpenSpec strictは同期前17項目成功。idna 3.20は公式PyPI／Unicode資料でIDNA2008、non-transitional方式、BSD-3-Clause、Python>=3.9を確認し全lockへ固定。

抽出は候補で、識別子の存在や所有者・攻撃者の同一性を認定しません。確信度と記録者は人の判断／自己申告です。graphの省略とfamily上限は明示し、一覧から辿れます。根拠の参照を保持するため言及・関係・監査のある本文はretentionで削除しません。共有ライブラリの案件分類は権限分離ではありません。

Cloudflare実接続、X実資格情報、GitHub CI有効化は引き続き後段。外部の実照会は第九段階には含めず、fixture確認と区別します。秘密情報検査・push・仕様同期結果は完了後追記します。
