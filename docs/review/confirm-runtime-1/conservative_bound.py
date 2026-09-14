"""Secondary empirical-Bernstein diagnostic for the finite procedure's positive gap.

Maurer & Pontil (COLT 2009), Theorem 11. Assumes independent game-level variables
in [0,1]. This does not bound optimal perfect-information value.
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def bound(values, alpha=.05):
    n = len(values)
    if n < 2 or any(not 0 <= x <= 1 for x in values):
        raise ValueError('Need at least two independent bounded game values')
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    log_term = math.log(2 / alpha)
    radius = math.sqrt(2 * variance * log_term / n) + 7 * log_term / (3 * (n - 1))
    return {'games': n, 'positive_gap_mean_with_missing_bounds': mean,
            'unbiased_sample_variance': variance, 'alpha': alpha,
            'one_sided_upper': min(1, mean + radius), 'radius_before_clipping': radius}


def usable_position(row, metadata, coverage, run_config):
    if (row is None or row.get('status') != 'ok'
            or metadata.get('status') != 'complete'
            or not coverage.get('analysis_included')):
        return False
    return (row.get('world_count') == len(metadata.get('worlds') or [])
            and row.get('action_count') == metadata.get('n_actions')
            and row.get('repeat_count') == run_config.get('repeats')
            and metadata.get('completed') == coverage.get('rows'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    manifest = [json.loads(line) for line in (args.runtime / 'manifest.jsonl').read_text().splitlines()]
    rows = json.loads((args.run / 'analysis.json').read_text())['positions']['position_results']
    observed = {r['position_id']: r for r in rows}
    coverage = {r['position_id']: r for r in json.loads((args.run / 'coverage.json').read_text())['details']}
    run_config = json.loads((args.run / 'run-config.json').read_text())
    games = defaultdict(list)
    missing = 0
    for entry in manifest:
        if entry['phase'] != 'confirmatory' or entry['band'] != 'low':
            continue
        row = observed.get(entry['position_id'])
        meta_path = args.run / (entry['position_id'].replace(':', '-') + '.meta.json')
        try:
            metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            if not isinstance(metadata, dict):
                metadata = {}
        except (ValueError, OSError):
            metadata = {}
        if not usable_position(row, metadata, coverage.get(entry['position_id'], {}), run_config):
            value = 1.
            missing += 1
        else:
            value = max(0., row['delta_all_pairs_upper'])
        games[entry['game_id']].append(value)
    output = bound([sum(v) / len(v) for v in games.values()])
    output.update(status='secondary_diagnostic_predeclared_before_confirmatory_outcomes',
                  missing_or_invalid_low_positions_bounded_at_one=missing,
                  interpretation='Upper bound for the positive part of this finite estimated contrast under independent-game assumptions. Includes worst-case unresolved values. It is not a bound on the true optimal perfect-information advantage.',
                  source='https://www.cs.mcgill.ca/~colt2009/papers/012.pdf',
                  source_location='Theorem 11; independent potentially nonidentically distributed variables; unbiased sample variance; values in [0,1]')
    (args.run / 'conservative-bound.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
