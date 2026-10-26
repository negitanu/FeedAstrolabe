## Purpose

Maintain and distribute the desktop application in the project repository.

## Requirements

### Requirement: ローカルアプリの統合
The repository SHALL include independently buildable desktop source, specifications, and tests under apps/local.

#### Scenario: 開発者がアプリをビルドする
- **WHEN** 開発者が apps/local の手順に従う
- **THEN** Web の実データや秘密情報を使わずアプリをビルドできる

### Requirement: タグからの配布
CI SHALL attach tested macOS, Windows, and Linux artifacts to the GitHub Release for the v0.1.0 tag.

#### Scenario: リリースタグを push する
- **WHEN** v0.1.0 タグが GitHub に push され、全ビルドが成功する
- **THEN** 対応する配布物を v0.1.0 Release から取得できる
