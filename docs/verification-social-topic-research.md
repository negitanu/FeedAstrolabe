# Mastodon／Bluesky SNS調査の検証

2026-10-21。変更 `social-topic-research`、schema v15。

## 公式APIの実接続

運用DBに触れず、一時ディレクトリのDBでアプリの実際のHTTPS通信・収集・ランキング・根拠保存を実行した。

- Mastodon `https://mastodon.social/api/v1/timelines/tag/AI`：成功、24時間以内40投稿、上位40件。
- Bluesky `https://api.bsky.app/xrpc/app.bsky.feed.searchPosts`：日本語検索・期間指定を確認。分野 `AI lang:ja` の上位／新着各100件から重複排除後200投稿、上位40件。
- 成功2件／失敗0件、根拠240件、foreign_key_check違反0件。実投稿本文・利用者情報を検証ログへ出力していない。一時DBは削除済み。
- `public.api.bsky.app` の検索は403、`api.bsky.app` は200だったため、検索の固定取得先を後者にした。大文字小文字を変える回避やスクレイピングは行わない。提供元の将来の制限変更は別途影響する。

## 自動テスト

`tests/test_social_research.py` で次を確認する。

- 登録時の通信なし、CSRF・API scope、入力／数値型／公開origin／タグ個数制限、編集の原子性。
- 上位／新着の固定エンドポイント、最大件数、投稿ID／作者ID／反応数検証、期間外・未来・非公開・ブーストの除外。
- 投稿重複排除、関連タグの投稿単位集計、反応数の版保存、既読・スター・根拠保持。
- 途中失敗時の部分保存なし、前回成功結果の保持、15分下限、全体停止、Bluesky共有／Mastodonサーバー別の429待機。
- 成功履歴30回の保持、購読削除時のcascade、bundle復元と再起動後の重複なし。
- 別の調査の記事を参照するランキングや不正なタグ集計を含むbundleの拒否。
- v14からの移行でX購読を停止、記事と既読・スターを保持、手動収集・再有効化・新規登録を拒否。
- Mastodonアカウントのページ途中失敗から再起動して続行し、全ページ完了までsince_idを進めない。

実Chromiumで1440×900／390×844の登録→収集→順位表示→設定変更→フォルダー内の記事一覧という流れを確認する。スクリプト文字列を含む投稿が実行されず、モバイルで横スクロールが発生しないことも検査する。スクリーンショットでテーマ・余白・文字の折り返しを確認した。

## コンテナ・復元

`scripts/verify_container.py --project feedastrolabe-social-final-verify` を実行した。運用 `.env` やTunnelを使わない分離プロジェクトで、最新版をビルドして以下を確認した。

- UID10001・read-only root・capabilities除外を維持。
- 実HTTPのscoped APIで記事とSNS調査結果を取得し、失効したキーを拒否。
- テスト投稿のスコア10、サンプル1件がbundleバックアップ／復元で保持され、foreign_key_check違反0件。
- Web／workerの強制再作成後もschema v15、調査ランキング、記事の既読・スター、案件・メモ版を保持。
- 正常終了後に検証用コンテナとネットワークを削除。検証用volumeは既存スクリプトの方針どおり残した。本番サービス・Hermesには操作していない。

## 完了チェック

全回帰テストは実Chromiumを含め **442 passed（69.85秒、skipなし）**。strict OpenSpecは全30項目成功。`git diff --check` は問題なし。追跡対象275候補と新規ファイルの秘密情報検査で検出なし。
