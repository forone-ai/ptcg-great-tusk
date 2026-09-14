"""Evaluate root actions across common hidden worlds with observation-only continuation.

The exact opponent decklist is oracle side information for this mechanism study.
This is not an evaluation of the shipped agent's win-rate improvement.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import random
import signal
import sys
import time
import types
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path


IMMUTABLE_TABLE_NAMES = {'CARD_TABLE', 'ATTACK_TABLE', '__builtins__', '__annotations__'}
STATE_TYPES = (dict, list, set, tuple, bytearray, str, int, float, bool, type(None))


def attack_plan_class(namespace):
    candidate = namespace.get('AttackPlan')
    return candidate if isinstance(candidate, type) and candidate.__name__ == 'AttackPlan' else None


def tracked_state(name, value, plan_class):
    return (not name.startswith('__') and name not in IMMUTABLE_TABLE_NAMES
            and (isinstance(value, STATE_TYPES)
                 or (plan_class is not None and isinstance(value, plan_class))))


def snapshot(namespace):
    plan_class = attack_plan_class(namespace)
    values = {name: value for name, value in namespace.items()
              if tracked_state(name, value, plan_class)}
    class_values = ({name: value for name, value in vars(plan_class).items()
                     if tracked_state(name, value, None)} if plan_class else {})
    # Copy the complete bundle together so aliases between plan_a/plan_b and
    # mutable class defaults are preserved within this namespace.
    saved = copy.deepcopy({'global_values': values, 'class_values': class_values})
    saved['plan_class'] = plan_class
    return saved


def restore(namespace, saved):
    plan_class = saved['plan_class']
    restored = copy.deepcopy({'global_values': saved['global_values'],
                              'class_values': saved['class_values']})
    for name in list(namespace):
        if (tracked_state(name, namespace[name], plan_class)
                and name not in restored['global_values']):
            del namespace[name]
    if plan_class is not None:
        namespace['AttackPlan'] = plan_class
        for name, value in list(vars(plan_class).items()):
            if tracked_state(name, value, None) and name not in restored['class_values']:
                delattr(plan_class, name)
        for name, value in restored['class_values'].items():
            setattr(plan_class, name, value)
    namespace.update(restored['global_values'])


def policy_state(function, agent_root):
    namespaces = []
    queue = [function.__globals__]
    seen = set()
    while queue:
        namespace = queue.pop()
        if id(namespace) in seen:
            continue
        seen.add(id(namespace))
        namespaces.append((namespace, snapshot(namespace)))
        for value in namespace.values():
            if isinstance(value, types.ModuleType):
                file_name = getattr(value, '__file__', None)
                if file_name and Path(file_name).is_relative_to(agent_root) and '/cg/' not in file_name:
                    queue.append(vars(value))
    return namespaces


def restore_policy(states):
    for namespace, saved in states:
        restore(namespace, saved)


def seed_for(*parts):
    return int(hashlib.sha256(':'.join(map(str, parts)).encode()).hexdigest()[:16], 16)


def root_has_visible_prizes(original):
    return any(isinstance(card, dict) and card.get('id')
               for player in original['current']['players']
               for card in player.get('prize') or [])


def prize_visibility(original, simulated_root=None):
    """Map original face-up Prize slots to the simulation's actual serials.

    The engine Card schema uses None for facedown Prizes. SearchBegin instead
    exposes the supplied fills. Only cards visible in the ORIGINAL root receive
    a certificate; never infer visibility from a simulated card's presence.
    """
    visible = [dict(), dict()]
    for owner, player in enumerate(original['current']['players']):
        for index, card in enumerate(player.get('prize') or []):
            if not isinstance(card, dict) or not card.get('id'):
                continue
            if simulated_root is None:
                raise ValueError('known_prize_requires_simulated_root_slot_mapping')
            simulated = simulated_root['current']['players'][owner].get('prize') or []
            if index >= len(simulated) or not isinstance(simulated[index], dict):
                raise ValueError('known_prize_slot_missing_in_simulated_root')
            replacement = simulated[index]
            if replacement.get('id') != card['id'] or not replacement.get('serial'):
                raise ValueError('known_prize_slot_identity_changed')
            visible[owner][int(replacement['serial'])] = int(card['id'])
    return {'visible': visible, 'masked_cards': 0, 'observations': 0,
            'root_visible_prizes': sum(len(cards) for cards in visible)}


def sanitize_continuation_observation(observation, visibility):
    """Redact fresh Search API dictionaries in place, never original replays.

    Typed Pokemon omit playerIndex by design; retain that public representation.
    Stadium, hand, looking, selection and public card fields are not rewritten.
    """
    current = observation.get('current') or {}
    for owner, player in enumerate(current.get('players') or []):
        prizes = player.get('prize') or []
        allowed = visibility['visible'][owner]
        remaining = set()
        for index, card in enumerate(prizes):
            if (isinstance(card, dict) and card.get('serial') in allowed
                    and card.get('id') == allowed[card['serial']]):
                remaining.add(card['serial'])
                continue
            visibility['masked_cards'] += int(isinstance(card, dict) and bool(card.get('id')))
            prizes[index] = None
        # Once a certified card leaves Prizes, do not re-reveal it if recycled.
        visibility['visible'][owner] = {serial: allowed[serial] for serial in remaining}
    visibility['observations'] += 1
    return observation


def privacy_check(observation, visibility):
    current = observation.get('current')
    if not current:
        return
    acting = current['yourIndex']
    # The public engine normally uses null for the other player's hand.
    # Reject any visible private hand rather than silently allowing clairvoyant continuation.
    cards = current['players'][1-acting].get('hand') or []
    if any(card and card.get('id', 0) for card in cards):
        raise ValueError('opponent_hand_visible_to_continuation')
    for owner, player in enumerate(current['players']):
        allowed = visibility['visible'][owner]
        for card in player.get('prize') or []:
            if card is not None and (not isinstance(card, dict)
                    or card.get('serial') not in allowed
                    or card.get('id') != allowed[card['serial']]):
                raise ValueError('uncertified_prize_visible_to_continuation')


def continue_game(main, state, our_player, ours, opponent_fn, coin_rng, max_steps,
                  visibility):
    coin_count = 0
    for steps in range(max_steps + 1):
        observation = sanitize_continuation_observation(state.get('observation') or {}, visibility)
        current = observation.get('current')
        if not current:
            return {'score': None, 'terminal': False, 'steps': steps, 'error': 'missing_current'}
        result = int(current.get('result', -1))
        if result in (0, 1, 2):
            return {'score': .5 if result == 2 else float(result == our_player),
                    'terminal': True, 'steps': steps, 'result': result, 'coin_count': coin_count,
                    'prize_cards_masked': visibility['masked_cards'],
                    'sanitized_observations': visibility['observations']}
        if result != -1:
            raise ValueError(f'unknown_engine_result:{result}')
        if steps == max_steps:
            return {'score': None, 'terminal': False, 'steps': steps, 'coin_count': coin_count,
                    'cutoff_reason': 'max_steps'}
        privacy_check(observation, visibility)
        select = observation.get('select') or {}
        if select.get('context') == 46:  # official SelectContext.COIN_HEAD
            desired = 1 if coin_rng.getrandbits(1) else 2  # YES / NO
            picks = [next(i for i, option in enumerate(select.get('option') or [])
                          if option.get('type') == desired)]
            coin_count += 1
        else:
            policy = ours if current['yourIndex'] == our_player else opponent_fn
            picks = policy(observation)
        if picks is None:
            raise ValueError('policy_returned_none')
        picks = [int(x) for x in picks]
        state = main._step(state['searchId'], picks)
    raise AssertionError('unreachable')


def evaluate_position(task):
    entry, settings = task
    started = time.monotonic()
    output_dir = Path(settings['out'])
    stem = entry['position_id'].replace(':', '-')
    raw_path = output_dir / (stem + '.jsonl')
    metadata_path = output_dir / (stem + '.meta.json')
    metadata = dict(entry, settings=settings, status='started')
    from worlds import make_worlds, extract_decklists_from_replay, observations_for_player
    try:
        agent_root = Path(settings['agent_root'])
        os.chdir(agent_root)
        sys.path.insert(0, str(agent_root))
        spec = importlib.util.spec_from_file_location('experiment_main', agent_root / 'main.py')
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        if not main._SEARCH_OK:
            raise RuntimeError('official_search_unavailable')
        data = json.loads(Path(entry['replay_path']).read_text())
        player = entry['our_player']
        obs = data['steps'][entry['step']][player]['observation']
        history = observations_for_player(data, player, entry['step'])
        deck_record = extract_decklists_from_replay(data)
        decks = deck_record['decks']
        candidates = []
        actual_counter = Counter(decks[1-player])
        for _, members in main._GROUPS:
            for deck, path in members:
                overlap = sum((Counter(deck) & actual_counter).values())
                candidates.append((overlap, path, deck))
        if not candidates:
            raise RuntimeError('no_opponent_policy')
        overlap, opponent_path, _ = max(candidates, key=lambda x: (x[0], x[1]))
        if overlap < settings['min_deck_overlap']:
            raise ValueError(f'proxy_deck_overlap_below_threshold:{overlap}')
        previous_cwd = os.getcwd()
        os.chdir(Path(opponent_path).parent)
        try:
            opponent_fn = main._opp(opponent_path)
        finally:
            os.chdir(previous_cwd)
        if opponent_fn is None:
            raise RuntimeError('opponent_policy_import_failed')
        if opponent_fn.__closure__:
            raise RuntimeError('opponent_policy_has_unhandled_closure_state')
        ours = main._sim_mod.agent
        main._sim_mod._MY_DECK_60 = dict(Counter(decks[player]))
        for old_obs in history:
            if old_obs.get('current') and old_obs.get('select'):
                ours(old_obs)
        opponent_search_disabled = '_SEARCH_OK' in opponent_fn.__globals__
        if opponent_search_disabled:
            opponent_fn.__globals__['_SEARCH_OK'] = False
        ours_state = policy_state(ours, agent_root)
        opponent_state = policy_state(opponent_fn, agent_root)
        own_module = main._sim_mod
        diagnostics = {'own_tracking_errors': 0}

        def strict_ours(observation):
            # Preserve optional tracking behavior but do not silently convert a
            # decision-function exception into the first legal action.
            try:
                own_module._track_observation(observation)
            except Exception:
                diagnostics['own_tracking_errors'] += 1
            return own_module._agent(observation)
        # Histories are only used for our information. The proxy opponent starts
        # from fresh memory; no actual opponent private hand history is imported.
        worlds = make_worlds(obs, decks[player], decks[1-player], settings['worlds'],
                             seed_for(settings['seed'], entry['position_id']), history=history)
        if not worlds:
            raise ValueError('no_worlds')
        observation_class = main.to_observation_class(obs)
        n_actions = len(obs['select']['option'])
        metadata.update({'deck_assumption': deck_record['metadata'], 'opponent_policy': opponent_path,
                         'opponent_deck_overlap_cards': overlap, 'opponent_memory': 'fresh_at_root',
                         'opponent_search_disabled': opponent_search_disabled,
                         'own_decision_fallbacks_rejected': True,
                         'proxy_internal_fallbacks_fully_audited': False,
                         'own_history_observations': len(history), 'n_actions': n_actions,
                         'root_options': obs['select']['option'], 'worlds': worlds,
                         'score_kind': 'terminal_only', 'manual_coin': True,
                         'other_engine_randomness_seedable': False,
                         'continuation_prize_visibility': 'Search API prize fills redacted on every step for both observers; only original root face-up slots mapped to simulation serials remain visible',
                         'root_visible_prizes': sum(isinstance(c, dict) and bool(c.get('id')) for p in obs['current']['players'] for c in p.get('prize') or []),
                         'prize_visibility_limitations': 'New face-up Prize changes are not inferred from exposed Search API fills; root-certified cards are forgotten on leaving the Prize zone. Legitimate selection/looking fields and policy memory remain available.',
                         'public_observation_representation': 'unchanged official typed schema; Pokemon has no playerIndex field; no guessed ownership rewrite',
                         'continuation_state_reset': 'mutable/scalar globals and audited local AttackPlan instances/class data attributes, including reachable local submodules; aliases preserved within each namespace; immutable card tables excluded',
                         'continuation_state_reset_limitations': 'not a generic clone of arbitrary custom instances, function/closure state or external modules; audited registered proxies only',
                         'status': 'running'})
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False)+'\n')
        completed = terminal = errors = total_steps = 0
        raw = raw_path.open('w')
        for world_index, world in enumerate(worlds):
            fills = world['fills']
            for repeat in range(settings['repeats']):
                action_order = list(range(n_actions))
                random.Random(seed_for(settings['seed'], entry['position_id'], world_index, repeat, 'order')).shuffle(action_order)
                for action in action_order:
                    if time.monotonic()-started > settings['position_time_limit']:
                        raise TimeoutError('position_time_limit')
                    restore_policy(ours_state)
                    restore_policy(opponent_state)
                    diagnostics['own_tracking_errors'] = 0
                    random_seed = seed_for(settings['seed'], entry['position_id'], world_index, repeat, 'chance')
                    random.seed(random_seed)
                    row = {key: entry[key] for key in ('game_id', 'position_id', 'hidden_count', 'opponent', 'phase', 'band')}
                    row.update({'world_id': world['id'], 'action_id': action, 'repeat': repeat,
                                'score_kind': 'terminal', 'coin_seed': random_seed,
                                'policy_proxy': Path(opponent_path).parent.name,
                                'my_deck_count': obs['current']['players'][player]['deckCount'],
                                'my_prize_count': len(obs['current']['players'][player].get('prize') or []),
                                'turn': obs['current']['turn']})
                    tick = time.monotonic()
                    try:
                        root = main.search_begin(observation_class, *fills, manual_coin=True)
                        visibility = prize_visibility(obs, asdict(root.observation)
                                                      if root_has_visible_prizes(obs) else None)
                        state = main._step(root.searchId, [action])
                        result = continue_game(main, state, player, strict_ours, opponent_fn,
                                               random.Random(random_seed), settings['max_steps'], visibility)
                        row.update(result)
                    except Exception as exc:
                        row.update({'score': None, 'terminal': False, 'steps': 0,
                                    'error': type(exc).__name__+':'+str(exc)[:240]})
                    finally:
                        main.search_end()
                    row['elapsed_seconds'] = round(time.monotonic()-tick, 6)
                    row.update(diagnostics)
                    raw.write(json.dumps(row, ensure_ascii=False)+'\n')
                    completed += 1
                    terminal += int(row['terminal'])
                    errors += int(bool(row.get('error')))
                    total_steps += row.get('steps', 0)
                raw.flush()
        raw.close()
        metadata.update(status='complete', completed=completed, terminal=terminal, errors=errors,
                        total_steps=total_steps, wall_seconds=round(time.monotonic()-started, 3))
    except Exception as exc:
        metadata.update(status='failed', error=type(exc).__name__+':'+str(exc)[:500],
                        wall_seconds=round(time.monotonic()-started, 3))
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False)+'\n')
    return {k: metadata[k] for k in ('game_id', 'position_id', 'phase', 'band', 'status',
                                     'completed', 'terminal', 'errors', 'wall_seconds', 'error') if k in metadata}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--phase', choices=('pilot', 'confirmatory'), default='pilot')
    parser.add_argument('--per-band', type=int, default=3)
    parser.add_argument('--worlds', type=int, default=8)
    parser.add_argument('--repeats', type=int, default=8)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--max-steps', type=int, default=1200)
    parser.add_argument('--min-deck-overlap', type=int, default=45)
    parser.add_argument('--position-time-limit', type=float, default=600)
    parser.add_argument('--seed', type=int, default=2026091401)
    parser.add_argument('--agent-root', default='/private/tmp/x16j_withopp_1789064695')
    args = parser.parse_args()
    settings = vars(args)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    entries, counts = [], Counter()
    for line in Path(args.manifest).read_text().splitlines():
        entry = json.loads(line)
        if entry['phase'] == args.phase and counts[entry['band']] < args.per_band:
            entries.append(entry)
            counts[entry['band']] += 1
    config = dict(settings, selected_position_ids=[x['position_id'] for x in entries],
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  worlds_sha256=hashlib.sha256((Path(__file__).parent/'worlds.py').read_bytes()).hexdigest())
    (output/'run-config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'started': True, 'positions': len(entries), 'settings': settings}), flush=True)
    started = time.monotonic()
    with (output/'progress.jsonl').open('w') as log:
        with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as executor:
            futures = [executor.submit(evaluate_position, (entry, settings)) for entry in entries]
            for future in as_completed(futures):
                try:
                    summary = future.result()
                except Exception as exc:
                    summary = {'status': 'worker_failed', 'error': repr(exc)}
                log.write(json.dumps(summary, ensure_ascii=False)+'\n')
                log.flush()
                print(json.dumps(summary, ensure_ascii=False), flush=True)
    print(json.dumps({'finished': True, 'wall_seconds': round(time.monotonic()-started, 3)}), flush=True)


if __name__ == '__main__':
    main()
