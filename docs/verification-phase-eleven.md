# 第十一段階の検証（2026-10-08）

OpenSpec `phase-eleven-network-intelligence`。schema9→10。DNS／IANA bootstrapと限定RDAP／RIPEstat経路・RPKI／CT JSON処理、固定観測、項目別イベント、許可・間隔・保持設定、APIと日本語UIを実装。

- 最終実Chromium/IPC付き全体テスト222件成功、13.05秒。新規7テストはTTL低下と回答変化の区別、TTL期限／NXDOMAIN／SERVFAILで旧値保持、private／wildcard／mapped IPv6／multicast／不正prefixとorigin拒否、IANA最も具体的管轄と未承認基点拒否、referral非追跡、CT発行とendpoint確認の区別、RIS空の範囲／RPKI組の不一致／200件上限、許可／read-write／CSRF／409／archive、固定対象変更拒否、triage連携、引用・最新・固定根拠保持、実v9 fixture移行とv10 bundle復元を確認。
- `scripts/verify_network.py --serve-port 5014 --data-dir /tmp/feedastrolabe-network-verify`：実HTTPで許可なし拒否・read拒否・5種の固定観測・前後の回答変化リンク・503時旧成功値stale・bundle復元を確認。CUAで一覧と詳細を確認し390px幅のscrollWidth=390、詳細script要素0、通常viewportへ戻した。
- `scripts/verify_network.py --live-public`：一時ライブラリだけでexample.com／8.8.8.8／8.8.8.0/24とAS15169を許可し、6取得を試行（2026-10-08 09:19 UTC）。Google DNS、IANA、Verisign RDAP、RIPEstat経路1.1、RPKI0.3の実取得成功。crt.shはtransport-or-formatでunknownを維持し実接続は未確認。再試行や制限回避は行わない。利用者の案件・メモ・添付を送信せず、実ライブラリの連携設定を有効化しない。
- `scripts/verify_observer.py --project feedastrolabe-network-verify`：独立4サービスの実Linux text/Markdown/PDF IPC、隔離ChromiumのJS観測、triage／対象／セキュリティを回帰。ネットワーク固定観測6件、前後イベント1件、旧成功値と失敗待機、許可状態が強制再作成後も保持。schema10／FK正常。サービス停止、独立volume保持。
- OpenAPI0.11全参照と105ルート／メソッドの照合成功、pip check正常。OpenSpec strict17項目成功。追加依存なし。

CTの実サービス取得は上記の通り未確認です。RDAPは5 RIRとVerisign com/netに限定、未知の登録局・referralを追跡しません。CT／RIS／RPKIの値を所有者認定・endpoint稼働・経路乗っ取りの結論に変えません。schema移行・Git検査・push・仕様同期は完了後記載します。Cloudflare実接続、X実資格情報、CIの権限拡張は延期を維持。

実writer停止中に `/data/pre-phase-eleven/` に検証済みschema9 private bundle（DB600）を保存。4サービスをschema10へ再作成しhealthy。全旧購読ID／URL、記事ID／feed／GUID／既読／スターと全旧案件／根拠／整理／対象／関係／セキュリティの記録をEXCEPT比較し不一致0、FK正常。購読1・記事35・案件0、全9連携enabled=0。利用者DBへ検証fixtureや外部照会を追加しない。
