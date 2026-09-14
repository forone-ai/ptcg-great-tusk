"""Select positions without conditioning on rewards; run on the replay host."""
import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


def band(hidden):
    return 'low' if hidden < 15 else ('mid' if hidden < 35 else 'high')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--per-band', type=int, default=400)
    parser.add_argument('--pilot-games', type=int, default=18)
    parser.add_argument('--seed', type=int, default=20260914)
    args = parser.parse_args()
    files = []
    for source in ('55565424', '55565056'):
        files.extend((Path('/private/tmp/kaggle_eps') / source / 'replays').glob('episode-*-replay.json'))
    files.sort()
    random.Random(args.seed).shuffle(files)
    old_path = Path('/private/tmp/trace2/results.json')
    old_games = {str(r['episode']) for r in json.loads(old_path.read_text())['results']} if old_path.exists() else set()
    counts = Counter()
    selected = []
    excluded = Counter()
    pilot_ids = set()
    seen_games = set()
    for path in files:
        if all(counts[('confirmatory', b)] >= args.per_band for b in ('low', 'mid', 'high')):
            break
        game_id = path.name.split('-')[1]
        if game_id in seen_games:
            excluded['duplicate_game_file'] += 1
            continue
        seen_games.add(game_id)
        if game_id in old_games:
            excluded['previously_examined_game'] += 1
            continue
        data = json.loads(path.read_text())
        names = data.get('info', {}).get('TeamNames', [])
        if names.count('GO HIROSHIMA 2') != 1:
            excluded['own_team_ambiguous'] += 1
            continue
        player = names.index('GO HIROSHIMA 2')
        candidates = {'low': [], 'mid': [], 'high': []}
        for index, step in enumerate(data['steps']):
            agent_step = step[player]
            obs = agent_step.get('observation') or {}
            cur, sel = obs.get('current'), obs.get('select')
            if agent_step.get('status') != 'ACTIVE' or not cur or not sel:
                continue
            if sel.get('context') != 0 or sel.get('minCount') != 1 or sel.get('maxCount') != 1:
                continue
            options = sel.get('option') or []
            if not 2 <= len(options) <= 12 or not obs.get('search_begin_input') or cur.get('looking'):
                continue
            if cur.get('result', -1) != -1:
                continue
            opponent = cur['players'][1-player]
            hidden = opponent['deckCount'] + opponent['handCount'] + len(opponent.get('prize') or [])
            candidates[band(hidden)].append((index, hidden, len(options)))
        if not any(candidates.values()):
            excluded['no_eligible_position'] += 1
            continue
        phase = 'pilot' if len(pilot_ids) < args.pilot_games else 'confirmatory'
        if phase == 'pilot':
            pilot_ids.add(game_id)
        for b, available in candidates.items():
            if not available or (phase == 'confirmatory' and counts[(phase, b)] >= args.per_band):
                continue
            stable_seed = int(hashlib.sha256(f'{args.seed}:{game_id}:{b}'.encode()).hexdigest()[:16], 16)
            index, hidden, n_options = random.Random(stable_seed).choice(available)
            selected.append({'game_id': game_id, 'position_id': f'{game_id}:{index}',
                             'replay_path': str(path), 'source': path.parents[1].name,
                             'our_player': player, 'step': index, 'hidden_count': hidden,
                             'band': b, 'phase': phase, 'opponent': names[1-player],
                             'n_options': n_options})
            counts[(phase, b)] += 1
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in selected))
    metadata = {'seed': args.seed, 'per_band_target': args.per_band, 'available_replays': len(files),
                'selection': 'one uniform eligible MAIN decision per game per band; no reward conditioning',
                'bands': {'low': 'H<15', 'mid': '15<=H<35', 'high': 'H>=35'},
                'counts': {f'{phase}:{b}': n for (phase, b), n in counts.items()},
                'unique_games': len({x['game_id'] for x in selected}), 'excluded': dict(excluded),
                'manifest_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix('.meta.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == '__main__':
    main()
