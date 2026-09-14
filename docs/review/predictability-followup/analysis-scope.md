# Exploratory follow-up: predictability

This follow-up was requested after the original confirmatory results and reference-stability estimates were known. It is not a new preregistered primary test. It does not change the original 900 selected positions, raw outcomes, code, stopping rule, or primary claim.

The question is whether positions with fewer cards remaining in the opponent's deck, hand and Prizes have more predictable simulated outcomes. The study does not manipulate how many cards become visible while holding the same board fixed. Associations across the three original H bands may reflect stage of play, board, own hidden state, action count, outcome saturation, and continuation-policy behavior.

Two quantities are kept distinct:

1. Action-selection repeatability, extracted from the existing final analysis. Exact agreement, tie-aware agreement and common/revealed action agreement are all retained. None is called forecast accuracy.
2. Held-out terminal-score prediction error, newly computed from the saved outcome tables. A predictor averages other sampled configurations and training repetitions for the same root action, then predicts outcomes from held-out configurations and held-out repetitions. Both configuration and repeat halves are swapped. Mean squared error is averaged equally across actions and positions. Lower error means these fixed-policy terminal scores were easier to forecast using this finite predictor.

The score scale is win 1, draw 0.5, loss 0. The score forecast is not represented as a calibrated probability of winning. A same-configuration predictor is a supplemental comparison; it uses fewer training continuations than the other-configuration predictor and thus does not isolate information from estimation precision.

Results retain all 900 positions through bounds for unresolved training and evaluation scores. The 898 error-free positions and the positions with varying terminal outcomes are separate exploratory sensitivity analyses. Removing all-win/all-loss positions is outcome-dependent and does not create a new confirmatory sample. Paired comparisons retain the same source game as the resampling unit; they do not control within-game changes in time or board.

The source is the archived fixed experiment: `../data/confirmatory-raw-and-analysis.tar.gz`, archive SHA-256 `824078bcd7f6a9b1e7d818c483b4672c4523ec0151af55de231d99d5efadbd59`. Original combined-cell SHA-256 is `3d639a3b9df38da9431c40869061e1d3e4e977466ef34906e1ebf58c61df7c63`.
