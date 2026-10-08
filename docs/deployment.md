# コンテナと Cloudflare Zero Trust

Docker Engine / Docker Desktop と Compose を使用します。Web と worker は同じ非 root イメージを使用し、データは `reader-data` named volume に保存します。root filesystem は read-only、capabilities を落とし、API キー全文や認証資格情報をイメージへ含めません。Docker ビルドは必要なアプリファイルだけを許可する .dockerignore を使います。

## ローカルのコンテナ起動

```sh
docker compose -f compose.yaml -f compose.local.yaml up --build -d --wait
```

http://127.0.0.1:5010 にアクセスします。native Python 起動の5000とは別のライブラリです。データ移行が必要なら下記の backup/restore を使用します。コンテナでは worker を同時に起動するため、設定画面のポーリング設定がそのまま反映されます。

```sh
docker compose -f compose.yaml -f compose.local.yaml ps
docker compose -f compose.yaml -f compose.local.yaml logs --tail 50 worker
docker compose -f compose.yaml -f compose.local.yaml down
```

`down` 後も volume は残ります。再起動では既読・スター・設定・APIキーが残ります。volume削除のコマンドは通常運用に使いません。Web の healthcheck は DB を含む最低限の生存確認。worker は定期更新プロセスとして動作します。

## Cloudflare の設定

実際の公開には次の設定が必要です。値はこのリポジトリに保存しません。

1. Cloudflare に接続した公開 hostname と Zero Trust team domain を決める。
2. Access に Self-hosted application を作成し、その hostname 全体を保護する。許可するユーザーのメールアドレス等を Allow policy に設定する。公開 API を機械から呼ぶ場合は Service Auth policy に service token を設定する。
3. アプリの Audience (AUD) tag と `https://<team>.cloudflareaccess.com` を記録する。
4. Remotely managed Tunnel を作り、hostname のサービスを **HTTP `web:5000`** に設定する。Host header は公開 hostname を使う。origin のポートをインターネット側へ直接公開しない。
5. `.env.example` を `.env` にコピーし、team domain、AUD、公開 hostname の実値を入力する。
6. `secrets/` ディレクトリを所有者だけがアクセスできるように作り、Tunnel token を `secrets/tunnel-token.txt` にテキストエディター等で保存する。トークンをコマンド行に直接書かない。

```sh
mkdir -p secrets
chmod 700 secrets
# secrets/tunnel-token.txt にトークンを保存した後：
chmod 644 secrets/tunnel-token.txt
```

cloudflared は非 root の UID65532 で動きます。ローカル Compose の file-backed secrets は元ファイルの mode を保持するため、mount 後にこの UID が読める permission が必要です。ホスト側では親ディレクトリの700によって他のユーザーから保護します。`.env` と `secrets/` は Git と Docker build context の対象外です。

```sh
docker compose -f compose.yaml -f compose.cloudflare.yaml config --quiet
docker compose -f compose.yaml -f compose.cloudflare.yaml up --build -d --wait
```

**Cloudflare 起動では compose.local.yaml を併用しません。** origin の host port は publish されません。アプリは `Cf-Access-Jwt-Assertion` の署名（RS256）・issuer・audience・exp・iat を検証し、認証失敗や JWKS 取得失敗で403を返します。キー取得はteamのHTTPS endpoint限定で、300秒cache・5秒timeoutです。Secure cookie、明示的な trusted hosts を有効にします。

公開 hostname が Access に未設定でも、origin は有効な JWT のない記事/UI/APIアクセスを拒否します。healthzは最低限のstatusだけを返す例外です。Tunnel の token はAccessの利用資格を代替しません。

このアプリは単一ライブラリ方式です。Access で許可されたメンバーは全員、設定と API キーを管理できます。

## 公開後の受入確認

- 許可ユーザーでログインし、記事、設定、POST 操作を確認する。
- 別ブラウザー/未許可ユーザーから拒否されることを確認する。
- service token + アプリ API key でAPIが200、片方を省略すると拒否されることを確認する。
- Web の host ports が未公開であることを `docker compose ps` で確認する。
- Tunnel を停止し外部アクセスが不能になることを確認する。

実ドメインと資格情報未設定の環境では、この確認は未完了です。ローカルの署名付きJWTテストだけで実公開確認済みとは扱いません。

## バックアップ・移行・復元

稼働中の DB は SQLite backup API で一貫した snapshot を作成できます。既存パスへの上書きはしません。API キーは hash、DB内のキーの権限や失効状態も snapshot の一部です。

native：

```sh
.venv/bin/python -m feedastrolabe.maintenance backup backups/library-20261008.sqlite3
```

コンテナ（snapshot は volume 内に作成）：

```sh
docker compose -f compose.yaml -f compose.local.yaml exec web python -m feedastrolabe.maintenance backup /data/library-20261008.sqlite3
mkdir -p backups
docker compose -f compose.yaml -f compose.local.yaml cp web:/data/library-20261008.sqlite3 backups/library-20261008.sqlite3
```

復元前に Web、worker、ページ観測を使用している場合は observer を停止します。元DBもbackupしてから実行してください。nativeではサービス停止後に `maintenance restore <snapshot>` を実行します。根拠を含まない v1〜v6 snapshot は v7 に移行されます。調査案件・タグ・メモの版履歴も同じ SQLite バックアップに含まれます。

コンテナでは対象サービスを停止し、snapshotを標準入力から one-off restore へ渡します。コンテナのUID10001が一時ファイルを作成するため、ホスト側のUIDやファイル所有者が違っていてもコピー時のpermission変更を必要としません。

```sh
docker compose -f compose.yaml -f compose.local.yaml stop web worker
docker compose -f compose.yaml -f compose.local.yaml run --rm --no-deps -T web python -m feedastrolabe.maintenance restore - < backups/library-20261008.sqlite3
docker compose -f compose.yaml -f compose.local.yaml up -d --wait
```

native→コンテナも同じ標準入力の手順で移行できます。DB snapshot と別に `secret.key` を安全にバックアップするとセッションの署名鍵も保持できます。新しい保存先で新しい secret.key が作られた場合、既存 cookie は再発行されますがDBのAPIキーは引き続き利用できます。

ローリング更新は今回の対象外です。コード更新・DB移行はbackupしてWeb/worker/observerを停止して行い、旧版への復帰は対応するsnapshotも復元します。nativeで変更したDBを旧プロセスと併用しないでください。

## 環境変数と運用設定

環境変数は接続先等の運用設定：`FEEDASTROLABE_DATA_DIR`、`FEEDASTROLABE_BIND_HOST`（native既定127.0.0.1、コンテナ0.0.0.0）、`FEEDASTROLABE_PORT`、`FEEDASTROLABE_ACCESS_MODE`、`CF_ACCESS_TEAM_DOMAIN`、`CF_ACCESS_AUD`、`FEEDASTROLABE_PUBLIC_HOSTS`（comma区切り）。

ポーリング間隔・pause・一覧件数・初期ビュー・APIレート上限は `/settings` の永続設定です。worker は処理中の取得が終了してから次の10秒tickで再読み込みします。個別フィードの間隔を優先し、連続失敗時は2倍ずつ最大24時間まで待機します。成功で失敗数は0に戻ります。全体pauseは自動収集のみ停止し、明示的なフィードの手動取得は利用できます。

旧 `worker --interval 900` も使えますが、明示指定すると画面の全体間隔を上書きします。通常は引数なしの worker を使ってください。表示の時刻はUTC。RSS/SNS の自動記事削除は行いません。ページ観測は設定した保存期間の未スター記事を削除します。

## 再現可能なコンテナ検証

```sh
.venv/bin/python scripts/verify_container.py
```

`feedastrolabe-verify` という独立したCompose projectのvolumeに検証記事を作り、実HTTP API、失効、backup/restore、container recreationを確認します。検証用ポートは5011です。検証用volumeは終了後も保持します。既存ライブラリのprojectを対象にしません。

参考：[Access JWT 検証](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)、[Tunnel token-file](https://developers.cloudflare.com/tunnel/reference/run-parameters/)、[サービス認証](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)。

ページ観測を使用している環境では、復元の各 Compose コマンドに `-f compose.observer.yaml` を追加し、停止対象に `observer` も追加します。[観測の起動と制限](observation.md) を参照してください。

第七段階以降、根拠を含むライブラリは DB／blob の一貫した `backup-bundle`／`restore-bundle` を使用します。旧 DB 単体の手順は根拠を持たない snapshot に限ります。現在の復元先は v7 になります。[根拠・添付・復旧の手順](evidence.md)を参照してください。
