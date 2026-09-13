#!/usr/bin/env python3
"""Poll our own Kaggle submissions' current score and episode count, and
append one row per submission to a growing CSV log.

Run this repeatedly (e.g. every 15-30 minutes) after a fresh submission to
build an empirical (games_played, score) curve for that submission, since
Kaggle's API does not expose the internal skill-rating (mu/sigma) history
directly -- only the current best-scoring snapshot per submission and the
list of completed episodes per submission.

Usage:
    python3 analysis/scripts/track_submission_convergence.py
    python3 analysis/scripts/track_submission_convergence.py --top 2
    python3 analysis/scripts/track_submission_convergence.py --competition pokemon-tcg-ai-battle
"""

import argparse
import csv
import io
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_PATH = REPO_ROOT / "logs" / "own_submission_convergence.csv"
FIELDNAMES = [
    "polled_at_utc",
    "submission_id",
    "submission_date",
    "description",
    "public_score",
    "episode_count",
]


def run_kaggle_csv(args, retries=3, retry_delay=15):
    last_exc = None
    for attempt in range(retries):
        try:
            result = subprocess.run(
                ["kaggle", *args, "--csv"],
                capture_output=True,
                text=True,
                check=True,
            )
            return list(csv.DictReader(io.StringIO(result.stdout)))
        except subprocess.CalledProcessError as exc:
            last_exc = exc
            print(f"warning: 'kaggle {' '.join(args)}' failed "
                  f"(attempt {attempt + 1}/{retries}): {exc.stderr.strip()[:200]}",
                  file=sys.stderr, flush=True)
            if attempt < retries - 1:
                time.sleep(retry_delay)
    raise last_exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--competition", default="pokemon-tcg-ai-battle",
        help="Simulation competition slug (default: pokemon-tcg-ai-battle)",
    )
    parser.add_argument(
        "--top", type=int, default=2,
        help="How many of the most recent submissions to poll (default: 2, "
             "matching the 'latest 2 are active' rule). Use 0 for all.",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Keep polling in a loop instead of exiting after one pass.",
    )
    parser.add_argument(
        "--interval", type=int, default=240,
        help="Seconds between polls in --watch mode (default: 240, i.e. "
             "matched to the ~4min/episode pace observed for a fresh, "
             "high-priority submission). Set this close to the actual "
             "episode cadence so each poll ideally captures ~1 new game.",
    )
    parser.add_argument(
        "--duration", type=int, default=0,
        help="Total seconds to keep watching (0 = forever, only meaningful "
             "with --watch). Ctrl-C or process kill also stops it.",
    )
    parser.add_argument(
        "--follow-newest", action="store_true",
        help="First wait until a submission newer than today's latest "
             "appears, then densely track ONLY that new submission from "
             "its very first episode onward (--top is ignored once "
             "tracking starts; only the new submission is followed).",
    )
    parser.add_argument(
        "--wait-interval", type=int, default=90,
        help="Seconds between checks while waiting for a new submission "
             "in --follow-newest mode (default: 90). Coarser than "
             "--interval since nothing to catch yet.",
    )
    args = parser.parse_args()

    only_submission_id = None
    if args.follow_newest:
        submissions = run_kaggle_csv(["competitions", "submissions", "-c", args.competition])
        baseline_id = submissions[0]["ref"] if submissions else None
        print(f"Waiting for a submission newer than {baseline_id} "
              f"(checking every {args.wait_interval}s)...", flush=True)
        while True:
            time.sleep(args.wait_interval)
            try:
                submissions = run_kaggle_csv(["competitions", "submissions", "-c", args.competition])
            except subprocess.CalledProcessError as exc:
                print(f"warning: submissions check failed, will retry next tick: {exc}",
                      file=sys.stderr, flush=True)
                continue
            if submissions and submissions[0]["ref"] != baseline_id:
                only_submission_id = submissions[0]["ref"]
                print(f"New submission detected: {only_submission_id} "
                      f"({submissions[0].get('description', '')[:60]}). "
                      f"Switching to dense per-episode tracking.", flush=True)
                break
        args.watch = True  # following a new submission implies watching it

    last_seen = {}
    start = time.monotonic()
    while True:
        try:
            submissions = run_kaggle_csv(["competitions", "submissions", "-c", args.competition])
        except subprocess.CalledProcessError as exc:
            print(f"warning: submissions poll failed, will retry next tick: {exc}",
                  file=sys.stderr, flush=True)
            if not args.watch:
                return 1
            time.sleep(args.interval)
            continue
        if not submissions:
            print("No submissions found.", file=sys.stderr)
            return 1

        if only_submission_id:
            targets = [s for s in submissions if s["ref"] == only_submission_id]
        else:
            # kaggle CLI already returns newest-first.
            targets = submissions if args.top == 0 else submissions[: args.top]

        polled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not LOG_PATH.exists()

        rows = []
        for sub in targets:
            sub_id = sub["ref"]
            try:
                episodes = run_kaggle_csv(["competitions", "episodes", sub_id])
            except subprocess.CalledProcessError as exc:
                print(f"warning: could not fetch episodes for {sub_id}: {exc}", file=sys.stderr)
                episodes = []
            rows.append({
                "polled_at_utc": polled_at,
                "submission_id": sub_id,
                "submission_date": sub["date"],
                "description": sub.get("description", ""),
                "public_score": sub.get("publicScore", ""),
                "episode_count": len(episodes),
            })

        with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerows(rows)

        for row in rows:
            sub_id = row["submission_id"]
            n_now = row["episode_count"]
            score_now = row["public_score"]
            prev = last_seen.get(sub_id)
            if prev is None:
                delta_note = "(baseline)"
            else:
                n_prev, score_prev = prev
                dn = n_now - n_prev
                try:
                    dscore = float(score_now) - float(score_prev)
                except ValueError:
                    dscore = float("nan")
                delta_note = f"(+{dn} game(s) -> {dscore:+.1f}pt)" if dn else "(no new games)"
            last_seen[sub_id] = (n_now, score_now)
            print(f"{row['polled_at_utc']}  {sub_id}  n={n_now:>4}  "
                  f"score={score_now:>8}  {delta_note}  {row['description'][:50]}",
                  flush=True)

        if not args.watch:
            print(f"\nAppended {len(rows)} row(s) to {LOG_PATH}")
            return 0

        elapsed = time.monotonic() - start
        if args.duration and elapsed >= args.duration:
            print(f"\n--watch duration ({args.duration}s) reached, stopping.")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
