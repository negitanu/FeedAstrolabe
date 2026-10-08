# 第四段階の検証（2026-10-08）

OpenSpec change: `phase-four-page-observation`。公開・ログイン不要ページの CSS テキスト観測を実装しました。Cloudflare の実接続は引き続き後段です。

## 自動検証

- `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：132件成功。schema v1/v3→v4、復元と observer 排他、基準・変更・無変化・復帰、Unicode/空白正規化、スター保持と保存期間、編集時の古い観測破棄、削除 cascade、pause/手動予約/backoff、CSRF/API権限を確認。
- 実 Chromium で JavaScript による遅延描画・標準 CSS 抽出・無効 CSS・Unix IPC を確認。短いジョブ上限のテストで Chromium 相当の子孫プロセスも終了することを確認。
- 同一 origin GET、public DNS pin、private address 拒否、redirect/POST/認証転送の拒否、取得サイズ・回数制限、IPC サイズと不正メッセージを検証。
- `pip check`：依存関係エラーなし。Playwright 1.63.0 と対応 Chromium を使用。
- `openspec validate --all --strict --no-interactive`：7項目成功。

## コンテナと既存データ

`scripts/verify_observer.py` は独立した `feedastrolabe-observer-verify` project で実 Chromium と JS fixture、初回0記事・変更/復帰2記事・無変化0記事、実 HTTP API、コンテナ再作成後の既読/スター保持を確認しました。

renderer の `network_mode: none`、UID10001、read-only、capabilities 無効、メモリー512 MiB、PID128を確認。外部 IP へのソケット接続は失敗し、DB が存在せず、唯一の volume mount は Unix IPC です。

稼働環境は移行前 schema v3 の `/data/pre-phase-four.sqlite3` を SQLite backup で保存し、Web/worker を停止して更新しました。購読1件と既存記事23件の ID・GUID・既読・スターをバックアップと比較し、全件保持を確認。v4 foreign_key_check はエラーなし。Web/RSS worker/observer/renderer の4サービスを起動しています。

稼働 renderer と一時 DB を使い、公開 HTTPS ページの `p` 要素を実取得して基準保存と2回目の無変化0記事を確認しました。`h1` のない同ページでは安全な要素未検出エラーを返し、基準・記事を保存しませんでした。利用者の DB へ検証購読は追加していません。

## 画面

実稼働 `/settings#pages` を通常幅と390px幅で確認。観測URL・CSS・間隔・待機・保存期間のフォームと説明が表示され、390px幅の document.scrollWidth は390px。テストでは登録・観測設定編集・差分記事表示を確認しています。

## 対象外と運用

ログイン、スクリーンショット、画像比較、クロス origin CDN、Cookie、POST、iframe は今回の対象外です。native 開発モードは OS のネットワーク隔離を提供しません。通常利用には Compose を使用します。X の実接続と Cloudflare の実公開は資格情報・対象設定後に検証します。GitHub CI は引き続きテンプレートで、稼働 CI の成功を主張しません。

push 前に候補ファイルと Git 履歴のパターン検査、Gitleaks を実行し、検出なしを確認しました。結果は秘密情報の完全検出を保証しません。設定・データ・鍵・認証ファイルは Git/build context の対象外です。
