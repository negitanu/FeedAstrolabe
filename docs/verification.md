# 第一段階の検証記録

検証日：2026-10-08。macOS / Python 3.14.8。依存バージョンは requirements-lock.txt に固定。

## 自動検証

- `.venv/bin/python -m pytest -q`：42 passed。
- `.venv/bin/python -m pip check`：依存関係の不整合なし。
- `openspec validate --all --strict --no-interactive`：phase-one-rss-reader の厳格検証成功。

RSS/Atom の登録、重複登録・不正フィードの拒否、再取得時の内容更新と既読/スター保持、DB 再起動後の保持、304 と条件付き取得、フィードごとのエラー分離、取得失敗時の既存記事保持、複合検索、LIKE 特殊文字、フィルターに限定した一括既読、30 件のページ送り、フォルダー変更、削除時の cascade、GET での状態不変、CSRF、HTML 除去、戻り先 URL、更新ロック、worker の一回実行を確認。

取得層はモック HTTP/DNS/socket で、private/mixed DNS・IPv4-mapped IPv6 の拒否、解決済み IP への接続、TLS ホスト名、リダイレクト先の再検査、条件付きヘッダー、サイズ上限、HTTP エラー、圧縮応答拒否、リダイレクト上限、時間上限を確認。

## ブラウザー確認

In-app browser から http://127.0.0.1:5000 にアクセス。

- 空のライブラリ、追加フォーム、日本語 UI を確認。
- `https://hnrss.org/frontpage` を「テクノロジー」に登録し、20 記事を実際に取得。
- 一覧から本文を開き、許可されたリンクが表示されることを確認。
- 既読操作で未読件数が 20 → 19、スター操作で保存件数が 0 → 1 になることを確認。
- 1280×720 と 390×844 で表示を確認。モバイル時の documentElement.clientWidth / scrollWidth はともに 390。
- 検索ボタンの改行を修正して再確認。
- Flask 開発サーバーでの確認後、README の Waitress 起動コマンドに切り替えて確認。

ブラウザー確認のフィードと記事は Git 管理外の instance/ に残している。UI 確認用のサンプルであり、ソースへのデモ記事の埋め込みはない。

## 現在の境界

第一段階は個人の localhost 利用。認証、コンテナ、Cloudflare 接続、SNS 取得、Playwright 観測は未実装で ROADMAP.md に記録。OpenSpec change は全作業完了として残し、利用者の確認後に同期・アーカイブできる状態にする。

ネットワークタイムアウトは OS の DNS リゾルバーの所要時間を完全には制限しない。大量フィードでは同期の手動更新に時間がかかるため、通常は定期 worker を利用する。外部配信側の挙動は変化し得るため、自動テストは再現可能な fixtures を利用している。
