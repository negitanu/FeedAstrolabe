# 実装順序

## 第一段階：RSS と Web UI

この change の対象。登録・分類・収集・検索・閲覧状態と永続化をローカルで利用できるようにする。受入条件は `openspec/changes/phase-one-rss-reader/specs/`、検証記録は `docs/verification.md` を参照する。

## 第二段階：コンテナと Cloudflare Zero Trust

変更 `phase-two-deployment-api-settings` でコンテナ・Access JWT 検証・API・設定・OPML を実装済み。ローカルコンテナで再作成・backup/restoreを検証。実Cloudflare接続はユーザーの指示で後段へ延期（タスク 4.3）。対象は非 root のイメージ、Web/worker の Compose、永続ボリューム、healthcheck、Cloudflare Tunnel と Access、秘密情報の環境変数管理、復旧手順。

受入条件：コンテナ再作成後も記事状態が残る。許可ユーザーのみ Access を通って利用できる。origin の直接公開を防ぎ、Tunnel 停止時は外部アクセス不能。バックアップからの復元を確認する。Access の境界と origin 側の JWT 検証要否を設計し、TRUSTED_HOSTS と HTTPS cookie を設定する。

必要な情報：実行ホスト、公開ドメイン、Cloudflare アカウント、Access で許可するユーザー。これらを確定してから実際の外部公開を行う。

## 第三段階：X など SNS フィード

変更 `phase-three-social-feeds` で X アカウント／リストと公開 Mastodon アカウントに対応。feeds/articles を共通の source / entry として使用し、プロバイダー別アダプター、ファイル認証、レート待機、再試行、永続 cursor による差分取得を実装する。X の実接続検証は資格情報と対象設定後に行う。

受入条件：指定したアカウントやリストの投稿を確認できる。投稿の一意 ID で重複排除し既読・スターを保持する。認証失敗・レート制限を UI に表示する。API キーを Git/ログに残さない。

必要な情報：SNS の種類、対象アカウント/リスト、利用可能な API プランと資格情報。X の取得方法や費用は実装時に公式資料で確認し決める。

## 第四段階：Playwright 固定ページ観測

第三段階完了後に OpenSpec change を作成。観測 URL、CSS セレクター、頻度、テキスト正規化、差分、必要に応じたスクリーンショットを設計する。ブラウザー処理は別 worker とし、取得先制限、並列数、タイムアウト、リソース上限、保存期間を設定する。

受入条件：指定要素の変化だけを新規エントリーとして通知・表示する。変化なしでは新規記事が増えない。JS 描画ページ、セレクター消失、タイムアウトを検証する。RSS/SNS と同じ UI で観測結果を読み、既読・スターを使える。

必要な情報：観測 URL と対象要素、頻度、ログイン要否、差分/画像の保存期間。
