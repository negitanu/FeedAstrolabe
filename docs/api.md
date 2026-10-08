# FeedAstrolabe API v1

設定画面 `/settings` から API キーを発行します。既定は読み取りのみ・90日。書き込み権限を選ぶと購読追加と記事状態の更新ができます。キー全文は発行時の応答だけに表示し、再表示できません。紛失した場合は旧キーを失効させて再発行します。

全エンドポイントで `Authorization: Bearer <API_KEY>` が必要です。キーを query parameter に入れる方式はありません。UI の cookie による API 認証もありません。キーごとのリクエスト上限は設定画面から変更できます（既定120回/分、1〜1000）。

## 読み取り

- `GET /api/v1/feeds`：購読一覧。`data` はフィードオブジェクトの配列。
- `GET /api/v1/feeds/{id}`：購読の詳細。URL、フォルダー、収集有効/無効、個別間隔、最終取得、連続失敗とエラー。
- `GET /api/v1/articles`：記事一覧。
- `GET /api/v1/articles/{id}`：記事の本文と既読・スター状態。

記事一覧の query：

- `limit`：1〜100、既定30。
- `feed`：フィード ID。
- `source_type`：`rss`、`x`、`mastodon`、`page` で記事を絞り込み。
- `is_read`、`is_starred`：`true` または `false`。
- `q`：タイトル/本文の部分一致、最大200文字。`%` と `_` も文字として検索。
- `before_id`：この ID より小さい記事を ID 降順で取得。
- `after_id`：この ID より大きい新規記事を ID 昇順で取得。0から初回の同期も可能。

`before_id` と `after_id` は同時に指定できません。通常取得は ID 降順です。Web UI の公開日時順とは並びが異なります。

```json
{
  "data": [
    {
      "id": 1,
      "feed_id": 1,
      "guid": "entry-guid",
      "title": "記事のタイトル",
      "link": "https://example.com/article",
      "content": "<p>安全に整形した本文</p>",
      "published_at": "2026-10-08 00:00:00",
      "is_read": false,
      "is_starred": true,
      "feed_title": "Example"
    }
  ],
  "has_more": false,
  "next_before_id": null,
  "next_after_id": null
}
```

通常ページ送りは `has_more=true` の間 `next_before_id` を次の `before_id` に指定します。新規記事同期では `next_after_id` を保存し、次の `after_id` に指定します。順序は昇順なので大量の新着があっても小さい ID を取り逃しません。既存記事の本文更新・既読変更は新規 ID を生成しません。変更検出が必要な場合は個別記事か通常一覧を再取得します。

時刻は UTC の `YYYY-MM-DD HH:MM:SS`。本文は表示用 HTML ですが、独自クライアントでも適切なサニタイズ/CSPを使用してください。

## 書き込み

`write` キーが必要です。JSON リクエストは `Content-Type: application/json` を指定します。

`POST /api/v1/feeds`

```json
{"url":"https://example.com/feed.xml","folder":"テクノロジー"}
```

初回取得に成功すると201、登録済みは409。通常の HTML URL からフィードを探索する機能はありません。同期取得のためクライアント側に十分なタイムアウトを設定してください。定期取得は worker が担当します。

SNS の登録も同じエンドポイントを使います。ネットワーク取得を行わず201で登録し、worker または UI の手動更新で取得します。認証トークンなど未定義のフィールドは拒否します。

```json
{"source_type":"x","source_kind":"account","target":"username","folder":"SNS"}
```

```json
{"source_type":"x","source_kind":"list","target":"123456789","folder":"SNS"}
```

```json
{"source_type":"mastodon","source_kind":"account","target":"alice","instance_url":"https://mastodon.social","folder":"SNS"}
```

購読応答に `source_type`、`source_kind`、`target`、`instance_url`、`provider_id`、`retry_at` が追加されます。記事応答にも `source_type` を追加。内部ページ cursor と認証トークンは返しません。詳細は [SNS 連携手順](social.md) を参照してください。

`PATCH /api/v1/articles/{id}`

```json
{"is_read":true,"is_starred":true}
```

片方のフィールドだけの指定も可能。true/false の JSON boolean のみを受け付けます。記事の本文やタイトルは変更できません。キーの発行・失効は UI で管理します。

## 呼び出し例

秘密情報は環境変数 `FEEDASTROLABE_API_KEY` に設定したものとして示しています。

```python
import json
import os
import urllib.request

request = urllib.request.Request(
    'http://127.0.0.1:5000/api/v1/articles?is_read=false&limit=20',
    headers={'Authorization': 'Bearer ' + os.environ['FEEDASTROLABE_API_KEY']},
)
with urllib.request.urlopen(request, timeout=45) as response:
    articles = json.load(response)['data']
```

外部の Cloudflare Access 配下で使用する場合、公開 hostname と追加の `CF-Access-Client-Id` / `CF-Access-Client-Secret` ヘッダーが必要です。Zero Trust でこのサービス認証を許可する Service Auth policy を作成してください。Cloudflare の service token とアプリの Bearer key は別の資格情報で、両方を通過する必要があります。

## エラー

```json
{"error":{"code":401,"message":"Invalid or expired API key"}}
```

400 入力不正、401 キー無効/期限切れ/失効、403 write 権限不足または Access 認証失敗、404 対象なし、409 重複、413 サイズ超過、415 JSON形式不正、429 回数上限、502 取得先通信失敗。401 には `WWW-Authenticate: Bearer`、429 には `Retry-After`（次の1分 window までの秒数）が付きます。未許可 Host は Flask の400となります。

OpenAPI 定義は [openapi.json](../feedastrolabe/static/openapi.json) にあります。

参考：[Cloudflare サービス認証](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)。

## ページ観測

`POST /api/v1/feeds` は `source_type: "page"` と `url`、`selector`、`settle_ms`、`poll_interval`、`retention_days` を受け付けます。登録時は取得せず201で返します。書き込みキーの `POST /api/v1/feeds/{id}/observe` は専用ワーカーへの予約を202で返します。記事一覧の `source_type=page` で差分記事を取得できます。基準本文は購読 API に含めません。設定と制限は [観測手順](observation.md) を参照してください。

## 購読の変更・削除・手動更新（第五段階）

書き込みキーで `PATCH /api/v1/feeds/{id}` を呼ぶと設定を部分変更できます。未指定の設定は保持します。`folder` は80文字以下、`enabled` は JSON boolean、`poll_interval` は60〜86400秒の整数または `null`（全体設定を継承）です。

```json
{"folder":"技術","enabled":true,"poll_interval":1800}
```

RSS とページ観測は `url` も編集できます。ページ観測では `selector`、`settle_ms`、`retention_days` を変更できます。URL は認証情報を含まない公開 HTTP(S) URL に限定します。編集時は取得せず、次回収集で公開 DNS を検証・pin します。SNS の取得対象、source_type は変更できません。

```json
{"url":"https://example.com/new-feed.xml"}
```

URL 修正後も購読・記事 ID と既読・スターは保持します。RSS は ETag/Last-Modified をリセットして次回は無条件取得。ページ観測の URL・セレクター・待機時間を変えると次回は新しい基準だけを保存し、過去記事と変更番号は保持します。フォルダー・保存期間だけの変更では基準を保持します。RSS の GUID が同じ記事は引き続き同一記事として扱います。

不正な設定は400、同じ取得対象の重複は409、存在しない ID は404です。複数設定のうち一つが不正でも、部分的には保存しません。RSS/SNS が収集中の編集・削除・同期更新は409で再試行します。

`DELETE /api/v1/feeds/{id}` は購読とその全記事・観測予約を削除し204（本文なし）を返します。スター記事も削除対象です。必要な場合はバックアップを保存してください。

`POST /api/v1/feeds/{id}/refresh` はすべての情報源で使えます。RSS/SNS は同期処理で200、`data.succeeded` / `data.failed` と最新の `data.feed` 状態を返します。失敗件数が1の場合は feed.error を確認してください。タイムアウトは通常取得処理の上限を考慮し、クライアントに余裕を持たせてください。通常の継続収集は worker を利用します。

ページ観測は202で `queued: true` を返し、専用 observer が処理します。既存 `/observe` も引き続き使えます。手動更新は pause 中にも実行できますが、SNS のプロバイダー待機中は429と `Retry-After` 秒数・`retry_at` を返し、外部 API を呼びません。

設定画面の「フィード別の収集設定」に URL 修正フォームがあります。API と同じ検証を使い、CSRF を必要とします。
