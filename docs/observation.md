# Playwright ページ観測

公開されたログイン不要のページの指定要素を観測します。`/settings#pages` で URL、標準 CSS セレクター、描画待機（0〜10秒）、間隔（60〜86400秒）、保存期間（1〜365日、既定90日）を登録します。同じ URL でも異なるセレクターを登録できます。

初回は基準保存だけを行います。要素の innerText を DOM 順に取得し、Unicode NFKC、行内空白の統一、空行除去を行って比較します。変化時は差分と現在の本文を記事として保存します。A→B→A は2件、変化なしは0件です。セレクターや待機時間を変更すると基準を取り直し、既存記事は保持します。エラー時にも前回基準を保持します。

通常の RSS/SNS と同じ閲覧・既読・スター・検索が使えます。成功した観測時に保存期間を過ぎた未スターの観測記事を削除します。スター済み記事は保持します。保存する基準は最新1件で、スクリーンショットや Cookie は保存しません。

## コンテナ起動

```sh
docker compose up --build -d --wait
```

標準の `compose.yml` でCloudflared Tunnel、Web、RSS/SNS worker、observer、rendererが起動します。UIは設定した公開URLへCloudflare Access経由でアクセスします。observer は10秒ごとに期限到来と手動予約を調べ、直列に観測します。Web/API の登録時はアクセスせず、手動更新も予約だけを行います。同じ購読の予約は重複せず、手動予約は pause 中にも実行されます。失敗時は安全なエラーと再試行待ち時間を表示します。

renderer は非 root、read-only、capabilities 無効、ネットワークなし、DB/秘密情報のマウントなしで起動します。メモリー512 MiB、CPU 1、PID 128、ジョブ45秒の上限を持ちます。通常の Chromium 自身の sandbox が有効であるとは主張せず、OS コンテナ境界で隔離します。renderer に共有するのは Unix ソケットのボリュームだけです。

同一 origin の GET だけを observer が public IP 検証・DNS pinning して仲介します。リダイレクト、Cookie、認証ヘッダー、POST、iframe、WebSocket、Service Worker、画像・動画・フォントを許可しません。1観測50リクエスト、全20 MiB、各5 MiB、取得予算30秒、テキスト5万文字です。クロス origin CDN を必要とするページは描画に失敗する場合があります。要素の消失・空テキスト・無効な CSS は記事を生成せずエラーになります。

## API

読み書きキーで `POST /api/v1/feeds` に次の JSON を送ります。

```json
{"source_type":"page","url":"https://example.com/","selector":"h1","settle_ms":1000,"poll_interval":900,"retention_days":90}
```

`POST /api/v1/feeds/<id>/observe` は観測予約を202で返します。`GET /api/v1/articles?source_type=page` で差分記事を取得できます。購読一覧は `has_baseline` を返しますが、基準本文や内部の識別用 URL fragment は返しません。詳細は [OpenAPI](../feedastrolabe/static/openapi.json) を参照してください。OPML は引き続き RSS/Atom のみです。

## native 起動と復旧

開発用 native 起動は OS ネットワーク隔離を提供しないため、通常利用は上記 Compose を推奨します。

```sh
.venv/bin/python -m pip install -c requirements.txt --group renderer
.venv/bin/python -m playwright install --with-deps --only-shell chromium
FEEDASTROLABE_RENDER_SOCKET=/tmp/feedastrolabe-render/renderer.sock .venv/bin/python -m feedastrolabe.renderer
# 別ターミナル、Web と同じ FEEDASTROLABE_DATA_DIR を使用
FEEDASTROLABE_RENDER_SOCKET=/tmp/feedastrolabe-render/renderer.sock .venv/bin/python -m flask --app feedastrolabe observer-worker
```

依存の選択にはpip 25.1以上を使用します。開発環境として `-r requirements.txt` を導入済みなら、ブラウザー本体のインストールから実行できます。コンテナでは単一の `Dockerfile` の `renderer` targetに必要な依存とheadless shellを含めています。

schema v4 は既存の RSS/SNS、記事 ID、既読・スター・キーを保ったまま移行します。移行前に [backup/restore 手順](deployment.md) で SQLite backup を保存してください。復元時は Web、worker、observer を停止してください。旧版へ戻すときは旧イメージと移行前バックアップを組み合わせます。v4 DB を旧イメージに渡さないでください。

実装の参考：[Playwright network](https://playwright.dev/python/docs/network)、[browser installation](https://playwright.dev/python/docs/browsers)、[Docker guidance](https://playwright.dev/python/docs/docker)。
