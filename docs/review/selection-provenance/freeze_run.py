"""Freeze outcomes-independent sample/config and code before a confirmatory run."""
import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--per-band', type=int, default=300)
    parser.add_argument('--worlds', type=int, default=16)
    parser.add_argument('--repeats', type=int, default=32)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    runtime = args.base / args.name
    runtime.mkdir(exist_ok=False)
    code_names = ('position_runner.py', 'worlds.py', 'statistics.py', 'protocol.md',
                  'collect_run.py', 'quality_summary.py', 'run_guard.py', 'conservative_bound.py')
    for name in code_names:
        shutil.copy2(args.base / name, runtime / name)
    source = args.base / 'positions-eligible.jsonl'
    selected, count = [], Counter()
    for line in source.read_text().splitlines():
        entry = json.loads(line)
        if entry['phase'] == 'confirmatory' and count[entry['band']] < args.per_band:
            selected.append(entry)
            count[entry['band']] += 1
    assert set(count) == {'low', 'mid', 'high'}
    assert all(n == args.per_band for n in count.values())
    assert len({(e['game_id'], e['band']) for e in selected}) == len(selected)
    # The primary band runs first to protect it from the predeclared deadline.
    # Membership and within-band order remain independent of outcomes.
    selected = [e for e in selected if e['band'] == 'low'] + [e for e in selected if e['band'] != 'low']
    manifest = runtime / 'manifest.jsonl'
    manifest.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in selected))
    agent_root = Path('/private/tmp/x16j_withopp_1789064695')
    sources = sorted(agent_root.rglob('*.py')) + sorted(agent_root.rglob('*.csv'))
    sources += [agent_root / 'cg/libcg.dylib']
    source_hashes = {str(p.relative_to(agent_root)): sha(p) for p in sources if p.is_file()}
    fixed = {'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
             'sample_source_sha256': sha(source), 'manifest_sha256': sha(manifest),
             'selection': 'First eligible positions in original outcomes-independent shuffled-game manifest; one per game/bin; no replacement after failure.',
             'execution_order': 'All selected low positions first; original relative order within low and within the remaining mid/high positions.',
             'counts': dict(count), 'independent_games_across_bins': len({e['game_id'] for e in selected}),
             'worlds': args.worlds, 'repeats': args.repeats, 'workers': args.workers,
             'seed': 2026091401, 'max_steps': 1200, 'position_time_limit_seconds': 600,
             'calculation_stop_utc': '2026-09-13T22:00:00+00:00',
             'primary_margin': 0.05, 'minimum_reference_stability': 0.80,
             'bootstrap_replicates': 4000, 'bootstrap_seed': 20260914,
             'code_sha256': {name: sha(runtime / name) for name in code_names},
             'agent_root': str(agent_root), 'agent_source_sha256': source_hashes,
             'pilot_results_excluded': True,
             'planning_note': 'N fixed using the 39-position corrected pilot and available eligible sample. Pilot low has only five games and zero estimated gap SD, so it is not treated as a reliable zero-variance population. We retain 300 games per band and judge precision from the fixed-sample interval. Pilot high reference stability is only about 0.61 at R32, so high-bin information-value interpretation remains a limitation; its sample remains descriptive. No confirmatory outcomes inspected.'}
    (runtime / 'frozen-config.json').write_text(json.dumps(fixed, indent=2) + '\n')
    print(json.dumps({k: v for k, v in fixed.items() if k != 'agent_source_sha256'}, indent=2))


if __name__ == '__main__':
    main()
