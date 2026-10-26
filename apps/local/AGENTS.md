# FeedAstrolabe-local 開発方針

- 最終目的は元版FeedAstrolabeのフル機能移植。docs/full-port-plan.mdと元版OpenSpecの対応を更新し、未完了機能を恒久的な対象外にしない。
- Go / Electron による個人用ローカルアプリ。元版 ../.. の実データ・秘密情報は読み込まない。
- 実装前に OpenSpec proposal / design / specs / tasks を作成し strict 検証する。実装後に本仕様、操作文書、README、検証記録を整合させる。
- UI は日本語。「読む・集める・調べる・まとめる・設定」。フォルダー選択は記事表示、矢印だけで開閉。並び順・幅・開閉を保持する。
- 全て既読は現在条件の未描画記事も対象。記事一覧はスクロール追加。購読停止は記事を保持。
- Electron は sandbox / contextIsolation を有効化し nodeIntegration を無効化。任意IPC・任意ファイル・任意URLの権限をrendererへ渡さない。
- 秘密情報・実データ・ビルド成果物・依存物をGitに含めない。元版との機能差と未検証項目を明記する。
- コミットする場合はローカルGitの本人名義を確認し、機能単位に分割。AI共同著者は追加しない。
