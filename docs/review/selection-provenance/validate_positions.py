"""Check structural eligibility before inspecting any simulated outcomes."""
import argparse
import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from worlds import extract_decklists_from_replay, make_worlds, observations_for_player


@lru_cache(maxsize=4)
def replay(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--agent-root', default='/private/tmp/x16j_withopp_1789064695')
    parser.add_argument('--min-deck-overlap', type=int, default=45)
    args = parser.parse_args()
    root = Path(args.agent_root)
    registry = json.loads((root/'opponents/registry.json').read_text())
    opponents = []
    for item in registry['runnable_opponents']:
        deck = [int(x) for x in (root/item['deck']).read_text().split()]
        opponents.append((Counter(deck), item['main']))
    counts, errors = Counter(), Counter()
    accepted = rejected = 0
    output = Path(args.out)
    with output.open('w') as valid, output.with_suffix('.rejected.jsonl').open('w') as invalid:
        for line in Path(args.manifest).read_text().splitlines():
            row = json.loads(line)
            try:
                data = replay(row['replay_path'])
                deck_record = extract_decklists_from_replay(data)
                player = row['our_player']
                actual = Counter(deck_record['decks'][1-player])
                overlap, policy = max((sum((actual & counter).values()), policy) for counter, policy in opponents)
                if overlap < args.min_deck_overlap:
                    raise ValueError(f'proxy_deck_overlap_below_threshold:{overlap}')
                obs = data['steps'][row['step']][player]['observation']
                history = observations_for_player(data, player, row['step'])
                worlds = make_worlds(obs, deck_record['decks'][player], deck_record['decks'][1-player],
                                     4, 2026091402, history=history)
                if len(worlds) < 4:
                    raise ValueError(f'fewer_than_four_distinct_worlds:{len(worlds)}')
                row['eligibility'] = {'snapshot_validated': True, 'full_history_legality_proven': False,
                                      'opponent_deck_overlap_cards': overlap, 'proxy_policy': policy}
                valid.write(json.dumps(row, ensure_ascii=False)+'\n')
                counts[f"{row['phase']}:{row['band']}"] += 1
                accepted += 1
            except Exception as exc:
                code = getattr(exc, 'code', str(exc).split(':')[0])
                errors[str(code)] += 1
                invalid.write(json.dumps(dict(row, eligibility_error=type(exc).__name__+':'+str(exc)), ensure_ascii=False)+'\n')
                rejected += 1
    summary = {'accepted': accepted, 'rejected': rejected, 'counts': dict(counts),
               'reasons': dict(errors), 'outcomes_inspected': False,
               'manifest_sha256': hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
               'valid_manifest_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
               'worlds_sha256': hashlib.sha256((Path(__file__).parent/'worlds.py').read_bytes()).hexdigest()}
    output.with_suffix('.meta.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
