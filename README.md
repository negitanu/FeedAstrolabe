# FeedAstrolabe

RSS/Atom・SNS・Webページの更新を集め、記事の閲覧から根拠付きの調査まで行う個人利用向けアプリです。Flask / SQLite で実装し、「読む・集める・調べる・まとめる・設定」から操作できます。

## コンテナで起動

`compose.yml` に Web、定期収集 worker、ページ観測 observer、隔離 renderer、Cloudflared Tunnel をまとめています。

1. `.env.example` を参考に `.env` を作成し、必須の `TUNNEL_TOKEN` を設定します。
2. Cloudflare 側で公開ホスト名、Access の許可ポリシー、Protect with Access を設定します。
3. コンテナを起動します。

```sh
docker compose config --quiet
docker compose build --pull
docker compose up -d --wait
```

Cloudflare Access 経由で公開 URL を開きます。ホストのポートは公開しません。データは `feedastrolabe_reader-data` ボリュームに保存します。任意の Ollama・通知連携も追加 Compose ファイルなしで設定できます。

状態確認・ログ・停止：

```sh
docker compose ps
docker compose logs --tail 50 web worker
docker compose down
```

`down` ではデータボリュームを削除しません。認証・任意連携・バックアップと復旧の詳細は[配備手順](docs/deployment.md)を参照してください。外部公開の受入確認は、実ドメインと資格情報を設定した環境で行ってください。

## ローカルで開発

macOS / Linux と Python 3.15 系を使用します。依存バージョンは `requirements.txt` に固定しています。

```sh
python3.15 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m feedastrolabe
```

[ローカル画面](http://127.0.0.1:5000)を開いて RSS / Atom の URL を登録します。「集める」→「RSS / Atom」で Webサイトまたはフィードの URL を入力すると、候補と最新記事を確認してから購読できます。確定時に初回取得を行います。HTML の alternate RSS/Atom 宣言を探索し、最大8候補を表示します。

別ターミナルで定期収集を起動します。既定は15分、最小は60秒です。

```sh
.venv/bin/python -m flask --app feedastrolabe worker
```

一度だけ更新する場合：

```sh
.venv/bin/python -m flask --app feedastrolabe refresh
```

Web だけでは定期収集しません。Web と worker は Ctrl-C で停止します。手動更新と worker の処理が競合した場合、後からの更新は実行中として扱います。

必要な依存だけを導入する場合は pip 25.1 以上で `pip install -c requirements.txt --group app` を使います。`pyproject.toml` の `app` は通常実行用、`renderer` はページ観測用、`test` はテスト用です。ブラウザーの導入と observer の起動は[ページ観測の手順](docs/observation.md)を参照してください。

コンテナは公式 `python:slim` を基底に、Python 3.15 系であることをビルド時に検査します。アプリ・renderer・cloudflared は `latest` タグを使用します。Hardened Images を利用できなかった理由とイメージ構成は[ビルドの検証記録](docs/verification-slim-unified-build.md)に記載しています。

## 記事を読む・購読を整理する

- RSS / Atom、Mastodon、Bluesky、ページ観測の記事をフォルダー単位でまとめて閲覧できます。X の新規収集は終了していますが、保存済み記事は保持します。
- フォルダー名で所属記事を表示し、矢印で開閉します。開閉状態はブラウザーに保存します。フォルダー・フィードの並べ替えとフォルダー間移動は左ペインのドラッグ操作、名前変更・設定・購読停止／再開・削除は右クリック／「⋯」から行います。左ペインの幅も変更できます。
- 記事一覧は **標準・1行・タイル** を切り替え、スクロールで追加読み込みします。本文の開閉や履歴操作でも、読み込み済み記事と一覧位置を保持します。本文は外側のクリックでも閉じ、開閉の動きは「動きを減らす」設定に従います。
- 最近読んだ記事の履歴を既読・スターと独立して保持します。公開日は新しい順／古い順、履歴は最近読んだ順でも表示できます。
- 「詳細検索」でタイトル／本文、追加語句（いずれか）、除外語句、公開日の範囲、複数の情報源を指定できます。
- 記事のチェックで最大100件を選び、既読／未読／スターを一括変更できます。選択は追加読み込みや本文の開閉でも維持されます。
- 未読・スター・フィード・フォルダー・案件・タグ・タイトル／本文検索を組み合わせられます。「全て既読」は未描画の記事を含む現在の表示条件全体が対象です。
- ライト・ダーク・システム連動、UTC／JST の表示に対応します。タイムゾーンはライブラリ共通で、保存日時・API・レポート・日時の入力条件は UTC です。

### 記事詳細

通常クリックで詳細を右側に重ねて表示します。一覧幅を変えず、上部ヘッダーとパンくずを避けた記事欄内で独立してスクロールします。中クリックまたは詳細タイトルのリンクで、元記事を新しいタブに開きます。

詳細は、アイキャッチ → タイトル → 時刻 → 既読・保存操作 → 横線 → 記事説明 → 横線 → 調査案件・タグ・根拠保存 → 前の記事・件数・次の記事の順です。アイキャッチは元ページの OGP / Twitter Card から取得できた場合だけ、幅480px（狭い画面では縮小）で表示します。

「既読にして次へ」は現在の記事を既読にし、同じ表示条件の次の記事へ進みます。最後の記事では一覧に戻ります。通常は詳細を開くだけでは既読になりません。「開いたら既読」の設定も選択できます。中クリックでは既読状態を変更しません。

JavaScript 無効時は標準表示・ネイティブの折り畳み・「すべて表示」による全件閲覧を利用できます。[画面と操作の手順](docs/navigation.md)を参照してください。

## 情報を集める・調べる・まとめる

- **SNS 調査**：Mastodon のハッシュタグ／アカウント、Bluesky のキーワードを収集し、注目投稿・関連タグ・履歴を表示します。OpenRouter / OrcaRouter による出典付き話題抽出、定期実行、予算上限にも対応します。[SNS 設定](docs/social.md)、[話題抽出](docs/openrouter-topics.md)。
- **ページ観測**：公開 URL と CSS セレクターを登録し、JavaScript 描画後のテキスト変化を差分記事にします。renderer はネットワークと DB から隔離し、observer が検証した同一オリジンのリソースだけを仲介します。ログイン・画像比較は対象外です。[設定と制限](docs/observation.md)。
- **調査案件・メモ・タグ**：記事を複数の案件へ関連付け、事実・情報源の主張・仮説を分けた Markdown メモを版管理します。アーカイブ／再開、公開区分、同時編集の競合検出に対応します。[操作と制限](docs/research.md)。
- **根拠・添付**：記事などを取得時点の根拠として保存し、引用や添付ファイルの来歴を保持します。[保存・引用・復旧](docs/evidence.md)。
- **ウォッチリスト・振り分け**：保存検索、理由付き優先度、受信箱、UTC 日次ダイジェスト、出典を残した重複整理を利用できます。[使い方](docs/triage.md)。
- **対象・関係**：CVE・IP・ドメイン・ASN・ハッシュ・リポジトリなどを扱い、出典付きの確認・訂正・別名・統合、引用付き関係、グラフ／タイムラインを管理します。[操作と上限](docs/entities.md)。
- **セキュリティ情報**：CISA KEV・FIRST EPSS・CVE Services の情報を日付と固定根拠付きで保持します。連携は明示的に有効化し、取得失敗時は直前の成功データを保持します。[設定と取得上限](docs/security-intelligence.md)。
- **ネットワーク情報**：DNS・RDAP・CT・経路・RPKI の受動観測と履歴、項目別変化、観測間隔・保存設定を扱います。[操作と観測範囲](docs/network-intelligence.md)。
- **AI 研究**：arXiv 論文版、GitHub 公開リリース、引用付きモデル版カード、ライセンス・評価・再現メモを管理します。[操作と範囲](docs/ai-research.md)。
- **出典付き調査補助**：Ollama と接続し、入力プレビューと承認を経て、固定引用付きの要約・翻訳・比較・回答を作成します。実モデルの品質検証は未確認です。[設定と制御](docs/grounded-assistant.md)。
- **レポート・通知・運用**：`/operations` でレポート、通知承認、ワーカー状態、世代バックアップを利用できます。実通知の受入確認は未実施です。[運用方法](docs/reports-operations.md)。

## 設定・API

設定画面でポーリング間隔、初期ビュー、API レート上限、表示タイムゾーンを変更できます。「AI接続」で OpenRouter / OrcaRouter を切り替え、設定エクスポートから秘密情報を除いた JSON を取得できます。[AI 接続と設定の持ち出し](docs/ai-providers-and-settings-export.md)を参照してください。

API は読み取り／書き込み権限と期限を持つ Bearer キーを必須とします。キーの発行・失効、記事取得、既読／スター更新、購読追加・編集・削除・手動更新に対応します。OPML のインポートは確認画面で追加予定・登録済み・重複を確認してから実行します。[API の利用方法](docs/api.md)を参照してください。

## 安全性と取得制限

ローカル開発の UI は既定で認証なしの localhost 専用です。コンテナでの公開は Cloudflare Access / Protect with Access に委ねます。

CSRF 保護、HTML 許可リスト、公開 IP の検証、DNS 固定、サイズ・時間・リダイレクト制限を備えます。本文中の外部画像や埋め込みは表示せず、任意のアイキャッチだけを安全な取得処理と同一オリジン配信で表示します。

取得は標準 HTTP(S) ポート、最大5 MiB、一度に最大2,000記事に制限し、非圧縮の `identity` 応答を要求します。DNS 解決時間は OS のリゾルバー設定に依存します。RSS / Atom・OPML の DTD・実体参照・外部参照・不正な XML は拒否します。取得に失敗しても既存記事・既読・スターは保持します。

秘密情報や実データは Git に含めません。push 前に以下を実行します。[検査範囲と限界](docs/security.md)も参照してください。

```sh
python3 scripts/check_secrets.py --staged --history
```

## データとバックアップ

ローカルの既定保存先は `instance/feeds.sqlite3`、秘密鍵は `instance/secret.key` です。`FEEDASTROLABE_DATA_DIR` に絶対パスを指定すると変更できます。Web・worker・observer は同じデータ保存先を使用します。

根拠ファイルを含むライブラリは `maintenance backup-bundle` / `restore-bundle` で DB とファイルを一貫して保存・復元します。停止してデータディレクトリ全体をコピーする方法も利用できます。稼働中の DB ファイル単体コピーでは WAL の内容や根拠ファイルが欠落する可能性があります。[配備・復旧手順](docs/deployment.md)と[根拠の復旧](docs/evidence.md)を参照してください。

## 開発・仕様・検証

開発・UI・検証・Git 管理・コミット名義の方針は [AGENTS.md](AGENTS.md) にまとめています。

現在の仕様は `openspec/specs/`、変更ごとの要件・設計・受入条件・タスクは `openspec/changes/` にあります。実装前に仕様を作成し、strict 検証と対応するテストを実行します。スキルは `.codex/skills/` にあります。

```sh
openspec validate --all --strict --no-interactive
.venv/bin/python -m pytest
```

過去の計画や検証記録には、後続変更で置き換えられた仕様も含みます。[調査ワークスペース計画](docs/research-workspace-plan.md)、[基盤・連続読み込みの検証](docs/verification-reader-platform-provider-refresh.md)、[詳細表示順の検証](docs/verification-article-detail-content-order.md)、[詳細パネル範囲の検証](docs/verification-constrain-detail-to-reader.md)を参照してください。

5機能の操作・検索条件・制限は[読む・集めるの拡張](docs/reader-productivity.md)、検証結果は[検証記録](docs/verification-reader-discovery-history-controls.md)を参照してください。

詳細の外側クリック・開閉の動き・faviconの更新は[検証記録](docs/verification-reader-panel-polish.md)を参照してください。
