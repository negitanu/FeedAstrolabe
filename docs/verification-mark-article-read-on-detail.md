# 記事詳細表示時の自動既読 検証記録

2026-10-25（JST）。この変更時点の検証記録。過去の sequential-article-reading、floating-article-detail、article-detail-content-order の記録は当時の動作を記載しており、現在の操作は README と navigation.md を参照。

## 変更

- 表示された本文の閲覧POSTで既読と閲覧履歴を同じトランザクションに保存。スターは保持。
- 一覧カード、既読操作、フォルダーを含むスコープ別件数を保存成功後に同期。
- 未読一覧でも本文と読み込み済み一覧を維持し、訪問済みの記事は履歴で再表示可能。他の検索条件は維持。
- 既読にして次へ／一覧へを削除。前後移動・閉じる・明示的に未読へ戻す操作は継続。
- 旧read-on-open設定に依存しない。中クリックとGET単独は既読にしない。JavaScript無効時は「既読・閲覧履歴に記録」で保存。

## 検証

- 最終の非ブラウザー全回帰: 589件成功、ブラウザー109件を除外（必要な31件は別途実行）。

- 実Chromium: 自動既読・中クリック・本文形状・画像・明示的な未読・履歴復帰・保存失敗16件成功。
- 履歴・検索・選択一括操作のブラウザー8件成功、プラットフォーム（連続読み込み・履歴・一括既読・キーボード・サイドバー）5件成功、モバイル前後移動のJavaScript有効／無効2件成功。合計31件。PCとモバイル、light/dark/systemを含む。
- OpenSpec `validate --all --strict`: 51件成功。
- Python 3.15.1、`pip check`: 不整合なし。依存追加・固定版変更なし。
- `git diff --check` 成功。追跡候補の秘密情報検査567件成功。
- `docker compose up -d --build --wait --wait-timeout 120 web worker observer` 成功（rendererも再構築）。web/rendererのhealthyとworker/observerの起動を確認。
- 稼働web内から実HTTP: `/healthz` 200、`/` 200、新しい自動既読スクリプトを確認。実行UIDは10001。
- DB移行なし。既存記事の検証目的の変更なし。未コミットのユーザー変更は維持し、コミットは実施しない。

## 未実施

有料AI API、外部配信、Cloudflare Accessの外部認証はこの変更では検証しない。稼働データの記事を選ぶ状態変更は避け、自動既読のDB検証は隔離テストDBで実施した。
