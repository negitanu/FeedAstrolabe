# 第十三段階の検証（2026-10-08）

OpenSpec `phase-thirteen-grounded-assistant`、schema11→12。Ollama固定adapter、停止状態のprofile、正確なJSONプレビューとhash承認、範囲限定検索／引用、生成系譜／保守的予約予算／独立した人のレビュー版を実装。

- 最終実Chromium/IPC付き全体テスト238件成功、15.16秒。追加9テストでexact wire／hash／非stream・toolsなし／approve再利用・不変根拠、空根拠のモデル非呼出／他案件拒否、restricted共有資料とsecret検出／承認hash差／公開区分変更後の送信拒否、注入命令をデータとして扱い設定不変／無効C99拒否／矛盾の不確実性とescapedscript、日予算／profile変更／中断時no retryと予約保持、local cloud.disabledとmodeldigest／remote proxy拒否、固定引用位置／read-write／CSRF／期限切れ409、実v11 fixture→v12と生成・review bundle復元、credential所有権・0600／symlink／固定endpoint／redirect安全失敗／Bearer限定cloudを確認。
- `scripts/verify_assistant.py --probe-local`：127.0.0.1:11434は未起動／未設定。実モデル生成・品質は未確認。クラウドcredentialも未設定で、modelインストール・アカウント作成・課金・利用者の資料送信を行っていない。fixture成功を実モデルの成功扱いしない。
- `scripts/verify_assistant.py --serve-port 5018 --data-dir /tmp/feedastrolabe-assistant-verify`：実HTTPでread拒否／未承認400／hash差409／同job再利用、exact wireと引用、human reviewと409、根拠不足で2件目はモデルを呼ばない、bundle復元。生成は明示した合成モデル。CUAでプレビューと生成結果を確認、長いhashの折り返しを修正後390px幅で両scrollWidth=390、script要素0、通常viewportへ戻す。
- `scripts/verify_observer.py --project feedastrolabe-assistant-verify`：独立4サービスのLinux添付IPC／隔離JSrenderer、triage／対象／security／network／AI版を回帰。強制再作成後にexact input/hash／選択引用／model系譜／usage／独立review1件／決定的insufficient／予算1回を保持。schema12／FK正常、volume保持、サービス停止。モデル実呼出は行わない。
- OpenAPI0.13全参照と128ルート／メソッド照合、追加依存なし、OpenSpec strict17項目成功。既存Git secret除外とbuild allowlistを維持。移行、秘密情報検査、push、archiveは完了後記載。

引用の意味／生成内容の真偽は人の判断で、独立検証済みの事実へ昇格しない。ローカルcloud無効statusのない古いruntimeを安全側に拒否。生成中はpolicyと送信の競合を避けるためwriterを直列化、他の書き込みは待機／busyの場合あり。料金は確認日の利用者設定による概算で請求保証ではない。中断／エラーは自動再送しない。Cloudflare/X実接続とCIの権限拡張は延期を維持。

実writer停止中 `/data/pre-phase-thirteen/` に検証済みschema11 private bundle（DB600）を保存。4サービスをschema12へ更新・再作成しhealthy。旧購読／記事既読・スターと全旧案件／根拠／整理／対象／関係／security／network／AI研究をEXCEPT比較し不一致0、FK正常。購読1・記事35・案件0、公開provider11件すべて無効、assistant profile0件で生成停止。利用者DBにfixtureや送信を追加しない。
