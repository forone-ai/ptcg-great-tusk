#!/usr/bin/env python3
"""Download all Kaggle episode artifacts for one submission.

This is an offline analysis helper. It fetches:

1. The submission's episode list.
2. Each replay JSON.
3. The current team's agent log for each replay, when the team index is known.

It does not touch submitted agent code.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


COMPETITION = "pokemon-tcg-ai-battle"


def default_kaggle_bin() -> str:
    local = Path(".venv/bin/kaggle")
    return str(local) if local.exists() else "kaggle"


def run_command(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            command,
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


def clean_csv_output(text: str) -> str:
    lines = text.splitlines()
    start = 0
    for index, line in enumerate(lines):
        if "," in line:
            start = index
            break
    csv_lines: list[str] = []
    for line in lines[start:]:
        if line.startswith("Use "):
            break
        if line.strip():
            csv_lines.append(line)
    return "\n".join(csv_lines) + ("\n" if csv_lines else "")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def fetch_episodes(kaggle_bin: str, submission_id: str, out_path: Path) -> list[dict[str, str]]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    completed = run_command([kaggle_bin, "competitions", "episodes", submission_id, "--csv"])
    out_path.write_text(clean_csv_output(completed.stdout), encoding="utf-8")
    return read_csv_rows(out_path)


def episode_id(row: dict[str, str]) -> str:
    values = {key.lstrip("\ufeff"): value for key, value in row.items()}
    value = values.get("id") or values.get("episodeId") or values.get("EpisodeId") or ""
    return value if value.isdigit() else ""


def replay_episode_id(replay: dict[str, Any]) -> str:
    value = replay.get("info", {}).get("EpisodeId") or replay.get("environment", {}).get("info", {}).get("EpisodeId")
    return str(value or "")


def team_names(replay: dict[str, Any]) -> list[str]:
    names = replay.get("info", {}).get("TeamNames") or replay.get("environment", {}).get("info", {}).get("TeamNames")
    return list(names or [])


def rewards(replay: dict[str, Any]) -> list[Any]:
    return list(replay.get("rewards") or replay.get("environment", {}).get("rewards") or [])


def choose_our_index(replay: dict[str, Any], team_name_contains: str) -> int | None:
    needle = team_name_contains.lower()
    for index, name in enumerate(team_names(replay)):
        if needle and needle in str(name).lower():
            return index
    return None


def download_replay(kaggle_bin: str, episode_id_value: str, replay_dir: Path, force: bool) -> Path:
    replay_dir.mkdir(parents=True, exist_ok=True)
    path = replay_dir / f"episode-{episode_id_value}-replay.json"
    if path.exists() and not force:
        return path
    run_command([kaggle_bin, "competitions", "replay", episode_id_value, "-p", str(replay_dir)])
    return path


def download_agent_log(
    kaggle_bin: str,
    episode_id_value: str,
    agent_index: int,
    log_dir: Path,
    force: bool,
) -> tuple[Path, str]:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"episode-{episode_id_value}-agent-{agent_index}-logs.json"
    if path.exists() and not force:
        return path, "exists"
    completed = run_command(
        [kaggle_bin, "competitions", "logs", episode_id_value, str(agent_index), "-p", str(log_dir)],
        check=False,
    )
    if completed.returncode == 0:
        return path, "downloaded"
    error_path = log_dir / f"episode-{episode_id_value}-agent-{agent_index}-logs.error.txt"
    error_path.write_text((completed.stderr or completed.stdout), encoding="utf-8")
    return error_path, "error"


@dataclass
class Row:
    episode_id: str
    create_time: str
    end_time: str
    state: str
    episode_type: str
    our_index: str
    our_reward: str
    opponent_name: str
    replay: str
    agent_log: str
    log_status: str


def write_manifest(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(Row.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--team-name-contains", default="GO HIROSHIMA")
    parser.add_argument("--kaggle-bin", default=default_kaggle_bin())
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--replay-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_dir = args.raw_dir or Path("analysis/raw") / args.date / f"own-dragapult-{args.submission_id}"
    replay_dir = args.replay_dir or Path("replays/kaggle-causal") / args.date / f"submission_{args.submission_id}"
    log_dir = raw_dir / "logs"

    episodes = fetch_episodes(args.kaggle_bin, args.submission_id, raw_dir / "episodes.csv")
    rows: list[Row] = []
    replay_downloaded = 0
    logs_downloaded = 0
    logs_error = 0

    for index, episode in enumerate(episodes, start=1):
        eid = episode_id(episode)
        if not eid:
            continue
        replay_path = download_replay(args.kaggle_bin, eid, replay_dir, args.force)
        replay_downloaded += 1
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        our_index = choose_our_index(replay, args.team_name_contains)
        reward_values = rewards(replay)
        names = team_names(replay)
        our_reward = ""
        opponent_name = ""
        log_path = Path("")
        log_status = "skipped"

        if our_index is not None:
            if our_index < len(reward_values):
                our_reward = str(reward_values[our_index])
            if len(names) == 2:
                opponent_name = str(names[1 - our_index])
            log_path, log_status = download_agent_log(args.kaggle_bin, eid, our_index, log_dir, args.force)
            if log_status == "downloaded":
                logs_downloaded += 1
            elif log_status == "error":
                logs_error += 1

        rows.append(
            Row(
                episode_id=eid or replay_episode_id(replay),
                create_time=episode.get("createTime", ""),
                end_time=episode.get("endTime", ""),
                state=episode.get("state", ""),
                episode_type=episode.get("type", ""),
                our_index="" if our_index is None else str(our_index),
                our_reward=our_reward,
                opponent_name=opponent_name,
                replay=str(replay_path),
                agent_log=str(log_path) if str(log_path) else "",
                log_status=log_status,
            )
        )
        print(f"[{index}/{len(episodes)}] episode={eid} our_index={our_index} reward={our_reward} log={log_status}")

    manifest_path = raw_dir / "artifact_manifest.csv"
    write_manifest(manifest_path, rows)
    print(f"[episodes] {len(episodes)} -> {raw_dir / 'episodes.csv'}")
    print(f"[replays] processed={replay_downloaded} dir={replay_dir}")
    print(f"[logs] downloaded={logs_downloaded} errors={logs_error} dir={log_dir}")
    print(f"[manifest] {manifest_path}")


if __name__ == "__main__":
    main()
