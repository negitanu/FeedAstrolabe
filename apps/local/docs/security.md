# 保存と安全性

## 信頼境界

Electron main は Go バイナリを子プロセスとして起動し、標準出力の起動応答から動的 localhost ポートと、起動ごとにランダム生成した256-bitトークンを取得します。画面へトークンを渡しません。

Go は `127.0.0.1` の動的ポートだけに bind します。RPCは POST / JSON / bearer を必須とし、Originヘッダー付き要求を拒否します。公開配備・認証ユーザー・複数ユーザーの分離を提供するAPIではありません。

Electron は sandbox / contextIsolation / webSecurity を有効化し、Node integration を無効化します。contextBridge の IPC はmain frame・webContents・ローカル画面URLを照合します。同一画面内の履歴フラグメントだけを許可し、操作名を許可リストで制限します。任意SQL・任意ファイル読取り・任意fetch・shell実行をrendererへ公開しません。

画面は file:// の同梱リソースだけを読み込みます。CSPでネットワーク接続・iframe・objectを拒否し、権限要求・新規ウィンドウ・画面遷移も拒否します。外部記事はユーザー操作でHTTP(S) URLだけを既定ブラウザーへ開きます。取得記事はGoで許可タグへサニタイズし、画面でも許可DOMだけを再構築します。script・外部画像・イベント属性・任意schemeを実行しません。

## 取得制限

標準 HTTP / HTTPS ポート、公開IPのみ、DNS解決後のIP固定、すべてのredirectの再検証、最大5redirect、応答最大5MiB、1リクエスト20秒、1フィード2000記事を上限とします。圧縮応答・DTD・実体宣言を拒否します。プロキシ環境変数はコレクターで使いません。安全性のため、社内・localhost・VPN内フィードは取得できません。

`FEEDASTROLABE_LOCAL_TLS12=1` またはGo起動引数 `--tls12` を明示した場合のみ、最大TLSバージョンを1.2に制限できます。証明書検証とネットワーク制限は維持し、自動フォールバックは行いません。

HTML alternate の探索は最大8候補、プレビューは各最大5件です。OPMLは5MiB / 500購読 / 32階層まで。バックアップ復元は64MiB / 20万行までで、不正入力はトランザクション全体を戻します。

## データ・終了

DBとバックアップは0600、新規データディレクトリは0700を指定します。SQLite WALにも同じDBのアクセス権が適用されます。バックアップを保存済みファイルへ上書きすると、そのファイルの権限も0600にします。ディスク暗号化はOS側の機能を利用してください。

Electron終了時はGoのstdinを閉じてHTTPと収集を停止し、6秒以内に終了しない子は強制終了します。Electronの異常終了でもstdinのEOFを受けて停止します。Go異常終了時はエラーを表示してアプリを終了します。

リポジトリは依存・bin・dist・DB・バックアップ等を除外します。利用者が選んだ任意名のバックアップファイルをリポジトリ内へ保存する場合はGit対象になり得るため、保存先をリポジトリ外にしてください。

## SNS・AI の境界（0.2.0）

SNSの取得は公開HTTPS・DNS/IP固定・redirect拒否・identity・5MiBで、投稿・反応数・ID・タグの型を検証します。失敗した複数ページの途中結果をcommitしません。BlueskyとMastodonサーバー単位の429待機をDBへ保存し、手動更新でも迂回しません。

AIは資格情報をGoの環境変数または所有者専用token fileから読み、rendererへ返しません。固定のprovider endpointだけにPOSTし、redirect・圧縮・1MiB超・重複JSONキー・ツール呼出し・不正引用・未知usageを拒否します。生成POSTは再送しません。OrcaRouterの費用が不明なら最大2回の読取り専用照会だけを許可し、なお不明なら予約額を維持します。

ローカルOllamaへの `127.0.0.1:11434/api/{status,tags,version,chat}` は明示した接続だけの例外です。他のlocalhost URLをフィードや外部APIへ許可するものではありません。cloud-disabled、model digest、remote modelなしを検証してから選択本文を送信します。モデルのインストールやpullは行いません。

クラウドはpublic案件と、それ以外の非公開案件へ関連しない資料だけに限定します。送信直前の再検証とネットワーク処理中はSQLite書込みを排他します。分類は単一利用者の送信ポリシーであり、利用者別のアクセス分離ではありません。認証値パターン検査は補助で、秘密の完全検出を保証しません。

schema1の事前JSON保存に失敗すれば移行せず、復元はAIを無効・未完了jobをfailedにします。入力hashと根拠hashを確認し、旧プレビューは設定版更新により再承認できなくします。ジョブ履歴は元の入力・設定・結果を保持しますが、キーは含みません。

## 同期の境界

同期通信とAccess cookieはElectron mainの専用セッションで管理します。rendererからのsync.prepare/accept/error直接呼出しは拒否し、設定保存・状態表示・固定originへの同期開始だけを許可します。ログイン画面はpreloadなし・sandbox/contextIsolation有効で起動し、アプリ画面のIPCを持ちません。認証redirectに記事を転送せず、変更履歴を保留します。詳細と未検証の外部受入は [同期文書](library-sync.md) を参照してください。
