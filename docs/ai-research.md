# 論文・モデル・リリースの追跡（第十二段階）

AI研究画面で案件と公開検索対象を登録します。arXivは`id:1706.03762`のような新／旧論文識別子（vN指定も可能）、または`cat:cs.AI`等のカテゴリーと任意の公開タイトル文字を指定。カテゴリーはcs.AI/cs.CL/cs.LG/cs.CV/stat.ML。GitHub公開リリースは小文字`owner/repo`。対象・検索文字は作成後固定です。私的な調査キーワードを送信しないでください。両連携は初期無効で、ウォッチの公開検索条件送信の明示許可も必要です。認証情報・メモ・添付を外部へ送信しません。

[arXiv公式API](https://info.arxiv.org/help/api/user-manual.html)のAtomを既存defusedxmlで解析し、5MiB・10000 XML要素・50件／ページを上限にDTD／entity／外部参照を拒否。[利用条件](https://info.arxiv.org/help/api/tou.html)の1接続・3秒以上間隔に対し、本実装は共通の順次lockとproviderごと60秒以上を使います。記述メタデータのCC0と論文本体の権利は区別し、本文ライセンスは不明のまま保持します。PDFやソースは取得せず、abstractページへリンクします。

[GitHub公式release API](https://docs.github.com/en/rest/releases/releases)はREST版2026-03-10で、公開リポジトリのリリースメタデータのみを匿名取得。[匿名上限60／時](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)に対し60秒以上の間隔と日予算（初期100）を使用。共有IPの他用途も上限を消費するため403 remaining=0のreset／429待機を尊重します。token追加・scope拡張は行いません。tagsだけの公開、draft、assets、clone、重みのダウンロード／実行は収集範囲に含みません。コードライセンスをリリースから推測しません。

50件×20ページ（1周期1000件）の限定範囲で収集し、版IDと正規化値SHA-256で重複を防ぎます。カーソルと固定根拠を同じDBトランザクションで保存し、失敗時は同じページを再試行。周期が完了するとページ0から再開します。動的なページ順は収集中にずれる可能性があり、最新検索で観測した改訂を保存する機能です。間の全改訂や全履歴の網羅を保証しません。上限に達した周期はtruncated。版の改訂や同じrelease IDの説明変更は新しい不変記録へ追加し、以前の根拠を上書きしません。初期間隔86400秒（3600〜604800）、cache初期86400秒にも制約されます。固定投影は案件へ紐付き、ウォッチリストで検索できます。検索欄は対象／モデル名／版、版詳細の検索は取得メタデータ内の文字を照合します。

モデル対象を手動登録し、案件に保存した固定根拠から引用を作ってモデル版カードを追加します。ライセンス・利用制約・ハードウェア・コンテキストの記述は引用に基づく記録者の転記です。空欄はunknown。費用をAPIで記録する場合はamount（非負有限decimal文字列）、currency（3文字）、unit、dateとカードの引用が必須。課金や価格照会はしません。カードは追記専用で訂正は新しい記録。paper／repository／model-cardの参照は同じ案件の引用とreviewed=trueが必要。版IDも指定する場合は同案件の実際の版URLと一致させます。リンクは追跡しません。

評価はdataset／dataset_version／split／metric／unit／direction（higher/lower）／harness／settings／hardware／contextを保存。claimedは同案件の固定引用が必要。reproducedは実行条件と結果メモが必要で、利用者の再現報告として表示し独立検証済みとは扱いません。unverifiedも保持できます。比較は同じ案件内に限り、記録条件の差はincompatible、欠損や出典状態の差はqualified。すべて一致しても記録上の一致であり、順位は付けません。

上限は案件100ウォッチ・1000モデル版カード、カード100リンク・1000評価、ウォッチ10000不変版。schema10→11、bundle schema6〜11の復元に対応。引用の案件整合性と原文ハッシュを復元前に確認し、版の固定根拠をretentionから保護します。

Bearer read/write API：案件の`ai-watches`（GET/POST）、`ai-watches/{id}`（GET/PATCH）、空bodyの`.../lookup`（POST、202予約のみ）、`.../versions`（GET、qとcursor）。案件の`ai-cards`（GET/POST）、`ai-cards/{id}`（GET）、`.../links`（POST）、`.../benchmarks`（GET/POST）、`ai-benchmarks/{left}/compare/{right}`（GET）。PATCHはexpected_revisionを必要とし、対象変更やarchive案件への追加は拒否します。OpenAPI0.12を参照。共有案件の分類はユーザー別のアクセス分離ではありません。
