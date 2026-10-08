# 受動的なネットワーク情報（第十一段階）

案件で公開ドメイン／IP／ASNを対象として登録し、ネットワーク画面からウォッチを作ります。対象と照会入力は作成後固定。変更時は別のウォッチを作成します。公開識別子送信の許可と共通連携設定の有効化が必要です。初期状態で全連携停止。案件・メモ・添付は送信しません。対象へのポートスキャン、TLS接続、設定変更は行いません。

DNSはA/AAAA/MX/NS/TXT/SOA/CAAだけを[Google Public DNS JSON](https://developers.google.com/speed/public-dns/docs/doh/json)へ照会。ECSは0.0.0.0/0。照会時刻、回答TTL、DNSSEC判定、応答範囲を保存し、TTL経過で古い観測と表示します。TTL低下だけでは回答変更イベントを作りません。NXDOMAIN/NODATAは照会範囲の応答で、SERVFAILや取得失敗を不存在へ変換しません。負の回答の有効期間を推測しません。

RDAPは[IANA bootstrap](https://www.iana.org/assignments/rdap-dns)の最新キャッシュから最も具体的な管轄を選び、レビュー済みHTTPS基点（5 RIR、Verisign com/net）だけを使います。IANA連携も有効にしてください。未対応登録局、より具体的な未承認の管轄、redirect/referralは追跡せず失敗として保持。連絡先vCardは観測の正規化値から除外します。共有cacheは公開応答原文を保持するため、原文に公開登録情報が含まれることはあります。

[RIPEstat network-info](https://stat.ripe.net/docs/data-api/api-endpoints/network-info)と[announced-prefixes](https://stat.ripe.net/docs/data-api/api-endpoints/announced-prefixes)はRISから見えたprefix/originと照会範囲を記録します。空の回答は世界全体の未使用を意味しません。[RPKI validation](https://stat.ripe.net/docs/data-api/api-endpoints/rpki-validation)は明示した正規prefixとoriginの組を検証します。valid/invalid/unknownはこの組の評価であり、所有者や経路乗っ取りを認定しません。取得上限は[RIPEstat利用条件](https://www.ripe.net/about-us/legal/ripestat-service-terms-and-conditions)を参照。

[crt.sh運営者のJSON仕様](https://github.com/crtsh/certwatch_db/issues/56)に従いexact domainを照会します。証明書掲載・発行・SAN・日付・発行者のメタデータだけを記録し、稼働中endpointを確認しません。最大200証明書、先頭1000行を処理し上限到達を表示。サービス保証や完全な網羅性は仮定しません。今回の実接続は取得失敗で未確認、JSON処理と再起動保持はfixtureで確認済みです。

公開識別子以外、private IP、IPv4 mapped IPv6、multicast、特殊用途domain、wildcard、任意URL、認証値を拒否。HTTPS送信先のpublic DNS pinning・TLS検証・redirect拒否は共通基盤を使います。providerごと60秒以上、UTC日予算（初期100）、429待機、3回までretry、5MiB応答、16MiB cacheの制限があります。ネットワークproviderの初期cache TTLは3600秒。ウォッチ間隔は3600〜604800秒、初期86400秒で共有cacheの有効時間にも制約されます。

固定観測は取得元URL、照会時刻、出典版（不明は不明）、原文SHA-256、正規化値を持ちます。変化イベントは前後の固定観測IDと項目別の値を保存します。失敗時は直前の成功値をstaleとして残します。最新成功値がない場合はunknown。固定根拠は案件へ紐付き、ウォッチリストで検索できます。

保存期間は7〜3650日（初期90日）。期限前のイベントと古い観測メタデータを整理し、最新観測・残存イベントの前後・引用／メモに使う観測を保護。固定根拠そのものと案件の固定参照は削除しません。schema9→10、根拠bundleはschema6〜10を復元可能です。共有ライブラリの案件分類はユーザー別のアクセス分離ではありません。

APIはBearer read/write。`GET/POST /api/v1/workspaces/{id}/network-watches`、`GET/PATCH /api/v1/network-watches/{id}`、空bodyの`POST .../lookup`、`GET .../observations`、`GET .../events`。PATCHは`expected_revision`が必要で対象変更不可。lookupは202で予約のみ、RDAPは先にbootstrapジョブを返す場合があります。詳細はOpenAPI0.11。
