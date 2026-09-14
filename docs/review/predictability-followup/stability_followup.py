"""Exploratory descriptions requested after confirmatory outcomes were known.

These metrics describe repeatability of action selection, not forecast accuracy.
No changes to original data, sample, analysis, or stopping rule.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

METRICS = ('revealed_split_exact_action_agreement',
           'revealed_split_cross_optimal_agreement',
           'public_revealed_same_action_fraction')


def quantile(values, q):
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def summarize(rows, seed=2026091407, count=4000):
    if not rows:
        return {'positions': 0}
    assert len({r['game_id'] for r in rows}) == len(rows)
    rng = random.Random(seed)
    n = len(rows)
    data = {metric: [row[metric] for row in rows] for metric in METRICS}
    boot = {metric: [] for metric in METRICS}
    for _ in range(count):
        indices = [rng.randrange(n) for _ in range(n)]
        for metric in METRICS:
            boot[metric].append(sum(data[metric][i] for i in indices) / n)
    return {'positions': n, 'distinct_games': n,
            'metrics': {m: {'mean': sum(data[m]) / n,
                            'two_sided_95': [quantile(boot[m], .025), quantile(boot[m], .975)]}
                        for m in METRICS}}


def paired(rows, only_complete=False):
    grouped = {}
    for row in rows:
        if only_complete and (row['error_rows'] or row['cutoff_rows']):
            continue
        grouped.setdefault(row['game_id'], {})[row['bin']] = row
    differences = []
    for game, bands in grouped.items():
        if 'low' in bands and 'high' in bands:
            differences.append(dict(game_id=game, **{m: bands['low'][m] - bands['high'][m] for m in METRICS}))
    return summarize(differences)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--analysis', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.analysis.read_bytes()
    rows = json.loads(raw)['positions']['position_results']
    assert len(rows) == 900 and all(r['status'] == 'ok' for r in rows)
    result = {
        'status': 'post_hoc_exploratory_after_primary_results_known',
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'bootstrap_replicates': 4000, 'bootstrap_seed': 2026091407,
        'metric_definitions': {
            METRICS[0]: 'Exact root action selected on even repeats matches that selected on odd repeats in the same sampled hidden world, averaged over worlds.',
            METRICS[1]: 'An action selected on one repeat half belongs to the tied-best set in the other half, averaged over both directions and sampled worlds.',
            METRICS[2]: 'Common action trained on other worlds equals revealed-world reference action, both using training repeats; evaluated over held-out world/repeat pairs.'},
        'all_900': {b: summarize([r for r in rows if r['bin'] == b]) for b in ('low', 'mid', 'high')},
        'without_two_error_positions': {b: summarize([r for r in rows if r['bin'] == b and not r['error_rows'] and not r['cutoff_rows']]) for b in ('low', 'mid', 'high')},
        'paired_low_minus_high': paired(rows),
        'paired_without_error_positions': paired(rows, True),
        'limitations': [
            'Measures action-selection repeatability and common/reference agreement, not held-out outcome prediction accuracy.',
            'H is opponent deck+hand+remaining Prizes; no number of revealed cards was experimentally manipulated.',
            'Game stage, board, own hidden state, action count, saturation and simulation noise may explain associations.',
            'Paired games control game identity only, not changing within-game board or turn.',
            'The 185 secondary error cells had zero training value in the original predeclared selector; full results preserve that definition and complete-position sensitivity is separate.',
            'Broad ties inflate agreement. Both exact and tie-aware metrics are reported.',
        ]
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
