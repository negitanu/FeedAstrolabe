# 第五段階の検証（2026-10-08）

OpenSpec change: `phase-five-subscription-management`。購読管理と API を追加し、schema v4 と既存の描画コンテナ境界を維持しています。

- `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：157件成功。既存の実 Chromium/IPC/強制終了に加え、RSS URL 修正後の無条件取得と記事 ID・既読・スター保持、原子的な不正 PATCH 拒否、重複、権限、CSRF、欠損ID、収集ロック、ページ基準/履歴/変更番号保持と古い観測破棄、削除 cascade、SNS の待機応答を確認。
- `openspec validate --all --strict --no-interactive`：8項目成功。
- 更新前の `/data/pre-phase-five.sqlite3` を SQLite backup で保存して4サービスを再ビルド・再作成。購読1件、既存記事23件の ID・URL・GUID・既読・スターを更新前 snapshot と比較し、全件保持。foreign_key_check はエラーなし。
- 新コンテナで `scripts/verify_subscriptions.py` を実行。一時ライブラリで実 HTTP の登録、URL修正、pause中の手動取得、状態保持、readキー拒否、不正な混合PATCHの原子性、ページ観測の重複予約、編集時の古い結果破棄、DELETE204と記事/予約cascadeを確認。既存利用者ライブラリに検証購読やキーは追加していません。
- 実稼働 `/settings#subscriptions` で URL修正フォームを通常幅と390px幅で確認。390px時の document.scrollWidth は390px。UI操作の保存・CSRFは回帰テストで確認し、既存購読URLは手動変更していません。

URL修正は過去記事を保持し、新しい取得元でも同じ GUID は同じ記事として扱います。SNSのアカウント/source_type変更は対象外です。RSS/SNSのAPI手動更新は同期処理で、失敗を200の failed件数/取得状況として返します。通常の定期収集は worker を使用します。

Cloudflare 実接続、X 実資格情報による取得と GitHub CI の有効化は従来どおり未完了です。CIはテンプレートを更新し、この検証結果をクラウドCIの結果として扱っていません。

push 前に Git候補/履歴のパターン検査と Gitleaks を実行し、検出なしを確認しました。資格情報・ローカルDB・バックアップを公開候補に含めません。秘密情報検出の完全性は保証しません。
