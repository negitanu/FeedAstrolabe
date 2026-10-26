## Context

未コミットの独立 Go/Electron アプリを Web 版リポジトリへ統合する。両者の実データは移動しない。

## Goals / Non-Goals

**Goals:** ソースと既存仕様を保持し、タグから OS ごとの成果物をビルドする。

**Non-Goals:** Web の DB 移行、未実装機能の移植、署名証明書の新規取得。

## Decisions

独立した依存関係を apps/local に残す。各 OS のネイティブ runner で Go と Electron をビルドし、テスト通過後に成果物をリリースへ追加する。署名設定がない場合は未署名として配布する。

## Risks / Trade-offs

未署名成果物は OS の警告が出る → 文書に記載する。CI 認証や外部依存の可用性は実行結果で確認する。
