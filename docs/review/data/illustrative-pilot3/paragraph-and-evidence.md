In pilot position 98900407:124 (excluded from the confirmatory analysis), Great Tusk can discard the opponent’s last four cards after Explorer’s Guidance. Although our own deck is empty, the opponent must draw first. A policy-free check of all 16 sampled worlds ended immediately in our win, before any opposing decision. Land Collapse therefore illustrates decision-relevant certainty despite 12 cards remaining in hidden zones; passing instead lost under every tested continuation.

Evidence and scope:

- Original replay: `/private/tmp/kaggle_eps/55565424/replays/episode-98900407-replay.json`; own player index 1; own observation at step 124. Global turn 34 is own turn 17. Step 123 logs PLAY of card 1185 (Explorer’s Guidance), serial 95, on the same turn. Step 124 has `supporterPlayed=true`, Great Tusk (58) active with 140 HP, no Special Conditions, opponent deck count 4, own deck count 0, and legal action index 4 = Land Collapse (attack 62).
- Official native API `cg.api.all_attack()` describes Land Collapse as discarding one card, or four after an Ancient Supporter. The complete returned attack data are in `mechanical_trace.json`.
- Additional mechanical verification used no continuation agent: for each of the 16 existing pilot worlds, SearchBegin then SearchStep([4]) returned terminal result 1 on global turn 35. The logs show four opponent DECK→DISCARD movements, own TURN_END, then opponent TURN_START. There are no intervening opponent decisions or coin selections. No new matches or confirmatory outcomes were used.
- The ordinary draw-before-actions rule is documented in the [official Pokémon TCG rulebook](https://assets.pokemon.com/assets/cms2/pdf/trading-card-game/rulebook/pal_rulebook_en.pdf). The native engine trace verifies the relevant timing in this competition implementation.
- This specific publicly explainable immediate win is stronger evidence than the heatmap alone. The heatmap remains a finite 32-repeat, fixed-policy illustration selected from 5 low-H pilot positions, excluded from the confirmatory analysis. Its post-selection margin is descriptive, not a confidence bound or a claim about every possible hidden state or perfect play.

Files:

- `selected_cases.json`: exact selection rule, all selected metrics, root option semantics, assumptions and input hashes.
- `all_pilot_low_H_metrics.json`: all five eligible pilot cases, so the selection is auditable.
- `root_public_observation.json`: selected root's original own-perspective observation, excluding search input.
- `mechanical_trace.json`: original root and same-turn observations, official card/attack data, native library hash, and all 16 policy-free traces.
- `figures/common_best_example.png`, `.svg`, `.pdf`: full means and even/odd repeat-fold means, with tied common best actions marked.

Logical verification fixtures passed: reject all-win/all-loss matrices; preserve tied common best actions; reject pooled ties with disjoint repeat folds; identify world-sensitive best-set counterexamples.

準備行動の追加確認: 保存済み最初の1世界で a0（Neutralization Zone）と a1（Great Tusk）の次に固定続行方策が Land Collapse を選ぶことを確認した。a3（Crushing Hammer）も表・裏の両分岐で同じ攻撃へ進み、自分の勝利となった。選択列は `preparation_policy_traces.json` に保存。この追加確認は元の32反復×16世界の統計を置き換えず、図の行の意味を説明するもの。

短い日本語説明:

相手の非公開領域にはまだ12枚ありますが、この局面では残り山札4枚という公開情報が勝敗を決めます。同じターンに「探検家の先導」を使っているため、イダイナキバの「じばんほうかい」で4枚すべてを捨てさせると、相手は行動前のドローに失敗します。自分の山札も0枚ですが、相手の番が先なので勝利します。公式エンジンで16世界すべて、攻撃1回から相手の選択機会なしに勝利することを確認しました。準備行動の行も勝ちになるのは、続行方策がその後に同じ攻撃を選ぶためです。この例は本試験から除外した予備例です。
