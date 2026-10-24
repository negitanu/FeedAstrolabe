## Context
一覧は通常リンクまたは開いたら既読にするPOSTで詳細を開く。現在は2列gridと上下の移動ナビを使用する。
## Goals / Non-Goals
Goals: 一覧幅・スクロール保持、中クリックで元記事、詳細タイトルへのリンク集約。
Non-Goals: DB変更、既読設定変更、本文末尾ナビの削除。
## Decisions
詳細はviewport右側にfixed配置し、モバイルでは画面幅以内に収める。詳細へのfocusはpreventScrollを使い一覧をスクロールしない。各カードに元記事URLを保持し委譲auxclickで処理するため、追加読み込みと開いたら既読の両方に対応する。元URLがない場合は別タブを開かない。詳細タイトルはnative anchorとnoopener noreferrerを使用する。上側sequence_linksのみ除去する。
## Risks / Trade-offs
右側の一覧はパネルに隠れる → 閉じる操作を常時アクセス可能にし、独立スクロールとテーマ色を維持する。
## Migration Plan
DB移行不要。アプリイメージ再構築で反映、旧イメージでロールバック可能。
