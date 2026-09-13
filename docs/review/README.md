# Kaggle Strategy: 検証結果と提出用原稿

「不完全情報ゲームの完全情報ゲーム化」というテーマを維持した、提出前の確認用一式です。900局面の計算は2026年9月14日6:08（日本時間）に完了しました。Kaggle上の原稿の変更・公開・正式提出は行っていません。提出期限は同日8:59です。

最初に `results-review-ja.md` を読み、`writeup-en.md` の英語本文を確認してください。本文の新規データへのリンクは、審査員が閲覧できる公開設定にしてから提出する必要があります。

| ファイル・フォルダ | 内容 |
|---|---|
| `writeup-en.md` | 2,000語以内の英語本文です。 |
| `results-review-ja.md` | 主要結果・限界・改善点の日本語説明です。 |
| `editorial-corrections-ja.md` | 元原稿・旧図と実装が食い違っていた点の修正一覧です。 |
| `media-gallery-captions-en.md` | 図の順序と英語キャプションです。 |
| `figures/` | 5図をPNG・SVG・PDFで保存しています。 |
| `data/confirm-1/` | 900局面の最終集計・全件照合です。 |
| `data/confirmatory-raw-and-analysis.tar.gz` | 全900局面の生データと実験時の分析出力です。解凍後は約1GB以上になります。 |
| `data/cohort_audit_v1/` | 2,000対戦の一覧と1,999リプレイの実戦到達集計です。 |
| `data/exploratory-confirm-low/` | 事後に選んだルールの具体例と、主検証300局面を探索した記録です。 |
| `data/illustrative-pilot3/` | 主検証から除外した予備実験の直接勝利例です。 |
| `reproducibility-notes.md` | 仮定、未解決結果の扱い、再集計手順、限界を説明しています。 |
| `reproduction/confirm-runtime-1/` | 事前に固定した解析・実行コードと対象900局面です。 |
| `reproduction/selection-provenance/` | 元1,241局面から適格1,029局面を経て900局面を選んだ来歴です。 |

主検証は300対戦です。各対戦の多数の計算を独立した対戦数として数えていません。結果は、固定した継続方策の下での有限な情報比較であり、真の完全情報最適解と同等であるという証明ではありません。

`reproduction/agent-runtime-source.tar.gz` と `reproduction/frozen-input-replays-498.tar.gz` は実行環境と選択済み入力の保管用です。公開用の再集計資料には、第三者の対戦エンジンと代理方策そのものを含めていません。再集計資料だけで保存済み結果から数値を再計算できます。新しく対戦を計算する場合の依存物と制限は再現手順に記載しています。
