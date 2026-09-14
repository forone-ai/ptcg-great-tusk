"""Independent scalar checks of forecast MSE and source-table provenance."""
import hashlib
import json
from pathlib import Path

BASE = Path('/Users/gonuts/agent-workspace/kaggle-information-experiment-20260914')
RUN = BASE / 'confirm-1'
FOLLOW = BASE / 'predictability-secondary'


def avg(xs):
    return sum(xs) / len(xs)


def main():
    rows = [json.loads(line) for line in (FOLLOW / 'positions.jsonl').read_text().splitlines()]
    inventory = json.loads((BASE / 'confirmatory-archive-inventory.json').read_text())['files']
    hashes = json.loads((FOLLOW / 'input-hashes.json').read_text())
    assert len(hashes) == 900
    for h in hashes:
        stem = h['position_id'].replace(':', '-')
        assert h['raw_sha256'] == inventory[stem + '.jsonl']['sha256']
        assert h['meta_sha256'] == inventory[stem + '.meta.json']['sha256']
    selected = []
    for band in ('low', 'mid', 'high'):
        selected.extend(sorted((r for r in rows if r['band'] == band and r['saturation'] == 'varied'), key=lambda r: r['position_id'])[:2])
    checked = []
    for position in selected:
        stem = position['position_id'].replace(':', '-')
        meta = json.loads((RUN / (stem + '.meta.json')).read_text())
        worlds = [w['world_id'] for w in meta['worlds']]
        cube = {(int(r['action_id']), r['world_id'], int(r['repeat'])): r['score']
                for r in (json.loads(line) for line in (RUN / (stem + '.jsonl')).read_text().splitlines())}
        action_mse = {'hidden_mse': [], 'revealed_mse': []}
        for action in range(position['actions']):
            errors = {'hidden_mse': [], 'revealed_mse': []}
            for world_index, world in enumerate(worlds):
                training_worlds = [w for i,w in enumerate(worlds) if i % 2 != world_index % 2]
                for test_parity in (0, 1):
                    train_repeats = [i for i in range(32) if i % 2 != test_parity]
                    q_hidden = avg([cube[action, w, r] for w in training_worlds for r in train_repeats])
                    q_revealed = avg([cube[action, world, r] for r in train_repeats])
                    for repeat in range(test_parity, 32, 2):
                        y = cube[action, world, repeat]
                        errors['hidden_mse'].append((q_hidden - y)**2)
                        errors['revealed_mse'].append((q_revealed - y)**2)
            assert all(len(v) == 512 for v in errors.values())
            for metric in action_mse:
                action_mse[metric].append(avg(errors[metric]))
        result = {'position_id': position['position_id']}
        for metric, values in action_mse.items():
            value = avg(values)
            assert abs(value - position[metric + '_bounds'][0]) < 1e-12
            assert abs(value - position[metric + '_bounds'][1]) < 1e-12
            result[metric] = value
        checked.append(result)
    summary = json.loads((FOLLOW / 'summary.json').read_text())
    for band in ('low', 'mid', 'high'):
        for endpoint in (0,1):
            value = avg([r['hidden_mse_bounds'][endpoint] for r in rows if r['band'] == band])
            expected = summary['groups']['all900_with_unresolved_bounds'][band]['metrics']['hidden_mse']['mean_bounds'][endpoint]
            assert abs(value - expected) < 1e-12
    output = {'all_900_raw_and_meta_hashes_match_original_archive': True,
              'independently_recomputed_varied_positions': checked,
              'all_band_means_verified': True,
              'source_script_sha256': hashlib.sha256((FOLLOW / 'analyze_predictability.py').read_bytes()).hexdigest()}
    (FOLLOW / 'independent-verification.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
