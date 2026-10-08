# 第十段階の検証（2026-10-08）

OpenSpec change: `phase-ten-security-intelligence`。登録済み公開コネクターの予約・キャッシュ・cooldown・予算、独立したKEV／EPSS／CVEの不変根拠、製品の適用性判断と参照メタデータを実装。schema8→9。

- 最終 `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：215件成功、12.35秒。新しい9テストで初期停止／公開識別子許可／任意endpoint・認証値拒否、60秒間隔／UTCbudget更新、cache再利用と並行予約冪等性、16MiB容量制限と旧データ保持、独立したCNA／ADP CVSS版、名前だけのpossible、EPSS失敗時stale／欠損null、malformed・異なるCVE・unsupported schema拒否、固定根拠retention、quoted確認／他案件・stale editの原子的拒否／設定変更後の判断履歴、read/write／CSRF、PoCの非取得、private redirect拒否／429待機／安全なerror／認証ヘッダー不使用、3回retry上限、実v8 fixture→v9と両bundle復元を確認。
- `scripts/verify_security.py --live-public`：一時ライブラリだけで公開済みCVE-2021-44228を明示許可し各providerへ1GET。CISA公式ミラーcatalog2026.10.04、EPSS API1.0、CVE JSON5.1を実取得しcurrent・KEV掲載・EPSS提供を確認（2026-10-08 08:49 UTC）。個別識別子だけを送信し、利用者DBの設定や調査資料を送信しない。カタログ日は取得日時と区別。外部データのfixture検証とは別の結果。
- `scripts/verify_security.py --serve-port 5013`：実HTTPでread拒否、許可なし予約拒否、3独立根拠、名前のpossible、固定引用による確認、409、PoCリンクのメタデータ、503時に旧score=0.95とstale、bundle復元、日本語UIを確認。CUAでカードと案件のウォッチ／連携設定を表示し390px幅で両方scrollWidth=390、script要素0。通常viewportへ戻す。
- `scripts/verify_observer.py --project feedastrolabe-security-verify`：独立4サービスで実Linux添付IPC／Chromium JS、renderer隔離、対象／triageを回帰確認。検証専用DBの公開観測3件・固定根拠・quoted判断・PoCメタデータ・503待機・旧スコアが強制再作成後も保持、schema9・FK正常。サービス停止、独立volume保持。
- 実writer停止後 `/data/pre-phase-ten/` に検証済みschema8 private bundle（DB600）を保存。4サービスをschema9へ更新／再作成しhealthy。全旧購読ID／URL、記事ID／feed／GUID／既読／スター、案件／メモ／タグ／根拠／引用／整理／対象・原言及／関係／監査をEXCEPT比較して不一致0、FK正常。移行時購読1／記事35／案件0。自動増分cursorと通常新着増加は不変記録の比較から区別。全連携enabled=0、利用者DBへfixture／公開照会を追加しない。
- OpenAPI0.10は全ローカル参照と98ルート／メソッドを実装に照合。追加依存なし、pip check正常。OpenSpec strict同期前17項目成功。既存の秘密情報運用文書を保持し、新機能の手順を別文書へ追加。

EPSSは30日予測、CVSSは出典ごとの深刻度、KEVは取得版の掲載です。未掲載・欠損・古い値を安全と表示しません。モデル版不明は不明のまま表示。バージョン制約の自動解析・資産スキャンは提供せず、名前一致はpossible、確認済みには引用が必要です。累計ジョブ10000・16MiB cache等の上限に達した際の履歴purgeは後段です。共有ライブラリの案件分類はアクセス分離ではありません。

Cloudflare実接続、X実資格情報、GitHub CI有効化は従来の延期を保持。秘密情報検査・push・仕様同期結果は完了後追記します。

実装 commit `c5fdad0` をGitHub mainへpushしリモート一致を確認。候補631件、Git履歴／全indexのGitleaksで検出なし。限定fingerprintを維持。正規仕様3要件・6シナリオを同期し `openspec/changes/archive/2026-10-08-phase-ten-security-intelligence/` にarchive、12/12タスク完了。
