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

変更 `phase-four-page-observation` で公開ページの CSS テキスト観測を実装。初回基準・差分記事・手動予約・保存期間・API とネットワーク隔離した Chromium を提供する。スクリーンショットとログイン対応は今回の対象外。ブラウザー処理は別 worker とし、取得先制限、並列数、タイムアウト、リソース上限、保存期間を設定する。

受入条件：指定要素の変化だけを新規エントリーとして通知・表示する。変化なしでは新規記事が増えない。JS 描画ページ、セレクター消失、タイムアウトを検証する。RSS/SNS と同じ UI で観測結果を読み、既読・スターを使える。

必要な情報：観測 URL と対象要素、頻度、ログイン要否、差分/画像の保存期間。

## 第五段階：購読管理・API拡充

変更 `phase-five-subscription-management` で API の購読設定変更・削除・全情報源の手動更新と、UI の RSS/ページ URL 修正を追加。記事・既読・スターを保持する編集、不正入力の原子的な拒否、収集中の排他、SNS 待機応答を検証する。Cloudflare の実接続と X の実資格情報検証は引き続き後段。

## 第六〜第十四段階：情報収集・調査ワークスペース（第六〜第九段階実装済み）

[詳細計画](docs/research-workspace-plan.md) と各OpenSpec changeに、proposal/design/specs/tasksを用意しました。

- 第六（実装済み）：調査案件・版付きメモ・タグ。`phase-six-research-workspaces`（2026-10-08 archive、正規仕様 `openspec/specs/research-workspaces/`）。
- 第七（実装済み）：根拠の不変保存・出典・引用・添付・復旧。`phase-seven-evidence-provenance`。
- 第八（実装済み）：ウォッチリスト・保存検索・説明付き優先度・重複整理。`phase-eight-watchlists-triage`。
- 第九（実装済み）：対象抽出・根拠付き関係・タイムライン。`phase-nine-entities-relations`。
- 第十：KEV/EPSS等のセキュリティ情報と共通外部連携基盤。`phase-ten-security-intelligence`。
- 第十一：DNS/RDAP/CT/経路/RPKIの受動的観測。`phase-eleven-network-intelligence`。
- 第十二：論文・モデル・リリース・評価条件の追跡。`phase-twelve-ai-research-tracking`。
- 第十三：出典付き・外部送信制御付きAI調査補助。`phase-thirteen-grounded-assistant`。
- 第十四：レポート・通知・バックアップ・監視・管理API。`phase-fourteen-reports-operations`。

第六〜第八のMVPと第九の対象・関係管理を実装済みです。次の実装は第十のchangeを明示して進めます。Cloudflare/Xの未完了実接続を自動で先行させません。後続changeは依存する実装完了後に仕様を再確認します。第十〜第十四は未実装です。計画の作成・検証だけで実装タスクを完了扱いしません。
