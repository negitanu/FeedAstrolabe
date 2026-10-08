# 第三段階の検証記録

検証日: 2026-10-08

- Python テスト101件成功。既存 RSS/API の回帰、v1/v2→v3 マイグレーション、SNS登録、権限、投稿の既読/スター保持、HTML無害化、ページ途中失敗と再起動後再開、3ページ上限、Xリスト境界、共有レート待機、認証ファイルの権限/シンボリックリンク拒否、エラーからの秘密情報除去を検証。
- OpenSpec 厳格検証：仕様3件・変更3件、計6件成功。pip check 成功。
- 隔離した `feedastrolabe-social-verify` コンテナで SNS の模擬API取得、実 HTTP 記事API、非root・read-only・cap drop、キー失効、backup/restore、サービス再作成後の永続性を確認。検証後にサービスを停止し、検証ボリュームは保持。
- 一時DBで Mastodon 公式公開アカウント `Mastodon@mastodon.social` の実API取得を確認（40投稿、成功1・失敗0）。ユーザーのライブラリに検証購読は追加していない。
- 実コンテナを更新前に `/data/pre-phase-three.sqlite3` へバックアップ。v3 更新後に既存23記事のID・guid・既読・スターと購読URL・フォルダーが一致することを確認。
- UIの SNS 登録フォームを通常幅と390px幅で確認。モバイルの scrollWidth は390pxで横溢れなし。
- 組み込み秘密情報検査と Gitleaks 8.30.1 で Git index/候補・全履歴を検査。第二段階タスク2.1の英文の誤検知のみ、該当 fingerprint に限定して除外。資格情報や運用DBは公開対象に含めない。

稼働先: http://127.0.0.1:5010/settings#social

X はオペレーターのトークン・API権限・対象が未設定のため、実APIの取得検証は未実施。Xのアカウント／リスト応答は公式仕様に沿ったfixtureで検証し、OpenSpecタスク3.4を未完了で保持する。Cloudflare実接続はユーザー指示で後段へ延期。

GitHub OAuth の workflow scope がないため、CI は `.github/ci-template.yaml` として保存し、自動実行は未設定。実装・仕様の push はこのテンプレートを含めて実行する。
