# 第八段階の検証（2026-10-08）

OpenSpec change: `phase-eight-watchlists-triage`。案件のウォッチリスト／保存検索、条件の不変版、包含・除外の判定と優先度の理由、増分worker、アプリ内受信箱／UTC日次ダイジェスト、完全一致／同じURLの重複グループと解除を実装。schema v6→v7。

- 全回帰 `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：198件成功。`tests/test_triage.py` の8テストで除外優先と双方の条件説明、案件scope、アーカイブ、immutable条件版／409、再処理冪等性、本文更新の新根拠版、literal %/_/SQL文字列、invalid AST／日時／40条件／100リスト上限、read/write／CSRF／巨大ID、タグ・日時・none条件、停止中の手動続行、実並行worker／編集競合、100件batch、25条件の公平なworker処理、元記事状態の保持、URL tracking／意味のあるquery／IPv4 private除外、抑制の再処理保持とredo、固定根拠のretentionを確認。実v6 fixtureのメモ固定・引用付き根拠を移行しFK／引用保持、IDの非再利用、v6/v7 bundle復元を確認。
- `scripts/verify_triage.py --serve-port 5012`：一時DBの実HTTPで条件作成・readキー拒否・通知／digest／seen・再試行・出典付き2グループ・解除・stale revision・v7 bundle復元・日本語UIを確認。利用者DBにfixtureを追加しない。
- `scripts/verify_observer.py --project feedastrolabe-triage-verify`：独立4サービスで evidence/attachmentの実HTTP・Linux text/Markdown/PDF IPC・実ChromiumのJS baseline/change/revertの回帰を実施。別の検証DBにtriage HTTP fixtureを永続化し、4サービスの強制再作成後schema7、条件版・通知2件・確認状態・解除状態・冪等性・FK整合性を確認。rendererのnetwork none／非root／read-only／DBなしも検証。検証サービスは停止し独立volumeは保持。
- CUA で受信箱、JSON条件編集と履歴、重複グループの両方のpublisher／元記事状態を確認。390px幅で受信箱・編集・グループ詳細の document.scrollWidth=390px、script要素0。長い説明文とcheckboxの幅を修正し、通常viewportへ復帰。
- 実writer停止後 `/data/pre-phase-eight/` にv6 DB／blobの検証済みbundleを保存（DB600）。4サービスを更新／再作成しhealthy。schema7、evidence AUTOINCREMENT、FK正常、移行前全購読ID／URL、記事ID／feed_id／GUID／既読／スター、案件／メモ／履歴／タグ／根拠／引用／固定参照をEXCEPT比較し不一致0。現在購読1件／記事32件／案件0件。通常収集の新着増加と旧記事の保持を区別。
- OpenAPI全ローカル参照と全ルート／HTTPメソッドが実装に存在することを確認。OpenSpec strict は同期前17項目成功。

照合は件数制限したID範囲を順番に処理します。FTSや正規表現検索は導入しません。過去根拠のタグ／関連付け変更は明示的再照合が必要。通知・グループにある根拠は参照保持のためretentionで削除せず、それらの保存期間管理は後段です。重複は完全一致と同じURLのみで、類似主張を自動統合しません。グループは共有ライブラリ全体、案件公開区分はユーザー権限分離ではありません。外部通知は未実装。

Cloudflare実接続、X実資格情報、GitHub CI有効化は従来どおり未完了。fixture結果を実外部接続の結果として扱いません。配布時のGit秘密情報検査・push・仕様同期の結果は完了後追記します。
