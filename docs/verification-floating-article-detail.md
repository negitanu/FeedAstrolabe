# フロート記事詳細の検証（2026-10-24）

OpenSpec change: `floating-article-detail`。

## 実装

一覧を縮めず右側に固定パネルを重ねる。通常選択・明示既読・開いたら既読の設定を維持する。中クリックは元記事を別タブに開き、既読を変更しない。詳細タイトルを元記事リンクにし、別の元記事ボタンと上側の前後・件数表示を除去。末尾ナビは維持。元URLなしでは別タブを開かない。

## 検証結果

- 既存の reader/navigation/platform/presentation の関連85テスト成功。フロート表示で隠れる一覧の操作は詳細を閉じてから行うようテストを更新。
- 新規 `tests/test_floating_detail.py`: 6 passed（最終実行、7.22秒）。PC 1280px・モバイル390px、light/dark、開いたら既読の両設定、追加読み込み記事の中クリック、元URLなし、タイトル別タブ、一覧幅・位置保持を実Chromiumで確認。
- 初回はブラウザー未導入、テスト設定の参照先誤り、テスト内window.open監視の自己呼び出しを検出。Chromiumを導入しテストを修正。最終結果は上記の通り。
- `openspec validate --all --strict`: 44 passed。
- `.venv/bin/python -m pip check`: No broken requirements found。
- `git diff --check`: 成功。
- PCのline/tilesとモバイルの既存スクリーンショット生成テスト成功。PCフロート表示の画像を目視確認。
- `docker compose up -d --build --wait web worker observer`: 成功。依存rendererも再構築されhealthy。
- 稼働webコンテナ内の実HTTPで `/healthz` と `/` が200、新しいフロートCSS配信を確認。

DB移行・依存パッケージ変更なし。外部Cloudflare認証と有料AI呼び出しは今回の変更対象外で未検証。
