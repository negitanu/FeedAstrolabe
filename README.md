# FeedAstrolabe

個人利用向けの RSS/Atom リーダー。第一段階の Web UI と収集機能を Flask / SQLite で実装しています。

## 起動

Python 3.11 以上（macOS / Linux）を使用します。`requirements-lock.txt` は検証時の全依存バージョン（テスト用を含む）を固定しています。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m feedastrolabe
```

http://127.0.0.1:5000 を開き、RSS / Atom の URL を登録してください。登録時に初回取得を行います。通常の Web ページからのフィード自動探索は未対応です。

別のターミナルで定期収集を起動します（既定 15 分、最小 60 秒）。

```sh
.venv/bin/python -m flask --app feedastrolabe worker --interval 900
```

一回のみ更新する場合：

```sh
.venv/bin/python -m flask --app feedastrolabe refresh
```

Web と worker は Ctrl-C で停止します。Web の起動だけでは定期更新しません。手動更新と worker が競合すると、後からの更新は実行中として扱います。

## 機能

- RSS/Atom 登録、削除、フォルダー変更、フィードごとの取得状況・エラー。
- 手動更新、定期収集、ETag / Last-Modified、重複排除。
- 日本語レスポンシブ UI、本文表示、元記事へのリンク、未読・スター・フィード・タイトル/本文検索、30 件ごとのページ送り。
- 既読・スターの永続化と、現在の検索条件に一致する記事の一括既読。
- CSRF 保護、HTML 許可リスト、public IP への取得限定、DNS pinning、サイズ/時間/リダイレクト制限。

本文を開くだけでは既読になりません。「既読にする」で変更します。外部画像や埋め込みは表示しません。取得は標準 HTTP(S) ポート限定、最大 5 MiB、一度に最大 2,000 記事です。HTTP 応答には非圧縮の identity を要求します。手動更新は同期処理なので、通常は worker を使ってください。DNS 解決の所要時間は OS のリゾルバー設定に依存します。

現段階は認証なしの localhost 専用です。起動コマンドは 127.0.0.1 に固定しています。外部アクセスは第二段階の受入条件を満たしてから行います。

## データとバックアップ

既定は `instance/feeds.sqlite3`、秘密鍵は `instance/secret.key`。Git に含めません。`FEEDASTROLABE_DATA_DIR` に絶対パスを指定すると保存先を変更できます。Web と worker には同じ値を設定します。

バックアップは Web/worker を停止して `instance/` 全体をコピーするか、SQLite の backup API を使用します。稼働中に DB ファイルだけをコピーすると WAL の内容が漏れる場合があります。復元時も両プロセスを停止してから置き換えます。

## OpenSpec / SDD

変更 `openspec/changes/phase-one-rss-reader/` に proposal、design、受入仕様、tasks があります。実装前に仕様を作成して厳格検証し、仕様に対応するテストで実装を検証します。初期化済みの Codex スキルは `.codex/skills/` にあります。

```sh
openspec validate --all --strict --no-interactive
.venv/bin/python -m pytest
```

実装確認後に仕様を同期・アーカイブします。新しい段階は別の change として作成してください。OpenSpec CLI は [公式手順](https://github.com/Fission-AI/OpenSpec) で導入できます（この環境は 1.3.1）。

## 次の段階

[ROADMAP.md](ROADMAP.md) に指定された四段階の順序、受入条件と必要な設定を記録しています。
