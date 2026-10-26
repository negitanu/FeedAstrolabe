## Context

初版にはRSSと案件/根拠があり、SNS/AIは未実装。ユーザーの最終目的は元版フル機能の移植であり、初版のnon-goalsは恒久的な対象外ではない。

## Goals / Non-Goals

**Goals:** SNS投稿から読む/調査/話題抽出まで、日本語UIで利用可能にする。Ollama補助は選択根拠のプレビュー→明示承認→永続ジョブ→固定引用結果→レビューの経路を実装。

**Non-Goals:** この変更ではページ観測・専門情報・対象グラフ・通知・DB移行ツールは追加しない。これらはフル移植計画の未完了項目として追跡する。実キーの発行・有料生成・モデルの自動pullは行わない。

## Decisions

- SNS定義はfeedに付随する別テーブル。social:hashの内部IDを使い、既存記事一覧・既読・スター・並び順を共用。RSS OPMLにはSNSを含めない。
- 固定Bluesky searchPosts（top/latest各100）、Mastodonタグ最大3×40、account lookup後最大3×40。HTTPS公開IP固定・redirect拒否・identity・5MiB。失敗は回全体を保存せず、429はサービス単位で共有待機。定期最小15分、エラーbackoff、成功履歴30回。
- 設定はprovider別JSONと版。OpenRouter/OrcaRouterとOllama local/cloudを同じ接続UIに置く。OpenRouter/OrcaRouterのactive選択はOllama設定の編集で変えず、調査補助と独立させる。routerには固定モデル/構造化出力/単価上限、Orca固有usage/cost照会。資格情報はGoの環境変数または0600token fileだけ。
- APIでpreviewと予約のみを行い、Go workerが1件ずつ処理。各jobはprovider/config/input/hash/保守的費用予約を固定し、dedupeを持つ。再起動時runningはfailed。claim後の送信トランザクション開始時はstate/hash/configをCAS照合し、間に復元が割り込んでも再起動しない。失敗・不明費用は予約を戻さず、生成POSTを再送しない。日次予算は全provider共通で切替不能。
- public/internal/restrictedの案件区分を追加。初版からの案件はpublic（既存挙動互換）、変更時はcase版を更新。クラウド送信は同一記事/本文hashが非公開案件に関連する場合拒否。SNS入力は最大20×400文字、32KiB。案件補助は最大8根拠×1200文字、入力byte+256<=8192。プレビュー30分、hash/profile/case/evidenceを実行直前再確認。
- 送信直前から完了まではSQLite単一接続のトランザクションで分類変更を排他。外部送信には認証値らしい文字列の検査。モデルにtools/search/filesystemを渡さず出力の引用ID/usage/finishを検証。
- ローカルOllamaだけ固定127.0.0.1:11434を例外許可。/api/status cloud.disabled、/api/tags digest/remoteなし、/api/versionを生成前に照合。クラウドは固定ollama.com、tokenは0600 regular fileを所有者確認して読む。署名/host/certificate検証は無効化しない。
- backup2には新テーブルを追加しbackup1は空の追加テーブルへ補完。復元時config.enabledとsocial.aiEnabledを無効にし、queued/runningはfailed。キーや実行先の任意URLを保存/復元しない。移行前は整合したschema1のJSONバックアップを自動取得。

## Risks / Trade-offs

- [APIのサービス契約差] → provider固有payload/usage/costを分離し、模擬HTTPで検証。公式仕様との差を文書化。
- [有料POSTの不確定失敗] → 予約維持、再送なし、ユーザーは新入力で再承認。
- [分類変更と送信の競合] → 送信中DB書込み排他。UIは最大90秒待機する可能性を説明。
- [フル移植は複数段階] → docs/full-port-plan.mdで元仕様との対応と未完了を追跡。今回の完了をフル移植完了と表示しない。
