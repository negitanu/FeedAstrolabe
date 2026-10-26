# SNS・AI 移植の検証（0.2.0）

検証日: 2026-10-26（JST）。OpenSpec変更 `add-social-ai`。最終目的は元版のフル機能移植だが、この記録はSNS・AIの追加と既存機能の回帰に限る。

## 仕様と移行

元版のsocial.md / openrouter-topics.md / grounded-assistant.md、selectable-ai-providers / grounded-assistantの本仕様と実装を確認した。実装前にproposal / design / specs / tasksを作成し、strict検証を成功させた。後から追加した定期収集の全体停止も、要件・受入条件を更新して検証した。

schema2はschema1の整合JSONをmigration-backupsへ保存してから更新する。テストで記事・状態の維持と事前コピーを確認。backup1の復元、backup2のSNS・AI履歴、設定JSON2の秘密情報・本文除外、予算履歴の維持、復元後のAI無効化・未完了job失敗化を確認した。ジョブ取得と送信の間に復元が割り込んでも、状態/hash/configの照合によって復元済みjobを再起動・上書きしないことも検証した。

## 自動テスト

Goの通常テストは31個のトップレベルテストに加え、Orca費用照会・Ollamaモード・不正応答のsubtestを含む。`go test -race -count=1 ./...`、`go vet ./...`、`go mod verify`は成功した。公開SNSを呼ぶTestLiveSocialは通常skipし、下記の任意スモークとして別実行した。

- SNS: タグ・アカウント・Bluesky、重複排除、順位/タグ、30回保持、既読保持、複数ページの途中失敗で原子的に破棄、サービス単位の429待機、停止・手動・自動解析。
- AI: provider固有payload/資格情報、切替後のジョブ接続先固定、同一入力dedupe、UTC共有予算、失敗・429・費用不明での予約保持、再起動時running失敗化、生成POSTの再送なし、他providerの待機からの独立。
- 応答: finish/usage/cost、出典ID、構造と必須フィールド、重複JSONキー、ツール呼出し拒否。Orcaの即時費用なしを最大2回のGETで照会し、なお不明なら予約を維持。
- 調査補助: 根拠なし、正確なpreview/hash・承認、期限切れ、設定/分類変更、他の非公開案件の関連付けと根拠参照メモ、ローカルOllamaのクラウド無効化/digest/モデル一致、クラウドtokenの権限とsymlink拒否、引用と人のレビュー版。
- 競合: 送信中は分類の書込みが完了しないことを並行テストし、送信後に適用されることを確認。全体停止後の自動jobは送信せず失敗化し、明示的な手動操作とは区別。

Electronの既存9操作シナリオとSNS・AIの2シナリオは、実ウィンドウで全件成功した。SNS登録、接続設定の切替と保持、ローカルOllamaの正確なpreview、未承認では送信なし、承認後1回だけの生成、引用表示、レビュー、分類変更を確認。既存の読書・検索・選択・永続化・ネイティブ入出力・復元・Go子プロセス終了も再確認する。

テスト用Ollamaは11434番が空いている場合だけ起動し、status / tags / version / chatに合成応答を返す。利用者のランタイムがそのポートを使用している場合は該当シナリオをskipし、そこへリクエストしない。今回の検証では模擬ランタイムを起動でき、skipせず通過した。

画面はスクリーンショットでも確認し、Git除外のtest-resultsに保存した。プレビューや履歴の本文はtextContentで表示し、HTMLを実行しない。

## 実ネットワーク

Bluesky searchPostsとMastodon公開タグへの資格情報なしGETでHTTP 200とJSON形式を確認した。さらに次のコマンドでGoコレクターの取得・検証・保存を実行した。

```sh
FEEDASTROLABE_LIVE_SOCIAL=1 FEEDASTROLABE_LOCAL_TLS12=1 go test -run '^TestLiveSocial$' -v ./internal/app
```

Blueskyはgolang検索、Mastodonはmastodon.socialのgolangタグ。両方とも40投稿を検証し、上位40件を一時DBへ保存した。SNS投稿・ログイン・設定変更は行っていない。TLS互換モードは初版で確認したこの環境固有の接続制限に対応する明示指定であり、証明書・公開IP検証は維持した。

OpenRouter / OrcaRouterの有料生成、Ollamaの実モデル生成、実モデルの日本語品質・事実性は未検証。APIキー・残高・利用者資料を使用していない。SNS実接続の成功をAI実生成の成功と同一視しない。

## 配布・補助検査

Go同梱のmacOS arm64 `.app` を `npm run pack` で生成した。最終生成物自体にも同じElectron E2Eを実行し、バージョン0.2.0、リーダーとSNS・AIの11シナリオ（親テストを含めTAP13件）がすべて成功した。署名・公証・DMGインストール・Windows/Linux実機は今回も未実施。

OpenSpecは2変更+6本仕様のstrict検証に成功。NodeのIPC権限テスト、Prettierチェック、Goモジュール検証、npm監査（既知の脆弱性0）、資格情報パターン・Git候補の空白検査も成功。Goのgovulncheckは未実施。パターン検査は完全な秘密情報検出の保証ではない。

## 残差

Ollamaの複数名前付きprofile、元版の個別予算台帳と全保持細部、Windowsのクラウドtoken ACL、案件全対象の分類伝播などはdocs/parity.mdに残す。JSページ観測、添付・タグ・振り分け、対象グラフ、専門情報、通知、元版DB移行は後続OpenSpec変更で移植する。今回の成功をフル移植完了とはしない。
