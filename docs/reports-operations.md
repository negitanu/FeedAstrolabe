# レポートと運用

`/operations` に出力・通知・ワーカー状態・バックアップをまとめました。schema13。通知先と定期バックアップは初期状態で未設定／無効です。通常の収集ワーカーが承認済み通知と予約済みバックアップを1件ずつ処理します。単発は `flask --app feedastrolabe operation-jobs`。

## 引用付き出力

案件の固定資料IDを1〜100件選択（空欄は最大100件）、Markdown／引用マニフェスト／JSON／CSV／STIX2.1対応範囲を保存・ダウンロード。各本文20000文字、出力全体4MiB、保存10000件まで。保存後のpayloadとSHA-256、引用元のID・本文hash・blob hash・capture/observation/publication日時は不変です。CSVは先頭の式記号、空白後の式記号、tab／改行をapostropheで保護。Excel等へ加工する際も安全な文字列として扱ってください。

通常はpublic案件だけ。internal/restricted案件、非公開案件でも参照される資料は除外します。明示したローカル用の非公開選択は保存できますが、そのレポートの通知は拒否します。対象・network/security観測は選択した資料からの記録だけを収録。任意の案件メモ・資格情報・APIキー・添付ファイル本体は含みません。既知のtoken／password／private key等の疑いは拒否します。未知の秘密情報を完全検出する保証はなく、公開区分とプレビューも確認してください。

STIXは[OASIS STIX2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html) の限定対応です。domain→domain-name、IPv4/IPv6→ipv4-addr/ipv6-addr、AS→autonomous-system、CVE→vulnerability、引用マニフェスト→noteをbundleに格納。UUIDv4、SDOのcreated/modified、noteの内部参照を設定し、OASIS公式 `stix2==3.0.2` parserで独立検証しました（検証用一時環境のみ、製品依存なし）。model/product/repository/hash等はSTIXに無理に変換せず、JSON/CSVを使います。言及の候補と確認済み事実は同一ではなく、indicator／relationship／TAXIIの全面対応を主張しません。

## 承認した通知

設定は最大20件、正確なHTTPS443 endpoint（query／fragment／userinfoなし）または単一メールアドレスを許可リストとして登録。WebhookパスはASCII200文字・各segment23文字以内。認証tokenをURLに埋め込むSlack/Discord型Webhookは対象外で、独立した署名検証の受信先を使います。新規UI設定は停止状態。宛先は固定で、変更する場合は別設定を作成。有効化だけでは送信しません。レポートの通知プレビューは正確なUTF-8 JSON payload・hash・宛先・設定版・30分期限を表示します。write API/UIの明示承認とhash照合で1ジョブを作成。同プレビューの承認は同じジョブを返し、成功済みの通知は再送しません。

送信直前にも公開区分・共有資料の区分・根拠hash・秘密情報・通知先設定版を検証。設定変更や公開→非公開への変更で停止。競合を避けるため送信中のwriterを直列化し、他の書き込みは短時間待機／busyになる場合があります。本文・認証値・応答本文を監査ログへ保存せず、試行番号・状態・安全なerror code・開始終了だけを記録します。

Webhookは公開DNSを毎回検証してTLS接続先を固定し、proxy／redirectを使いません。`X-FeedAstrolabe-Signature: sha256=...` は正確なbodyをHMAC-SHA256署名、`Idempotency-Key` は全試行共通のジョブUUID。受信側で署名検証・重複抑止を実装してください。明示的な429/503のみ最大3回、120／240秒待機で再試行。受信側が失敗応答前に処理した場合の重複は受信側の冪等制御に依存します。成功後は再送なし、タイムアウト／中断／不明なSMTP結果は送達不明として停止し、自動再送しません。SMTPは公開DNSの固定TLS465、送信元・正確な宛先・安定したMessage-ID、応答64行／64KiB／30秒期限とsocket10秒上限。平文やTLS検証回避なし。

運用者の `FEEDASTROLABE_DELIVERY_CONFIG_FILE` はowner-only0600の通常JSONファイル（16KiB以内）、symlink不可。内容は `destinations` の正確な宛先配列、Webhook用 `webhook_secret`（32文字以上）、メール用 `smtp` object（host／port465／sender／username／password）。資格情報はDB/UI/Gitに入力しません。既存Git除外のsecrets/、instance/やprivate volumeを使い、実値をシェル引数・履歴に貼り付けないでください。

コンテナは任意の `compose.delivery.yaml` を追加し、private volume `/data/delivery-config.json` をアプリUID10001所有・0600で事前作成します。ファイルベースCompose secretsのUID制限回避は行わず、アプリ所有のファイルとして配置してください。この追加composeは既定環境には適用していません。実際のSMTP／Webhookアカウントと宛先の接続は未設定・未確認。検証は合成本文と模擬transportだけで、利用者の資料を外部へ送りません。

## 世代バックアップと復元

予約をworkerが処理し、既存のDB＋全参照blob＋manifest bundleを作成して再検証。公開／非公開を含むライブラリ全体をバックアップするため、private保存を維持してください。`/data/backups/backup-<UUID>` は0700、DB／manifest／blobsは0600。初期は定期無効、間隔86400秒、7世代、合計4GiB。間隔3600〜604800秒、1〜30世代、合計1MiB〜100GiB、1世代2GiB上限。作成前にDBとblobサイズ・余裕1MiBを予約し、作成後にも実容量を検査。容量不足で止まるため、上限には新旧両世代を置ける余裕を確保してください。

作成後、履歴にある古い世代のmanifestと全blobを再検証してから保存期間終了分を削除。不明な保存物、symlink、破損は勝手に削除せず安全な失敗として残します。中断した世代はfailed、成功扱いしません。バックアップ内には取得時点の自身のrunningジョブが含まれ、復元後の初回処理でinterruptedになる場合があります。定期実行の結果は運用画面とAPIで確認できます。別媒体へのコピーも行ってください。

復元はUI/APIに用意していません。Webとworkerのプロセス生存中は共有runtime.lockを保持し、CLI復元は排他ロックを要求するので、sleep中のworkerやWebだけ稼働中でも拒否します。全blob、引用の固定位置、生成入力、レポートと通知hash、FK・DB整合性を検証後に置き換えます。旧DB schemaにも対応する画像とバックアップを併せて保管してください。

```sh
docker compose -p feedastrolabe -f compose.yaml -f compose.local.yaml -f compose.observer.yaml stop web worker observer renderer
# 対象世代のパスを確認してから、停止状態のライブラリへ復元。
docker compose -p feedastrolabe -f compose.yaml -f compose.local.yaml -f compose.observer.yaml run --rm --no-deps -T web python -m feedastrolabe.maintenance restore-bundle /data/backups/backup-REPLACE_WITH_GENERATION
docker compose -p feedastrolabe -f compose.yaml -f compose.local.yaml -f compose.observer.yaml up -d --wait
```

CLIは残存WALも拒否します。サービスを停止してSQLite checkpointを完了したうえで再実行。worker/APIを起動したままロックファイルを削除する回避はしないでください。復元元の世代自体は置き換え対象DBとは別ディレクトリです。

## 運用とAPI

ワーカーのstart／end／processed／安全なerror code、最後のheartbeatと10分のstale判定、ジョブ履歴を表示。本文や照会URL／tokenはhealthへ出しません。直近100件をUI、worker履歴は1000件保持、APIはcursor最大100件。unknown/staleは独立した監視判定で、`/healthz` のWeb疎通とは区別。CI `.github/ci-template.yaml` はworkflow権限待ちで未稼働、現在のOAuth権限を拡張していません。

settings PATCHは指定フィールドを既存値と合わせ全体検証して保存。poll_interval60〜86400、page_size10〜100、api_rate_limit1〜1000、polling_enabled boolean、default_view all/unread/starred。一括記事状態は1〜100 unique positive IDs、is_read/is_starred booleanで全ID存在確認後に原子的更新。readキーや101件、1件でも未知IDなら変更なし。

OPMLはXML1MiB、最大100購読、DTD/entity禁止、public URL形式、local/private拒否。全入力を検証後に原子的に登録し、重複URLはskipped。即時取得はせず通常RSSワーカーが後でDNS／public IPを検証。エクスポートはRSSのみでSNS/pageを含みません。APIキー発行は従来どおり設定UI限定で、既存キーのscopeは自動拡張しません。全APIはBearerのread/writeと既存のrate制限を使います。
