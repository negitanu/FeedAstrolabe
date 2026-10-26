## Context

元版は Flask / SQLite で多数の外部連携を持つ。空の FeedAstrolabe-local を git init してから本変更を開始した。初回リリースはローカル完結するコア経路を実装する。

## Goals / Non-Goals

**Goals:** 実フィードを購読し、検索・読書・整理・案件メモ・根拠・レポートを再起動後も利用可能。macOS で開発起動・配布ビルド可能な構造。

**Non-Goals:** 元版DBの直接移行、外部公開サーバー、SNS収集、隔離ブラウザーによる観測、AI生成、専門情報連携、エンティティグラフ・通知は初版の受入対象外。docs/parity.md に後続の移植項目を残す。

## Decisions

- Go標準HTTPと modernc SQLite（CGO不要）。ローカルJSONファイル方式より更新の原子性・参照整合性を優先。DBは単一接続、foreign keys、有効なschema_versionで管理。
- Goは127.0.0.1の動的ポートにbind。256-bit bearerを起動毎に生成し、mainだけがstdout readyで取得。rendererはloadFileで静的UI、限定contextBridgeからmainへ要求。API tokenをrendererへ渡さない。APIはOrigin付き要求を拒否。
- Electron mainはbridge送信元を検証、操作許可リストを持つ。外部ページはHTTP(S)のみ既定ブラウザーへ。navigation/window-open/permissionsを拒否。sandboxとCSPで未信頼記事を隔離。記事はtextContentでプレーンテキスト表示し、外部画像を読み込まない。
- HTTP取得は公開IPだけ、標準ポート、DNS検証後IP固定、各リダイレクト再検証、圧縮なし、5MiB/20秒/最大2000記事。XMLのDTD/実体拒否。RSS/Atomはgofeed、HTML discoveryはx/net/htmlで解析。
- SQLiteトランザクションで更新・インポート・復元。既読/スターは再収集で変えない。原記事が消えても保存記事は残す。取得失敗は既存内容を維持し、フィードにエラー表示。
- フォルダー/フィード順、テーマ、幅、開閉はDB。記事はIDキーと公開日順、queryのoffsetで追加。詳細開閉でDOMと位置を維持。
- OPMLはURL検証後プレビューと確定、重複を除去。設定JSONは秘密情報・本文なし。完全JSONバックアップは内容/状態/根拠を含み、復元前に現在データを別ファイルへ書き出す手順を必須とする。
- npm lockとgo.sumで依存固定。Go buildとElectron builderでネイティブバイナリをresourcesへ同梱。

## Risks / Trade-offs

- [元版との機能差] → 機能表で実装済/未移植を明示し、UIに未実装ボタンを置かない。
- [プレーンテキストで記事書式を失う] → XSSや追跡リソースを排除、元記事は明示操作で外部ブラウザーへ。
- [停止中は更新しない] → 起動時・指定間隔・手動更新。外部worker常駐は不要。
- [署名証明書なし] → 開発用非署名ビルドを提供、署名/notarizationは未検証。
- [元版データとの混同] → 別userDataパスと専用バージョン付き形式。元版DBは開かない。

## 検証中に判明した接続互換性

この開発環境ではGo 1.27のTLS 1.3 ClientHelloがタイムアウトし、TLS 1.2なら公式Goブログを取得できた。原因が中間ネットワークかサーバーかは未確定。自動ダウングレードや証明書検証の無効化はせず、明示的な `FEEDASTROLABE_LOCAL_TLS12=1` / `--tls12` の互換モードを用意する。既定はTLS 1.2以上・最大版はGo標準のままとする。
