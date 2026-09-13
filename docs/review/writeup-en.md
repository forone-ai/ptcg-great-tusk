# Great Tusk: Making Imperfect Information Behave Like Perfect Information

## The strategic idea

Our theme is **「不完全情報ゲームの完全情報ゲーム化」: make imperfect information behave like perfect information where decisions matter.** Great Tusk removes the opponent's deck while Crustle and Neutralization Zone buy turns. Protection can also make some hidden opposing attacks irrelevant. The aim is to reach positions where knowing the remaining hidden configuration provides little additional help in choosing a move.

This is a local, operational claim. An emptying deck does not reveal its order, allocate cards between hand and Prizes, or eliminate future randomness. We therefore distinguish three questions: do small hidden zones occur in actual games; does extra hidden-state information change decision quality there; and does search improve the deployed agent's win rate?

The final submission scored **799.3, rank 1,150 of 6,807**. Its opponent registry was missing from the archive, so its search path was disabled. Its official results support an evaluation of the deck and rule policy. The additional information experiment below is post-deadline analysis and does not change that performance score.

## A deck built to change the decision problem

Great Tusk ×4 supplies the deck-out clock. Land Collapse discards one opposing deck card, or four after an Ancient Supporter. Explorer's Guidance ×4 therefore supports the win condition as well as drawing cards. Great Tusk is a Basic without a Rule Box, giving up one Prize when knocked out.

Dwebble ×4 and Crustle ×4 supply time. Ascension finds the evolution, while Bug Catching Set ×2 helps establish the board. Crustle blocks damage from Pokémon ex attacks and can attack through effects on the opposing Active. Against Grass-weak Grimmsnarl, its attack route offers a different way to win.

Neutralization Zone protects our non-Rule-Box attackers against ex/V damage. Rock Fighting Energy protects Fighting-type Great Tusk from attack effects; Mist Energy provides effect protection without that type restriction. Battle Cage protects Benched Pokémon from damage-counter placement effects; it does not prevent ordinary bench damage. These protections answer different threats. Crushing Hammer ×2, Xerosic's Machinations ×2, Budew ×1 and Jumbo Ice Cream ×2 slow opposing attacks or keep the wall in play. The submitted list contains two Hammers.

The default route builds a mill-ready Great Tusk and a Crustle wall. Visible opponent cards can instead trigger the attack route, particularly against Grimmsnarl or lists that recycle Energy into the deck. The route can change when the estimated race changes, with thresholds that discourage repeated switching. Against Alakazam, special Energy is attached cautiously because opposing lists can remove it.

The strategy has a concrete cost: time spent establishing the wall can lose the opening. A prized Neutralization Zone, an attack-effect answer arriving late, or disruption of the Energy sequence can prevent the intended endgame. We report early endings and losses alongside successful transitions.

## The implemented decision system

Actual action selection uses visible archetype evidence, route-specific board requirements, deck-budget gates and sequencing priorities. The route controller uses observed deck-depletion pace. Three additional heuristic clocks—opposing deck-out, our deck-out, and opposing Prize completion—are recorded as diagnostics, not used directly as the action selector.

Archetype recognition directs Energy toward Great Tusk for milling or the Crustle line for Prizes. In ordinary Prize-route resupply, once our deck reaches 20 cards, six-card digging requires the remainder to exceed half the opponent's deck, rounded up, plus six. Emergency recovery branches can override this gate. Healing prioritizes a damaged, energized Active; Energy removal targets Munkidori more strongly when damage-counter threats are visible.

At our eighteenth turn in episode 103027623:259, our deck had seven cards and the opponent's five. Reconstructing the observation history, the rule rejected routine Explorer's Guidance: after consuming six cards, one would remain, failing its budget requirement of more than nine. Guidance received −5,000; Dwebble received 40,000 and was played before attacking. These are ordering scores, not probabilities. In this example, selected after the primary test, both that preparation and immediate Superb Scissors won across all 16 configurations and 32 repeats; Guidance lost throughout. A representative continuation showed why: digging exhausted our deck before the remaining Prize route could finish.

In registry-enabled development builds, visible card fingerprints select a reproduced opponent deck and a policy for simulated continuation. Sampled hidden configurations feed the competition Search API and a tree search that trades estimated value against exploration. The endgame condition checks whether **either** deck is at most 14 cards; it does not require both decks to be small. A learned value function can also evaluate a truncated endgame rollout.

Rules still bypass search in some apparently decisive positions. Therefore, smaller hidden zones and larger search gains are separate hypotheses: information may cease to matter because a rule already finds a sufficient action. The final archive's disabled search makes this distinction essential.

Determinizing hidden states is established work. Long et al. studied conditions under which Perfect Information Monte Carlo performs well; Frank et al. describe the danger of combining future choices that require unavailable information. Our design principle is to steer play toward suitable decision problems, rather than claim determinization itself as new. In the experiment below, only root selection receives extra hidden information. Subsequent Search API observations are explicitly redacted to mask unknown Prizes; originally visible Prizes are tracked separately.

## Actual-game formation and robustness

The two final submissions have 2,000 recorded games and 1,999 available replays; one drawn game's replay is missing. The audit includes wins, losses and early endings. We define H as the opponent's deck count plus hand count plus remaining Prize count. H measures cards in hidden zones, not entropy or the number of identities the agent has forgotten.

The final submissions won 541/1,000 and 539/1,000 games. Among available replays, 776/1,999 (38.8%) reached H < 15 at a nonterminal MAIN decision: 602 eventual wins and 174 eventual losses. The corresponding rates by final submission were 402/999 and 374/1,000. Low H therefore occurs repeatedly, but it is not synonymous with winning.

At our fifth, tenth and fifteenth turns, 1,892, 1,067 and 356 games respectively reached a MAIN decision. Their median H was 34, 21 and 18. Another 107, 932 and 1,643 games had already ended, with one missing replay unresolved at every checkpoint. Of the 107 games ending before our fifth MAIN turn, 97 were losses: the opening remains a concrete weakness.

Fixed own-turn checkpoints separate games still being played from games already ended. A game ending before a checkpoint is not counted as successful information reduction. Reaching a small H is associated with game progress and deck-out wins; it does not establish that reducing H causes a higher win rate.

## Does hidden information still change the useful choice?

We fixed a new experiment before inspecting its confirmatory outcomes. Each sampled game contributes at most one eligible decision per H band: below 15, 15–34, and at least 35. We use MAIN decisions requiring one action from 2–12 legal candidates and evaluate every candidate. Pilot games and games in a prelisted earlier analysis are excluded.

For each position, we sample both players' hidden configuration subject to card conservation and supported observation-history constraints. Both methods are given the correct 60-card decklists. This is an explicit analysis assumption, not information available to the deployed agent. The configuration includes our unknown deck order and Prizes as well as the opponent's hidden cards. Opponent continuations use a fixed registry proxy with at least 45 cards overlapping the actual list; they are not the original Kaggle opponent.

The **ordinary-information choice** selects one action across sampled configurations. This is an analysis-only selector using the correct decklists, not the deployed rule policy's root choice. The **revealed-configuration reference** can select a different action for the particular configuration. Both then use the same observation-limited continuation policies. We score only terminal outcomes: win 1, draw 0.5, loss 0. The reference does not know future coin outcomes.

We split configurations and repetitions so the ordinary-information choice is evaluated on unseen configurations and both choices are scored on repetitions unused for action selection. All root candidates receive the same simulation allocation. Policy memory is restored between branches. Coin seeds are recorded; other engine randomness is not fully seedable.

The primary quantity is the mean reference-minus-ordinary score difference in H < 15 positions. We predeclared a five-percentage-point practical margin and a one-sided 95% upper interval, resampling independent games. Thousands of continuations from one game do not become thousands of independent samples. Unresolved continuations receive worst-case bounds; missing planned low-H positions preclude a complete-cohort primary claim. Reference selection stability and all-win/all-loss frequencies are separate quality checks.

All **300 preselected low-H games** were analyzed, with 925,696 terminal continuations and no errors or cutoffs. The revealed reference gained **0.80 percentage points** over the common-action selector (95% interval: 0.43–1.22). Its one-sided 95% upper was **1.16 points**, below the predeclared five-point margin. A predeclared conservative bound on the positive part of the finite contrast gave an upper of 4.29 points, so negative estimates alone do not explain this finding.

Tie-aware reference agreement was 98.3%. However, 183 positions were all-win and 22 all-loss across tested continuations; 95 had varying outcomes, with descriptive agreement of 94.8%. Saturation helps explain the small average. Extra information retained a small positive benefit, and some individual positions benefited considerably more. The result supports limited *average* sensitivity under the specified procedure, not invariant decisions everywhere.

Descriptively, the middle and high bands gained 2.17 and 1.14 points (300 games each). Reference stability was 84.4% and 60.2%; the high band failed the 80% screen. These results do not establish decreasing information value across bands. All 185 continuation errors occurred in two secondary positions and retained worst-case treatment.

An excluded pilot illustrates the mechanism. At episode 98900407:124, Great Tusk could discard the opponent's last four cards after Explorer's Guidance. Our deck was empty, but the opponent had to draw first. A separate engine check won after this single attack in all 16 configurations, before any opposing decision. Passing instead lost in every tested continuation: the choice mattered, but the hidden arrangement did not change the winning attack.

This finite reference is not an optimal perfect-information solver or an upper bound on its value. Weak continuation policies, candidate restrictions, incomplete history reconstruction and finite action estimates limit the claim. Differences across H bands are descriptive; turn, board state and our own hidden zones also change. Complete inputs, exclusions, code hashes and analysis outputs accompany the experiment.

## What remains unconfirmed

A separate post-deadline local comparison at a **10-second search cap** scored 64.5% without search over 636 games and 69.6% with search over 212 games. This cap differs from the final submission's two-second setting. The approximately five-point difference had a 95% interval spanning zero; it does not establish a search benefit. Earlier ladder builds also differ in policy and opponent pool, so their apparent search advantage is not a causal estimate.

The next engineering step is an exact-archive smoke test that verifies the registry and search activation. The next research step is to identify useful, nontrivial decisions with low information sensitivity and test a policy that reaches them more often against held-out opponents. The contribution we can defend now is the strategic formulation, its implemented deck and rule system, and an explicit, reproducible test of its local mechanism.

## Sources and reproducibility

- Long et al. (2010), [Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search](https://www.cs.du.edu/~sturtevant/papers/pimc.pdf).
- Frank, Basin and Matsubara (1998), [Finding Optimal Strategies for Imperfect Information Games](https://cdn.aaai.org/AAAI/1998/AAAI98-071.pdf).
- [Deck, agent and development analyses](https://github.com/forone-ai/ptcg-great-tusk).
- [Frozen protocol, all 900 position outcomes, analysis code, exclusions and figure evidence](https://drive.google.com/file/d/18-lE5aWEn7VgOH8da0VoQUPygWpsTfZ7/view).
