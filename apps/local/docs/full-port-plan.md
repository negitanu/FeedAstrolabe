# フル機能移植の計画

最終目的は元版 FeedAstrolabe の全機能を Go / Electron に移植すること。初版の対象外記述は後続移植を拒否するものではない。完了判定は元版 openspec/specs と操作文書の契約を実装・検証できたときとする。

1. 完了: 読書・RSS/Atom・フォルダー・検索・既読/スター/履歴・基本案件/根拠・JSON復旧（create-go-electron-app）。
2. 主要経路実装: SNS、話題抽出、OpenRouter/OrcaRouter、Ollama調査補助、公開区分（add-social-ai）。対応元: social.md / openrouter-topics.md / selectable-ai-providers / grounded-assistant。
3. 未着手: タグ・案件分類拡張・根拠添付/来歴/引用位置・公開区分の全対象伝播（research-workspaces / evidence-provenance）。SNS/AIの送信保護から先行して分類を導入。
4. 未着手: JSページ観測と隔離レンダラー、画像取得（feed-collection / reader-interactions）。Electron表示プロセスとは別の隔離取得基盤が必要。
5. 未着手: 保存検索・watchlist・優先度・受信箱・ダイジェスト・出典を保持する重複整理（watchlists-triage）。
6. 未着手: 対象・関係・別名/訂正/統合・グラフ/タイムライン（entities-relations）。
7. 未着手: KEV/EPSS/CVE、DNS/RDAP/CT/経路/RPKI、arXiv/GitHub/model-card（security-intelligence / network-intelligence / ai-research-tracking）。
8. 未着手: 通知承認・世代バックアップ・運用レポート・権限付き公開API（reports-operations / local-operation）。サーバー/コンテナ固有配備機能はデスクトップ相当の機能要件へ対応付ける。
9. 未着手: 元版データの読取専用移行と差分検証、全機能設定export、元版UI細部・ヒーロー画像・全テーマ/アクセシビリティの同等性、各OS署名/公証。

各段階は個別OpenSpec変更で要件・依存・受入条件を定義してから実装する。完了した機能と未検証の外部サービスを docs/parity.md と検証記録に反映する。元版の実データ・秘密情報は検証に使用しない。

## 今回の依頼で確定した範囲

`sync-local-web` は双方向同期に加えて上記の全未移植機能を対象とします。利用者の選択によりGo / Electronを維持し、Python基盤同梱は採用しません。同期部分と記事HTML/収集間隔/JSON v3は実装済みですが、全機能移植のtasks 3.1〜3.10は未完了です。これらを恒久的な対象外や次の依頼が必要な項目へ変更しません。
