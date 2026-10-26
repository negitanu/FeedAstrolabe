## Why

デスクトップ版を同じプロジェクトで保守し、再現可能な配布物を提供する。

## What Changes

- 既存ローカルアプリのソース、仕様、文書、テストを apps/local に統合する。
- v0.1.0 タグから GitHub Actions で各 OS の配布物を生成する。
- Web 版の既存データと未コミット変更を保持する。

## Capabilities

### New Capabilities
- `desktop-distribution`: デスクトップアプリの統合とリリース。

### Modified Capabilities

## Impact

Go、Node、Electron の独立した依存関係と GitHub Actions を追加する。Web 版のバージョンや DB は変更しない。
