# 情報収集・調査ワークスペース実装計画

作成日：2026-10-08。対象はセキュリティ、OSINT、ネットワーク、生成 AI の情報収集・検証・整理です。第六段階の調査案件・版付きメモ・タグは実装済みです。第七〜第十四段階まで実装・検証済みです。実モデル／実通知とCI権限などの外部設定は未確認・未稼働として残します。

## 現在の基盤と方針

第五段階までの RSS/SNS/ページ観測、購読管理、API、設定、Compose を再利用します。Flask、SQLite、日本語の server-rendered UI、単一ユーザー／共有ライブラリを維持します。ワークスペースは調査テーマの整理単位であり、ユーザーごとの閲覧権限分離を意味しません。

Cloudflare の実接続と X の実資格情報検証は既存タスクで延期を維持します。新しい計画の依存条件にしません。GitHub CI はテンプレートのみで、有効化には workflow 権限が必要です。モデル・新しい外部 API の利用条件や資格情報は、各段階の調査タスクで確定します。

実装順は、根拠を残せる調査基盤を先に作り、対象の関連付け・分野別連携・AI 補助へ拡張します。AI の出力も元の資料から辿れるようにし、情報源の主張、自分の仮説、検証結果を区別します。

## 第六段階：調査案件・メモの基盤

Change：[phase-six-research-workspaces](../openspec/changes/archive/2026-10-08-phase-six-research-workspaces/proposal.md)

- 調査目的、確認したい問い、状態、アーカイブを持つワークスペース。
- 同じ購読・記事を複数案件に関連付ける。記事の複製や購読の移動は不要。
- Markdown メモ、タグ、事実／情報源の主張／仮説の区別、メモの版履歴。
- UI/API による操作と、公開／内部／制限付きの外部送信分類。

受入条件：案件をアーカイブしても記事・既読・スターが消えない。メモの同時編集は409で保護。UIのCSRF、API権限、Markdownの安全な表示を確認する。

依存：実装済みの第一〜第五段階。実装済み。操作は [research.md](research.md)、受入結果は [検証記録](verification-phase-six.md) を参照。

## 第七段階：根拠保存・出典管理

Change：[phase-seven-evidence-provenance](../openspec/changes/archive/2026-10-08-phase-seven-evidence-provenance/proposal.md)

- 取得時の本文／選択要素テキストを、変更されない根拠の版として保存。
- URL、発行元、公開日時、観測日時、取得日時、取得方法、SHA-256、引用位置を保持。
- テキスト・Markdown・PDF資料の添付と、制限付きの安全な抽出・ダウンロード。
- 記事・購読を削除しても、案件に固定した根拠・引用を保持。
- DBと根拠ファイルを一緒に検証して backup/restore する。

受入条件：上流の訂正や購読削除後も引用が同じ版を指す。容量上限・不正ファイルを拒否。欠損ファイルのあるバックアップを正常復元と扱わない。

依存：第六段階。保存内容が加工済み表現であることと、ハッシュが真実性の保証ではないことを表示します。既存記事の後付け保存は、その時点で保存したものとして記録します。

## 第八段階：ウォッチリスト・保存検索・整理

Change：[phase-eight-watchlists-triage](../openspec/changes/archive/2026-10-08-phase-eight-watchlists-triage/proposal.md)

- 製品・組織・識別子・テーマの監視と、案件ごとの保存検索。
- 含める／除外する条件、優先度ルールと判定理由。
- 同一URL・本文の重複グループ化。元資料と状態は保持。
- アプリ内の一致イベント一覧、日次ダイジェスト、再処理。

受入条件：再試行しても通知イベントが重複しない。除外判定でも元資料は消えない。重複グループから各出典へ戻れる。

依存：第六・第七段階。任意SQLや無制限の正規表現を実行しません。メール／Webhookへの送信は第十四段階です。

**ここまでをMVPの完了条件**とします。案件を作り、情報を紐付け、根拠を保存し、関心対象の新着を整理できる状態です。

## 第九段階：対象抽出・関係・タイムライン

Change：[phase-nine-entities-relations](../openspec/changes/archive/2026-10-08-phase-nine-entities-relations/proposal.md)

- CVE、ドメイン、IP、ASN、ハッシュ、リポジトリ識別子の抽出・正規化。
- 組織・製品・モデルの別名と手動訂正、対象ごとの横断検索。
- 根拠・確度・観測時点・有効期間を持つ関連付け。
- 件数を制限したグラフ、時系列表示、統合と取り消しの履歴。

受入条件：同じIPの表記違いを集約し、元の表記と出典も保持。共有IPを所有者の同一性と断定しない。誤った統合を元に戻せる。

依存：第七・第八段階。初期抽出は規則ベースで、名前の類似性だけで自動統合しません。

## 第十段階：脆弱性・セキュリティ情報連携

Change：[phase-ten-security-intelligence](../openspec/changes/archive/2026-10-08-phase-ten-security-intelligence/proposal.md)

- 共通の外部連携ジョブ、許可接続先、キャッシュ、予算・レート待機、出典管理。
- CISA KEV、FIRST EPSS、CVE／ベンダーの参照情報。
- 影響製品、修正・回避策、PoCの参照、悪用状況の評価カード。
- 関心製品との該当確認：確認済み／可能性あり／不明。

受入条件：KEVの悪用確認、EPSSの予測値、CVSSの深刻度を区別。取得失敗は古い値／不明を表示し、ゼロや安全と扱わない。PoCを自動実行しない。

依存：第九段階。非公開メモや添付資料は外部の調査APIへ送らず、選択した公開識別子だけを扱います。

## 第十一段階：DNS・証明書・経路の観測

Change：[phase-eleven-network-intelligence](../openspec/changes/archive/2026-10-08-phase-eleven-network-intelligence/proposal.md)

- 公開DNS・RDAP、RIPEstatの経路／RPKI、CTの証明書メタデータを順に連携。
- 時点付き観測、TTL・取得元・対象範囲、フィールドごとの差分。
- ドメイン／IP／ASNの履歴を案件・対象・ウォッチリストに関連付け。
- 取得頻度、呼出上限、履歴の保存期間。

受入条件：証明書の発行を実稼働の証拠と混同しない。データの欠落と観測された不存在を区別。origin ASNの変化を自動的に経路ハイジャックと断定しない。

依存：第九・第十段階。初期範囲は受動的な公開情報の参照です。ポートスキャン、内部ネットワーク探索、ルーター／ROA設定変更は含めません。

## 第十二段階：生成AIの論文・モデル・実装追跡

Change：[phase-twelve-ai-research-tracking](../openspec/changes/archive/2026-10-08-phase-twelve-ai-research-tracking/proposal.md)

- arXivの検索・論文版、GitHubのリリースを増分収集。
- 論文・モデル・コード・モデルカードの関連付け。
- 出典付きのライセンス、利用条件、必要環境、モデルの主張。
- データセット・評価条件・指標・測定元を持つベンチマーク記録。
- 公表値と自身の再現結果を分離。

受入条件：論文の更新で旧版の根拠を上書きしない。ライセンス不明を許可と扱わない。条件の違う評価を同一条件として順位付けしない。

依存：第九・第十段階。モデルの重みやリポジトリを自動取得・実行する機能は含めません。

## 第十三段階：出典付きAI調査補助

Change：[phase-thirteen-grounded-assistant](../openspec/changes/archive/2026-10-08-phase-thirteen-grounded-assistant/proposal.md)

- 日本語要約、翻訳、複数資料比較、案件内の質問応答。
- 根拠の版・引用位置を検証した出典表示、不足／矛盾の提示。
- ローカル／承認した外部モデルの選択、送信本文の事前表示、費用・処理量上限。
- モデル・プロンプト・入力資料・出力・人手レビューの履歴。

受入条件：根拠がない場合は不明と返す。制限付き資料は既定で外部送信しない。記事内の命令から秘密情報参照や設定変更を行わない。別案件の資料を誤って参照しない。

依存：第七・第九・第十二段階。初期状態は無効。モデル／提供元は実装時に公式仕様・利用条件・費用を確認して選びます。AIによる外部アクセス・シェル実行・設定変更は提供しません。

## 第十四段階：レポート・通知・運用

Change：[phase-fourteen-reports-operations](../openspec/changes/phase-fourteen-reports-operations/proposal.md)

- 出典付きMarkdownレポート、根拠マニフェスト、JSON／CSV、検証したSTIX 2.1サブセット。
- 任意のメール／Webhook送信、宛先・接続先・送信本文の確認、再試行と重複防止。
- ワーカーのheartbeat、処理履歴、停止検知、運用画面。
- 根拠ファイルを含む定期バックアップ、世代管理、停止状態での検証付き復元。
- 全体設定・記事状態の一括更新・OPMLの管理APIと、権限がある場合のCI有効化。

受入条件：既定で秘密情報・制限付き資料を出力しない。CSV式の注入、WebhookのSSRF、再送重複を防ぐ。稼働中／壊れたバックアップからの復元を拒否する。

実装：schema13、固定資料の不変出力、署名Webhook／TLSメールの承認待ちqueue、heartbeat、定期世代bundleとruntime生存中の復元拒否、管理API。[操作と限界](reports-operations.md)、[検証](verification-phase-fourteen.md)。依存：第八・第十一・第十二段階。AI補助には依存しないため、モデルが未設定でも人手の調査レポートを出せます。APIキー発行のAPI化、複数ユーザー権限、完全なSTIX/TAXII互換性は別の設計が必要です。

## 初期の上限と外部設定

- 案件名120文字、メモ本文10万文字、タグ名80文字、API一覧100件／ページを初期上限とします。
- 添付は1件10MiB、ライブラリ容量は初期500MiBの設定可能な上限。根拠の固定と保存期間は別に扱います。
- グラフは初期depth2／表示200ノード。大量の結果はページ送り・対象の絞り込みで扱います。
- 外部APIの呼出予算、モデルのトークン・費用上限は実装前に公式条件と運用希望から確定。資格情報はチャット／Gitに入れず、無効状態のまま機能を検証できる設計にします。
- スクリーンショット・ログイン観測、複数ユーザー権限、キーボード操作・表示テーマ・全文抽出は今回の調査基盤計画に含めず、別changeの候補として保持します。

## 依存関係と完了判定

基本順序は第六→第七→第八→第九→第十です。その後のネットワーク連携とAI研究追跡は共通連携基盤の上に個別に進められます。AI補助はAI研究追跡と根拠基盤の後、レポート・運用は分野別連携の後に進めます。

各 change の `tasks.md` には前提確認、実装、受入テスト、UI/API/コンテナ確認、文書・秘密情報検査・Git管理、仕様同期・archiveを記載しました。**第六〜第十四は実装・検証済み（実モデル・実通知は未設定、CIはworkflow権限待ち）**です。OpenSpecのartifactが揃っていることと、機能が実装済みであることは区別します。後続changeは依存する実装が完了するまで着手しません。

1. 実装前：依存するchangeと現在のコード・schemaを確認し、必要なら仕様を更新して厳格検証。
2. 実装：タスクごとに実装し、意味のある受入テストが通った項目のみ完了にする。
3. 運用確認：移行前backup、既存ID／既読／スター保持、実HTTP、レスポンシブUI、コンテナ再作成を確認。
4. 外部連携：fixture確認と実接続確認を分け、未設定の資格情報・利用条件は未確認と記録。
5. 配布：OpenSpec全体検証、Git候補と履歴の秘密情報検査、commit/push、検証記録。
6. 完了：受入完了後に仕様を同期・archive。未完了の外部接続を完了扱いしない。

開始時に選択する change：

```sh
openspec status --change phase-nine-entities-relations --json
openspec instructions apply --change phase-nine-entities-relations --json
openspec validate --all --strict --no-interactive
```

第六段階ではスキーマ v5 のランタイム実装・DB移行を完了しました。後続段階や外部送信は未実装です。日程・工数は、初期MVPの実装実績と外部サービス条件を確認してから見積もります。

## 連携仕様の一次資料

- [CISA KEVデータ](https://github.com/cisagov/kev-data)：悪用確認カタログ。
- [FIRST EPSS](https://www.first.org/epss/)：30日以内の悪用確率の推定。環境固有の影響評価とは区別。
- [RIPEstat](https://stat.ripe.net/docs/data-api/api-endpoints/routing-history)：経路履歴。用途・API条件は実装前に再確認。
- [Certificate Transparency](https://certificate.transparency.dev/howctworks/)：証明書ログの仕組み。
- [arXiv API条件](https://info.arxiv.org/help/api/tou.html)、[GitHub Releases API](https://docs.github.com/en/rest/releases/releases)：検索・版／リリース収集。
- [STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html)：対象・関係・確度の交換形式。
- [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)：生成AIの情報完全性等のリスク検討資料。
