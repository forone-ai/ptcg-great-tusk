# Media Gallery captions

Upload the figures below in this order. Figures 1–3 support the main narrative; Figures 4–5 supply comparison quality and a separate mechanical illustration. Keep the correct official decklist image alongside these figures. The text below belongs in the Media Gallery, not in the 2,000-word body.

## 1. The rule preserves the Prize route

File: `figures/01-rule-and-prize-route.png`

Exploratory illustration selected after analysis of all 300 low-H primary positions; the primary sample and estimates remain unchanged. At own turn 18 (global turn 35) in position 103027623:259, H=12, our deck contains seven cards and the opposing deck five. The heatmap shows three of 12 evaluated root actions. Playing Dwebble and using Superb Scissors each have score 1 in every one of 16 worlds × 32 repetitions; Explorer’s Guidance has score 0 in every cell, with the same separation in even/odd repeat folds. The original rule chooses Dwebble first, prepares, then uses Superb Scissors in the representative trace; attacking immediately is a separately evaluated root intervention. The lower table follows one sampled world under the fixed continuation policies. Each of the three traced lines gives the opponent six decisions, including attack-target and Prize/promotion choices, not six full turns. Preparing Dwebble or attacking immediately preserves enough future draws to take the remaining four Prizes by own turn 20. Explorer’s Guidance first moves six cards out of the deck, leaving one; after the next mandatory draw, the following draw fails before the third attack. Crustle’s ability prevents attack damage from Pokémon ex, including the active Marnie’s Grimmsnarl ex; this does not prevent the benched Munkidori’s damage-counter ability. Prize identities remain masked in continuation observations. This is a post-hoc illustration and one representative trajectory, not a confidence bound, a full-history proof, or a guarantee against optimal opposition.

## 2. Formation in actual games

File: `figures/02-actual-game-formation.png`

Available: 776/1,999 (38.82%) reached H < 15: 602 eventual wins and 174 losses.
Checkpoints: first nonterminal own MAIN; single-option states are included.
All 2,000 listed games are retained; ended games keep their outcomes, not H = 0.
One missing draw remains unresolved. Descriptive counts do not establish causality.

## 3. Primary information comparison

File: `figures/03-primary-information-result.png`

Predeclared low-H comparison: 300 complete positions from 300 distinct games. The mean finite revealed-reference advantage was 0.8005 percentage points (two-sided game-bootstrap 95% interval 0.4254 to 1.2227; one-sided upper 1.1592), below the predeclared five-point margin. Intervals use 4,000 resamples of games, not individual continuations. The positive residual benefit is not zero. All-win/all-loss categories refer to every tested root action and continuation at a position, not proved forced outcomes. High tie-aware agreement is not a guarantee of an optimal reference; broad training ties were common. The comparison uses correct full decklists, sampled configurations and fixed observation-limited continuations.

## 4. Secondary comparisons and reference quality

File: `figures/04-secondary-comparisons.png`

Descriptive comparison across 300 independently sampled games per hidden-card-count band (900 positions in total; games can overlap across bands). H is the opponent’s deck count plus hand count plus remaining Prize count; it is not entropy. Panel A uses the finite root-action reference followed by fixed continuation policies receiving ordinary observations. Short thick marks show the worst-case lower and upper means when unresolved continuation outcomes vary over [0,1]; coincident or very narrow marks can appear as a single tick. Thin whiskers use the lower endpoint of the two-sided 95% game-cluster bootstrap interval for the lower mean bound and the upper endpoint for the upper mean bound (4,000 bootstrap replicates). They are outer bootstrap limits incorporating unresolved-case bounds, not confidence intervals for true optimal perfect-information value. The displayed mean bounds and their outer intervals are, in percentage points:

H < 15: mean bounds [0.800456, 0.800456]; outer 95% bootstrap limits [0.425448, 1.222689]; reference stability 98.34375%; n=300 games.

H = 15–34: mean bounds [2.166341, 2.167643]; outer 95% bootstrap limits [1.681616, 2.681982]; reference stability 84.37500%; n=300 games.

H ≥ 35: mean bounds [1.127604, 1.145182]; outer 95% bootstrap limits [0.768555, 1.501953]; reference stability 60.21875%; n=300 games.

Reference stability is game-weighted split-half selected-action membership in the other half’s tied-best set, averaged over both directions. The predeclared diagnostic screen is 80%. Low and middle bands pass; the high band fails. A passing screen is not a calibrated oracle-quality guarantee, and broad ties can inflate agreement. Thus the high-band gap must not be interpreted as showing that hidden information matters little. The low/middle/high pattern is nonmonotonic and descriptive; game composition differs across bands and no causal effect of H is established.

Panel B reuses the existing disjoint saturation categories. A position with any unresolved continuation enters only the unresolved category. Counts (all win, all loss, all draw, varied, unresolved, incomplete) are: low: [183, 22, 0, 95, 0, 0]; mid: [65, 14, 0, 220, 1, 0]; high: [2, 0, 0, 297, 1, 0].

All 900 selected positions completed. Of 2,845,184 continuation cells, 2,844,999 have terminal results and 185 remain unresolved (one middle-band position and one high-band position). No unresolved result is assigned a loss. Each evaluated root action uses 16 worlds and 32 repetitions.

Source: /Users/gonuts/agent-workspace/kaggle-information-experiment-20260914/confirm-1/final-summary.json; completed_at_utc=2026-09-13T21:09:11.716707+00:00; SHA256=38463917412631ad761d604eb76059bf0b3d30f05d35a5aa0a296049ada8b30f.

## 5. A direct win in an excluded pilot

File: `figures/05-pilot-mechanism.png`

Illustrative pilot position 98900407:124 (H=12), excluded from the confirmatory analysis. The public state shows Great Tusk active, Explorer’s Guidance played this turn, and four cards left in the opponent’s deck. Land Collapse discards all four; the opponent reaches their mandatory draw before our next turn, so our empty deck does not prevent this immediate win. A policy-free official-engine check returned our win after one SearchStep in each of 16 sampled worlds, before any opponent decision. The heatmap uses 32 fixed-policy continuations per action and world; even/odd folds of 16 repeats have identical tied-best sets. Actions a0, a1 and a3 are preparatory moves whose continuation policy subsequently selects Land Collapse. Switch and End turn lose under the tested continuation policy; this does not claim that every possible Switch continuation loses. The example was selected by the published worst-world margin rule from the pilot and is not evidence of prevalence or optimal play.
