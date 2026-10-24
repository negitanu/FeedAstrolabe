# FeedAstrolabe

個人利用向けの RSS/Atom リーダー。RSS、SNS、API・設定、Playwright のページ観測と調査ワークスペースを Flask / SQLite で実装しています。Cloudflare の実公開は接続先の設定後に行います。

## 標準起動（Cloudflared Tunnel）

`compose.yml` に Web・収集worker・observer・renderer・Tunnelをまとめています。`.env` の必須項目は **`TUNNEL_TOKEN` だけ**です。公開ホスト名・Accessの許可ポリシー・Protect with Accessは[Cloudflare側で設定](docs/deployment.md)します。Tunnel tokenの別ファイルは不要です。

```sh
docker compose config --quiet
docker compose build --pull
docker compose up -d --wait
```

公開URLをCloudflare Access経由で開きます。Dockerのホストポートは公開せず、サービス間はbridgeネットワークを使い、rendererはネットワークから隔離します。データは従来と同じ `feedastrolabe_reader-data` ボリュームへ保存します。X・Ollama・通知の任意設定も `.env` のファイルパスだけで指定でき、追加Composeファイルは不要です。

## native 開発起動

Python 3.15 系（最新安定パッチ）（macOS / Linux）を使用します。全依存の固定バージョンは `requirements.txt` に集約しています。以下は観測・テスト用を含む開発環境の導入です。

```sh
python3.15 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m feedastrolabe
```

http://127.0.0.1:5000 を開き、RSS / Atom の URL を登録してください。登録時に初回取得を行います。通常の Web ページからのフィード自動探索は未対応です。

必要な依存だけを導入する場合は、pip 25.1以上で `.venv/bin/python -m pip install -c requirements.txt --group app` を使います。`pyproject.toml` の `app` は通常実行用、`renderer` は観測用、`test` は全テスト用です。ブラウザー本体の導入は[観測の手順](docs/observation.md)を参照してください。

Dockerは公式 `python:slim` を基底にPython 3.15系をビルド時に検査し、アプリ・renderer・cloudflaredは`latest`タグを使用します。対象のHardened Imagesは今回の環境で解決できず、公式イメージを採用しました。Dockerも単一の `Dockerfile` を使い、Composeが通常実行用の `app` と観測用の `renderer` を選びます。通常実行イメージにブラウザーやテスト依存を含めず、観測イメージにはheadless shellだけを入れます。[統合・容量の検証記録](docs/verification-slim-unified-build.md)を参照してください。

別のターミナルで定期収集を起動します（既定 15 分、最小 60 秒）。

```sh
.venv/bin/python -m flask --app feedastrolabe worker
```

一回のみ更新する場合：

```sh
.venv/bin/python -m flask --app feedastrolabe refresh
```

Web と worker は Ctrl-C で停止します。Web の起動だけでは定期更新しません。手動更新と worker が競合すると、後からの更新は実行中として扱います。

## 機能

画面の入口は「読む・集める・調べる・まとめる・設定」です。フォルダー名は所属フィードの記事を表示し、矢印だけで開閉します。フォルダーとフィードは左ペイン内でドラッグして並べ替え、フィードは別フォルダーへ移動できます。右クリック／「⋯」から名前変更・編集・購読停止／再開・削除を行います。左ペインの幅は境界をドラッグして変更できます。

記事一覧はスクロールで追加読み込みし、本文を開閉しても読み込み済みの記事を維持します。「全て既読」は未描画分も含む表示条件全体が対象です。「設定」→「AI接続」でOpenRouter／OrcaRouterを選択できます。設定一覧の「設定をエクスポート」から、秘密情報を除いたJSONをダウンロードできます。[操作手順](docs/navigation.md)と[実装・検証記録](docs/verification-reader-platform-provider-refresh.md)を参照してください。

- RSS/Atom 登録、削除、フォルダー変更、フィードごとの取得状況・エラー。
- フィード一覧はフォルダーを最上位にし、RSS / Atom・Mastodon・Bluesky・ページ観測（保存済みX記事も保持）を同じフォルダーの中にまとめます。各フィードに種類ラベルを表示し、フォルダーには1件以上の未読件数を表示します。「未分類」も折り畳めます。開閉はブラウザーに保存し、フォルダー名やフィードを選んでも開閉状態は変えません。旧来の種類別フォルダー設定は、全種類が閉じていた場合だけ閉状態を引き継ぎます。
- 記事一覧の「表示形式」で **標準・1行・タイル** を切り替えられます。表示形式は同じブラウザー・同じアクセス先で保存し、検索・追加読み込み・本文表示後も復元します。並び順・検索条件・既読・スターは共通です。1行表示はタイトルを省略して密に並べ、タイル表示はタイトルと要約のカードを画面幅に合わせて並べます。保存機能が使えない環境でも現在の画面で切替できます。JavaScript無効時は標準表示とネイティブの折り畳みを利用できます。
- 手動更新、定期収集、ETag / Last-Modified、重複排除。
- 案件・タグ・検索・一括既読・表示切替をコンパクトなツールバーへまとめ、見出しと記事カードの余白を削減しました。スマートフォンは「ライブラリ・フォルダー」を開いて移動でき、通常は記事を先に表示します。JavaScript無効時はナビゲーションを開いたまま利用できます。
- 日本語レスポンシブ UI、本文表示、元記事へのリンク、未読・スター・フィード・タイトル/本文検索、スクロールによる追加読み込み。JavaScript無効時は「すべて表示」で全件へ到達できます。
- 本文の「前の記事」「次の記事」で、現在のフィード・検索・案件・タグ・未読／スター条件のまま連続閲覧できます。「既読にして次へ」は現在の記事だけを既読にして、直後の記事へ進みます。最後の記事では一覧に戻ります。本文末尾にも操作を置き、モバイルでは移動先の本文へスクロールします。JavaScriptが無効でも使えます。
- 既読・スターの永続化と、現在の検索条件に一致する記事の一括既読。
- CSRF 保護、HTML 許可リスト、public IP への取得限定、DNS pinning、サイズ/時間/リダイレクト制限。

本文を開くだけでは既読になりません。「既読にする」「既読にして次へ」で変更します。外部画像や埋め込みは表示しません。取得は標準 HTTP(S) ポート限定、最大 5 MiB、一度に最大 2,000 記事です。HTTP 応答には非圧縮の identity を要求します。手動更新は同期処理なので、通常は worker を使ってください。DNS 解決の所要時間は OS のリゾルバー設定に依存します。

記事の表示条件・一括既読・手動更新では、不正な ID や重複した条件、200文字を超える検索語を HTTP 400 で拒否します。ID の省略・空欄は従来どおり全体表示です。存在しないフィードへの手動更新は404となり、取得しません。URL内の ID は1〜9223372036854775807に制限します。[入力検証の改修記録](docs/verification-input-boundary-hardening.md)を参照してください。

native の既定は認証なしの localhost UI です。API は常に Bearer キーを要求します。標準のコンテナ起動は認証をCloudflare Access／Protect with Accessへ委ねるtunnel modeです。公開前にCloudflare側の保護を設定し、公開後の受入確認を行ってください。

## データとバックアップ

既定は `instance/feeds.sqlite3`、秘密鍵は `instance/secret.key`。Git に含めません。`FEEDASTROLABE_DATA_DIR` に絶対パスを指定すると保存先を変更できます。Web と worker には同じ値を設定します。

バックアップは `maintenance backup-bundle` で DB と根拠ファイルの一貫した bundle を作成します。停止して `instance/` 全体をコピーする方法も利用できます。稼働中に DB ファイルだけをコピーすると WAL の内容が漏れる場合があります。復元時も Web/worker/observer を停止してから置き換えます。

## OpenSpec / SDD

継続する開発・UI/UX・検証・Git管理の指針は [AGENT.md](AGENT.md) にまとめています。

仕様は `openspec/specs/`、変更ごとのproposal・design・差分仕様・tasksは `openspec/changes/` にあります。直近の `reader-platform-provider-refresh` は全29タスクを完了し、Python 3.15.1で全635テストと稼働環境の確認を完了しました。[検証記録](docs/verification-reader-platform-provider-refresh.md)に結果と未実施範囲を記録しています。実装前に仕様を作成して厳格検証し、仕様に対応するテストで実装を検証します。初期化済みの Codex スキルは `.codex/skills/` にあります。

```sh
openspec validate --all --strict --no-interactive
.venv/bin/python -m pytest
```

直近の変更は本仕様へ同期済みで、変更資料は未アーカイブのまま保持しています。過去の変更資料は当時の要件・検証履歴を含み、後続変更で置き換えられた機能もあります。Cloudflareの実外部アクセス受入は引き続き未完了で、X実収集の保留項目はX新規収集終了により対象外です。新しい段階は別の change として作成してください。OpenSpec CLI は [公式手順](https://github.com/Fission-AI/OpenSpec) で導入できます（この環境は 1.3.1）。

## API・設定とコンテナ

`/settings` で全体のポーリング間隔、初期ビュー、APIレート上限を変更できます。フィード別の設定・購読停止は左ペインの右クリック／「⋯」から操作します。記事一覧のページ表示件数設定は廃止しています。APIキーは読み取り/書き込み権限と1〜365日の期限を指定して発行・失効します。OPMLのインポート/エクスポートも利用できます。UIのインポートは追加予定・登録済み・ファイル内重複をプレビューし、確認後に登録します。取り消した場合は変更せず、確認画面の有効期限は15分です。

RSS/AtomとOPMLはDTD・実体参照・外部参照・不正なXMLを拒否します。XMLの深さは64まで、要素数はRSS/Atomで100,000、OPMLで10,000までです。DTDに依存するフィードや整形式でないフィードは取得できません。失敗時も保存済みの記事・既読・スターは保持します。[取り込みの改修・検証記録](docs/verification-safe-import-preview.md)を参照してください。

「収集と表示」の「表示タイムゾーン」で UTC／JST（日本標準時）を選択できます。選択はライブラリ共通で保存され、記事・根拠・期限・運用履歴などの画面表示に反映されます。保存日時、JSON API、レポート出力、日時の検索・入力条件は UTC のままです。既存ライブラリの既定値は UTC です。

- [第二段階の検証記録](docs/verification-phase-two.md)：実施した検証と外部接続の未完了項目。
- [API の利用方法](docs/api.md)：フィード・記事取得、cursor、購読追加、既読/スター更新。
- [コンテナ・Cloudflare・復旧手順](docs/deployment.md)：単一 `compose.yml` によるTunnel起動、Access検証、任意連携の設定、backup/restore。

通常のnative開発起動はlocalhost専用です。標準のコンテナ起動は `compose.yml` のCloudflared TunnelとAccess認証を使用します。

## SNS 連携

「SNS トレンド調査」で Mastodon のハッシュタグ／Bluesky のキーワードと収集間隔を登録できます。公式APIで分野別の公開投稿を定期収集し、反応数による注目投稿・関連タグ・履歴を表示します。APIキーは不要です。RSS と共通の記事一覧でも既読・スター・検索を使えます。Mastodon アカウント購読も継続対応します。X の新規収集は終了し、既存購読は停止、保存済み記事は保持します。 AI接続にOpenRouterまたはOrcaRouterを設定すると、重要な話題・判断理由・出典を抽出できます。手動／定期収集後の自動実行と予算上限に対応します。[AI接続の設定](docs/ai-providers-and-settings-export.md)と[抽出の動作](docs/openrouter-topics.md)を参照してください。[SNS 設定と取得仕様](docs/social.md) と [第三段階の検証記録](docs/verification-phase-three.md) を参照してください。外部公開の受入確認は、実ドメインと資格情報を設定した環境で実施してください。

公開先は [GitHub](https://github.com/negitanu/FeedAstrolabe)。push 前に `python3 scripts/check_secrets.py --staged --history` を実行してください。[秘密情報の管理](docs/security.md) に検査範囲と限界を記載しています。

## 実装計画と検証状況

段階別の計画は[調査ワークスペース計画](docs/research-workspace-plan.md)、現在の画面構成は[操作手順](docs/navigation.md)、変更ごとの受入条件と完了状況は `openspec/changes/` を参照してください。

## 固定ページの観測

「集める」→「ページの変化」で公開 URL と CSS セレクターを登録します。登録後の変更は左ペインの右クリック／「⋯」から行います。初回は基準を保存し、その後のテキスト変化を差分記事として表示します。JavaScript 描画に対応し、未読・スター・検索・記事 API を共通で利用できます。

```sh
docker compose build --pull
docker compose up -d --wait
```

描画コンテナはネットワークと DB を持たず、専用 observer が検証した同一 origin のリソースだけを仲介します。[観測の設定・制限](docs/observation.md) と [第四段階の検証記録](docs/verification-phase-four.md) を参照してください。ログインや画像比較は対象外です。

## 購読管理

左ペインのフィードの右クリック／「⋯」→「設定」で RSS/ページ観測の取得 URL を修正できます。既存記事・既読・スターを保持し、次回収集で取得情報や観測基準を取り直します。API は `PATCH /api/v1/feeds/{id}`、`DELETE /api/v1/feeds/{id}`、`POST /api/v1/feeds/{id}/refresh` に対応します。すべて書き込みキーが必要です。[API 手順](docs/api.md) と [第五段階の検証記録](docs/verification-phase-five.md) を参照してください。

## 調査ワークスペースへの拡張計画

セキュリティ・OSINT・ネットワーク・生成AIを扱う [第六〜第十四段階の実装計画](docs/research-workspace-plan.md) をOpenSpecで定義しました。調査案件・根拠保存・ウォッチリストを最初のMVPとします。第六段階の調査案件・版付きメモ・共有タグは実装済みです。第七〜第十四段階を実装・検証済みです。`/operations` からレポート・通知承認・ワーカー状態・世代バックアップを利用できます。[運用方法](docs/reports-operations.md)。実モデルと実通知は未設定、CIはworkflow権限待ちです。


`/workspaces` から調査案件を作成し、既存フィード・記事を複数の案件へ関連付けられます。Markdown メモは事実／情報源の主張／仮説と版履歴を持ち、同時編集は409で保護します。共有タグ、案件／記事タグによる検索、アーカイブ／再開、公開区分を UI・API から利用できます。[操作と制限](docs/research.md)、[第六段階の検証](docs/verification-phase-six.md) を参照してください。

第七段階以降、根拠を含むライブラリは DB／blob の一貫した `backup-bundle`／`restore-bundle` を使用します。旧 DB 単体の手順は根拠を持たない snapshot に限ります。復元時は現在のDB schema 18へ移行します。[根拠・添付・復旧の手順](docs/evidence.md)を参照してください。

第八段階では案件の保存検索・ウォッチリスト、理由付き優先度、受信箱／UTC日次ダイジェスト、出典を残した重複整理を実装しました。[使い方](docs/triage.md)。

## 対象・根拠付き関係（第九段階）

CVE／IP／ドメイン／ASN／ハッシュ／リポジトリの候補抽出、手動の組織・製品・モデル登録、出典付き元表記、確認・訂正、別名、取り消せる統合、引用付き関係の版履歴、案件内のグラフ／タイムラインを提供します。[操作と上限](docs/entities.md)、[検証記録](docs/verification-phase-nine.md)を参照してください。外部照会は第十・第十一段階で提供します。

## セキュリティ情報（第十段階）

CISA KEV／FIRST EPSS／CVE Servicesの独立した日付・帰属・固定根拠、関心製品と人の引用付き適用性判断、確認済み参照リンクを提供します。公開CVEの明示許可と連携の有効化で取得し、失敗時は直前の成功データを保持します。[操作と取得上限](docs/security-intelligence.md)、[検証記録](docs/verification-phase-ten.md)を参照してください。

## ネットワーク情報（第十一段階）

DNS／RDAP／CT／経路／RPKIの受動観測、日付と固定根拠を持つ履歴、項目別変化、観測間隔と保存設定を提供します。[操作と観測範囲](docs/network-intelligence.md)、[検証記録](docs/verification-phase-eleven.md)を参照してください。

## AI研究（第十二段階）

arXiv論文版とGitHub公開リリース、引用付きモデル版カード、ライセンス・条件の不明状態、評価／再現メモと条件比較を提供します。[操作と範囲](docs/ai-research.md)、[検証記録](docs/verification-phase-twelve.md)を参照してください。

## 出典付き調査補助（第十三段階）

Ollamaの明示設定、正確な入力プレビューと承認、固定引用付き要約／翻訳／比較／回答、保守的予算、人の独立レビューを提供します。実モデルは未設定で品質検証は未確認です。[設定と制御](docs/grounded-assistant.md)、[検証記録](docs/verification-phase-thirteen.md)を参照してください。

### 記事一覧とフロート詳細

記事一覧の通常クリックで、一覧幅とスクロール位置を保ったまま右側に詳細を重ねて表示します。詳細は独立してスクロールでき、モバイルでは画面幅に収まります。「閉じる ×」で一覧に戻ります。記事の中クリックは元ページを新しいタブで開き、既読状態を変更しません。詳細タイトルも元ページへの別タブリンクです。元URLがない記事ではリンクを表示しません。上側の前後移動・件数表示と「元記事を開く」ボタンは廃止し、本文末尾の前後移動と「既読にして次へ」は利用できます。
