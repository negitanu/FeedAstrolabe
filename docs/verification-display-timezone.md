# 表示タイムゾーンの検証（2026-10-08）

OpenSpec display-timezone。schema13→14、settings.display_timezone、UTC／Asia/Tokyo（JST）を追加。既存ライブラリはUTCを維持。共有ライブラリ全体の表示設定。

- 追加5テスト成功：設定保存と再読込、旧フォーム互換、UTC/JST切替、翌日への繰越、offset付き日時、欠損／不正値、全テンプレートのcompile、API scope／不正値の原子的拒否、APIと保存日時のUTC維持、genuine schema13 fixtureの移行／再実行／データ保持、schema14 bundleの復元と選択保持。
- 回帰250件成功、ブラウザー依存2件skip、ローカルUnixソケット制限のある既存renderer検証2件を除外。制限下での全体実行はその2件が失敗したため、成功として扱わない。
- OpenSpec全18項目の厳格検証とgit diff --check成功。
- 日時のフォーム入力、UTCの日次ダイジェスト条件、API timestamps、固定レポート／通知payloadはUTCを維持。UI表示だけ変換する。

## 反映

コンテナ運用の場合は既存手順に従いwriterを停止し、schema13 bundleを取得・検証してから全サービスを新しいimageへ更新する。新しいアプリ起動時にschema14へ移行する。戻す場合は旧imageと移行前bundleを使う。本変更の検証では稼働中ライブラリの移行やコンテナ更新は実施していない。
