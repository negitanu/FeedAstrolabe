# OpenRouter重要トピック抽出の検証

2026-10-21。変更 `openrouter-topic-extraction`、schema v16。

## 実装範囲と検証方法

既存SNS収集回の公開記事から、最大20抜粋／32KiBを固定OpenRouter endpointへ送信する解析を追加した。モデルと予算は明示的に設定する。手動・分野別自動実行、重要度・要約・理由・未確認点・出典リンク、正確な送信内容の確認に対応する。

OpenRouterの構造化出力、プロバイダーのデータポリシー・単価上限、usage.costの仕様を公式資料で確認した。実際のAPIキー・有料生成は使用せず、通信と生成は合成応答で検証した。実モデルの日本語品質、選択モデルとアカウントの利用可否、請求額は未確認である。キーを設定して有効化する前に運用者がモデルと予算を選ぶ。

## 機能・境界テスト

`tests/test_social_ai.py` は以下を検証する。

- 初期無効、未設定キーでの拒否、設定版の競合、入力型・単価・日次・1回上限、モデルIDと危険なvariantの拒否。
- 正確なwire/hash、最大20資料と本文400文字、サイズ上限、固定promptと構造化出力、出典ID・重要度・本文型の検証。
- 同じ収集回・設定版の二重予約・二重送信なし、GETの副作用なし、既存記事を変更しないこと。
- private案件のfeed・article・evidence・quotation・noteとの関連を除外し、enqueue後に分類が変わった場合も送信しないこと。
- 認証値らしい資料の除外、資料不足時の送信なし、不正なhashを送信前・bundle検証時に拒否。
- 自動解析と全体／分野の停止、日次回数・費用予約、API申告費用の超過を予算へ反映、429共有待機。
- 途中切れ、tool call、無効JSON、重複キー、NaN、圧縮・サイズ超過、認証・課金エラーなどを安全に拒否し、本文・キーを例外に含めないこと。
- 通信層から構造化結果・利用量・費用記録までの統合フロー。
- running中断は再送しないこと、失敗時に前回成功結果とその表示を保持すること。
- v15 fixtureからの移行と、bundle復元で成功履歴を保持しながらAI設定／自動解析を無効化し、未完了予約を再送しないこと。
- read/write scope・CSRF、入力・履歴・キー有無のAPI、キー値の非表示。

実Chromiumの1440×900と390×844で、手動解析予約→worker処理→結果表示→評価観点と自動化の設定→OpenRouter設定への移動を確認する。横スクロールがなく、APIキーがDOMへ出ないことを検査する。生成文のscript文字列をHTMLとして挿入しないことはテストクライアントでも確認した。スクリーンショットで表示を確認した。

## コンテナ・復元

`scripts/verify_container.py --project feedastrolabe-openrouter-verify` を実行し、最新コードで再実行も行った。実運用 `.env` とキーを使わず、分離したイメージ・volume・networkで検証した。

- Web／workerが正常起動し、UID10001・read-only root・capabilities除外を維持。
- fixture予約の競合を避けるため、health確認後に検証用workerを一時停止して模擬生成を行い、再作成時にworkerの正常起動も再確認。
- OpenRouterの合成応答から重要度90のトピックを保存し、実HTTPのscoped APIから結果を取得。
- 根拠bundleのバックアップ／復元で解析結果・記事・メモを保持し、復元したOpenRouter設定は無効であることを確認。
- Web／workerの強制再作成後も重要トピックとsource参照、schema v16を保持。
- 旧prompt・schemaの送信履歴も入力hashで検証でき、再ビルド後のバックアップが成功。
- 正常終了後に検証用コンテナ・networkを削除。volumeは既存検証方針どおり残した。本番とHermesへの操作はない。

## 完了結果

実Chromiumを含む最終の全回帰は **489 passed（74.81秒、skipなし）**。strict OpenSpecは全31項目成功。`git diff --check` と追跡対象275候補・新規ファイルの秘密情報検査で問題を検出しなかった。
