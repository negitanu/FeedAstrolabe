# Cloudflared Tunnel と標準コンテナ構成

通常運用は `compose.yml` 一つで起動します。Docker Engine / Docker Desktop と Composeを使用します。Web・RSS/SNS worker・observer・renderer・cloudflared tunnelを含み、originのホストポートを公開しません。Web/worker/observer/tunnelは `reader` bridgeネットワークを使用し、rendererはネットワークなし・IPCソケットだけを共有します。

アプリは非root UID/GID10001、root filesystemはread-only、capabilities無効で動きます。データは従来と同じ `reader-data` named volumeへ保存します。プロジェクト名の既定は `feedastrolabe`、実ボリューム名は `feedastrolabe_reader-data` と `feedastrolabe_renderer-ipc` です。資格情報はGitとDocker build contextから除外します。

## Cloudflare の必須設定

1. Cloudflareに接続した公開hostnameを決めます。
2. AccessにSelf-hosted applicationを作成し、hostname全体を保護します。許可するメールアドレス等をAllow policyに設定します。機械からAPIを呼ぶ場合はService Auth policyにservice tokenを設定します。
3. Remotely managed Tunnelを作り、公開hostnameのサービスを **HTTP `web:5000`** に設定します。
4. Tunnelの公開ルートで **Protect with Access** を有効にし、上記Access applicationで検証させます。UI・APIを含むhostname全体を保護し、Bypassを設定しません。
5. `.env.example` を `.env` にコピーし、`TUNNEL_TOKEN` にTunnelのtokenを入力します。ローカルの必須項目はこれだけです。未設定・空欄ならComposeの構成解決を拒否します。Tunnel tokenの別ファイルは不要です。

```sh
cp .env.example .env
chmod 600 .env
# .env の TUNNEL_TOKEN にエディターで入力
```

cloudflaredはUID65532で動きます。Composeは公式の `TUNNEL_TOKEN` 環境変数をTunnelサービスだけに渡し、コマンド引数や他のコンテナには含めません。`.env` はGit・build contextから除外します。構成確認は `docker compose config --quiet` を使用してください。通常の `config` 出力やDocker管理者による環境変数の参照にはtokenが含まれます。

## 標準の起動・停止

```sh
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
docker compose logs --tail 50 tunnel worker
```

設定した公開URLをCloudflare Access経由で開きます。追加のComposeファイルやprofile指定は不要です。既定の `tunnel` modeでは、許可する公開hostnameとJWT検証をCloudflare側のAccess／Protect with Accessで管理します。アプリは転送された公開Hostを受け入れ、Secure cookie・CSRF・API Bearer認証を維持します。originのhost portは公開しないでください。同じbridgeに信頼できないコンテナを接続しないでください。

Tunnel tokenはコネクターの接続資格情報であり、閲覧者のログイン制限ではありません。Accessが未設定なら公開URLは誰でも操作できるため、ルート作成前にAccessを設定してください。アプリからCloudflare側の設定の正しさは確認できません。[公式の認証委譲手順](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/#3-validate-the-access-token)と後述の公開後受入確認を使用します。

```sh
docker compose down
```

`down` 後もnamed volumeは残ります。Web/worker/observerの再作成では記事・既読・スター・設定・APIキーを保持します。workerは通常収集・承認済みジョブを処理し、observerはページ観測を処理します。このアプリは単一ライブラリ方式で、Accessで許可されたメンバー全員が設定とAPIキーを管理できます。

## 任意：アプリ内でもJWTを検証する

Cloudflare側だけでなくアプリ内でも検証したい場合に限り、`.env` へ次を追加します。標準のtunnel modeでは不要です。

```dotenv
FEEDASTROLABE_ACCESS_MODE=cloudflare
CF_ACCESS_TEAM_DOMAIN=https://your-team.cloudflareaccess.com
CF_ACCESS_AUD=your-application-audience-tag
FEEDASTROLABE_PUBLIC_HOSTS=reader.example.com
```

この `cloudflare` modeでは3設定をアプリ起動時に検証し、不足時は起動を拒否します。Access JWTの署名（RS256）・issuer・audience・exp・iatと明示的なHostを検証し、認証失敗やJWKS取得失敗では403を返します。JWTのない `/healthz` は最低限のstatusだけを返します。JWKSは300秒cache・5秒timeoutです。native開発の既定は引き続きlocalhost専用の `local` modeです。

## 既存構成からの移行

従来の基本設定と追加ファイルは `compose.yml` へ統合しました。データをバックアップしてから、Tunnel tokenを `.env` に入力し、同じプロジェクト名で起動してください。旧 `FEEDASTROLABE_TUNNEL_TOKEN_FILE` は廃止し、`TUNNEL_TOKEN` を使います。従来 `-p` で独自のプロジェクト名を使っていた場合は、今後もその名前を指定します。既存のボリュームを削除する必要はありません。`COMPOSE_FILE` が旧ファイルを指している場合はその指定を解除します。標準のhost port公開はなくなるため、ブラウザーの接続先を公開URLへ変更します。

Ollamaのhost file secretを使用していた場合は、下記の手順でprivate volumeへ配置し、`.env` をコンテナ内パスへ変更します。通知の設定ファイルが既にprivate volumeにある場合は、そのパスを `.env` へ設定します。実際のファイル移動・資格情報変更・稼働サービスの再起動は運用者が実施します。

X収集は廃止しました。旧 `FEEDASTROLABE_X_TOKEN_FILE` は使用しません。Mastodon／Blueskyの公開API調査に認証ファイルは不要です。

## 任意の連携設定

重要トピック抽出は `.env` に `OPENROUTER_API_KEY` または `ORCAROUTER_API_KEY` の値を直接記載します。別ファイルは不要です。Webとworkerのみに渡し、「設定」→「AI接続」でプロバイダ・モデル・予算・有効化を設定するまで生成しません。[AI接続の設定](ai-providers-and-settings-export.md)を参照してください。


Ollama cloud・通知は、未使用なら `.env.example` の2つのファイルパスを空欄のままにします。任意の資格情報ファイルがなくても基本構成は起動できます。

使用する場合はアプリUID/GID10001・0600の通常ファイルをprivate volumeへ保存し、`.env` にコンテナ内のパスを指定します。ファイルの所有者・permission・symlink検査は維持します。値そのものを環境変数へ入れません。同名の環境変数をシェルでexportしている場合は `.env` より優先されるため、解除するかコンテナ内パスへ変更してください。

```dotenv
FEEDASTROLABE_OLLAMA_TOKEN_FILE=/data/ollama-token
FEEDASTROLABE_DELIVERY_CONFIG_FILE=/data/delivery-config.json
```

起動後、ホストの非公開ファイルをアプリ自身のUIDで保存する例です。標準入力を使用し、ファイル内容をコマンド引数や出力へ載せません。通知の場合は入力・出力パスを対応するファイルへ変更してください。

```sh
docker compose exec -T web python -c '
import os, sys
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, "wb") as handle:
    handle.write(sys.stdin.buffer.read())
' /data/ollama-token < secrets/ollama-token.txt
# .env の使用するパスだけを設定した後：
docker compose up -d --wait
```

未使用のパスは空欄にしてください。設定しただけで購読・モデル生成・通知を有効にすることはなく、各画面の登録と承認も必要です。資格情報ファイルはDB／根拠bundleと別に安全にバックアップしてください。詳細は [SNS](social.md)、[調査補助](grounded-assistant.md)、[通知](reports-operations.md) を参照してください。

## 公開後の受入確認

- Accessのhostname全体を保護するAllow policyと、TunnelルートのProtect with Accessが有効であることを確認する。
- 未ログインのブラウザーで記事・設定・APIへ直接アクセスし、アプリの内容を取得できないことを確認する。
- 許可ユーザーでログインし、記事・設定・POST操作を確認する。
- 別ブラウザー／未許可ユーザーが拒否されることを確認する。
- service tokenとアプリAPI keyの両方でAPIが200、片方を省略すると拒否されることを確認する。
- `docker compose ps` でWebのhost portが未公開であることを確認する。
- `docker compose stop tunnel` で外部アクセスが不能になり、`docker compose up -d tunnel` で復帰することを確認する。

実ドメインと資格情報を使うこの確認は、ローカルの署名付きJWTテストや検証用コンテナとは別に実施します。

## バックアップ・復元

根拠を含むライブラリはDB／blobを一貫させるbundleを使います。既存パスには上書きしません。

```sh
docker compose exec web python -m feedastrolabe.maintenance backup-bundle /data/library-REPLACE_WITH_GENERATION
mkdir -p backups
docker compose cp web:/data/library-REPLACE_WITH_GENERATION backups/library-REPLACE_WITH_GENERATION
```

復元前に元データもバックアップし、書き込みを行うWeb・worker・observerを停止します。

```sh
docker compose stop web worker observer
docker compose run --rm --no-deps -T web python -m feedastrolabe.maintenance restore-bundle /data/backups/backup-REPLACE_WITH_GENERATION
docker compose up -d --wait
```

上の復元例は、volume内に存在する世代バックアップを指定します。ホストへ保存したbundleの復元・manifest検証は [根拠と復旧](evidence.md)、定期バックアップは [運用](reports-operations.md) を参照してください。

根拠を含まない旧DBだけのsnapshotに限り、nativeの `maintenance backup backups/library.sqlite3`、コンテナの `maintenance backup /data/library.sqlite3`、停止後の `docker compose run --rm --no-deps -T web python -m feedastrolabe.maintenance restore - < backups/library.sqlite3` を利用できます。復元したDBは現行スキーマへ移行します。`secret.key` も別途安全に保存するとセッション署名鍵を保持できます。旧コードへ戻す際は対応する旧snapshotを復元してください。

## 環境変数と開発

Composeの接続先・Access設定は `.env.example` を参照してください。native開発起動は [README](../README.md#native-開発起動) のlocalhost方式を利用できます。native既定のbind先は127.0.0.1、コンテナ内部は0.0.0.0です。nativeとコンテナは既定で別のライブラリを使います。

ポーリング間隔・pause・一覧件数・初期ビュー・APIレート上限は `/settings` の永続設定です。workerは処理中の取得終了後、次の10秒tickで設定を再読込します。個別間隔を優先し、失敗時は2倍ずつ最大24時間まで待機します。成功時に失敗数は0へ戻ります。全体pauseは自動収集を止め、明示的な手動取得は利用できます。`worker --interval` の明示指定は画面の全体間隔を上書きします。

## 再現可能なコンテナ検証

```sh
.venv/bin/python scripts/verify_container.py
.venv/bin/python scripts/verify_observer.py
```

検証用の `*-verify` プロジェクトと専用イメージ／ボリュームを使います。`compose.yml` を基本に、一時ファイル内だけでWebの認証をlocalへ切り替え、Tunnelを無効化します。運用者の `.env` と任意の資格情報パスを使用せず、ホストポートも公開しません。正常終了・失敗時とも検証コンテナを停止し、検証用volumeは残します。通常運用で一時設定を使用する必要はありません。

参考：[Docker Compose profiles](https://docs.docker.com/reference/compose-file/profiles/)、[Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/)、[Access JWT検証](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)。
