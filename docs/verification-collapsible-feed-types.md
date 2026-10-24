# フィード種類の折り畳み（2026-10-08）

- RSS / Atom、X、Mastodon、ページ観測の順に、存在する種類だけdetails/summaryで表示。種類内のフォルダー分類、未読数、選択リンクを保持。
- 全体表示では全種類open、フィード選択時は選択された種類のみopen。開閉状態の永続化は含まない。
- テスト用ライブラリに4種類5購読を作成し、各リンクの一意表示・NULL未読の0表示・件数合算・同名フォルダーの種類内表示・選択時のopenとaria-currentをHTMLで確認。
- reader/social/display-timezoneの48テスト成功。OpenSpec全19項目strict成功、git diff --check成功。
- JavaScript追加なし。native disclosureのマウス／タッチ／キーボード操作を使用。実ブラウザーでの見た目と稼働コンテナへの反映は未確認。

追補：開閉状態の保存と実ブラウザー検証は、その後の [persistent-feed-disclosure](verification-persistent-feed-disclosure.md) で追加しました。上記は初回実装時の記録です。
