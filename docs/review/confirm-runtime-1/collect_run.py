"""Audit frozen run coverage and collect only position cell files."""
import argparse
import json
from collections import Counter
from pathlib import Path


def completion_problems(metadata, config, rows):
    """Require the planned rectangle, not merely a rectangle in partial data."""
    problems = []
    if metadata.get('status') != 'complete':
        problems.append('metadata_not_complete')
    worlds = metadata.get('worlds') or []
    world_ids = [str(w.get('id', w.get('world_id'))) for w in worlds if isinstance(w, dict)]
    actions, repeats = metadata.get('n_actions'), config.get('repeats')
    if (not world_ids or len(world_ids) != len(worlds)
            or len(set(world_ids)) != len(world_ids)
            or 'None' in world_ids or not isinstance(actions, int) or actions < 1
            or not isinstance(repeats, int) or repeats < 1):
        return problems + ['missing_or_invalid_planned_dimensions']
    planned = {(w, str(a), r) for w in world_ids for a in range(actions) for r in range(repeats)}
    actual = []
    try:
        actual = [(str(row['world_id']), str(row['action_id']), int(row['repeat'])) for row in rows]
    except (KeyError, TypeError, ValueError):
        problems.append('invalid_cell_identifiers')
    if len(actual) != len(set(actual)):
        problems.append('duplicate_cells')
    if set(actual) != planned or len(rows) != len(planned):
        problems.append('incomplete_or_unexpected_planned_rectangle')
    if metadata.get('completed') != len(rows):
        problems.append('metadata_completed_count_mismatch')
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    config = json.loads((args.run / 'run-config.json').read_text())
    expected = config['selected_position_ids']
    assert len(expected) == len(set(expected))
    counts, details, durations = Counter(), [], []
    with ((args.run / 'cells.jsonl').open('w') as target,
          (args.run / 'partial-cells.jsonl').open('w') as partial,
          (args.run / 'corrupt-lines.jsonl').open('w') as corrupt):
        for position in expected:
            stem = position.replace(':', '-')
            meta_path = args.run / (stem + '.meta.json')
            raw_path = args.run / (stem + '.jsonl')
            problems = []
            try:
                meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
                if not isinstance(meta, dict):
                    raise ValueError('metadata_not_object')
            except (ValueError, OSError) as exc:
                meta = {'status': 'metadata_invalid', 'error': str(exc)}
                problems.append('unreadable_or_invalid_metadata')
            status = meta.get('status', 'unstarted')
            counts[status] += 1
            rows, valid_lines = [], []
            if raw_path.exists():
                for number, raw_line in enumerate(raw_path.read_bytes().splitlines(), 1):
                    try:
                        line = raw_line.decode('utf-8')
                        row = json.loads(line)
                        if not isinstance(row, dict):
                            raise ValueError('cell_not_object')
                    except ValueError as exc:
                        counts['corrupt_raw_lines'] += 1
                        problems.append('corrupt_raw_line')
                        corrupt.write(json.dumps({'position_id': position, 'line': number,
                                                  'raw': raw_line.decode('utf-8', errors='replace'),
                                                  'error': str(exc)}) + '\n')
                        continue
                    if row.get('position_id') != position:
                        problems.append('position_id_mismatch')
                    rows.append(row)
                    valid_lines.append(line)
                    counts['terminal_rows'] += int(row.get('terminal') is True)
                    counts['error_rows'] += int(bool(row.get('error')))
                    counts['tracking_errors'] += row.get('own_tracking_errors', 0)
                    counts['prize_cards_masked'] += row.get('prize_cards_masked', 0)
                    counts['sanitized_observations'] += row.get('sanitized_observations', 0)
                    counts['cutoff_rows'] += int(not row.get('terminal') and not row.get('error'))
            problems += completion_problems(meta, config, rows)
            included = not problems
            destination = target if included else partial
            for line in valid_lines:
                destination.write(line + '\n')
            counts['analysis_included_positions' if included else 'analysis_excluded_positions'] += 1
            counts['analysis_cell_rows' if included else 'partial_cell_rows'] += len(rows)
            counts['cell_rows'] += len(rows)
            if 'wall_seconds' in meta:
                durations.append(meta['wall_seconds'])
            details.append({'position_id': position, 'status': status, 'rows': len(rows),
                            'analysis_included': included, 'exclusion_reasons': sorted(set(problems)),
                            'error': meta.get('error')})
    summary = {'selected_positions': len(expected), 'counts': dict(counts),
               'position_seconds_sum': sum(durations),
               'position_seconds_mean': sum(durations) / len(durations) if durations else None,
               'position_seconds_max': max(durations) if durations else None,
               'coverage_complete': counts['analysis_included_positions'] == len(expected),
               'cells_policy': 'cells.jsonl contains only metadata-complete planned rectangles; parseable partial rows are in partial-cells.jsonl; malformed raw lines are preserved in corrupt-lines.jsonl; all original files are untouched',
               'details': details}
    (args.run / 'coverage.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'details'}))


if __name__ == '__main__':
    main()
