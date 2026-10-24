# 出典付き調査補助（第十三段階）

調査補助画面でモデル設定を追加し、明示的に有効にします。初期状態は設定なし・生成停止。日本語summary／translation／compare／qaを提供します。資料・固定引用を選択し、正確な生成API body・実行先・入力hash・予約費用をプレビューしてから、承認チェックでジョブを予約します。プレビューだけでは生成や送信しません。引用／資料IDはこの案件のものだけ、8件まで・各1200文字以内。入力はUTF8 byte＋256の保守的token上限8192以内、出力初期512・最大2048token。プレビューは30分で失効し、再利用は同じjob IDになります。

[Ollama公式Chat](https://docs.ollama.com/api/chat)をnon-stream JSONで利用し、tools／search／shell／URL取得／設定変更はモデルに提供しません。資料中の命令はデータとして固定プロンプトへ入れます。生成したclaimは選択引用IDが必須。無効な引用や不正な応答は結果を採用せず、根拠がない質問は決定的にinsufficientと返してモデルを呼びません。引用位置・hashの検証は内容の真偽・意味の検証ではありません。矛盾、不確実性、提案は生成した未検証記述として表示。実モデルの品質・日本語の忠実度は現在未確認です。

ローカルは固定`127.0.0.1:11434`。運用者がOllamaを別途用意し、[クラウドを無効化](https://docs.ollama.com/faq)してください（OLLAMA_NO_CLOUD=1等）。`/api/status`のcloud.disabled=true、`/api/tags`の登録モデルSHA256とremote_host/modelなしを毎回照合してから生成。runtime版とdigestを系譜へ保存します。未対応statusやdigest不一致なら入力を送信しません。cloudを含むモデル名もローカル登録不可。アプリはモデルをインストール／pullしません。コンテナ内のloopbackはホストのOllamaではありません。運用者が自分の隔離したOllamaサービスを`ollama`というサービス名で用意した場合だけ、信頼するCompose設定でFEEDASTROLABE_OLLAMA_LOCAL_HOST=ollamaを指定できます。このphaseは実ランタイムの配置を行っていません。

クラウドは固定`https://ollama.com/api/chat`。匿名のローカルproxyをcloudと扱いません。[公式認証](https://docs.ollama.com/api/authentication)のBearerを、FEEDASTROLABE_OLLAMA_TOKEN_FILEで指定する所有者のみ読める非公開regularファイル（0600、symlink拒否、4096byte以下）から読みます。tokenはDB・Git・ブラウザ・入力系譜へ保存しません。Dockerは標準`compose.yml`で対応します。[任意の認証ファイルの配置手順](deployment.md#任意の連携設定)でprivate volumeの`/data/ollama-token`へアプリUID/GID10001・0600で保存し、`.env`に`FEEDASTROLABE_OLLAMA_TOKEN_FILE=/data/ollama-token`を設定して`docker compose up -d`で反映します。ホスト側`secrets/ollama-token`はGitとbuildから除外されます。未使用ならパスは空欄のままにし、ファイルも不要です。secretの作成・配置は利用者の運用設定です。

外部処理はpublic案件だけ。選択資料が別のinternal／restricted案件の固定・メモ・引用にも参照される場合は拒否。質問と選択範囲に対する認証値らしい文字列の検出も実施しますが、完全な検出を保証しません。必ず表示した入力を確認してください。承認hash、プロフィール版、分類、引用hashを生成直前に再照合。分類変更と送信が競合しないよう、最大90秒の生成中は既存evidence／SQLite書き込みlockを保持します。他の書き込みは待機／busyになる場合があります。ライブラリのreadキーも入力や結果を閲覧でき、分類は利用者別のアクセス分離ではありません。

[公式料金](https://ollama.com/pricing)はモデル・時刻で変わります。クラウド設定は確認日とinput_rate／output_rate（micro USD／百万token、cachedやoff-peak割引を使わない上限側の料金）が必須。未知の料金では登録しません。初期1回100000 micro USD（0.10 USD）、日1000000（1 USD）、日10回。保守的token上限×料金を予約し、日予算を超える承認を拒否します。料金は利用者設定に基づく概算で、実請求額の保証ではありません。応答usageが不明／上限超過なら結果拒否。クラウドmodelの重み版は不明で、応答modelとadapter版のみを系譜に残します。プロファイル名・モデル・種類・digestは固定で、変更時は別profile。日予算はUTC、翌日実行は実行日にも予約。

グローバルに1生成、90秒総期限・10秒socket待機・1MiB応答、POST自動retryなし。失敗／中断時に予約を返却しません。中断中のrunningジョブは再起動後failedとし、新しい入力プレビューと承認が必要です。既存workerが1件ずつ処理し、`flask --app feedastrolabe assistant-jobs`でも1件実行できます。原文・生成出力・入力系譜は不変、人のreviewed／rejected／draftは独立した版でexpected_revisionを照合。モデル設定20・preview履歴10000・未完了job20の上限があります。

schema11→12。bundle schema6〜12復元、入力hashと全選択引用位置を復元前に検証し固定根拠を保持。APIはread/write Bearer、`assistant-profiles` GET/POSTとPATCH、案件の`assistant-previews` POST、preview GETと`.../jobs` POST（approved=true＋input_hash）、案件の`assistant-jobs` GET、job GETと`.../reviews` GET/POST。OpenAPI0.13を参照。

検証は合成資料・模擬モデルで実HTTP／コンテナを確認。ローカル11434のprobeは未起動／未設定で、クラウドtokenも未設定のため実モデル生成は未確認です。モデル・アカウントの作成、課金、利用者資料の送信は行っていません。
