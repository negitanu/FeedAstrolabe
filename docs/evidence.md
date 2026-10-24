# 根拠・出典・引用

`/evidence` で取得時点の本文と出典を確認し、案件・メモへ固定できます。RSS/SNS は加工済みテキスト、ページ観測は選択要素のテキストを保存します。元サイト全体やスクリーンショットの保存ではありません。変更時は別版になり、同じ本文・出典情報の再取得では増えません。

公開日時、観測日時、保存日時を分けて表示します。公開日時がない記事と移行済み旧記事は「不明」です。過去記事の「現在の本文を根拠として保存」は backfill-now と表示し、過去に保存した証拠として扱いません。購読／記事を削除しても、保存した本文・出典・引用は残ります。SHA-256 は保存内容の整合性を示し、真実性を保証しません。

引用は根拠 ID、固定テキストのハッシュ、0起点の Unicode 文字位置（終了は含まない）、完全一致する文字列で保存します。ブラウザー JavaScript の UTF-16 長とは異なります。案件・メモへの固定、または引用がある根拠は保存期間による削除対象から外れます。引用の編集・削除 API は提供していません。

## 添付と容量

案件詳細から UTF-8 text、Markdown、PDF を添付できます。1件10MiB、抽出テキスト10万文字、PDF200ページまで。暗号化・不正形式・MIME／拡張子不一致は拒否します。画像PDFのOCRはありません。表示はエスケープしたテキストだけです。元ファイルは添付扱いの application/octet-stream でダウンロードします。

添付解析には 標準 `compose.yml` の renderer が必要です。解析子プロセスはネットワーク・DB・秘密鍵にアクセスできず、CPU15秒、Linuxアドレス空間384MiB、全ジョブ45秒、コンテナ512MiBの制限を持ちます。macOS native の IPC 検証ではアドレス空間制限を設定しません。renderer 未接続時は保存せずエラーになります。Python pypdf 6.19.0 を固定し、PDF内のプログラムや添付を実行しません。

初期容量500MiB、設定範囲10MiB〜10GiB、固定していない根拠の保存期間は初期90日（1〜3650日）。容量判定は管理対象ファイルの実サイズを含み、同じ bytes は再利用します。通常の `/evidence` の使用量 API は DB に登録した bytes です。中断で残った孤立ファイルも容量判定に含まれます。上限超過でも通常の記事収集は継続し、根拠保存エラーを `/evidence` に表示します。上限を下げても既存の根拠は消しません。

削除は自動 worker に組み込まず、運用者が明示的に実行します。

```sh
.venv/bin/python -m flask --app feedastrolabe prune-evidence
```

## 一貫したバックアップ

v6 の根拠は DB と `evidence-blobs/` の両方が必要です。DB単体の backup／restore は根拠が含まれるライブラリでは拒否します。

```sh
.venv/bin/python -m feedastrolabe.maintenance backup-bundle backups/library-20261008
# web / worker / observer をすべて停止してから実行
.venv/bin/python -m feedastrolabe.maintenance restore-bundle backups/library-20261008
```

bundle は `feeds.sqlite3`、`manifest.json`、`evidence-blobs/` の3要素です。保存時は排他制御下でSQLite snapshotと全参照ファイルを検証し、完成後に公開します。復元は DB、全ファイルのハッシュ／サイズ、外部キー、引用位置を確認し、欠損・余計なファイル・symlink・不正な引用・稼働中のWALを拒否します。停止状態で行い、更新前の bundle も保持してください。通常例外時には旧データへ戻しますが、復元中のプロセス強制終了や電源断に備えた外部バックアップも必要です。

コンテナでは共通の Compose オプションを使います。

```sh
docker compose exec web python -m feedastrolabe.maintenance backup-bundle /data/library-20261008
mkdir -p backups
docker compose cp web:/data/library-20261008 backups/library-20261008
```

復元用 bundle は同じ volume にある状態で全 writer を停止し、`run --rm --no-deps -T web python -m feedastrolabe.maintenance restore-bundle /data/library-20261008` を実行してから再起動します。ホストの bundle を持ち込む場合は停止前に private な `/data/` へコピーし、UID10001で読める所有者・権限にしてください。秘密鍵 `secret.key` は bundle に含まず別途安全に保管します。DBにはキーのハッシュ・案件・メモが含まれるため、bundle を Git や公開ストレージに入れないでください。
