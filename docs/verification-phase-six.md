# 第六段階の検証（2026-10-08）

OpenSpec change: `phase-six-research-workspaces`。調査案件、複数案件へのフィード／記事関連付け、版付き Markdown メモ、共有タグ、公開区分と API を実装。SQLite は v4 から v5 に移行します。

- `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：183件成功。既存の実 Chromium／IPC／強制終了に加え、v4 移行と v5 backup/restore、ID／既読／スター／観測基準／予約／SNS待機保持、複数案件とフィード経由の重複排除、アーカイブの読み取り継続・編集拒否・再開、実並行メモ編集と409、完全な版履歴、タグ上限／重複／名前変更／検索、古い検索IDの選択保持、readキー拒否・未認証401・CSRF・XSS・不正入力の原子性を確認。
- `scripts/verify_research.py`：native と最終 web コンテナ内の一時 DB で実 HTTP の関連付け、タグ付き重複排除、版編集／競合、readキー拒否、アーカイブ、UI、v5 復元を確認。検証キー全文を出力せず、利用者のライブラリに追加しません。
- `scripts/verify_container.py --project feedastrolabe-research-verify --port 5011`：独立ボリュームで非 root／read-only、認証API／失効、案件リンク・メモ履歴を含む backup/restore、Web／worker 強制再作成後の状態を確認。検証用サービスを停止し、独立ボリュームは保持。
- CUA で日本語の案件一覧、案件詳細、メモ、ライブラリを確認。検証画面で390px幅の案件詳細／メモ／ライブラリの document.scrollWidth は390px、メモの img/script 要素は0。Markdown の見出し／強調を表示し、HTMLは文字として扱います。通常幅へ戻しました。
- 実稼働の web／worker／observer を停止して `/data/pre-phase-six.sqlite3` を SQLite backup で保存（600、schema v4）。4サービスを再ビルド／再作成後、schema v5、購読1件・記事28件を確認。移行前全記事の ID／feed_id／GUID／既読／スターと全購読の ID／URL を照合し、欠損／不一致0。foreign_key_check はエラーなし。利用者ライブラリの検証用案件は0件。
- OpenAPI のローカル参照と、全記載ルート／HTTPメソッドが実装に存在することを確認。`pip check` は依存関係エラーなし。OpenSpec全体を strict 検証（同期前17項目）。

受入シナリオは `tests/test_research.py` に対応します。研究組織／archive は `test_multiple_workspaces_feed_union_archive_and_delete`、版競合は `test_note_atomic_conflict_history_and_archive` と `test_concurrent_note_writers`、scope／安全な表示は `test_scope_csrf_and_safe_markdown_ui`、タグ／pagination は `test_tags_rename_association_filters_and_bounds` と UI・上限テスト、移行／復元は `test_v4_migration_and_research_backup` で確認しました。

案件は共有ライブラリの整理単位です。公開区分は利用者ごとの権限分離・暗号化を提供しません。関連フィードの新着表示は archive 後も続き、記事削除時にはそのリンクも削除されます。不変な根拠保存・添付・ウォッチリストは第七段階以降の未実装機能です。

Cloudflare実接続、X実資格情報取得とGitHub CI有効化は従来どおり未完了です。CIはテンプレートのみ更新しました。外部サービスの受入結果として fixture を扱いません。Git候補／履歴のパターン検査と Gitleaks 履歴・全index候補検査で検出なし。既存の第二段階英語タスク文だけの限定fingerprintを維持し、広い除外は追加していません。実装 commit `035e01e` を GitHub main に push して一致を確認後、4要件・7シナリオを `openspec/specs/research-workspaces/spec.md` に同期し、`openspec/changes/archive/2026-10-08-phase-six-research-workspaces/` に archive。archive 自体のタスク3.5は処理成功後に完了し、11/11タスク完了。同期後の strict 検証も17項目成功。
