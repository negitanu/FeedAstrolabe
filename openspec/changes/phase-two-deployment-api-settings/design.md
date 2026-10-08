## Context
第一段階は localhost の Flask/SQLite リーダー。DB と既読/スター状態を維持しながら、第二段階と追加の API・設定機能を導入する。

## Goals / Non-Goals
**Goals:** 非 root コンテナ、永続化、Cloudflare Access 検証、キー付き API、設定と OPML。
**Non-Goals:** SNS と Playwright は後続段階。今回は SaaS 型の複数ユーザー分離を導入しない。すべての Access 許可ユーザーは同じライブラリの管理者となる。

## Decisions
- Compose の web/worker は同一イメージ、named volume、read-only root、cap_drop、no-new-privileges。通常構成はポートを公開せず、ローカル override だけ 127.0.0.1:5010 を使用。Cloudflare profile は token-file secret と access mode を明示する。
- Access mode は local/cloudflare を環境変数で固定。cloudflare では team domain を HTTPS cloudflareaccess.com に限定し、PyJWT の JWKS cache と RS256、issuer、audience、expiry、iat 検証を使う。認証不成立や JWKS 障害は fail closed。healthz は最低限の生存情報のみを返す。Secure cookie と trusted host は公開設定に連動。
- API は /api/v1。Authorization: Bearer を必須とし、UI セッションによる代替認証や query key は認めない。JSON mutations はキーで認証し、UI POST の CSRF 保護は維持。API を外部から呼ぶ際は Access の service token と API key の両方を必要とする。
- 256 bit ランダム API キーを一度だけ発行画面に表示し、DB には SHA-256 digest と識別 prefix のみ保存。read/write scopes、有効期間 1〜365 日（既定90）、失効、最終利用時刻を持つ。発行・失効は UI のみ。キー単位の固定1分 window で atomic DB rate limit。
- 記事 API は ID による cursor と max100 の limit。通常は ID 降順、after_id を使う新規記事同期は ID 昇順。既存記事の更新検出は cursor の対象外なので必要なら再取得する。UI の publication date 順は維持。
- SQLite version2 migration は init lock 内のトランザクションで実施し、既存テーブルの設定列と settings/api_keys を追加。ページ件数30、default view all、interval900 を既定とし、第一段階互換を保つ。
- worker は処理中の取得が完了してから10秒刻みで永続設定を読み、due-only 収集。interval60〜86400、個別指定または全体既定、global/per-feed pause。失敗時は指数バックオフを最大24時間まで実施し手動更新はdue制約を受けない。旧 --interval は明示指定時に全体既定を上書きする。
- OPML は defusedxml と最大100フィード・1MiB。インポートではネットワーク取得せず購読だけを登録してworkerへ委ね、重複を飛ばす。全URLを先に検査し入力エラー時は全体を追加しない。export は資格情報を含めない。
- 自動記事削除は今回導入しない。スターや未読の保持を優先し、保存期間は別変更で再取込み抑制を含めて設計する。

## Risks / Trade-offs
- Cloudflare 設定なしでは外部の実利用検証はできない → JWT を生成した受入テストとローカル Compose 検証を行い、実接続確認を別の未完了タスクとして記録。
- 同期購読追加や手動更新は遅い配信先で待つ → API タイムアウトと呼び出し方法を文書化、通常更新はworker。
- 全許可ユーザーが管理者 → Access の許可範囲を限定し、複数ユーザー分離は後続で設計。
- ローカル Docker secret はホストの通常ファイル → secrets/ をGit除外し、file permission とtoken rotationを文書化。

## Migration Plan
既存DBのbackup APIでsnapshotを取得し、停止後にversion2へ更新する。backup/restoreコマンドと復旧手順を提供。旧コードへの復帰はsnapshotを復元して行う。composeのvolumeはdownで残し、down -vは運用手順に含めない。

## Open Questions
公開ドメイン、team domain、AUD、Tunnel token、許可メール、稼働ホスト。資格情報未確定でもコンテナとAPI/設定の検証は独立して完了できる。
