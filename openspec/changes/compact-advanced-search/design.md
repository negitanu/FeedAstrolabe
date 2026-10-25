## Context
語句は改行区切りのtextarea、情報源はmultiple selectで表示される。
## Goals / Non-Goals
**Goals:** 1行の高さで入力し、キーボード・タッチ・JavaScript無効時も複数情報源を選べる。
**Non-Goals:** 検索のAND/OR/NOT、日付・情報源制限の変更。
## Decisions
語句UIはCSV形式の別パラメーターを使い、サーバーで既存の改行区切り条件へ正規化する。表示時はCSVへ戻し、カンマを含む語句や引用符と旧URLを保持する。二形式の同時指定は拒否する。情報源は標準details/summaryのプルダウン内にチェックボックスを置き、既存のsourcesパラメーターを維持する。共通テーマ色でパネルを描画し、狭い画面で幅を制限する。nonce付きreader-search.jsで選択件数、Escapeと外側クリックによる閉鎖を補助する。
## Risks / Trade-offs
- CSVの解釈誤り → カンマ区切りのプレースホルダーとエラー、引用句の回帰テスト。
- 長い情報源一覧 → 高さを制限しパネル内をスクロールする。
## Migration Plan
DB変更なし。コンテナ再構築・再起動、healthと実HTTPを確認する。

## Layout refinement
情報源を検索対象の直前へDOM順序で配置し、詳細検索の有効幅600px以上では6項目を同じ行へ並べる。狭い画面では従来の自動折り返しを維持する。
