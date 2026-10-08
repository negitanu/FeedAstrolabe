# 秘密情報と公開リポジトリ

GitHub の `negitanu/FeedAstrolabe` は公開リポジトリです。ソースコード、仕様、架空の例だけを公開します。実運用データと資格情報は公開対象に含めません。

`.gitignore` は instance、secrets、backups、dotenv、SQLite、秘密鍵、証明書コンテナ、OPML、ログ、OS/クラウド資格情報を除外します。`.env.example` は非秘密の設定例のみ許可します。`.dockerignore` はアプリと本番依存ロックだけを許可するため、DB・トークンはビルドへ送りません。すでに tracked のファイルは ignore 追加だけで除外されないため、index と履歴も検査します。

push 前に以下を実行します。

```sh
python3 scripts/check_secrets.py --staged --history
gitleaks git --redact --no-banner .
gitleaks dir --redact --no-banner --max-target-megabytes 10 feedastrolabe
gitleaks dir --redact --no-banner --max-target-megabytes 10 docs
```

Gitleaks 8.30.1 は履歴・候補ファイルにも適用しました。第二段階のタスク 2.1 の英文「keys, issuance/revocation」が generic-api-key の誤検知となるため、`.gitleaksignore` に該当履歴・該当行の fingerprint だけを記載しています。ファイル全体やルール全体の除外はありません。CI テンプレート `.github/ci-template.yaml` は SHA 固定の公式 Actions と checksum を検証した Gitleaks を使用します。既存 OAuth 認証に workflow scope がないため、GitHub による workflow 作成の push 拒否を受け、現時点では自動実行対象のディレクトリへ配置していません。CI を有効にする場合は、適切な権限で `.github/workflows/ci.yaml` に移してください。ローカル検証・秘密情報検査は実施済みです。

組み込み検査は Git index の全ファイルと、全ローカル ref から到達する過去の blob を調べます。秘密鍵、一般的なクラウド/GitHub/Slack トークン、JWT、資格情報 URL、長い認証情報リテラルと危険なファイル名を検出します。検出時は場所とルール名だけを表示し、値を表示しません。これは全種類の秘密を検出する保証ではありません。Gitleaks の検査と差分レビューを併用し、秘密を作成時から専用ファイルへ隔離することが主な対策です。

SNS の認証先は X の HTTPS API に固定し、認証付きリダイレクトは拒否します。プロバイダーのエラー本文・生の例外をログ／画面に出しません。X トークンはファイルから取得ごとに読み直し、DB/API に含めません。アプリの API キーは SHA-256 ハッシュだけを保存し、全文は発行時に一度だけ表示します。DB バックアップにもキーのハッシュと閲覧履歴が含まれるため公開しません。

公開済みの資格情報が見つかった場合は、まず提供元で失効・再発行します。Git 履歴を書き換えるだけでは資格情報の漏えいは解消できません。履歴改変や force push は別途判断し、通常の更新では実施しません。
