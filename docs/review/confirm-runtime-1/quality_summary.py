"""Descriptive reference quality and outcome saturation; no sample extension rule."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    analysis = json.loads((args.run / 'analysis.json').read_text())['positions']
    valid = {r['position_id'] for r in analysis['position_results'] if r['status'] == 'ok'}
    buckets = defaultdict(list)
    for line in (args.run / 'cells.jsonl').read_text().splitlines():
        row = json.loads(line)
        buckets[row['position_id']].append(row)
    counters = defaultdict(Counter)
    for position, rows in buckets.items():
        count = counters[rows[0]['band']]
        count['positions'] += 1
        metadata = json.loads((args.run / (position.replace(':', '-') + '.meta.json')).read_text())
        if position not in valid or metadata.get('status') != 'complete':
            count['incomplete_positions'] += 1
            continue
        count['complete_positions'] += 1
        observed = [r['score'] for r in rows if r.get('terminal') and not r.get('error')]
        if len(observed) != len(rows):
            count['positions_with_unresolved'] += 1
            continue
        if len(set(observed)) == 1:
            count['all_cells_identical'] += 1
            count[{0: 'all_cells_loss', 0.5: 'all_cells_draw', 1: 'all_cells_win'}[observed[0]]] += 1
        else:
            count['outcome_varies_across_cells'] += 1
        per_action = defaultdict(list)
        for row in rows:
            per_action[str(row['action_id'])].append(row['score'])
        means = [sum(values) / len(values) for values in per_action.values()]
        if max(means) - min(means) > 1e-12:
            count['actions_have_different_sample_mean'] += 1
    results = {}
    for band in ('low', 'mid', 'high'):
        block = analysis['by_arm_and_bin']['reference'][band]
        if not block:
            continue
        results[band] = {'independent_games': block['independent_games'],
                         'game_difference_sd': block['exploratory_sd_of_game_differences'],
                         'reference_quality': {k: v for k, v in block['estimates'].items()
                                               if k.startswith('revealed_') or k == 'terminal_cell_fraction'},
                         'saturation': dict(counters[band])}
    output = {'description': 'Pilot calibration uses dispersion, reference stability, saturation, and runtime. A saturated outcome is an empirical property of this finite continuation; it is not a proved forced win/loss.',
              'by_band': results}
    (args.run / 'quality.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
