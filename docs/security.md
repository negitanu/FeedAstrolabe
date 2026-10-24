# 秘密情報と公開リポジトリ

GitHub の `negitanu/FeedAstrolabe` は公開リポジトリです。ソースコード、仕様、架空の例だけを公開します。実運用データと資格情報は公開対象に含めません。

`.gitignore` は instance、secrets、backups、dotenv、SQLite、秘密鍵、証明書コンテナ、OPML、ログ、OS/クラウド資格情報を除外します。`.env.example` は非秘密の設定例のみ許可します。Tunnel tokenは `.env` の `TUNNEL_TOKEN` に記載し、ファイルを0600で保護します。ComposeはTunnelだけにtokenを渡します。`.dockerignore` はアプリソースと依存定義だけを許可するため、DB・トークンはビルドへ送りません。すでに tracked のファイルは ignore 追加だけで除外されないため、index と履歴も検査します。

標準Composeの `tunnel` modeは、Cloudflare Accessの許可ポリシーとcloudflaredのProtect with Accessへ認証・hostname制限を委ねます。アプリ内JWT検証の設定は任意です。Tunnel tokenだけでは閲覧者を認証しないため、公開ルートのAccess保護を必ず設定します。originのhost portは非公開のままにし、同じbridgeには信頼できるサービスだけを接続します。Secure cookie・CSRF・API Bearer認証はアプリで維持します。外部の未ログイン／未許可ユーザーが拒否されることは、[公開後の受入確認](deployment.md#公開後の受入確認)で検証します。

push 前に以下を実行します。

```sh
python3 scripts/check_secrets.py --staged --history
gitleaks git --redact --no-banner .
gitleaks dir --redact --no-banner --max-target-megabytes 10 feedastrolabe
gitleaks dir --redact --no-banner --max-target-megabytes 10 docs
```

Gitleaks 8.30.1 は履歴・候補ファイルにも適用しました。第二段階のタスク 2.1 の英文「keys, issuance/revocation」が generic-api-key の誤検知となるため、`.gitleaksignore` に該当履歴・該当行の fingerprint だけを記載しています。ファイル全体やルール全体の除外はありません。CI テンプレート `.github/ci-template.yaml` は SHA 固定の公式 Actions と checksum を検証した Gitleaks を使用します。既存 OAuth 認証に workflow scope がないため、GitHub による workflow 作成の push 拒否を受け、現時点では自動実行対象のディレクトリへ配置していません。CI を有効にする場合は、適切な権限で `.github/workflows/ci.yaml` に移してください。ローカル検証・秘密情報検査は実施済みです。

組み込み検査は Git index の全ファイルと、全ローカル ref から到達する過去の blob を調べます。秘密鍵、一般的なクラウド/GitHub/Slack トークン、JWT、資格情報 URL、長い認証情報リテラルと危険なファイル名を検出します。検出時は場所とルール名だけを表示し、値を表示しません。これは全種類の秘密を検出する保証ではありません。Gitleaks の検査と差分レビューを併用し、秘密をGit・ビルドコンテキストから隔離することが主な対策です。

SNSの投稿収集はMastodon／Blueskyの公式公開APIだけを使い、認証情報を送信しません。BlueskyのAPI originは固定し、Mastodonは公開HTTPS originとDNS/IPを検証します。リダイレクトと応答サイズ・件数超過を拒否し、429待機を提供元ごとに共有します。プロバイダーのエラー本文・生の例外をログ／画面に出しません。X収集とトークン読み込みは廃止し、保存済み記事は保持します。アプリの API キーは SHA-256 ハッシュだけを保存し、全文は発行時に一度だけ表示します。DB バックアップにもキーのハッシュと閲覧履歴が含まれるため公開しません。

公開済みの資格情報が見つかった場合は、まず提供元で失効・再発行します。Git 履歴を書き換えるだけでは資格情報の漏えいは解消できません。履歴改変や force push は別途判断し、通常の更新では実施しません。

## 外部 XML と購読の確認

RSS/Atomはfeedparserへ渡す前に、[defusedxml](https://github.com/tiran/defusedxml/blob/main/README.md)によるストリーミング検証でDTD・実体宣言・外部参照を拒否します。整形式でないXMLも処理を止め、例外に含まれる本文や外部識別子をログ・画面へ出しません。RSS/Atomは5MiB・100,000要素・深さ64、OPMLは1MiB・10,000要素・深さ64までです。OPMLは従来どおり最大100購読を全件検証してから登録します。

UIのOPMLアップロードは読み取り専用のプレビューです。確定POSTはCSRFに加え、用途を限定したHMAC-SHA256署名、15分の有効期限、現在のセッションとの照合、512KiBまでの確認データと購読項目の再検証を要求します。署名と期限を検証してから内容を復元します。確認データはレスポンスにのみ置き、Cookie・DB・ログへ保存しません。登録はトランザクションと既存の更新ロックで保護し、既存の購読設定を上書きしません。[検証記録](verification-safe-import-preview.md)を参照してください。

OpenRouterの重要トピック抽出は明示的に有効化した場合のみ、最大20件の公開投稿抜粋を固定HTTPS endpointへ送信します。非公開案件との関連を送信前に再確認し、認証値らしい抜粋を除外します。APIキーは `.env` からWeb／workerの環境へ渡し、DB／画面／ログへ記録しません。構造化出力、出典ID、token数、API申告費用を検証し、料金上限とUTC日次予約を適用します。POST自動再送はせず、復元後は無効化します。[送信・費用・保持の仕様](openrouter-topics.md)を参照してください。
