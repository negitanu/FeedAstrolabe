# Feedly 実画面と FeedAstrolabe の機能差分調査

調査日：2026-10-25（JST、実画面の主な確認時間 07:14〜07:22）。比較基準：FeedAstrolabe `6160d25`、製品版 `0.15.0`、DB schema 18。

> 実装追記：この比較は `6160d25` 時点の記録です。F01〜F05の基礎機能は、後続のOpenSpec変更 `reader-discovery-history-controls` で実装しました。F03の人気順等、当該変更に含まれない範囲は残っています。[操作手順](reader-productivity.md)と[検証記録](verification-reader-discovery-history-controls.md)を参照してください。

## 結論

改善候補を20領域に整理した。優先度は、日常の購読・読む作業への効果と、既存実装を活かせるかで判断している。Feedly の全機能の完全な棚卸しや、性能・AI品質の優劣の判定ではない。

先に着手する候補は **サイト URL からの RSS 探索、閲覧履歴、古い順、詳細検索の操作画面、複数選択**。続いて日付指定の一括既読と購読外 URL の保存。高度な AI や新規外部接続より、毎日の読書と購読追加を先に改善する順序を推奨する。

保存検索、記事保存、案件・タグ・メモ、根拠固定、完全重複整理、AI 要約／翻訳／比較／質問、レポート、SMTP／Webhook、限定的 STIX 2.1 出力は既にある。これらを一括して「不足」と扱ってはいけない。

## 調査方法と確認の限界

- 一時ディレクトリへローカル導入した **Playwright MCP** を利用し、既定の **headed Chrome** を操作した。Python クライアントはリポジトリの既存 `.venv` を利用。グローバルインストールはしていない。
- Feedly は本人がログインしたセッションで確認した。画面には **Pro の期限切れ**の案内があった。このため、有料機能は入口・設定・説明の確認と、実処理の動作確認を区別する。
- Follow sources の4タブ、IPA URL の探索結果、Search、Read later、Recently read、既読記事の本文とメニュー、Today、一覧の表示・フィルターメニュー、フォルダー・フィードの右クリックと再分類、Preferences の General / Appearance / Saving & Sharing / Mark as Read / Feedly AI を確認した。
- 購入、更新、プラン変更、無料体験開始、Billing の選択、有料 API 生成、外部連携の認可、送信は行っていない。購読・保存・編集・削除・一括既読の確定操作も行っていない。
- UI の複数選択は解除し、フォルダー設定・再分類はキャンセルし、確認のために展開したフォルダーを閉じ、最後は Today に戻した。既読記事を1件再度開いたため、Feedly 内部の閲覧時刻等は更新される可能性がある。アカウントの内部状態全体が不変であるとは主張しない。
- FeedAstrolabe はコード・DB定義・現行操作文書を照合した。今回、稼働中の FeedAstrolabe や実データを変更せず、新たな受入試験・外部サービス接続は行っていない。既存の検証記録と今回の実施内容は区別する。
- セッションの Cookie、トークン、個人用 URL、購読一覧、記事本文は成果文書へ転載していない。生の MCP 出力は `/private/tmp/feedastrolabe-feedly-mcp/output/` に一時保存されており、Git には含めない。

**判定**：「未実装」は相当する実装を確認できなかったもの。「一部あり」は土台や代替手段があり、対象範囲または操作導線に差があるもの。**観測区分**は Feedly 側の確認強度を示し、利用可能プランの保証ではない。

## 優先度別の詳細

### P1：毎日の読む・集める作業を優先

#### F01 サイト URL からの RSS 探索・購読前プレビュー

判定：**未実装** ／ Feedly の観測：**実画面** ／ 証跡：E01, E02

Feedly：IPA の通常サイト URL を入力すると、3種類の RSS 候補、最新記事、更新頻度、Similar feeds が表示された。トピックや言語からも情報源を探索できる。

FeedAstrolabe：RSS / Atom URL を直接入力し、その URL をフィードとして解析する。通常 HTML からの自動探索は README でも未対応と明記。

提案：まず HTML の alternate RSS/Atom を探索し、候補と最新記事を確認してから登録する。大規模な外部サイト索引や推薦は後段に分ける。

受入条件案：サイト URL から複数候補を比較でき、選ぶまで購読を作らない。既存の URL 検証・取得制限を探索先にも適用する。

実装根拠：[README.md](../README.md#L41)、[feedastrolabe/templates/settings_parts/rss.html](../feedastrolabe/templates/settings_parts/rss.html#L1)、[feedastrolabe/collection.py](../feedastrolabe/collection.py#L27)。

#### F02 最近読んだ記事の履歴

判定：**未実装** ／ Feedly の観測：**実画面** ／ 証跡：E06

Feedly：Recently read の独立一覧を確認し、その中の既読記事を開けた。

FeedAstrolabe：既読フラグはあるが、閲覧イベントや読んだ日時に基づく履歴一覧はない。公開日時順の既読記事と閲覧履歴は異なる。

提案：記事を開いた履歴と既読変更を分けて記録し、最近の閲覧から再発見できる入口を置く。

受入条件案：古い公開日の記事でも直近に開けば履歴上位になる。一括既読で履歴を埋めず、未読へ戻す操作とも整合する。Feedly の内部記録方式は未確認。

実装根拠：[feedastrolabe/db.py](../feedastrolabe/db.py#L13)、[feedastrolabe/__init__.py](../feedastrolabe/__init__.py#L318)、[feedastrolabe/templates/index.html](../feedastrolabe/templates/index.html#L10)。

#### F03 古い順・人気順の並べ替え

判定：**一部あり** ／ Feedly の観測：**設定画面** ／ 証跡：E07, E08

Feedly：Newest / Oldest の選択肢と、全体設定の Most popular / Most popular + latest を確認した。

FeedAstrolabe：一般記事の一覧は公開日時の降順固定。SNS の注目投稿スコアはあるが、RSS を含むリーダー全体の並び替えではない。

提案：古い順を先に追加する。人気順は評価データと意味を定義して別途検討する。

受入条件案：並び順を変えても追加読み込み、前後の記事、未読移動、履歴復元で欠落や重複がない。人気スコア不明をゼロ評価と混同しない。

実装根拠：[feedastrolabe/reader_stream.py](../feedastrolabe/reader_stream.py#L15)、[feedastrolabe/reader_navigation.py](../feedastrolabe/reader_navigation.py#L1)、[docs/social.md](../docs/social.md#L1)。

#### F04 通常リーダーの詳細検索 UI

判定：**一部あり** ／ Feedly の観測：**実画面・制限あり** ／ 証跡：E16, E17

Feedly：キーワード検索で Find in Title、AND / OR / NOT、Sources、Published、Languages の条件画面が表示された。Pro+ の案内も表示され、制限解除や網羅性は未検証。

FeedAstrolabe：通常一覧はタイトル・本文への一つの部分一致検索。案件の保存検索には all / any / none、日時条件などが既にある。

提案：既存の条件評価を再利用し、通常一覧でもタイトル限定・期間・除外・複数情報源をフォームで指定できるようにする。

受入条件案：JSON を書かず条件を組み立てられ、保存検索と通常一覧の意味が一致する。言語判定や外部 Web 全文検索は別要件にする。

実装根拠：[feedastrolabe/__init__.py](../feedastrolabe/__init__.py#L139)、[feedastrolabe/templates/index.html](../feedastrolabe/templates/index.html#L40)、[feedastrolabe/triage.py](../feedastrolabe/triage.py#L20)。

#### F05 記事の複数選択と一括操作 UI

判定：**一部あり** ／ Feedly の観測：**実画面** ／ 証跡：E14

Feedly：一覧のチェック選択で 50 articles selected と Save to Board が表示された。選択を解除し、保存等の実行はしていない。

FeedAstrolabe：全条件を対象にする「全て既読」と、1〜100 ID を指定する既読・スター更新 API がある。任意の記事を複数選ぶリーダー UI はない。

提案：一覧の選択状態と操作バーを追加し、まず既読・未読・スターを既存 API で扱う。案件・タグへの一括関連付けは追加契約が必要。

受入条件案：描画済み選択と検索条件全体を明確に区別する。追加読み込み後も選択を保持し、未知 ID や失敗で部分更新しない。

実装根拠：[feedastrolabe/templates/article_cards.html](../feedastrolabe/templates/article_cards.html#L1)、[feedastrolabe/operations_api.py](../feedastrolabe/operations_api.py#L103)、[feedastrolabe/templates/index.html](../feedastrolabe/templates/index.html#L40)。

#### F06 指定日より古い記事だけを一括既読

判定：**一部あり** ／ Feedly の観測：**設定の説明** ／ 証跡：E10

Feedly：Mark all as read button の設定に、older than オプションのメニューを出す旨が表示された。実際の既読化はしていない。

FeedAstrolabe：現在のフィード・フォルダー・検索等の全条件を既読にできるが、通常リーダーに日付境界はない。

提案：既存の「全て既読」から日付条件を指定できるようにする。F04 と日時条件の解釈を共有する。

受入条件案：表示タイムゾーンと実際の UTC 境界を一致させる。未描画記事にも適用し、境界以降の記事・スターを保持する。

実装根拠：[feedastrolabe/__init__.py](../feedastrolabe/__init__.py#L359)、[feedastrolabe/templates/index.html](../feedastrolabe/templates/index.html#L40)、[feedastrolabe/display_time.py](../feedastrolabe/display_time.py#L1)。

#### F07 購読外の記事・PDF を URL で単独保存

判定：**一部あり** ／ Feedly の観測：**入力欄** ／ 証跡：E12

Feedly：Add article or PDF link の URL 入力欄と Add ボタンを確認した。実取り込みはしていない。

FeedAstrolabe：購読済み記事の根拠保存と、テキスト・Markdown・PDF のファイル添付がある。任意の記事 URL を単独でクリップする入口はない。

提案：記事 URL をプレビューしてライブラリ／案件へ保存する経路を追加する。購読追加やページ差分監視とは分ける。

受入条件案：フィードを作らず URL から資料を保存し、取得日時・出典・本文を固定できる。本文取得失敗時はリンクのみの保存を区別する。

実装根拠：[feedastrolabe/templates/article_detail.html](../feedastrolabe/templates/article_detail.html#L1)、[feedastrolabe/templates/workspace.html](../feedastrolabe/templates/workspace.html#L8)、[feedastrolabe/attachments.py](../feedastrolabe/attachments.py#L1)。

### P2：整理・見やすさ・取り込みの拡張

#### F08 記事を隠す・ミュート状態の表示制御

判定：**一部あり** ／ Feedly の観測：**メニュー・設定画面** ／ 証跡：E15, E21

Feedly：記事メニューに Hide、一覧フィルターに Show Muted Articles があった。非表示やミュート条件の保存はしていない。

FeedAstrolabe：案件の保存条件では除外できるが、通常記事一覧の個別非表示状態や表示切替はない。購読停止は新規収集を止める別機能。

提案：まず記事の非表示と解除を追加する。ルールによるミュートを加える場合も、既存ウォッチの除外条件と役割を整理する。

受入条件案：記事・根拠・既読・スターを削除せず非表示にでき、対象を確認して戻せる。ミュート条件の詳細は Feedly 側で未検証。

実装根拠：[feedastrolabe/db.py](../feedastrolabe/db.py#L13)、[feedastrolabe/triage.py](../feedastrolabe/triage.py#L126)、[feedastrolabe/__init__.py](../feedastrolabe/__init__.py#L318)。

#### F09 同一フィードの複数フォルダー所属

判定：**未実装** ／ Feedly の観測：**設定画面** ／ 証跡：E13

Feedly：Reorganize selected feeds で Added In と Personal Folders の複数チェック欄を確認した。保存せず Cancel で閉じた。

FeedAstrolabe：feeds.folder は一つの文字列。移動はできるが同じフィードを二つのフォルダーへ所属させられない。案件への関連付けは複数可能だが、購読分類とは異なる。

提案：必要ならフォルダー所属を中間テーブルへ移し、取得・記事・既読を共有したまま複数分類する。

受入条件案：複数フォルダー所属でも二重取得や記事の複製がない。D&D、順序、OPML、削除／購読停止を再設計する。

実装根拠：[feedastrolabe/db.py](../feedastrolabe/db.py#L8)、[feedastrolabe/folders.py](../feedastrolabe/folders.py#L1)、[feedastrolabe/platform_schema.py](../feedastrolabe/platform_schema.py#L1)。

#### F10 フィード／フォルダーのお気に入りとクイック移動

判定：**未実装** ／ Feedly の観測：**入口・メニュー** ／ 証跡：E19

Feedly：フォルダーと個別フィードのメニューに Add to Favorites があった。Go to... の入口と Command-K の案内も確認したが、移動ダイアログの動作は確認できていない。

FeedAstrolabe：記事のスター、フォルダー順序、記事操作のショートカットはある。情報源自体のピン留めや名前での全体移動はない。

提案：情報源のお気に入りを先に検討し、多数の情報源を名前で探して移動できるようにする。

受入条件案：記事スターと対象を混同せず、フォルダー・フィード・案件へ名前で移動できる。Go to の詳細動作は追加調査対象。

実装根拠：[feedastrolabe/templates/index.html](../feedastrolabe/templates/index.html#L10)、[feedastrolabe/static/reader-stream.js](../feedastrolabe/static/reader-stream.js#L1)、[feedastrolabe/folders.py](../feedastrolabe/folders.py#L1)。

#### F11 Today のような分野別の概要表示

判定：**一部あり** ／ Feedly の観測：**実画面** ／ 証跡：E18, E08

Feedly：Today / Me にフォルダー別の記事セクション、Explore タブ、人気記事に関する設定を確認した。推薦アルゴリズムは未確認。

FeedAstrolabe：全記事／未読／スターの時系列一覧が中心。案件の日次ダイジェストと SNS の注目投稿はあるが、購読全体を横断する概要ではない。

提案：読む画面で分野別の新着・注目記事を俯瞰できる表示を検討する。最初は新着と手動優先度でもよい。

受入条件案：概要から元のフォルダー条件へ進める。人気度や推薦を採用する場合は、根拠と未評価を区別する。

実装根拠：[feedastrolabe/templates/index.html](../feedastrolabe/templates/index.html#L10)、[docs/triage.md](../docs/triage.md#L1)、[feedastrolabe/templates/social_research.html](../feedastrolabe/templates/social_research.html#L19)。

#### F12 近似重複の抑制と同一ストーリーの集約

判定：**一部あり** ／ Feedly の観測：**有料機能の説明** ／ 証跡：E11

Feedly：設定に near-exact duplicate の除去と related articles の clustering があり、Pro+ と説明されていた。実際の判定品質は試していない。

FeedAstrolabe：固定根拠の完全一致テキスト／正規化 URL による重複グループがある。近似重複や異なる記事の同一話題判定、読む一覧への集約はない。

提案：完全重複グループのリーダー内表示を先に整え、近似重複と話題クラスタリングを別の判定として追加する。

受入条件案：判定理由と全出典へアクセスでき、誤ったグループを解除できる。元記事・根拠・既読を削除／統合しない。

実装根拠：[feedastrolabe/triage.py](../feedastrolabe/triage.py#L141)、[feedastrolabe/triage.py](../feedastrolabe/triage.py#L153)、[docs/triage.md](../docs/triage.md#L35)。

#### F13 文字サイズ・フォントと表示設定の保持範囲

判定：**一部あり** ／ Feedly の観測：**設定画面** ／ 証跡：E09, E08

Feedly：Font family、Text size、Display density、Article view と、フィード／ボード別に設定を上書きできる説明があった。

FeedAstrolabe：ライト／ダーク／システム、標準／1行／タイル、密度の実装はある。本文フォント・文字サイズの選択や情報源別設定はなく、表示形式はブラウザー共通の localStorage キー。

提案：まず本文サイズと読みやすいフォントを追加する。本文を一覧内に展開する形式、情報源別設定、端末間同期は別々に要否を判断する。

受入条件案：日本語・長文・狭い画面でも読みやすく、テーマやブラウザー拡大と両立する。既存の密度・表示形式を重複実装しない。

実装根拠：[feedastrolabe/templates/settings_parts/appearance.html](../feedastrolabe/templates/settings_parts/appearance.html#L1)、[feedastrolabe/static/article-layout.js](../feedastrolabe/static/article-layout.js#L1)、[feedastrolabe/__init__.py](../feedastrolabe/__init__.py#L124)。

#### F14 記事内ノート・エンティティ／重要文の強調導線

判定：**一部あり** ／ Feedly の観測：**設定の説明** ／ 証跡：E20, E11

Feedly：記事上部の Notes、Inline entities、AI highlights の設定説明を確認した。Notes と重要文強調には有料プラン表記があり、作成・生成はしていない。

FeedAstrolabe：版管理メモ、固定引用、出典付きエンティティ抽出がある。通常リーダーの本文中からこれらへ直接つながる操作や自動重要文強調はない。

提案：まず本文選択から既存の固定引用・メモへ進む導線とエンティティ参照を改善する。AI 自動強調は品質評価後に扱う。

受入条件案：選択位置と固定本文の対応が崩れず、原文と人の注記と生成内容を区別できる。Feedly 側の注釈操作・品質は未検証。

実装根拠：[feedastrolabe/templates/article_detail.html](../feedastrolabe/templates/article_detail.html#L1)、[feedastrolabe/templates/workspace.html](../feedastrolabe/templates/workspace.html#L8)、[feedastrolabe/entities.py](../feedastrolabe/entities.py#L9)、[docs/evidence.md](../docs/evidence.md#L1)。

#### F15 Google News のキーワード監視作成 UI

判定：**一部あり** ／ Feedly の観測：**入力・説明画面** ／ 証跡：E03

Feedly：Company, product, or keyword、ニュースサイト範囲、言語の入力と、引用符・intitle・除外・AND / OR の使い方が表示された。登録はしていない。

FeedAstrolabe：既知の RSS URL を登録できるので、別途用意した Google News RSS は一般 RSS として扱える可能性がある。キーワードから監視フィードを作る専用導線や取得互換性の確認はない。

提案：Google News RSS の生成・プレビューを情報源追加へ組み込む。独自のニュース検索インデックスとは分ける。

受入条件案：条件・言語・対象サイトを明示し、生成した URL と記事を確認してから登録する。互換性・取得制限を確認する。

実装根拠：[feedastrolabe/templates/settings_parts/rss.html](../feedastrolabe/templates/settings_parts/rss.html#L1)、[feedastrolabe/collection.py](../feedastrolabe/collection.py#L83)、[feedastrolabe/templates/settings_parts/sns.html](../feedastrolabe/templates/settings_parts/sns.html#L1)。

#### F16 RSS のないページから個々の記事を取り込むビルダー

判定：**一部あり** ／ Feedly の観測：**入口・説明** ／ 証跡：E01

Feedly：通常サイト URL の検索結果に Build RSS feed と、ページに列挙された記事を購読する説明があった。ビルダーを起動・生成していない。

FeedAstrolabe：ページ観測は CSS セレクター内のテキスト変化を差分記事にする。リンク一覧から新着記事を抽出して個別の記事として取り込む機能ではない。

提案：ページ観測を流用できる部分を調べ、項目・リンク・タイトルの抽出設定を別モードとして検討する。

受入条件案：新着項目を URL 等で識別し、一覧の単なる並び替えを新着と誤認しない。画面上で選択できるビルダーの詳細は別途確認が必要。

実装根拠：[docs/observation.md](../docs/observation.md#L1)、[feedastrolabe/templates/settings_parts/page.html](../feedastrolabe/templates/settings_parts/page.html#L1)、[feedastrolabe/observation.py](../feedastrolabe/observation.py#L1)。

### P3：用途と運用コストを見て選ぶ拡張

#### F17 ニュースレターの受信取り込み

判定：**未実装** ／ Feedly の観測：**アップグレード案内のみ** ／ 証跡：E04

Feedly：Newsletters タブには Feedly へニュースレターを配信する説明と Upgrade の案内が表示された。受信用アドレス発行や登録はしていない。

FeedAstrolabe：レポートを SMTP 送信する機能はあるが、メールを受信して記事へ変換する経路はない。

提案：メール受信基盤・重複抑止・本文変換を含む独立した情報源として検討する。送信機能の追加だけでは満たせない。

受入条件案：受信したメールを情報源と対応付けて表示できる。導入前に受信基盤と運用負担を決める。Feedly の実受信は未検証。

実装根拠：[feedastrolabe/delivery_transport.py](../feedastrolabe/delivery_transport.py#L1)、[feedastrolabe/social.py](../feedastrolabe/social.py#L1)、[docs/reports-operations.md](../docs/reports-operations.md#L1)。

#### F18 Reddit の検索・コミュニティ・個人フィード接続

判定：**一部あり** ／ Feedly の観測：**接続の説明のみ** ／ 証跡：E05

Feedly：Reddit タブに検索・コミュニティ・個人フィードを扱う説明と Connect to Reddit が表示された。認可していない。

FeedAstrolabe：SNS 専用接続は Mastodon / Bluesky。Reddit 専用接続・検索条件・認可管理はない。一般 RSS 経由の可否は今回未検証。

提案：必要な範囲を公開 RSS と認可 API に分けて調べ、SNS 情報源の共通モデルへ追加する。

受入条件案：必要権限・取得範囲・レート制限を明示し、認可を取り消せる。Feedly の実取得や利用可能プランは未確認。

実装根拠：[feedastrolabe/social.py](../feedastrolabe/social.py#L1)、[feedastrolabe/social_http.py](../feedastrolabe/social_http.py#L1)、[docs/social.md](../docs/social.md#L1)。

#### F19 概念・別名・分類を使う検索と AI Feed

判定：**一部あり** ／ Feedly の観測：**候補 UI・有料案内** ／ 証跡：E16, E17

Feedly：ransomware 入力時に Basic keyword match と説明・別名付き AI Models が分かれて表示され、脆弱性・脅威アクター・IoC 等の検索テンプレートがあった。AI Feed 追跡はアップグレード案内。

FeedAstrolabe：リテラルな保存検索、別名を持つ対象、CVE/IP 等の抽出、SNS の AI 話題抽出はある。概念候補を選ぶ記事横断検索や脅威分類体系はない。

提案：ローカルの別名展開や既存対象による絞り込みから開始する。Feedly 相当の分類モデルや全 Web 検索は独立した大規模要件。

受入条件案：単語一致と概念判定を区別し、対象範囲・一致理由・誤分類の修正手段を持つ。モデル品質や全体網羅性は今回比較できていない。

実装根拠：[feedastrolabe/triage.py](../feedastrolabe/triage.py#L20)、[feedastrolabe/entities.py](../feedastrolabe/entities.py#L9)、[feedastrolabe/social_ai.py](../feedastrolabe/social_ai.py#L1)。

#### F20 記事からの外部保存・共有連携

判定：**一部あり** ／ Feedly の観測：**設定一覧** ／ 証跡：E20

Feedly：Saving & Sharing に Evernote、OneNote、Instapaper、Mastodon、メール、Custom sharing 等の設定が並んでいた。接続や共有は実行していない。

FeedAstrolabe：引用付きレポートと承認付き SMTP／署名 Webhook があるが、個別記事から外部ノートや後で読むサービスへ保存する組み込み連携はない。

提案：用途のある連携から記事 URL・タイトルの送出導線を検討する。既存レポート通知とは契約を分ける。

受入条件案：送信する項目と宛先を確認でき、不要な本文を送らない。各サービスの現在の API・利用条件や実接続は実装時に確認する。

実装根拠：[docs/reports-operations.md](../docs/reports-operations.md#L1)、[feedastrolabe/templates/article_detail.html](../feedastrolabe/templates/article_detail.html#L1)、[feedastrolabe/delivery.py](../feedastrolabe/delivery.py#L1)。

## 既存機能を活かす実装順序

1. **読む体験**：F02 履歴、F03 古い順、F05 複数選択。履歴は既読フラグと分離し、並び順は reader_stream / reader_navigation / 追加読み込みを同時に設計する。
2. **条件の共通化**：F04 詳細検索と F06 日付指定既読。保存検索の all / any / none と一般記事検索の意味を整理し、UI から同じ条件モデルを扱う。
3. **追加のしやすさ**：F01 RSS 探索。次に F07 単独 URL 保存と F15 Google News。取得処理・プレビュー・確定操作を共通化できる部分を確認する。
4. **読み疲れの軽減**：F08 非表示、F12 重複のリーダー内集約、F13 文字サイズ。近似判定と人気度は、根拠・品質評価が用意できてから追加する。
5. **データ構造や運用の拡張**：F09 複数フォルダーは schema と順序保存に影響する。F17〜F20 の接続先やモデル拡張は、具体的な利用目的を決めて別変更とする。

この順序は推奨で、実装時間や費用の確定見積もりではない。履歴・非表示を個人単位にするか、既存の共有ライブラリ単位にするかは設計時に決める。

## 差分が小さい／既にあるため、丸ごと新設しないもの

- **Read later / Boards**：スター、複数案件への記事関連付け、タグ、案件メモが既にある。独立した「後で読む」を作るなら、スターとの使い分けを先に決める。
- **AI 要約・翻訳・質問**：出典付き調査補助が存在する。残る課題は記事からの入口、対象範囲、品質・実モデル検証。機能がないわけではない。
- **保存検索・優先度・ダイジェスト**：案件単位のウォッチで対応済み。リーダー全体への展開や Today との統合を検討する。
- **重複整理**：完全一致／正規化 URL の根拠グループはある。近似重複、同一話題、一覧のまとめ表示が追加範囲。
- **本文パネル・連続読み込み・テーマ・基本ショートカット・フォルダー D&D**：既存実装がある。Feedly を模倣して重複した設定や入口を増やさない。
- **レポート・通知・STIX**：承認付き通知と限定 STIX 出力を備える。外部ノート保存、TAXII、全面的な threat actor / malware / ATT&CK 体系は同じものではない。
- **ページ観測**：変化の検知には対応済み。個々の記事リンクを抽出する RSS Builder とは目的が異なる。

リポジトリの方針に従い、情報源管理の独立一覧、専用の並び順設定ページ、表示件数上限やページ送りを再導入しない。新しい情報源は「集める」、編集は左ペイン、記事操作は対象の近くに置く。実装へ進む段階では OpenSpec に要件・設計・受入条件を作成する。本調査で製品コードや DB を変更していない。

## 今回、機能の成否を判定していない領域

Team Newsletter / Share With Teammates の入口は見えたが、作成・招待・配信・権限分離は確認していない。チーム共有、共同編集、通知の自動配信を動作確認済みの差分とは扱わない。

Feedly AI の重要文抽出・意味検索・重複判定の精度、購読元の過去記事網羅性、ニュースレターの実受信、Reddit の認可、RSS Builder の生成、モバイル専用アプリ・オフライン・拡張機能、外部サービスへの実送信、性能・アクセシビリティ全般は未検証。Go to の入口は確認したが、クリック後のダイアログ動作は確認できなかった。これらを「正常動作する」として実装優先度の根拠にはしない。

## Feedly の一次情報と証跡索引

画面の入口：[Today](https://feedly.com/i/my/me)、[Follow sources](https://feedly.com/i/discover)、[Search](https://feedly.com/i/search)。各項目の根拠はログイン後の実画面であり、公開サイトの広告だけから機能の成否を推定したものではない。Preferences はアカウントメニューから開くモーダル。

以下は2026-10-25 JSTに Playwright MCP で採取したスナップショットの識別子。生データには個人用の情報が含まれるため、本文には一般的な機能説明だけを残す。一時ディレクトリが削除されると生スナップショットへは戻れないが、本書の観測記録は残る。

- **E01**：サイト URL から3種類の RSS 候補・記事・更新頻度、Build RSS feed。`page-2026-10-24T22-16-01-831Z.yml`

- **E02**：Top Feeds / Explore、トピック・サイト・RSS 検索、言語選択。`page-2026-10-24T22-15-49-908Z.yml`

- **E03**：Google News のキーワード・言語・対象サイト入力と検索演算子の説明。`page-2026-10-24T22-15-38-215Z.yml`

- **E04**：ニュースレター受信のアップグレード案内。実受信は未確認。`page-2026-10-24T22-15-31-123Z.yml`

- **E05**：Reddit の検索・コミュニティ・個人フィードの接続説明。未接続。`page-2026-10-24T22-15-43-795Z.yml`

- **E06**：Recently read 一覧。既読記事を1件開いて閉じた。`page-2026-10-24T22-17-26-002Z.yml`

- **E07**：保存記事の Newest / Oldest 選択肢。変更なし。`page-2026-10-24T22-17-10-497Z.yml`

- **E08**：General: 並び順、Article view、個別設定の上書き、開始画面など。`page-2026-10-24T22-18-30-814Z.yml`

- **E09**：Appearance: Font family / Text size / Display density。`page-2026-10-24T22-18-38-524Z.yml`

- **E10**：Mark as Read: older than メニュー、スクロール・キー操作の自動既読説明。`page-2026-10-24T22-18-48-484Z.yml`

- **E11**：Feedly AI: 近似重複、話題集約、エンティティ・重要文強調の説明。生成なし。`page-2026-10-24T22-18-56-218Z.yml`

- **E12**：記事・PDF の URL 追加欄。追加なし。`page-2026-10-24T22-20-38-287Z.yml`

- **E13**：複数フォルダーのチェック欄。変更せずキャンセル。`page-2026-10-24T22-20-09-168Z.yml`

- **E14**：UI 上で50記事を選択し Save to Board を確認。その後全選択解除。`page-2026-10-24T22-21-53-462Z.yml`

- **E15**：既読記事メニューの Hide / Keep Unread。実行なし。`page-2026-10-24T22-17-57-320Z.yml`

- **E16**：Search の脆弱性・脅威アクター・IoC 等の条件テンプレート。`page-2026-10-24T22-16-08-127Z.yml`

- **E17**：キーワード、AND / OR / NOT、対象情報源・期間・言語と Pro+ 案内。`page-2026-10-24T22-16-22-899Z.yml`

- **E18**：Today / Me のフォルダー別セクションと Explore。`page-2026-10-24T22-21-19-692Z.yml`

- **E19**：フォルダー／フィードの Add to Favorites メニュー。`page-2026-10-24T22-19-25-901Z.yml`

- **E20**：Saving & Sharing: Notes、外部保存先、メール、カスタム共有の設定。`page-2026-10-24T22-18-43-455Z.yml`

- **E21**：一覧フィルターの Unread Only / Show Muted Articles。`page-2026-10-24T22-19-16-311Z.yml`


## 成果物の検証

20件の識別子の一意性、参照ソースファイルの存在と行番号範囲、21件の観測証跡と MCP スナップショットの対応を機械的に確認した。比較ビューは TypeScript の strict 型検査を通過した。文書への個人名・アカウント識別子の混入も点検した。製品実装を変更していないため、製品テストやコンテナ再構築は実施していない。
