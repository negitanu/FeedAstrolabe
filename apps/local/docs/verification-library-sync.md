# sync-local-web 検証記録 — 2026-10-26

## 現在の到達点

依頼全体は未完了。今回の変更は Go / Electron による全機能移植を含み、OpenSpec tasks 3.1〜3.10 は未完了のまま保持する。同期基盤だけの完了を全機能移植の完了と扱わず、変更はアーカイブしていない。tasks は20項目中8項目を完了とした。

実装済み: 両側の永続journal、安定キー、項目別clock、再送/重複ID検証、購読停止・既読・スターの独立競合、削除墓標、親より先に届いた記事の反映、カーソル/世代検査、移行前SQLiteバックアップ、設定画面、main所有のAccessセッション、同期停止/設定変更による通信中断。記事の安全なHTML表示、RSSの情報源別間隔、旧SNS識別子の互換化、設定/完全JSON v3も追加した。

Web schema19 / local schema2へ同期拡張テーブルを追加する方式。プロトコルはv1。依存の追加・更新は行っていない。既存の非root/read-only/renderer隔離とローカルIPC認証は維持した。

## 成功した検証

- Web: `FEEDASTROLABE_SYNC_BINARY=/private/tmp/feedastrolabe-sync-test .venv/bin/python -m pytest -q --disable-warnings` — **610 passed / 125 skipped**。スキップは既存のブラウザー/外部接続等の条件付き検証。全件成功という意味ではない。
- 新規Web同期テスト: 7件。再送、再起動、独立した既読/スター、本文サニタイズ、日本語UTF-8応答、同一IDの異なる内容の拒否、入力の原子性、Origin、世代/カーソル、移行前バックアップ、収集間隔、停止と名前変更、削除と名前変更の到着順序を確認。
- 実HTTP相互運用: 一時ライブラリでFlaskとGoを127.0.0.1のサーバーとして起動。Web `/healthz`、記事転送、オフラインの既読/スター、応答喪失後のGo再起動、再送、停止、未読、削除が成功。実フィード・実アカウントは利用せず、全体収集を停止した合成データを使用。
- Go: `go test -race ./...` / `go vet ./...` 成功。同期の原子取込み、設定変更中の応答拒否、独立した停止状態、削除順序、永続送信待ち、旧バックアップ/SNS ID、情報源別間隔、HTML、設定/バックアップv3を検証。旧機能の読書・SNS・AI・予算・復元テストも成功。
- Electron: **14 tests passed**。読書/詳細/スクロール、条件全体の既読、フォルダー/並べ替え、案件/根拠、設定/バックアップ/再起動、SNS/AI、同期を実操作。同期画面はライト/ダーク/システム、720pxの狭い画面でも入力/保存/同期/停止を確認。
- Access模擬HTTP: Cookieなしのredirectでカーソルが進まないこと、main専用セッションでログイン後に同期できること、ログイン画面にastrolabe IPCがないこと、HTML応答で状態を保持することを確認。
- Node policy/transport: **5 tests passed**。main frame・URL・webContents制約、任意操作の拒否、同期origin、redirect/HTML/不正/過大JSON。
- `pip check`、`go mod verify`、`npm ls --depth=0`、Prettier、差分の空白検査が成功。
- OpenSpec `validate --all --strict`: Web **55項目**、local **10項目**成功。

最初の通常sandbox実行では既存のソケット作成テストが権限制約で失敗した。上記の最終結果はローカルサーバー/rendererテストを実行できる権限で再検証した結果であり、失敗を成功へ読み替えたものではない。

## 未完了・未実施

- Goの全機能移植。根拠添付/引用/分類、隔離観測・画像、triage、対象/関係、セキュリティ/ネットワーク/AI研究連携、モデルprofile/分類伝播、通知/運用/公開API、完全なデータ移行/UI同等性。同期APIや汎用保存をこれらの代わりとはしない。
- 実Cloudflared/Entra IDでの認証・認証期限切れ・条件付きAccessポリシーの受入、有料AI生成、外部サービスの実接続、Windows/Linux実機。
- 前回の検証時点では未実施だった稼働環境のコンテナ再build/restartと本番HTTP確認（下の追記で実施済み）。実データ、秘密ファイル、稼働DBはこの検証に使用せず、一時ライブラリのhealth/HTTP確認と区別した。
- ブラウザー条件付きの125件は今回実行していない。Web画面自体の変更はなく、変更したElectron画面を実操作した。

コミット・pushは実行していない。localは作業開始時から全ソースが未追跡で、既存内容を一括ステージしていない。生成物・ライブラリ・秘密情報は追跡対象に加えていない。

## 同期失敗への修正・配備（2026-10-26 同日追記）

利用者の画面でチェックボックスがラベルから離れていた。原因は既存の共通 `check-field` ではなく未定義の `check` を指定し、通常入力の全幅/縦並びCSSが適用されたこと。共通スタイルへ統一し「同期を有効にする（起動中は1分ごと）」とした。停止中は手動同期ボタンも無効にする。

稼働Webは同期モジュール不在、originのGET `/api/sync/v1/exchange` は404だった。認証なしの公開URLは403で、表示されていた汎用通信エラーだけでは認証と未反映を区別できなかった。main通信にread-only GET事前確認を追加し、同期API不在404・Access redirect/403・DNS/TLS/timeoutを区別する。認証前の事前確認には記事本文/変更イベントを含めない。

Nodeテストは6件成功。更新したElectron同期実操作ではチェックボックスのサイズ・ラベルとの位置、停止時のボタン、AccessへのGETredirect、認証後同期、API不在404、HTML失敗時のカーソル保持、全テーマ・狭い画面を確認した。実データをテストfixtureにはしていない。

配備ではオンラインbundle `before-sync-api-20261026-6c71cfa4` を取得・検証・ホストbackupsへ保管し、Web/worker/observerを停止した直前に `before-sync-api-offline-20261026-6c71cfa4` を再取得・検証した。どちらもDBと参照blobを含む。停止時のbundleと移行後の稼働DBで、記事全列（既読/スター含む）、購読、フォルダー/フィード順、閲覧履歴、設定のハッシュ一致と外部キー整合性を確認した。内容を表示したりテストへ取り出したりしていない。

同期APIを含む共通イメージをbuildし、Web/worker/observerを再起動した。Webのhealth 200、GET同期ルート405を実HTTPで確認。worker/observerはrunning、Web/rendererはhealthy。非root 10001・read-only・renderer network=noneを維持した。旧イメージIDの直接再タグ付けは利用できなかったため、変更前の追跡済みソースから復旧用 `feedastrolabe:before-sync-api-20261026` を構築して保持した。バックアップはGit除外済みbackupsにも保管している。

実ユーザーのEntraログイン後の公開URL同期は未確認。利用者の認証操作とlocal再起動が必要で、未認証403を同期成功とは扱っていない。Go全機能移植は引き続き未完了。

追記後のOpenSpecタスクは24項目中13項目が完了。追加修正後のElectron全実操作も14件成功し、Node6件と両側のstrict検証が成功した。今回の修正はmain/画面の変更で、既存の全機能移植・全領域UI同等性は未完了のまま保持する。
