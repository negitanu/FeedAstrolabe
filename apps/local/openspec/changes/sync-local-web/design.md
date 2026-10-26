## Context

Web は Flask / SQLite schema19、local は Go / Electron schema2。連番IDとデータ形式が異なる。local は初期状態で全ソースが未追跡のため、既存内容を消さず変更ファイルを明示する。

## Goals / Non-Goals

**Goals:** 双方向の購読・記事・既読/スター・収集状態同期、未接続スタンドアロン、Goの全業務機能移植。Cloudflare Access経由の通信とElectron隔離を両立する。

**Non-Goals:** アプリ独自認証、秘密鍵やAPIキーの同期、実データの検証利用、Python実行基盤の同梱。調査データ同期は当初の読書/収集同期とは別契約とするがローカル機能は移植対象。

## Decisions

1. protocol version1の変更イベントを用いる。キーは購読URLと記事guidで、DB連番は転送しない。状態イベントを本文と分け、既読とスターの変更を独立して保持する。
2. SQLite triggerで既存のUI/API/workerの変更を同じトランザクションのjournalへ記録。Lamport clock とイベントIDの辞書順で同一項目の競合を解決し、受信でclockを進める。削除墓標も保持。初期false状態は既存の既読を上書きしない。
3. Webはhubとして永続seq/cursorと重複IDを保持する。localは送信済seqを応答取込トランザクションでのみ進める。中断時は同じイベントを再送し、ネットワーク待ち中はDBをロックしない。バッチ上限と本文サイズ上限を持つ。全履歴を保持し、cursor喪失時も再同期可能。
4. 同期を既定で無効にし、設定・接続先・last success・errorを端末固有として保持。Electron mainが設定済みoriginへの通信とAccessセッションを所有する。rendererには任意URL通信やcookieを渡さない。認証切れ/redirectでは未送信を保持する。
5. local業務モジュールを既存Store/Collector/RPCへ統合し、日本語画面内編集を追加する。各領域のWeb仕様を受入契約とし、未完了をtasks/parityへ明示して完了済と混同しない。

## Risks / Trade-offs

- 同じ項目をオフライン同時変更 → clock/IDの決定的優先。異なる項目は合成。
- 異なるライブラリの初回結合 → 破壊的置換を避けて和集合。削除は墓標を保持。
- Cloudflare Access認証が切れる → main所有のログイン画面で再認証し再送。外部環境受入は模擬HTTP検証と分ける。
- 観測/AI/通知の二重実行 → 同期された結果の受信でジョブを起動しない。秘密/予算は端末固有。
- 全機能移植の範囲が広い → 元仕様ごとに実装/検証を追跡し、単なる汎用CRUDを同等性の完了と扱わない。

## Migration Plan

起動時の整合バックアップ後に追加テーブル/triggerを作る。既存の連番/本文/状態/順序を維持。実環境への反映はバックアップ・再build・health/HTTP確認後。ロールバックではバックアップから戻し、旧アプリと新schemaを混用しない。

## Synchronization failure follow-up (2026-10-26)

稼働Webに同期モジュールがなくGET同期ルートは404、未認証の公開URLは403だった。初回同期前にデータを送らないGETでPOST専用ルート（405）を確認し、認証redirect/403・API不在404・ネットワーク失敗を区別する。チェックボックスには既存check-field共通スタイルを使う。配備前は旧イメージを復旧参照として保持し、DBとblobの検証済bundleを取得する。配備後はhealthとGET405を実HTTPで確認し、稼働データをテストfixtureとして取り出さない。
