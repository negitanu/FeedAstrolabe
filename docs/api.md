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

## 調査案件・メモ・共有タグ（第六段階）

すべての読み取りは read または write キー、変更は write キーが必要です。新しい API も既存のレート上限に従います。詳細は [OpenAPI](../feedastrolabe/static/openapi.json) と [ワークスペースの操作](research.md) を参照してください。

- `GET/POST /api/v1/workspaces`、`GET/PATCH /api/v1/workspaces/{id}`：案件一覧・作成・詳細・編集。作成は `title` 必須。`purpose`、`questions`、`status`（active/paused/completed）、`classification`（public/internal/restricted）、`archived`（JSON真偽値）を指定できます。
- `GET /api/v1/workspaces/{id}/feeds`、`GET /api/v1/workspaces/{id}/articles`：関連フィード／記事。記事は直接リンクとフィード経由を重複排除し、関連フィードの新着も含みます。
- `POST/DELETE /api/v1/workspaces/{id}/feeds/{feed_id}`、`.../articles/{article_id}`、`.../tags/{tag_id}`：既存IDの関連付け／解除。本文なし、成功204、同じ操作を再実行可能。元の購読・記事は変更しません。
- `GET/POST /api/v1/workspaces/{id}/notes`、`GET/PATCH /api/v1/notes/{id}`：メモ一覧・作成・詳細・版付き編集。作成は `title` 必須、`body`、`label`（fact/source-claim/hypothesis、既定hypothesis）、`archived` を指定できます。
- `GET /api/v1/notes/{id}/revisions`：変更できない完全な版履歴。履歴の cursor は記事IDの代わりに版番号を使います。
- `GET/POST /api/v1/tags`、`GET/PATCH /api/v1/tags/{id}`：共有タグ。変更本文は `{"name":"OSINT"}`。重複名は409。
- `POST/DELETE /api/v1/articles/{id}/tags/{tag_id}`、`.../notes/{id}/tags/{tag_id}`：記事・メモのタグ関連付け。

案件・メモ・タグ・版・関連フィードの記事一覧は `limit`、`before_id`、`after_id` と記事と同じ cursor 応答を使います。案件／メモ一覧は既定でアーカイブを除外し、`archived=true` でアーカイブのみ取得します。詳細はアーカイブ後も取得できます。案件／メモ一覧の `tag={id}`、記事一覧の `workspace={id}&tag={id}` で絞り込めます。存在しない案件／タグのフィルターは404です。

PATCH メモの例：

```json
{"expected_revision": 1, "body": "## 確認事項\n\n根拠を照合する。", "label": "hypothesis"}
```

`expected_revision` は正の JSON 整数で、変更項目が最低1つ必要です。保存は版番号を増やし、古い版による変更は409で原子的に拒否します。案件・メモの削除相当操作は `archived:true` です。アーカイブ済み案件は `{"archived":false}` だけで再開し、通常編集・関連変更・配下メモ編集は再開まで409です。メモ再開は `{"expected_revision":3,"archived":false}`。案件・メモの hard DELETE は提供しません。

## 根拠・出典（第七段階）

- `GET /api/v1/evidence`：本文を除く一覧。共通 limit／before_id／after_id に加えて workspace／note／article ID フィルター。案件への直接固定、案件内メモの固定、引用の和集合です。
- `GET /api/v1/evidence/{id}`：固定本文、版、出典URL、取得方法、公開／観測／保存日時、bytes とテキストのハッシュ。
- `GET /api/v1/evidence/{id}/download`：ハッシュ検証済み元ファイルを添付として取得。
- `POST /api/v1/articles/{id}/evidence`：空本文で現在の記事を backfill-now 保存（201）。同一内容は同じ ID を返します。
- `POST /api/v1/workspaces/{id}/attachments`：multipart の file 1件だけ。text／Markdown／PDF、10MiBまで。抽出・容量確認後に保存し案件へ固定（201）。
- `POST`／`DELETE /api/v1/workspaces/{id}/evidence/{evidence_id}` および `/api/v1/notes/{id}/evidence/{evidence_id}`：空本文で固定／解除（204）。アーカイブされた親は409。
- `GET`／`POST /api/v1/workspaces/{id}/quotations`：引用一覧／完全一致引用の保存（201）。POST JSON例：`{"evidence_id":1,"start":0,"end":8,"quote":"Original","note_id":null}`。位置は Unicode 文字数で、note_id は省略可能です。
- `GET`／`PATCH /api/v1/evidence-settings`：容量 bytes、保存日数、登録済み使用量、保存エラー先頭100件。PATCH例：`{"quota_bytes":524288000,"retention_days":90}`。

書き込みには write キーが必要です。根拠の本文や出典を上書きするAPIはありません。記事の `source_published_at` は情報源が明示した公開日時（不明時null）です。表示用 `published_at` の取得日時代用とは区別します。ファイル整合性不正や容量超過は保存せず400、固定本文ハッシュ不正の detail は409。上限超過のリクエストは413です。[保存・添付・復旧の手順](evidence.md)を参照してください。

## ウォッチと整理（第八段階）

- `GET`／`POST /api/v1/workspaces/{id}/watchlists`：条件一覧／作成（201）。作成例：`{"name":"CVE監視","query":{"any":[{"field":"text","op":"contains","value":"CVE-"}]},"priority":"high","reason":"利用製品の調査"}`。
- `GET`／`PATCH /api/v1/watchlists/{id}`：現行条件／新しい版。PATCHはexpected_revision必須、古い版は409。
- `GET /api/v1/watchlists/{id}/revisions`：条件の全版履歴（共通cursor一覧）。
- `GET /api/v1/watchlists/{id}/preview?after_id=0`：読み取りだけの照合、最大100根拠、next_after_idで続き。通知を作りません。
- `POST /api/v1/watchlists/{id}/reprocess`：空本文で現行版のcursorをリセットして最大100件再照合。`/process` はcursorを維持して続きの最大100件。
- `GET /api/v1/workspaces/{id}/watch-events`：採用／除外を含む受信箱。seen／included=true/falseと共通cursor一覧。
- `GET /api/v1/workspaces/{id}/digest?date=2026-10-08`：実在するUTC日付の採用通知。省略時は現在UTC日付。
- `PATCH /api/v1/watch-events/{id}`：`{"seen":true}`で確認状態を変更。
- `GET /api/v1/duplicate-groups?suppressed=false`：グループ一覧。`GET /api/v1/duplicate-groups/{id}` はメタデータ、`/{id}/members` は根拠と元の記事状態の共通cursor一覧。
- `PATCH /api/v1/duplicate-groups/{id}`：`{"suppressed":true}`で解除、falseで再び有効化。

変更・処理にはwriteキーが必要です。アーカイブされた案件への変更は409。グループ操作は共有ライブラリ全体へ適用します。包含・除外条件の構文、処理と保存期間は[ウォッチの手順](triage.md)を参照してください。

## 対象と関係（第九段階）

- `GET/POST /api/v1/entities`：対象一覧／登録。kindとliteral q、workspace、共通cursor。例：`{"kind":"domain","value":"example.com","display_name":"調査対象"}`。組織／製品／モデルの同名登録は別対象です。
- `GET /api/v1/entities/{id}`：現在の代表root_idを含む詳細。
- `GET/POST /api/v1/entities/{id}/aliases`：別名のcursor一覧／手動登録。`{"value":"別表記","reviewed":true,"author":"local-user"}`。reviewedの応答は0/1。
- `GET /api/v1/entities/{id}/mentions`、`GET /api/v1/evidence/{id}/mentions`：出典付き言及一覧。前者はworkspaceとfamily_truncated、後者はextraction（未処理null、truncatedは0/1）を返します。
- `POST /api/v1/evidence/{id}/extract-entities`：空本文で再抽出。人の訂正は維持します。
- `POST /api/v1/mentions`：`{"evidence_id":1,"entity_id":2,"start":0,"end":11,"original":"example.com","status":"confirmed","author":"local-user"}`。位置と元表記は固定本文の完全一致が必要。
- `GET/PATCH /api/v1/mentions/{id}`：詳細／訂正。例：`{"expected_revision":1,"status":"rejected","author":"local-user"}`。entity_idも訂正可能。原位置は変更不可。
- `POST /api/v1/entities/{id}/merge`：`{"target_id":2,"expected_revision":1,"reviewed":true,"reason":"手動照合","author":"local-user"}`。`/unmerge` はtarget_id／reviewedを除き現行版と理由で解除します。
- `GET /api/v1/entities/{id}/timeline`：監査cursor一覧、workspace、family_truncated。
- `GET /api/v1/entities/{id}/graph?workspace=1&depth=2&limit=200`：対象／引用付き関係／truncated。深さ0〜2、最大200対象／400関係。
- `GET /api/v1/relations`：workspace／entity／archivedとcursor一覧。
- `POST /api/v1/workspaces/{id}/relations`：`{"source_id":2,"target_id":3,"predicate":"observed-address","quotation_id":1,"label":"source-claim","confidence":"unknown","author":"local-user"}`。任意observed_at／valid_from／valid_toはUTC `YYYY-MM-DD HH:MM:SS` またはnull。引用は同じ案件に属する必要があります。
- `GET/PATCH /api/v1/relations/{id}`：現行版／新しい判断版。PATCHは正のexpected_revisionと変更項目が必要。archived:trueで表示をアーカイブ。
- `GET /api/v1/relations/{id}/revisions`：引用と判断を保持する不変版のcursor一覧。

読み取りはread/write、変更はwriteキー、通常のレート制限に従います。古いexpected_revisionは409、原子的に拒否します。関係・統合の意味と上限は[対象の手順](entities.md)、定義はOpenAPI 0.9を参照してください。

## セキュリティ情報・コネクター（第十段階）

- `GET /api/v1/connectors`：登録済みkev/epss/cveの設定・送信先・帰属・UTC日budget・cooldown。
- `PATCH /api/v1/connectors/{provider}`：`{"expected_revision":1,"enabled":true,"ttl_seconds":86400,"daily_budget":100}`。enabledはJSON真偽値、応答は0/1。初期停止。
- `POST /api/v1/connectors/{provider}/jobs`：`{"input":"CVE-2021-44228","public_identifier":true}`。kevだけinput=catalog。202で共有ジョブを予約、HTTP内で外部取得しません。任意URL／認証値不可。
- `GET /api/v1/connector-jobs`、`GET /api/v1/connector-jobs/{id}`：状態・試行・次の試行・安全なerrorコード。一覧はproviderと共通cursor。
- `GET/POST /api/v1/workspaces/{id}/security-watches`：案件の監視一覧／登録。例 `{"entity_id":1,"product":"Log4j","version":"2.0","outbound_public":true}`。製品と版はローカルのみ。
- `GET/PATCH /api/v1/security-watches/{id}`：独立したdated signals・適用性のカード／expected_revision付き設定編集。entity_id、product、version、outbound_public、enabledを変更可能。
- `POST /api/v1/security-watches/{id}/reviews`：`{"expected_revision":1,"status":"confirmed","quotation_id":1,"reason":"固定資料を確認","author":"local-user"}`。statusはconfirmed/possible/unknown、confirmedには同じ案件の引用必須。
- `GET /api/v1/security-watches/{id}/reviews`：判断の不変版cursor一覧。
- `GET /api/v1/entities/{id}/vulnerability`：kev/epss/cveのcurrent/stale/unknown、原観測日時、最終確認、出典版、直前成功レコード、固定根拠。未提供EPSSはscore=null。
- `GET /api/v1/entities/{id}/security-observations`：公開レコード投影の不変履歴cursor一覧。
- `GET/POST /api/v1/workspaces/{id}/security-references`：引用と手動確認付きの参照一覧／作成。`{"entity_id":1,"url":"https://example.com/advisory","kind":"advisory","quotation_id":1,"reviewed":true}`。kindはadvisory/fix/poc。リンクを取得・実行しません。

read/writeキーと既存APIレート制限、CSRF、親案件アーカイブ、409競合に従います。各項目の意味・帰属・上限・staleは[運用手順](security-intelligence.md)とOpenAPI0.10を参照してください。

第十一段階のネットワークウォッチ、固定観測、項目別変化、空bodyでの照会予約をOpenAPI0.11へ追加しました。[操作と取得制限](network-intelligence.md)を参照してください。

第十二段階の研究ウォッチ／版／モデルカード／明示レビュー済み関連資料／条件付き評価比較をOpenAPI0.12へ追加しました。[操作と上限](ai-research.md)を参照してください。
