# 第十四段階の検証（2026-10-08）

OpenSpec `phase-fourteen-reports-operations`、schema12→13。固定資料の可搬出力、公開区分と秘密情報検査、署名Webhook／TLSメールの正確な内容承認と永続ジョブ、運用状態、検証付き世代bundle、停止中だけの復元、scope付き管理APIを実装。

- 最終の実Chromium／隔離IPCを含む全249テスト成功、19.13秒。追加11テスト：公開区分／非公開共有資料／別案件／CSV formulaとhash manifest、既知秘密情報の本文と引用URL、STIX domain/IP/ASN/CVEと内部note参照、approve hash／再承認同job／retry同idempotency／成功再送なし、policy変更／送達不明／中断／429最大3回、Webhook public pin／任意protocol・privateIP・redirect・query・URL token・symlink／0600拒否と正確なHMAC、TLSメールexact宛先／CRLF／stable Message-ID／認証値非収録、heartbeat stale／定期無効と有効／世代保持／manifest・blob確認／稼働中復元拒否、quota／stale revision、bulk read403・101件400・未知ID404の原子性／settings全体検証／OPML重複・DTD・private拒否とCSRF、 genuinev12→v13／report引用retention／両bundle復元、malformed formatと期限切れ承認を確認。
- STIX2.1は[OASIS標準](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html)を確認し、製品と分離した一時環境のOASIS公式 `stix2==3.0.2` parserでdomain／IPv4／IPv6／ASN／CVEと引用noteの6オブジェクトをcustomなしで受理。unsupported modelを除外。製品依存・lock追加なし、全面STIX/TAXII互換性は主張しない。
- `scripts/verify_operations.py --serve-port 5020 --data-dir /tmp/feedastrolabe-operations-final-verify`：最終コード実HTTPでsettings/read403、report/read403・hash、未承認400・hash差409・同job202、成功1回／永続audit、bulk101拒否、backup/read403・予約とbundle検証、online restore拒否と別パス復元。送信は明示したfixture transportだけ、外部実宛先・SMTP・Webhookは未設定／未確認。利用者の資料・tokenの外部送信なし。
- CUAで最終日本語運用画面／レポート／送信プレビューを390px幅で確認。フォームselectをblock・全幅へ改善、hash／本文を折返し、横scroll=390、script要素0。通常viewportへ戻す。本文のscript文字列はescaped textとして表示。
- `scripts/verify_observer.py --project feedastrolabe-operations-final-verify`：独立4サービスのLinux PDF添付／IPC／JavaScript renderer隔離を回帰、triage／対象／security／network／AI／assistant／operations各HTTPとbundleを確認。強制再作成後にreport/citation hash、成功通知1試行とaudit、検証済み世代／worker processed3を保持。schema13／FK正常、volume保持、サービス停止。実外部通知を行わない。
- OpenAPI0.14全参照と151 method/routes一致、pip check成功。CI既存GitHub OAuth scopeを読み取り確認：gist/read:org/repo、workflowなし。テンプレート `.github/ci-template.yaml` を未稼働のまま保持し、UI/API/docsで外部設定として記録。OAuth権限を広げない。

制限：秘密情報検出は既知markerで万能ではない。共有資料の公開区分も再確認、APIキーはライブラリ共通権限。Webhook受信側のIdempotency-Key対応が必要で、曖昧な送達は自動再送しない。quotaは新旧世代両方の余裕を要し、破損／不明な保存物は保持して停止。バックアップの自己ジョブは取得時runningとして復元されることがあり、次のworkerでinterrupted。runtime.lock削除や稼働中の復元回避は不可。Cloudflare/X、CT実取得、AI実モデル、実通知とCI権限は未設定・未確認事項を維持。


実writer停止中 `/data/pre-phase-fourteen/` にschema12 private bundleを保存・全hash検証、DB600を確認。schema13へ移行し旧60テーブルすべてを双方向EXCEPT比較、不一致0、FK正常。購読1・記事36・案件0（通常RSS収集による記事追加を保持）、public provider11件すべて無効、model profile0／notification profile0／report0、定期backup無効。4サービスを最終画像で再作成、正常起動。CUAで実5010の `/operations` にschema13、両workerの新しいheartbeat、無送信の初期設定を確認。実稼働processの共有runtime.lockに対する排他取得も非破壊で拒否を確認。

OpenSpec strict17項目成功。Git除外・build allowlistを維持。秘密情報検査／push／archiveは結果を追記。
