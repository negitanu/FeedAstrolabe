# 第十二段階の検証（2026-10-08）

OpenSpec `phase-twelve-ai-research-tracking`、schema10→11。公開Atom／リリース、retry-safe page、重複しない不変版、引用付きモデルカード／明示レビュー済み関連、条件付き評価比較を実装。

- 最終ロジックの実Chromium/IPC付き全体テスト229件成功、14.57秒。追加7テストは論文改訂v1/v2・release説明変更・旧根拠と重複防止、失敗時cursor保持・不正ページ・1000件範囲表示、DTD/entity/privateID／他repo／任意query拒否、同案件引用・unknown license/cost・通貨単位日付必須、reviewedリンク／他案件拒否、異なるdataset版・欠損条件・再現メモ・NaN／Infinity等拒否、read/write／許可／CSRF／409／archive／入力固定、実v10 fixture→v11と両bundle復元、triage検索と固定根拠retentionを確認。
- `scripts/verify_ai_research.py --live-public`：一時データで公開論文1706.03762とpallets/flaskを明示許可し各1GET。arXiv最新版1件、GitHub公開release38件の実取得成功（2026-10-08 09:36 UTC）。メタデータだけ、利用者案件・メモ・添付・tokenは送信しない。実ライブラリの設定は変更しない。
- `scripts/verify_ai_research.py --serve-port 5016 --data-dir /tmp/feedastrolabe-ai-final-verify`：実HTTPでread拒否／許可なし409／版2追加／quotedモデル・ライセンスunknown／reviewedリンク／dataset_version差によるincompatible／bundle保持。最終テンプレートは5017へ再読込しCUAで確認。モデル・版履歴・一覧・比較を390px幅で確認し、比較の横overflowを修正後scrollWidth=390。版詳細のscript要素0、通常viewportへ戻す。
- `scripts/verify_observer.py --project feedastrolabe-ai-final-verify`：独立4サービスで実text/Markdown/PDF IPC／隔離JSrenderer、triage／対象／security／networkの回帰。強制再作成後、paper/release版3件、引用付きカードと参照、評価の条件差を保持しschema11／FK正常。独立volume保持、サービス停止。
- OpenAPI0.12全参照／118ルートと実装を照合。追加依存なし。最終操作文書とOpenSpec検証、移行、Git検査、push、archiveは完了後追記。

arXivは検索で返された最新版を観測し、未観測の中間改訂の全網羅ではありません。GitHubは公開releaseだけ。50件×20ページの周期と動的ページ変化の範囲を開示。論文本体／モデル／コードの権利をメタデータライセンスから推論しない。カードの主張・費用は引用に基づく転記、再現は利用者報告、条件一致でも順位や独立検証済み表示をしない。Cloudflare/X実接続とCIの権限拡張は延期を維持。

実writer停止中 `/data/pre-phase-twelve/` にschema10 private bundle（DB600）を保存し検証。4サービスをschema11へ再作成しhealthy。全旧購読ID／URL、記事ID／feed／GUID／既読／スターと案件／根拠／triage／対象／関係／security／network記録をEXCEPT比較し不一致0、FK正常。購読1・記事35・案件0、11providerすべてenabled=0、利用者DBへfixture／照会を追加しない。OpenSpec strict17項目／pip check成功。秘密情報検査とGit結果は完了後記載。

実装commit `4157961` をGitHub mainへpushしリモート一致。候補757件、履歴／全index Gitleaks検出なし。正規仕様3要件・6シナリオを同期し `2026-10-08-phase-twelve-ai-research-tracking` へarchive、12/12タスク完了。
