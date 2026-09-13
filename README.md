# Great Tusk — PTCG AI Battle Challenge (Strategy Category writeup companion)

Team **GO HIROSHIMA 2** · Kaggle *The Pokémon Company – PTCG AI Battle Challenge* (Simulation + Strategy).
Final Simulation entry: rating 799.3, rank 1,150 / 6,807 teams.

This repository accompanies our Strategy Category writeup. It contains the exact agent source of the final
submission, the scripts that produced every ladder figure in the writeup, and the per-game labels for the
7,006 ladder games behind those figures — so any reader can re-derive the numbers.

## What is here

| Path | Contents |
|---|---|
| `agent/` | Final submission source (`main.py`, `rule_policy.py`, `puct_tree.py`, `engine/`, `strategy/`) and the 60-card `deck.csv` (card IDs) / `decklist.csv` (names, counts, roles) |
| `analysis/` | Ladder analysis: episode fetch (`kdl.py`), timeline and matchup tables (`lb_timeline.py`, `lb_lists.py`, `lb_bands.py`), figure generation (`make_lb_figs.py`), plus the proxy-league runner and submission-gate helpers used during development |
| `analysis/ladder_games_labelled.json` | 7,006 ladder games: episode id, date, submission, opponent team, opponent deck family, result |
| `docs/writeup/` | Writeup figures and the scripts that draw the concept diagrams |
| `docs/` | Internal engineering notes referenced by the writeup (final-night report, evaluation principles, post-deadline proposals) |

## What is deliberately not here

- The competition engine binaries (`cg/`), card database, replays and episode JSON: these are Competition Data under the
  competition rules and are not redistributed. Download them from the competition Data tab and place the runtime under `agent/cg/`.
- `opponents/`: the registry of reproduced public opponent decks and agents the search layer uses for determinization.
  These are other participants' published code; we do not redistribute them. `agent/main.py` documents the registry
  format (`opponents/registry.json` with `runnable_opponents: [{id, deck, main, archetype}]`) and falls back to rule-only
  play when the directory is absent.

## Reproducing the ladder figures

```
pip install kaggle matplotlib numpy
# 1. list our submissions and every episode they played (needs your own Kaggle API token)
python analysis/kdl.py <submission_ids> ""
# 2. join with a team->deck label table and build the tables / figures
python analysis/lb_timeline.py
python analysis/make_lb_figs.py out/
```

`lb_timeline.py` expects a `state.json` mapping Kaggle team ids to deck labels (we built ours from the public
leaderboard's visible decks); the labelled JSON above is the output we used.

## Running the agent locally

Place the official runtime under `agent/cg/`, then use the competition's `sample_submission` harness or
`analysis/run_proxy_league.py --candidate-main agent/main.py --our-deck agent/deck.csv --registry <your registry> --out out.json`.

## License

MIT for everything authored by the team (see `LICENSE`). Pokémon Elements referenced in code comments and documentation
remain the property of The Pokémon Company and are used only as permitted by the competition rules.
