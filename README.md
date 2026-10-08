# FeedAstrolabe

個人利用向けの RSS/Atom リーダー。RSS、SNS、API・設定、Playwright のページ観測と調査ワークスペースを Flask / SQLite で実装しています。Cloudflare の実公開は接続先の設定後に行います。

## 起動

Python 3.11 以上（macOS / Linux）を使用します。`requirements-lock.txt` は検証時の全依存バージョン（テスト用を含む）を固定しています。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m feedastrolabe
```

http://127.0.0.1:5000 を開き、RSS / Atom の URL を登録してください。登録時に初回取得を行います。通常の Web ページからのフィード自動探索は未対応です。

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

- RSS/Atom 登録、削除、フォルダー変更、フィードごとの取得状況・エラー。
- 手動更新、定期収集、ETag / Last-Modified、重複排除。
- 日本語レスポンシブ UI、本文表示、元記事へのリンク、未読・スター・フィード・タイトル/本文検索、30 件ごとのページ送り。
- 既読・スターの永続化と、現在の検索条件に一致する記事の一括既読。
- CSRF 保護、HTML 許可リスト、public IP への取得限定、DNS pinning、サイズ/時間/リダイレクト制限。

本文を開くだけでは既読になりません。「既読にする」で変更します。外部画像や埋め込みは表示しません。取得は標準 HTTP(S) ポート限定、最大 5 MiB、一度に最大 2,000 記事です。HTTP 応答には非圧縮の identity を要求します。手動更新は同期処理なので、通常は worker を使ってください。DNS 解決の所要時間は OS のリゾルバー設定に依存します。

native の既定は認証なしの localhost UI です。API は常に Bearer キーを要求します。外部公開では Cloudflare Access mode を使用し、公開後の受入確認を行ってください。

## データとバックアップ

既定は `instance/feeds.sqlite3`、秘密鍵は `instance/secret.key`。Git に含めません。`FEEDASTROLABE_DATA_DIR` に絶対パスを指定すると保存先を変更できます。Web と worker には同じ値を設定します。

バックアップは `maintenance backup-bundle` で DB と根拠ファイルの一貫した bundle を作成します。停止して `instance/` 全体をコピーする方法も利用できます。稼働中に DB ファイルだけをコピーすると WAL の内容が漏れる場合があります。復元時も Web/worker/observer を停止してから置き換えます。

## OpenSpec / SDD

変更 `openspec/changes/phase-one-rss-reader/` と `openspec/changes/phase-two-deployment-api-settings/` に proposal、design、受入仕様、tasks があります。実装前に仕様を作成して厳格検証し、仕様に対応するテストで実装を検証します。初期化済みの Codex スキルは `.codex/skills/` にあります。

```sh
openspec validate --all --strict --no-interactive
.venv/bin/python -m pytest
```

実装確認後に仕様を同期・アーカイブします。新しい段階は別の change として作成してください。OpenSpec CLI は [公式手順](https://github.com/Fission-AI/OpenSpec) で導入できます（この環境は 1.3.1）。

## API・設定とコンテナ

`/settings` で全体/フィード別のポーリング間隔、pause、表示件数、初期ビュー、APIレート上限を変更できます。APIキーは読み取り/書き込み権限と1〜365日の期限を指定して発行・失効します。OPMLのインポート/エクスポートも利用できます。

- [第二段階の検証記録](docs/verification-phase-two.md)：実施した検証と外部接続の未完了項目。
- [API の利用方法](docs/api.md)：フィード・記事取得、cursor、購読追加、既読/スター更新。
- [コンテナ・Cloudflare・復旧手順](docs/deployment.md)：localhost:5010でのCompose、Access検証、外部接続設定、backup/restore。

通常のnative起動はlocalhost専用です。コンテナの外部公開はCloudflare用ComposeとAccess認証を組み合わせます。

## SNS 連携

設定画面で X アカウント／リストと Mastodon の公開アカウントを登録できます。RSS と共通の画面・記事 API で読み、既読・スター・検索を使えます。X の認証は Git 管理外のファイルから読み込みます。[SNS 設定と取得仕様](docs/social.md) と [第三段階の検証記録](docs/verification-phase-three.md) を参照してください。Cloudflare の実接続は後段へ延期しています。

公開先は [GitHub](https://github.com/negitanu/FeedAstrolabe)。push 前に `python3 scripts/check_secrets.py --staged --history` を実行してください。[秘密情報の管理](docs/security.md) に検査範囲と限界を記載しています。

## 次の段階

[ROADMAP.md](ROADMAP.md) に指定された四段階の順序、受入条件と必要な設定を記録しています。

## 固定ページの観測

設定画面の「ページ観測」で公開 URL と CSS セレクターを登録します。初回は基準を保存し、その後のテキスト変化を差分記事として表示します。JavaScript 描画に対応し、未読・スター・検索・記事 API を共通で利用できます。

```sh
docker compose -f compose.yaml -f compose.local.yaml -f compose.observer.yaml up --build -d --wait
```

描画コンテナはネットワークと DB を持たず、専用 observer が検証した同一 origin のリソースだけを仲介します。[観測の設定・制限](docs/observation.md) と [第四段階の検証記録](docs/verification-phase-four.md) を参照してください。ログインや画像比較は対象外です。

## 購読管理

設定画面で RSS/ページ観測の取得 URL を修正できます。既存記事・既読・スターを保持し、次回収集で取得情報や観測基準を取り直します。API は `PATCH /api/v1/feeds/{id}`、`DELETE /api/v1/feeds/{id}`、`POST /api/v1/feeds/{id}/refresh` に対応します。すべて書き込みキーが必要です。[API 手順](docs/api.md) と [第五段階の検証記録](docs/verification-phase-five.md) を参照してください。

## 調査ワークスペースへの拡張計画

セキュリティ・OSINT・ネットワーク・生成AIを扱う [第六〜第十四段階の実装計画](docs/research-workspace-plan.md) をOpenSpecで定義しました。調査案件・根拠保存・ウォッチリストを最初のMVPとします。第六段階の調査案件・版付きメモ・共有タグは実装済みです。第七〜第十三段階は実装済み、第十四段階は後続計画です。


`/workspaces` から調査案件を作成し、既存フィード・記事を複数の案件へ関連付けられます。Markdown メモは事実／情報源の主張／仮説と版履歴を持ち、同時編集は409で保護します。共有タグ、案件／記事タグによる検索、アーカイブ／再開、公開区分を UI・API から利用できます。[操作と制限](docs/research.md)、[第六段階の検証](docs/verification-phase-six.md) を参照してください。

第七段階以降、根拠を含むライブラリは DB／blob の一貫した `backup-bundle`／`restore-bundle` を使用します。旧 DB 単体の手順は根拠を持たない snapshot に限ります。現在の復元先は v7 になります。[根拠・添付・復旧の手順](docs/evidence.md)を参照してください。

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
