# 第七段階の検証（2026-10-08）

OpenSpec change: `phase-seven-evidence-provenance`。不変な根拠版、公開／観測／保存日時、固定と正確な引用、添付解析、容量・保存期間、blobを含む復旧を実装。schema v5→v6。

- `FEEDASTROLABE_TEST_BROWSER=1 .venv/bin/python -m pytest -q`：190件成功（8.73秒）。`tests/test_evidence.py` の7テストで上流更新・同一取得・変更後の復帰、削除後の出典保持、ページ基準、現在時点の後付け保存、引用位置／ハッシュ、read/write/CSRF、アーカイブ、実IPCの text／Markdown／PDF、暗号化／不正MIME／path／サイズ／symlink、実ファイル容量と孤立ファイル、固定を除く保存期間、v5移行、正常bundleと不完全／改竄／余分なファイルの拒否を確認。既存 RSS/SNS/観測/研究機能の回帰も成功。
- `scripts/verify_evidence.py --skip-attachments --serve-port 5012`：native 一時DBで実HTTPの固定根拠・引用・購読削除・scope・download・bundle検証。native fixtureの添付は明示的に省略。
- `scripts/verify_observer.py --project feedastrolabe-evidence-verify`：独立4サービスで上記HTTP検証を添付省略なしで実行。実 Linux parser の text／Markdown／PDF と実 Chromium のJS描画・基準／変更／無変更／復帰を確認。renderer network=none、DB mountなし、非root、read-only、512MiB、pids128。再作成後のschema v6・観測状態・既読／スター保持を確認。検証サービスは終了時に停止、独立volumeは保持。
- CUA の日本語UIで削除済み情報源、公開日時「不明」、固定本文、出典ハッシュ、引用と案件固定を確認。390px幅の詳細・一覧で document.scrollWidth=390px、詳細のscript要素0。通常viewportへ復帰。
- 実 web/worker/observer 停止後、`/data/pre-phase-seven.sqlite3` をSQLite backupで作成（schema5、600）。4サービスを更新・再作成しhealthy。旧全購読ID／URL、記事ID／feed_id／GUID／既読／スター、案件・メモ・版・タグを EXCEPT で照合し不一致0。schema6、foreign_key_check正常、現在購読1件／記事30件／案件0件。通常workerで増えた新着を移行損失と混同せず、利用者DBにfixture案件・添付を追加していない。
- OpenAPIの全ローカル参照と記載HTTPメソッド／実ルートを検証。`pip check`正常。OpenSpec strict 17項目成功。

根拠は加工済み表現、ハッシュは整合性確認であり真実性の認定ではありません。legacy記事の実公開日時は不明のまま移行します。添付はOCR／ブラウザー内PDF表示に対応せず、最大10MiB／200ページ／抽出10万文字。LinuxでCPU／アドレス空間／コンテナ制限を検証し、macOS nativeではアドレス空間制限を適用していません。[pypdfの抽出仕様とメモリー上の注意](https://pypdf.readthedocs.io/en/latest/user/extract-text.html)を確認して6.19.0に固定しました。

外部接続の確認は区別します。Cloudflare実接続は指示どおり後段、X実資格情報とGitHub CI有効化は従来どおり未完了。添付・外部ページの受入は決定的fixtureで、利用者の調査内容を外部へ送信していません。配布時の秘密情報検査とGit/仕様同期の結果は完了後に追記します。

実装 commit `6dfae28` を GitHub main へ push してリモート一致を確認。Git候補432件の秘密情報パターン検査、Gitleaks履歴・全index候補の検査で検出なし。既存の限定fingerprintを維持。正規仕様 `openspec/specs/evidence-provenance/spec.md` を同期し `openspec/changes/archive/2026-10-08-phase-seven-evidence-provenance/` に archive、12/12タスク完了。
