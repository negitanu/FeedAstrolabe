# SNS フィード

設定画面の「SNS を購読」で登録します。登録時はネットワークへ接続せず、worker の次の巡回またはライブラリの手動更新で取得します。各購読の間隔・停止・フォルダー・削除は RSS と同じ操作です。全体の定期収集を停止している場合は手動更新してください。

## 対応対象

- X アカウント：ユーザー名（@ 省略可）または数値ユーザー ID。名前は初回に ID を解決して保存します。
- X リスト：数値リスト ID。`https://x.com/i/lists/<ID>` の ID 部分を指定します。
- Mastodon：`https://mastodon.social` のような公開 HTTPS サーバーと、そのサーバーのローカルユーザー名。公開・未収載投稿だけを保存します。認証必須のサーバーは対象外です。

投稿・DM 送信、ホームタイムライン、非公開 Mastodon 投稿、ブラウザーによる SNS スクレイピングは実装対象に含みません。

## X の認証

X Developer Console で必要な読み取り権限を持つ Bearer token を用意します。リストの取得には利用する認証方式に応じて `tweet.read`、`users.read`、`list.read` が必要です。利用資格・残高・権限は契約とトークンに依存します。API は従量課金方式なので、Console の利用上限と料金を確認してから購読を有効にしてください。本実装はトークンの発行・OAuth ログイン・支払い設定を行いません。

トークンはチャット、Git、コマンド引数、購読 URL、環境変数の値へ貼らず、`secrets/x-bearer-token.txt` に安全なエディターで保存します。ファイルはトークン一つだけ（末尾改行可）とします。`secrets/` は Git 管理外です。

```sh
mkdir -p secrets
chmod 700 secrets
# エディターで secrets/x-bearer-token.txt を作成
chmod 600 secrets/x-bearer-token.txt
export FEEDASTROLABE_X_TOKEN_FILE="$PWD/secrets/x-bearer-token.txt"
```

native の Web と worker に同じファイルパスを設定します。シンボリックリンク・別ユーザー所有・他ユーザーが読める native ファイルを拒否します。パスだけを環境変数で指定し、トークン自体は DB に保存しません。次の取得でファイルを読み直すので、トークン交換時はファイルを安全に置換してください。

Docker では UID 10001 のプロセスがファイルを読む必要があります。Docker Compose の file-backed secrets は UID/mode の書き換えを保証しないため、ホストの親ディレクトリは700、コンテナ用ファイルは644にします。ホストの他ユーザーは親ディレクトリを通れません。Docker 管理権限を持つユーザーは信頼境界内です。

```sh
chmod 700 secrets
chmod 644 secrets/x-bearer-token.txt
docker compose -f compose.yaml -f compose.local.yaml -f compose.social.yaml up --build -d --wait
```

トークンは Web/worker の `/run/secrets/feedastrolabe_x_token` へ読み取り専用でマウントされます。コンテナに通常のホストファイルパスを指定する場合は600で読める所有者に設定してください。Mastodon だけなら追加 Compose ファイルは不要です。Cloudflare 用構成へも `compose.social.yaml` を追加できますが、実 Cloudflare 接続は後段のタスクです。

## 収集と保持

初回は最近の X 最大100件／Mastodon 最大40件を取得し、その時点を基準にします。過去記事を全件収集する機能ではありません。以降は一度に最大3ページずつ差分を取得します。ページごとに投稿と続きの位置を同一トランザクションで保存し、途中失敗・再起動後も続きを取得します。すべての差分ページを終えるまで基準 ID を進めません。X リストは `since_id` 非対応のため、既存の基準 ID に到達した時点でページングを終了します。

投稿 ID で重複を防ぎ、同じ ID を再取得した場合は本文を更新して既読・スター状態を保持します。削除・編集・リストへの古い投稿の追加を全件再同期する機能はありません。提供側の履歴制限や cursor 失効により、長期間停止した後は欠落する可能性があります。cursor エラーを黙ってリセットせず、設定画面にエラーを表示します。

429 は Retry-After／レート reset を考慮して待機します（既定待機15分、上限7日）。同じ X トークンを使う全購読を待機させ、手動更新でも待機を守ります。他の失敗は既存の指数バックオフに従います。HTTP401/403は認証・権限のエラーとして表示します。投稿本文は HTML を無害化し、画像・埋め込みリソースは取得しません。

投稿は既存の `/api/v1/articles` で取得できます。`source_type=x` または `source_type=mastodon` で絞り込めます。OPML は RSS の購読だけをエクスポートします。SNS 設定と記事は SQLite バックアップに含まれ、X トークンは別途安全に保管します。

## 公式資料（2026-10-08 確認）

- [X アカウントの投稿](https://docs.x.com/x-api/users/get-posts)
- [X リストの投稿](https://docs.x.com/x-api/lists/get-list-posts)
- [X 料金・利用上限](https://docs.x.com/x-api/getting-started/pricing)
- [Mastodon アカウント・公開投稿 API](https://docs.joinmastodon.org/methods/accounts/)
