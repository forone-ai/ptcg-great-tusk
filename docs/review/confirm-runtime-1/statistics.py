"""Read-only, standard-library analysis for the information experiment.

Python 3.11+. No simulation, network, or input mutation. Run --help or --self-test.
Primary inference gives equal weight to independent games and clusters by game.
Opponent summaries are descriptive. All conclusions are conditional on the
candidate actions and observation-limited continuation policy.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


def average(xs):
    values = list(xs)
    return sum(values) / len(values) if values else None


def sample_sd(xs):
    values = list(xs)
    if len(values) < 2:
        return None
    center = average(values)
    return math.sqrt(sum((x - center) ** 2 for x in values) / (len(values) - 1))


def quantile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return None
    index = probability * (len(ordered) - 1)
    left = int(index)
    return ordered[left] + (ordered[min(left + 1, len(ordered) - 1)] - ordered[left]) * (index - left)


def normal_quantile(probability):
    lo, hi = -10.0, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if 0.5 * math.erfc(-mid / math.sqrt(2)) < probability:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def bin_name(hidden_count):
    return 'low' if hidden_count < 15 else ('mid' if hidden_count < 35 else 'high')


def load_jsonl(path):
    with Path(path).open() as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'{path}:{line_number}: invalid JSON: {error}') from error
            if not isinstance(value, dict):
                raise ValueError(f'{path}:{line_number}: expected object')
            yield value


def numeric_score(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 1)


def power_plan():
    za, zb = normal_quantile(.975), normal_quantile(.8)
    counts = []
    for difference in (.10, .05):
        p0, p1 = .5, .5 + difference
        pooled = (p0 + p1) / 2
        n = (za * math.sqrt(2 * pooled * (1 - pooled))
             + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2 / difference ** 2
        counts.append({'baseline': p0, 'alternative': p1,
                       'games_per_arm_normal_approximation': math.ceil(n),
                       'worst_variance_approximation': math.ceil(2 * .25 * (za + zb) ** 2 / difference ** 2)})
    ze = normal_quantile(.95)
    equivalence = [{'sd_of_game_mean_difference': sd,
                    'independent_games_if_true_gap_zero': math.ceil(((ze + zb) * sd / .05) ** 2),
                    'one_sided_95_margin_at_100_games': ze * sd / math.sqrt(100)}
                   for sd in (.05, .10, .15, .20, .30, .50)]
    return {'win_rate_difference': counts, 'alpha_two_sided': .05, 'power': .8,
            'one_sided_information_gap_margin': .05,
            'paired_difference_planning_examples': equivalence,
            'warning': 'Approximate planning, not a guarantee. Units are independent game clusters, not worlds/actions/repeats. Use blinded pilot SD and measured runtime to freeze N before confirmatory analysis.'}


def prepare_positions(records, phase='confirmatory'):
    buckets, diagnostics = {}, Counter()
    for row in records:
        diagnostics['input_rows'] += 1
        if phase != 'all' and row.get('phase', 'confirmatory') != phase:
            diagnostics['other_phase_rows'] += 1
            continue
        if 'phase' not in row:
            diagnostics['missing_phase_rows'] += 1
        try:
            game = str(row['game_id'])
            position = str(row['position_id'])
            hidden = int(row['hidden_count'])
            world = str(row['world_id'])
            action = str(row['action_id'])
            repeat = int(row['repeat'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f'Invalid position row identifiers: {error}') from error
        if hidden < 0 or repeat < 0:
            raise ValueError('hidden_count and repeat must be nonnegative')
        arm = str(row.get('arm', 'reference'))
        opponent = str(row.get('opponent', 'unknown'))
        policy_proxy = str(row.get('policy_proxy', row.get('proxy_opponent', 'unspecified')))
        key = (arm, game, position)
        bucket = buckets.setdefault(key, {'game_id': game, 'position_id': position,
                    'arm': arm, 'opponent': opponent, 'policy_proxy': policy_proxy, 'hidden_count': hidden,
                    'bin': bin_name(hidden), 'cells': {}, 'problems': set(),
                    'score_kinds': Counter(), 'error_count': 0, 'cutoff_count': 0})
        if (bucket['opponent'], bucket['policy_proxy'], bucket['hidden_count']) != (opponent, policy_proxy, hidden):
            bucket['problems'].add('position_metadata_changed_between_rows')
        score = row.get('score')
        terminal = row.get('terminal') is True
        error = bool(row.get('error'))
        # A numeric heuristic cutoff is deliberately excluded from terminal scoring.
        observed = float(score) if terminal and not error and numeric_score(score) else None
        if terminal and not error and not numeric_score(score):
            bucket['problems'].add('terminal_row_without_valid_score')
        bucket['score_kinds'][str(row.get('score_kind', 'unspecified'))] += 1
        bucket['error_count'] += int(error)
        bucket['cutoff_count'] += int(not terminal and not error)
        cell_key = (world, action, repeat)
        cell = (observed, terminal, error)
        if cell_key in bucket['cells']:
            diagnostics['duplicate_cells'] += 1
            if bucket['cells'][cell_key] != cell:
                bucket['problems'].add('conflicting_duplicate_cell')
        else:
            bucket['cells'][cell_key] = cell
    results = [crossfit_position(bucket) for bucket in buckets.values()]
    diagnostics['positions'] = len(results)
    diagnostics['valid_positions'] = sum(r['status'] == 'ok' for r in results)
    diagnostics['invalid_positions'] = len(results) - diagnostics['valid_positions']
    return results, dict(diagnostics)


def crossfit_position(bucket):
    cells = bucket['cells']
    worlds = sorted({w for w, _, _ in cells})
    actions = sorted({a for _, a, _ in cells})
    repeats = sorted({r for _, _, r in cells})
    problems = set(bucket['problems'])
    output = {key: bucket[key] for key in ('game_id', 'position_id', 'arm', 'opponent', 'policy_proxy', 'hidden_count', 'bin')}
    output.update(world_count=len(worlds), action_count=len(actions), repeat_count=len(repeats),
                  error_rows=bucket['error_count'], cutoff_rows=bucket['cutoff_count'],
                  score_kinds=dict(bucket['score_kinds']))
    if len(worlds) < 4:
        problems.add('fewer_than_four_worlds')
    if len(actions) < 2:
        problems.add('fewer_than_two_actions_not_a_decision_test')
    if len(repeats) < 4 or len(repeats) % 2:
        problems.add('need_an_even_number_of_at_least_four_repeats')
    if len(cells) != len(worlds) * len(actions) * len(repeats):
        problems.add('incomplete_world_action_repeat_rectangle')
    if problems:
        return dict(output, status='invalid', reasons=sorted(problems))
    # Fixed fold assignment by sorted identifiers; no outcome-dependent split.
    world_folds = [worlds[::2], worlds[1::2]]
    repeat_folds = [repeats[::2], repeats[1::2]]

    def selection_value(world_set, action, repeat_set):
        # Predeclared conservative selection rule: unresolved training cells get 0.
        # This is a policy definition, not an imputation used for reporting scores.
        return average((cells[w, action, r][0] if cells[w, action, r][0] is not None else 0.0)
                       for w in world_set for r in repeat_set)

    def choose(world_set, repeat_set):
        values = {a: selection_value(world_set, a, repeat_set) for a in actions}
        best_value = max(values.values())
        ties = {a for a, v in values.items() if abs(v - best_value) <= 1e-12}
        # Stable, world-independent tie break on semantic action IDs.
        return min(ties), ties, values

    points, lower, upper = [], [], []
    evaluated_pairs = same_action = terminal_pairs = 0
    public_choices, revealed_choices = Counter(), Counter()
    for wf in (0, 1):
        evaluation_worlds, training_worlds = world_folds[wf], world_folds[1 - wf]
        for rf in (0, 1):
            training_repeats, evaluation_repeats = repeat_folds[rf], repeat_folds[1 - rf]
            public_action, _, _ = choose(training_worlds, training_repeats)
            public_choices[public_action] += 1
            for world in evaluation_worlds:
                revealed_action, _, _ = choose([world], training_repeats)
                revealed_choices[revealed_action] += 1
                for repeat in evaluation_repeats:
                    evaluated_pairs += 1
                    left = cells[world, revealed_action, repeat][0]
                    right = cells[world, public_action, repeat][0]
                    terminal_pairs += int(left is not None and right is not None)
                    if revealed_action == public_action:
                        # Identical action/continuation has zero contrast even if unresolved.
                        same_action += 1
                        points.append(0.0); lower.append(0.0); upper.append(0.0)
                    elif left is not None and right is not None:
                        delta = left - right
                        points.append(delta); lower.append(delta); upper.append(delta)
                    else:
                        lower.append((left if left is not None else 0.0) - (right if right is not None else 1.0))
                        upper.append((left if left is not None else 1.0) - (right if right is not None else 0.0))
    exact_agreement, tie_overlap, tied, cross_optimal, tie_jaccard = [], [], [], [], []
    for world in worlds:
        a0, t0, _ = choose([world], repeat_folds[0])
        a1, t1, _ = choose([world], repeat_folds[1])
        exact_agreement.append(int(a0 == a1))
        tie_overlap.append(int(bool(t0 & t1)))
        cross_optimal.append((int(a0 in t1) + int(a1 in t0)) / 2)
        tie_jaccard.append(len(t0 & t1) / len(t0 | t1))
        tied.extend([int(len(t0) > 1), int(len(t1) > 1)])
    return dict(output, status='ok',
                delta_identified_pairs=average(points),
                delta_all_pairs_lower=average(lower), delta_all_pairs_upper=average(upper),
                n_evaluation_pairs=evaluated_pairs, n_identified_pairs=len(points),
                identified_pair_fraction=len(points)/evaluated_pairs,
                terminal_pair_fraction=terminal_pairs/evaluated_pairs,
                terminal_cell_fraction=sum(v[0] is not None for v in cells.values())/len(cells),
                public_revealed_same_action_fraction=same_action/evaluated_pairs,
                revealed_split_exact_action_agreement=average(exact_agreement),
                revealed_split_best_set_overlap=average(tie_overlap),
                revealed_split_cross_optimal_agreement=average(cross_optimal),
                revealed_split_best_set_jaccard=average(tie_jaccard),
                revealed_training_tie_fraction=average(tied),
                public_action_selection_counts=dict(public_choices),
                revealed_action_selection_counts=dict(revealed_choices))


FIELDS = ('delta_identified_pairs', 'delta_all_pairs_lower', 'delta_all_pairs_upper',
          'identified_pair_fraction', 'terminal_pair_fraction', 'terminal_cell_fraction',
          'public_revealed_same_action_fraction', 'revealed_split_exact_action_agreement',
          'revealed_split_best_set_overlap', 'revealed_split_cross_optimal_agreement',
          'revealed_split_best_set_jaccard', 'revealed_training_tie_fraction')


def game_clusters(position_results):
    grouped = defaultdict(list)
    for row in position_results:
        if row['status'] == 'ok':
            grouped[(row['arm'], row['game_id'], row['bin'])].append(row)
    clusters = []
    for (arm, game, bin_), rows in grouped.items():
        opponents = {r['opponent'] for r in rows}
        proxies = {r['policy_proxy'] for r in rows}
        if len(opponents) != 1:
            raise ValueError(f'Opponent changed within game/bin: {arm}, {game}, {bin_}')
        record = dict(arm=arm, opponent=next(iter(opponents)),
                      policy_proxy=next(iter(proxies)) if len(proxies) == 1 else 'mixed',
                      game_id=game, bin=bin_, positions=len(rows))
        record.update({f: average(r[f] for r in rows if r[f] is not None) for f in FIELDS})
        clusters.append(record)
    return clusters


def standardized_mean(strata, field):
    values = []
    for rows in strata.values():
        value = average(r[field] for r in rows if r[field] is not None)
        if value is None:
            return None
        values.append(value)
    return average(values)


def summarize_clusters(clusters, bootstrap=4000, seed=20260914):
    if not clusters:
        return None
    # Actual team names can number in the hundreds. Do NOT weight singleton teams
    # equally or bootstrap within singleton team strata in the primary analysis.
    strata = {'all_sampled_games': clusters}
    opponents, proxies = defaultdict(list), defaultdict(list)
    for row in clusters:
        opponents[row['opponent']].append(row)
        proxies[row['policy_proxy']].append(row)
    estimates = {field: standardized_mean(strata, field) for field in FIELDS}
    randomizer = random.Random(seed)
    boot = {field: [] for field in ('delta_identified_pairs', 'delta_all_pairs_lower', 'delta_all_pairs_upper')}
    can_infer = len(clusters) >= 20
    if can_infer:
        for _ in range(bootstrap):
            sampled = {name: randomizer.choices(rows, k=len(rows)) for name, rows in sorted(strata.items())}
            for field in boot:
                value = standardized_mean(sampled, field)
                if value is not None:
                    boot[field].append(value)
    intervals = {field: {'two_sided_95': [quantile(values, .025), quantile(values, .975)],
                          'one_sided_95_upper': quantile(values, .95),
                          'one_sided_95_lower': quantile(values, .05),
                          'bootstrap_replicates': len(values)}
                 for field, values in boot.items()}
    return dict(independent_games=len({r['game_id'] for r in clusters}),
                game_bin_clusters=len(clusters), positions=sum(r['positions'] for r in clusters),
                opponent_games={name: len(rows) for name, rows in sorted(opponents.items())},
                opponent_descriptive={name: {'games': len(rows), 'delta': average(r['delta_identified_pairs'] for r in rows if r['delta_identified_pairs'] is not None)} for name, rows in sorted(opponents.items())},
                policy_proxy_descriptive={name: {'games': len(rows), 'delta': average(r['delta_identified_pairs'] for r in rows if r['delta_identified_pairs'] is not None)} for name, rows in sorted(proxies.items())},
                standardization='equal sampled independent games; equal positions within game/bin; no equal-team reweighting',
                estimates=estimates, intervals=intervals,
                exploratory_sd_of_game_differences=sample_sd(r['delta_identified_pairs'] for r in clusters if r['delta_identified_pairs'] is not None),
                inference_available=can_infer,
                inference_warning=None if can_infer else 'Require >=20 independent game/bin clusters. This is a minimum diagnostic threshold, not a guarantee of sufficient power.')


def high_low_contrast(clusters, bootstrap=4000, seed=20260915):
    games = {}
    for row in clusters:
        if row['bin'] in ('low', 'high'):
            games.setdefault(row['game_id'], {})[row['bin']] = row
    original = list(games.values())

    def unpaired_estimate(sampled):
        values = {b: average(g[b]['delta_identified_pairs'] for g in sampled if b in g and g[b]['delta_identified_pairs'] is not None)
                  for b in ('low', 'high')}
        return None if None in values.values() else values['high'] - values['low']

    paired = [g['high']['delta_identified_pairs'] - g['low']['delta_identified_pairs']
              for g in original if 'high' in g and 'low' in g
              and g['high']['delta_identified_pairs'] is not None
              and g['low']['delta_identified_pairs'] is not None]
    rng, unpaired_values, paired_values = random.Random(seed), [], []
    if len(original) >= 20:
        for _ in range(bootstrap):
            # Carry all bins from a sampled game together even in the full-sample
            # contrast, preserving any overlap in game IDs across the bins.
            value = unpaired_estimate(rng.choices(original, k=len(original)))
            if value is not None:
                unpaired_values.append(value)
    if len(paired) >= 20:
        for _ in range(bootstrap):
            paired_values.append(average(rng.choices(paired, k=len(paired))))
    return {'status': 'exploratory_secondary',
            'paired_same_game_subset': {'games': len(paired), 'high_minus_low': average(paired),
                'two_sided_95': [quantile(paired_values, .025), quantile(paired_values, .975)],
                'bootstrap_replicates': len(paired_values)},
            'unpaired_full_sample': {'unique_games': len(original), 'high_minus_low': unpaired_estimate(original),
                'two_sided_95': [quantile(unpaired_values, .025), quantile(unpaired_values, .975)],
                'bootstrap_replicates': len(unpaired_values)},
            'warning': 'Both contrasts are associations, not a causal effect of hidden-card count. The paired subset selects games observed in both bins; the full sample has different game composition in each bin.'}


def analyze_positions(records, phase='confirmatory', bootstrap=4000, seed=20260914,
                      margin=.05, min_reference_stability=.80):
    positions, diagnostics = prepare_positions(records, phase)
    clusters = game_clusters(positions)
    by_arm, primary = {}, {}
    for arm in sorted({r['arm'] for r in positions}):
        rows = [r for r in clusters if r['arm'] == arm]
        by_arm[arm] = {b: summarize_clusters([r for r in rows if r['bin'] == b], bootstrap, seed) for b in ('low', 'mid', 'high')}
        by_arm[arm]['high_minus_low'] = high_low_contrast(rows, bootstrap, seed + 1)
        low = by_arm[arm]['low']
        upper = low['intervals']['delta_all_pairs_upper']['one_sided_95_upper'] if low else None
        point_upper = low['intervals']['delta_identified_pairs']['one_sided_95_upper'] if low else None
        complete_rectangles = all(r['status'] == 'ok' for r in positions if r['arm'] == arm and r['bin'] == 'low')
        stability = low['estimates']['revealed_split_cross_optimal_agreement'] if low else None
        stability_passed = stability >= min_reference_stability if stability is not None else None
        margin_met = (upper < margin) if upper is not None else None
        primary[arm] = {'margin': margin, 'low_definition': 'hidden_count < 15',
                        'one_sided_95_upper_including_worst_case_unresolved': upper,
                        'one_sided_95_upper_identified_pairs_only': point_upper,
                        'statistical_margin_criterion_met': margin_met,
                        'all_selected_low_positions_analysable': complete_rectangles,
                        'reference_quality_screen': {
                            'metric': 'game-weighted split-half selected-action membership in the other half\'s tied-best set, averaged over both directions',
                            'value': stability, 'predeclared_minimum': min_reference_stability,
                            'screen_passed': stability_passed,
                            'information_value_claim_unconfirmed_due_to_low_stability': not stability_passed if stability_passed is not None else None,
                            'warning': 'The 0.80 default is a predeclared diagnostic screen, not a calibrated guarantee of oracle quality. Broad ties can inflate agreement; inspect tied-best-set overlap, Jaccard, tie fraction and terminal completion. Passing does not prove true-oracle equivalence.'},
                        'margin_and_stability_screen_met': bool(margin_met and stability_passed and complete_rectangles),
                        'coverage_warning': 'Coverage here includes only positions appearing in the input. Compare against the frozen manifest, including generation failures and unstarted positions, before any conclusion.',
                        'interpretation': 'Criterion concerns this finite-reference procedure only. It is NOT an upper bound on true perfect-information value; oracle misselection, missing positions, wrong worlds, or a weak continuation can create small gaps.',
                        'requires_quality_review': True}
    return {'diagnostics': diagnostics, 'primary': primary, 'by_arm_and_bin': by_arm,
            'position_results': positions,
            'warnings': ['No bin prevalence is inferred from quota-sampled positions.',
                         'Public root choice excludes the evaluation world; both choices exclude evaluation repeats.',
                         'Negative cross-fitted differences are retained, not clipped to zero.',
                         'Unresolved training outcomes select conservatively as zero; outcome reporting instead uses [0,1] bounds.',
                         'Primary percentile bootstrap assumes sampled games are independent and gives them equal weight. Worlds, actions, and repeats are not independent sample units. Actual opponent teams are descriptive only.',
                         'Other arms and high-minus-low are exploratory unless separately preregistered.']}


def analyze_wholegames(records, phase='confirmatory', bootstrap=4000, seed=20260916):
    arms, seen, diagnostics = defaultdict(list), {}, Counter()
    for row in records:
        diagnostics['input_rows'] += 1
        if phase != 'all' and row.get('phase', 'confirmatory') != phase:
            diagnostics['other_phase_rows'] += 1
            continue
        arm, game = str(row['arm']), str(row['game_id'])
        key = (arm, game)
        if key in seen:
            if seen[key] != row:
                raise ValueError(f'Conflicting whole-game duplicate: {key}')
            diagnostics['duplicate_rows'] += 1
            continue
        seen[key] = row
        result = str(row.get('result', '')).lower()
        terminal_result = {'win': 1., 'loss': 0., 'draw': .5, 'w': 1., 'l': 0., 'd': .5}.get(result)
        supplied_score = row.get('score')
        if terminal_result is not None and supplied_score is not None and supplied_score != terminal_result:
            raise ValueError(f'Whole-game score/result conflict: {key}')
        value = terminal_result
        if value is None and row.get('terminal') is True and numeric_score(supplied_score):
            value = float(supplied_score)
        if row.get('error'):
            value = None
        reach = row.get('reach', {})
        if isinstance(reach, bool):
            reach = {'reach': reach}
        if not isinstance(reach, dict):
            reach = {}
        arms[arm].append(dict(game_id=game, opponent=str(row.get('opponent', 'unknown')),
                             score=value, our_first=row.get('our_first'), our_seat=row.get('our_seat'),
                             result=result, reach={str(k): v for k, v in reach.items() if isinstance(v, bool)}))
    output = {}
    for arm, rows in arms.items():
        completed = [r for r in rows if r['score'] is not None]
        reaches = sorted({k for r in rows for k in r['reach']})
        output[arm] = {'started_games': len(rows), 'completed_games': len(completed),
                       'unresolved_games': len(rows)-len(completed),
                       'wins': sum(r['score'] == 1 for r in completed),
                       'draws': sum(r['score'] == .5 for r in completed),
                       'losses': sum(r['score'] == 0 for r in completed),
                       'score_rate_completed': average(r['score'] for r in completed),
                       'win_rate_completed': average(float(r['score'] == 1) for r in completed),
                       'score_rate_all_started_lower': sum(r['score'] or 0 for r in rows)/len(rows),
                       'score_rate_all_started_upper': sum(r['score'] if r['score'] is not None else 1 for r in rows)/len(rows),
                       'opponent_games': dict(Counter(r['opponent'] for r in rows)),
                       'actual_first': dict(Counter(str(r['our_first']) for r in rows)),
                       'seat': dict(Counter(str(r['our_seat']) for r in rows)),
                       'reach_all_started': {k: {'observed_true': sum(r['reach'].get(k) is True for r in rows),
                                                'observed_false': sum(r['reach'].get(k) is False for r in rows),
                                                'missing': sum(k not in r['reach'] for r in rows),
                                                'rate_lower': sum(r['reach'].get(k) is True for r in rows)/len(rows),
                                                'rate_upper': sum(r['reach'].get(k) is not False for r in rows)/len(rows)} for k in reaches}}
    contrasts = []
    arm_names = sorted(arms)
    for ia, a in enumerate(arm_names):
        for b in arm_names[ia+1:]:
            common = {r['opponent'] for r in arms[a]} & {r['opponent'] for r in arms[b]}
            strata = {(arm, opp): [r for r in arms[arm] if r['opponent'] == opp]
                      for arm in (a, b) for opp in sorted(common)}
            def estimate(sampled, mode):
                values = {}
                for arm in (a, b):
                    ms = []
                    for opp in sorted(common):
                        rows = sampled[arm, opp]
                        if mode == 'observed':
                            x = average(r['score'] for r in rows if r['score'] is not None)
                        else:
                            # Lower/upper refer to the contrast b-a, not each arm.
                            replacement = (0 if arm == b else 1) if mode == 'lower' else (1 if arm == b else 0)
                            x = average(r['score'] if r['score'] is not None else replacement for r in rows)
                        if x is None:
                            return None
                        ms.append(x)
                    values[arm] = average(ms)
                return values[b]-values[a] if common else None
            rng, draws = random.Random(seed), []
            if common and all(len(rows) >= 2 for rows in strata.values()):
                for _ in range(bootstrap):
                    sampled = {key: rng.choices(rows, k=len(rows)) for key, rows in sorted(strata.items())}
                    value = estimate(sampled, 'observed')
                    if value is not None:
                        draws.append(value)
            contrasts.append({'contrast': f'{b} minus {a}', 'common_fixed_opponents': sorted(common),
                              'score_difference_standardized': estimate(strata, 'observed'),
                              'unresolved_difference_bounds': [estimate(strata, 'lower'), estimate(strata, 'upper')],
                              'exploratory_two_sided_95': [quantile(draws,.025),quantile(draws,.975)],
                              'bootstrap_replicates': len(draws)})
    return {'diagnostics': dict(diagnostics), 'arms': output, 'contrasts': contrasts,
            'status': 'exploratory_secondary_unpaired_comparison',
            'warning': 'No requirement that whole-game win-rate differences be significant. Reach denominators include every started game; missing reaches are bounded, never silently removed. Opponents are fixed strata.'}


def self_test():
    # Deliberately synthetic fixtures; these never enter any experimental report.
    base = {'game_id':'synthetic-g1', 'position_id':'synthetic-p1', 'opponent':'synthetic-op',
            'hidden_count':10, 'phase':'confirmatory','terminal':True,'score_kind':'terminal'}
    rows = [dict(base, world_id=f'w{w}', action_id=a, repeat=r, score=float(a=='a'))
            for w in range(4) for a in ('a','b') for r in range(4)]
    result, _ = prepare_positions(rows)
    assert result[0]['delta_all_pairs_upper'] == 0
    # Worlds w0,w1 prefer a; w2,w3 prefer b. Every training fold contains one each.
    varied = [dict(row, score=float((row['action_id']=='a') == (int(row['world_id'][1:])<2))) for row in rows]
    result, _ = prepare_positions(varied)
    assert abs(result[0]['delta_identified_pairs']-.5)<1e-12
    assert result[0]['terminal_pair_fraction'] == 1
    unresolved = [dict(row, terminal=False, score=None) if row['world_id']=='w0' else row for row in varied]
    result, _ = prepare_positions(unresolved)
    assert result[0]['delta_all_pairs_lower'] <= result[0]['delta_all_pairs_upper']
    bad, _ = prepare_positions(rows[:-1])
    assert bad[0]['status'] == 'invalid'
    # Many singleton actual opponents must still have nonzero game-level uncertainty.
    many = [dict(row, game_id=f'synthetic-g{g}', position_id=f'synthetic-p{g}',
                 opponent=f'singleton-team-{g}', policy_proxy=f'proxy-{g%2}')
            for g in range(40) for row in (varied if g % 2 else rows)]
    analyzed = analyze_positions(many, bootstrap=100)
    low = analyzed['by_arm_and_bin']['reference']['low']
    assert low['independent_games'] == 40 and low['inference_available']
    assert low['intervals']['delta_identified_pairs']['two_sided_95'][0] < .25
    assert low['intervals']['delta_identified_pairs']['two_sided_95'][1] > .25
    assert low['estimates']['delta_identified_pairs'] == .25
    assert analyzed['primary']['reference']['reference_quality_screen']['screen_passed']
    # All worlds prefer different actions across repeat halves: ties do not hide instability.
    unstable = [dict(row, score=float((row['action_id']=='a') == (row['repeat'] % 2 == 0))) for row in rows]
    unstable_analysis = analyze_positions(unstable, bootstrap=100)
    assert unstable_analysis['primary']['reference']['reference_quality_screen']['information_value_claim_unconfirmed_due_to_low_stability']
    # The same 40 games have both bins; paired contrast is distinct from the full sample.
    doubled = many + [dict(row, hidden_count=40, position_id=row['position_id']+'-high') for row in many]
    paired_analysis = analyze_positions(doubled, bootstrap=100)
    contrast = paired_analysis['by_arm_and_bin']['reference']['high_minus_low']
    assert contrast['paired_same_game_subset']['games'] == 40
    assert contrast['paired_same_game_subset']['high_minus_low'] == 0
    assert contrast['unpaired_full_sample']['unique_games'] == 40
    games = [{'game_id':f'{arm}-{i}', 'arm':arm,'opponent':'synthetic-op',
              'result':'draw' if i else 'win','score':.5 if i else 1.,'reach':{'checkpoint_low':i==0}}
             for arm in ('off','on') for i in range(2)]
    whole = analyze_wholegames(games, bootstrap=50)
    assert whole['arms']['on']['score_rate_completed'] == .75
    assert whole['arms']['on']['win_rate_completed'] == .5
    print('Synthetic self-tests passed; no real experimental outcomes were generated.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--positions', type=Path)
    parser.add_argument('--wholegames', type=Path)
    parser.add_argument('--phase', default='confirmatory')
    parser.add_argument('--bootstrap', type=int, default=4000)
    parser.add_argument('--seed', type=int, default=20260914)
    parser.add_argument('--margin', type=float, default=.05)
    parser.add_argument('--min-reference-stability', type=float, default=.80,
                        help='Predeclared diagnostic threshold; do not tune after results.')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.bootstrap < 100 or not (0 < args.margin < 1) or not (0 <= args.min_reference_stability <= 1):
        parser.error('bootstrap must be >=100, margin in (0,1), and stability threshold in [0,1]')
    result = {'analysis_version':'1.1', 'protocol':'protocol.md', 'phase':args.phase,
              'bootstrap_seed':args.seed, 'bootstrap_replicates':args.bootstrap,
              'power_planning':power_plan(), 'inputs':{}}
    for name in ('positions', 'wholegames'):
        path = getattr(args, name)
        if path:
            digest = hashlib.sha256()
            with path.open('rb') as source:
                for chunk in iter(lambda:source.read(1024*1024),b''):
                    digest.update(chunk)
            result['inputs'][name] = {'path':str(path.resolve()),'sha256':digest.hexdigest()}
    if args.positions:
        result['positions'] = analyze_positions(load_jsonl(args.positions), args.phase, args.bootstrap,
                                               args.seed, args.margin, args.min_reference_stability)
    if args.wholegames:
        result['wholegames'] = analyze_wholegames(load_jsonl(args.wholegames), args.phase, args.bootstrap, args.seed+2)
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(content+'\n')
    else:
        print(content)


if __name__ == '__main__':
    main()
