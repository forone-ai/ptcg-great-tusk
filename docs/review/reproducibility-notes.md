# Reproducing the hidden-information experiment

This experiment evaluates a finite root-action selection procedure. It does not measure the submitted agent's win-rate improvement or prove equivalence to an optimal perfect-information solver.

## Frozen experiment

- Freeze time: 2026-09-14 04:16:55 Japan time.
- Start time: 2026-09-14 04:17:15 Japan time.
- Finish time: 2026-09-14 06:08:27 Japan time (111.2 minutes; 900/900 positions complete).
- Fixed sample: 900 positions from 498 distinct recorded games, with 300 distinct games in each H band.
- H: opponent deck count + hand count + remaining Prize count; low <15, mid 15–34, high ≥35.
- Each position: up to 16 distinct sampled configurations, all 2–12 available root candidates, 32 continuations per configuration/candidate.
- Execution: eight independent worker processes on the iroha Mac mini. Low positions run first, without changing sample membership.
- Per-continuation limit: 1,200 engine steps. Per-position time budget: 600 seconds, checked between continuations. A single policy call is not preempted by this position budget.
- Hard run deadline: 2026-09-14 07:00 Japan time. The run guard terminates the experiment process group at that deadline.
- Primary margin: 0.05 score points, equivalent to five percentage points on a win=1/draw=0.5/loss=0 scale.
- Primary uncertainty: independent-game bootstrap, 4,000 resamples, seed 20260914.
- Simulation master seed: 2026091401.
- Diagnostic reference-stability threshold: 0.80. This is a screen, not a guarantee of optimality.
- Secondary conservative diagnostic: the positive part of the finite contrast, with an empirical Bernstein upper bound and missing/invalid positions bounded at one.

The frozen runtime contains the manifest, complete configuration, analysis protocol and source hashes. Its manifest SHA-256 is `ab8b5d77334f75d97bf66d3789b18c43a79232b81ab043f3e390c21d44f0c0c2`.

The protocol preserves planning examples, including earlier candidate targets of 400 positions per band. Actual execution uses the final frozen configuration: 300 per band, up to 16 configurations and 32 repeats. The earlier planning text is not rewritten retrospectively.

The frozen source inventory covered Python files, deck CSV files and the macOS native engine. It did not include `opponents/registry.json`. That auxiliary configuration is supplied separately, with a supplemental dependency inventory captured after the run began and before confirmatory outcomes were inspected. This later checksum is not represented as a freeze-time checksum. The inventory found no mismatch in any source file that had been hashed at freeze time. Other bundled platform libraries were not used in this macOS experiment.

After completion, all 58 inventoried agent dependencies had the same checksums as the supplemental inventory. The final low-H results exactly match the earlier snapshot taken only after all 300 planned low-H games had completed. The later middle/high outputs did not change that analysis.

All 900 planned position tables were complete: 2,844,999 terminal continuations and 185 exceptions, with no cutoffs or own-policy tracking errors. The 185 exceptions were `KeyError: 0` in two secondary positions from episode 101687484 (34 in middle-H step 126 and 151 in high-H step 16). Root cause is unconfirmed. Error scores remain null and receive the predeclared unresolved-outcome treatment. They were not dropped or counted as observed losses. All 925,696 low-H continuations were terminal without exceptions.

## What each comparison knows

Both analysis selectors receive the correct two 60-card decklists and the same observation-history constraints supported by the sampler. This is a study assumption. It is not a claim that the deployed agent knew the opposing decklist.

The configuration-averaged selector chooses a common root action using other sampled configurations. The revealed-configuration selector chooses a root action for the particular configuration. Selection and scoring use separate repetition folds. Subsequent choices use the same observation-limited policies. The revealed selector does not know future coin flips.

For 16 configurations, the common selector trains on the other eight configurations and 16 training repeats per action; the revealed selector trains on its one configuration and 16 training repeats per action. The underlying outcome table allocates equal simulations to every candidate, but these two estimators do not have equal estimation precision. Configurations are sorted by ID and split alternately; repeats are similarly split by parity. A tie is broken in ascending stringified root-candidate ID order. An unresolved training score is zero by the predeclared selection rule, not declared to be an observed loss.

Configurations vary the opponent's hidden allocations and both players' unknown deck order/Prizes. They satisfy card conservation and supported current/history constraints. They are not a posterior proven consistent with every past action, draw, or likelihood. The fixed proxy policy is selected from the registry by deck overlap, with a minimum of 45 matching cards out of 60; it is not the original Kaggle opponent agent. Its memory starts fresh at the root. The proxy may be weaker than the actual opponent.

Deck overlap counts repeated copies, and ties in proxy selection are broken by policy path. Our policy memory is warmed with its ACTIVE observations through the root; the proxy starts with fresh memory. The continuation proxy's search is disabled. This initialization is asymmetric and is not a reconstruction of the original opposing agent's private memory.

## Visibility and policy state

The Search API exposes supplied Prize fills in its reconstructed observation. Before either continuation policy is called, unknown Prizes are masked. Prizes visible in the original root are certified by owner/slot and tracked using simulation serial numbers. Newly face-up Prizes cannot be inferred solely from the API's full exposure, so unsupported new visibility is not added. The opponent's hand is checked for private exposure.

The public `current` and `select` fields matched the typed original observation in six engine-root checks after masking. Six following end-turn transitions also passed observer-switch privacy checks. Known-Prize handling passed synthetic tests; no non-null Prize example was found in 5,718 inspected ACTIVE frames from 39 earlier games. This is not a complete verification of every possible game effect.

Mutable/scalar policy globals and the audited AttackPlan instances/class data are restored between branches. Aliases within a namespace are retained. This is not a general snapshot of every arbitrary Python object, closure, module or external resource. The own decision function's exceptions are surfaced rather than silently replaced by the first legal action. Proxy-internal fallbacks are not universally instrumented.

Pilot runs 1 and 2 preceded the Prize-visibility correction and are excluded from scientific results. Corrected pilot 3 used separate pilot games and completed 39 positions / 115,712 terminal continuations without errors or cutoffs in about seven minutes. Its high-H reference remained unstable, which was recorded before confirmatory outcomes were inspected.

## Files and independent sample units

- `frozen-config.json` / `manifest.jsonl`: fixed sample, settings, code hashes and source provenance.
- `run-config.json` / `guard-status.json`: executed settings and start/finish/deadline status.
- One `game-step.jsonl` per position: every configuration/action/repetition outcome, terminal/error/cutoff status, seeds and privacy diagnostics.
- One `game-step.meta.json` per position: original root candidates, sampled fills, configuration validation, proxy identity and completion status.
- `coverage.json`: every selected position, including unstarted, partial, failed or malformed positions.
- `cells.jsonl`: only metadata-complete, unique, full planned evaluation tables used in analysis.
- `partial-cells.jsonl` / `corrupt-lines.jsonl`: retained incomplete or malformed data, outside the main analysis.
- `analysis.json`: fixed primary and descriptive secondary estimates, game-level intervals and quality diagnostics.
- `quality.json`: all-win/all-loss/all-draw/mixed finite outcomes. These are observations, not proved forced outcomes.
- `conservative-bound.json`: a separate bounded diagnostic that includes every selected low-H game.
- `analysis-coverage-verification.json`: external comparison of the full frozen manifest, collector eligibility and valid statistical positions, plus verification of the frozen analysis source hashes.

The primary bootstrap uses complete planned evaluation tables. Within such a table, unresolved continuations contribute interval bounds. A missing or invalid position is not silently represented by this bootstrap: the external coverage check must show all 300 planned low-H positions valid before making a complete-cohort primary claim. The separate conservative diagnostic assigns one to any missing or invalid selected low-H position. It does not replace a failed primary analysis or poor reference quality.

Different configurations, candidate actions and repetitions from one game are not independent games. Each H band has 300 independent game units; the union has 498 because a game can appear in more than one band. The high-minus-low analysis carries a game's bands together when resampling and also reports the common-game subset separately.

## Re-run the analysis

The scripts use Python 3.11 or later. Core statistics use the standard library. Figure generation additionally uses NumPy and Matplotlib. Keep the frozen code and raw run directory together; do not modify a frozen runtime in place.

```sh
python /path/to/frozen-runtime/collect_run.py /path/to/run
python /path/to/frozen-runtime/statistics.py --positions /path/to/run/cells.jsonl --phase confirmatory --bootstrap 4000 --margin .05 --min-reference-stability .80 --output /path/to/run/analysis.json
python /path/to/frozen-runtime/quality_summary.py /path/to/run
python /path/to/frozen-runtime/conservative_bound.py --runtime /path/to/frozen-runtime --run /path/to/run
```

Re-running the simulations additionally requires the same agent/proxy files, competition engine, registry and source replays identified in the manifest. Update paths in a copied manifest when moving machines, preserve the original manifest/hash, and record the path-only transformation. The tested environment was macOS arm64 with the project's Python 3.11.15 virtual environment. A Linux/AWS runtime was not tested in this experiment. The recorded Python/coin seeds do not control every internal engine random operation; a fresh simulation may produce different scores. Analysis of the saved raw data is reproducible.

The frozen guard rejects a start after its original deadline. For a new simulation, copy the runtime, set an appropriate new hard deadline and paths, and label it a derived run. Preserve the original frozen files and record every changed field. Do not treat the derived run as the original confirmatory experiment.

## Actual-game cohort audit

The separate cohort uses all 2,000 listed episodes of submissions 55565056 and 55565424. There are 1,999 replay files; draw episode 103457731 is missing. It remains unresolved for reach/checkpoint measures. Metadata rewards and replay rewards agree in all 1,999 available games; all final statuses are DONE and no own-turn parity inconsistencies were found. These archives do not contain an explicit terminal engine result in their observations.

The cohort's denominators are not inferred from the quota-sampled experiment. The first own MAIN at own turns 5, 10 and 15 is recorded even when only one candidate exists. A game ending before a checkpoint retains its win/loss/draw classification; it is not assigned H=0 or counted as perfect-information success. Formation is descriptive, without a causal deck or policy comparison.

## Selection provenance and illustrative examples

The selection-provenance directory preserves the original 1,241-position manifest, 1,029 eligible positions, metadata and exclusion IDs. Reapplying the recorded selection reproduces the exact frozen 900-position manifest. All 212 initial rejections failed the proxy-deck overlap requirement. The pilot reservation/selected games and 39 earlier-inspected games have no overlap with the final 498. Re-selecting from the entire original population requires all 1,999 replay inputs; the separate input archive includes only the 498 games needed for the selected simulation.

Episode 103027623:259 was chosen after the primary analysis from a search through all 300 low-H tables. It illustrates the implemented deck-budget rule, not a new confirmatory subgroup. The accompanying search outputs retain all 300 IDs and input hashes, including counterexamples. For the illustrated Dwebble action, the rule was reconstructed from 83 earlier observations and then invoked once at the root. Separate representative continuations explain the mechanism but do not replace the full 16-configuration × 32-repeat outcome table.

Episode 98900407:124 comes from corrected, excluded pilot 3. Its direct engine check demonstrates an immediate deck-out win for Land Collapse in 16 supplied configurations; it is separate from the fixed-policy heatmap and from the confirmatory sample. Neither example estimates how often the mechanism occurs in the original population.

## References

- Maurer and Pontil (2009), [Empirical Bernstein Bounds and Sample Variance Penalization](https://www.cs.mcgill.ca/~colt2009/papers/012.pdf), Theorem 11.
- Long et al. (2010), [Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search](https://www.cs.du.edu/~sturtevant/papers/pimc.pdf).
- Frank, Basin and Matsubara (1998), [Finding Optimal Strategies for Imperfect Information Games](https://cdn.aaai.org/AAAI/1998/AAAI98-071.pdf).
