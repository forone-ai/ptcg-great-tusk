#!/usr/bin/env python3
"""Run a candidate against independent registry agents on the official engine.

The bundled engine does not expose a deterministic seed. Results are therefore
independent repeated trials, not seed-paired games. The runner preserves raw
engine outcomes, including result=2 draws, and writes a provenance sidecar.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_RUNTIME = ROOT / "agent"
if str(AGENT_RUNTIME) not in sys.path:
    sys.path.insert(0, str(AGENT_RUNTIME))
_NATIVE = os.environ.get("PTCG_NATIVE_CG")
if _NATIVE and os.path.isdir(_NATIVE):
    sys.path.insert(0, _NATIVE)

_AGENT_MODULE_ROOTS = (
    ROOT / "agent",
    ROOT / "analysis/candidates",
    ROOT / "analysis/opponents",
    ROOT / "league/entries",
)

_CANDIDATE_ENVIRONMENT_KEYS = (
    "ALAKAZAM_TURNPLAN_GATES",
    "ALAKAZAM_TURNPLAN_V3_GATES",
    "ALAKAZAM_TURNPLAN_V4_GATES",
    "RAGING_BOLT_PLANNER_GATES",
    "RAGING_BOLT_PLANNER_STRICT",
    "RAGING_BOLT_PURE_V2_GATES",
)


@dataclass(frozen=True)
class GameOutcome:
    result: int
    steps: int
    elapsed_sec: float
    first_player: int


def read_deck_csv(path: Path) -> list[int]:
    rows = [row.strip() for row in path.read_text(encoding="utf-8").splitlines() if row.strip()]
    if len(rows) != 60:
        raise ValueError(f"Deck must contain 60 card IDs: {path} has {len(rows)}")
    return [int(row) for row in rows]


def _is_agent_module(module: ModuleType) -> bool:
    raw_file = getattr(module, "__file__", None)
    if not raw_file:
        return False
    try:
        module_path = Path(raw_file).resolve()
    except (OSError, RuntimeError):
        return False
    return any(module_path.is_relative_to(root.resolve()) for root in _AGENT_MODULE_ROOTS)


def _purge_agent_modules() -> None:
    """Avoid sharing generic packages such as strategy/engine across agents."""
    for name, module in list(sys.modules.items()):
        if name == "cg" or name.startswith("cg."):
            continue
        if isinstance(module, ModuleType) and _is_agent_module(module):
            del sys.modules[name]


def load_agent(path: Path, module_name: str) -> ModuleType:
    _purge_agent_modules()
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load agent module: {path}")
    module = importlib.util.module_from_spec(spec)
    agent_dir = str(path.parent)
    sys.path.insert(0, agent_dir)
    previous_module = sys.modules.get(module_name)
    sys.modules[module_name] = module
    # Kaggle本番は CWD=/kaggle_simulations/agent。相対 "deck.csv" を読む公開エージェント
    # (prvsiyan_ala/naoto714他6体)が迷子ファイルを掴む事故(2026-07-31発覚)を防ぐため、
    # import中だけ本番同様にエージェントdirへchdirする
    _prev_cwd = os.getcwd()
    os.chdir(agent_dir)
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous_module
        raise
    finally:
        os.chdir(_prev_cwd)
        if sys.path and sys.path[0] == agent_dir:
            sys.path.pop(0)
    if not hasattr(module, "agent"):
        raise RuntimeError(f"Agent module has no agent(obs): {path}")
    return module


def _forced_first_selection(obs: dict[str, Any], first_player: int) -> list[int] | None:
    """Return the IS_FIRST choice that makes the requested player start.

    YES means the player who owns the prompt goes first; NO means the other
    player goes first.  The official setup currently routes this prompt to
    player 0, but using ``yourIndex`` keeps the mapping faithful to the prompt
    contract if that routing changes.
    """
    select = obs.get("select") or {}
    context = select.get("context")
    if context not in (41, "IS_FIRST"):
        return None
    if first_player not in (0, 1):
        raise ValueError(f"first_player must be 0 or 1, got {first_player}")
    current = obs.get("current") or {}
    prompt_player = int(current.get("yourIndex", -1))
    if prompt_player not in (0, 1):
        raise RuntimeError("IS_FIRST prompt has no valid current.yourIndex")
    desired_type = 1 if first_player == prompt_player else 2  # OptionType.YES / NO
    for index, option in enumerate(select.get("option") or []):
        if option.get("type") in (desired_type, "YES" if desired_type == 1 else "NO"):
            return [index]
    raise RuntimeError(f"IS_FIRST prompt has no option for requested first player {first_player}")


def _balanced_actual_our_first(game_index: int) -> bool:
    """Return the candidate order target for a seat/order-balanced 4-game cycle.

    Candidate seats already alternate 0, 1, 0, 1.  The True, False, False,
    True order below covers p0-first, p1-second, p0-second, and p1-first once
    per cycle, avoiding a seat/order confound in promotion evidence.
    """
    if game_index < 0:
        raise ValueError(f"game_index must be non-negative, got {game_index}")
    return game_index % 4 in (0, 3)


def _first_player_for_candidate_order(
    our_player_index: int,
    actual_our_first: bool,
) -> int:
    """Translate candidate-relative actual order to the engine player index."""
    if our_player_index not in (0, 1):
        raise ValueError(f"our_player_index must be 0 or 1, got {our_player_index}")
    return our_player_index if actual_our_first else 1 - our_player_index


def _validate_actual_order_options(
    *,
    games_per_opponent: int,
    balance_actual_order: bool,
    force_player_zero_first: bool,
) -> None:
    if balance_actual_order and force_player_zero_first:
        raise ValueError(
            "--balance-actual-order and --force-player-zero-first are mutually exclusive"
        )
    if balance_actual_order and games_per_opponent % 4 != 0:
        raise ValueError(
            "--balance-actual-order requires --games-per-opponent to be a multiple of 4"
        )


def play_game_detailed(
    agent0,
    agent1,
    deck0,
    deck1,
    max_steps: int,
    force_first_player: int | None = None,
) -> GameOutcome:
    """Play one game and preserve the raw result and actual first player."""
    from cg.game import battle_finish, battle_select, battle_start

    started = time.monotonic()
    obs, start_data = battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(f"battle_start failed: {start_data.errorType}")
    first_player = -1
    try:
        for step in range(max_steps):
            current = obs.get("current") or {}
            observed_first = int(current.get("firstPlayer", -1))
            if observed_first in (0, 1):
                first_player = observed_first
            result = int(current.get("result", -1))
            if result in (0, 1, 2):
                return GameOutcome(result, step, time.monotonic() - started, first_player)
            if result != -1:
                raise RuntimeError(f"Unknown engine result: {result}")
            acting = int(current.get("yourIndex", 0))
            forced = (
                _forced_first_selection(obs, force_first_player)
                if force_first_player in (0, 1)
                else None
            )
            selection = forced if forced is not None else agent1(obs) if acting == 1 else agent0(obs)
            obs = battle_select(selection)
    finally:
        battle_finish()
    raise TimeoutError(f"Battle did not finish within {max_steps} selections.")


def play_game(agent0, agent1, deck0, deck1, max_steps):
    """Backward-compatible three-value adapter used by older local scripts."""
    outcome = play_game_detailed(agent0, agent1, deck0, deck1, max_steps)
    return outcome.result, outcome.steps, outcome.elapsed_sec


def classify_result(result: int, our_player_index: int) -> str:
    if result == 2:
        return "draw"
    if result in (0, 1):
        return "win" if result == our_player_index else "loss"
    return "unknown"


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {key: 0 for key in ("win", "loss", "draw", "error", "unknown")}
    for row in rows:
        status = str(row.get("status", "unknown"))
        counts[status if status in counts else "unknown"] += 1
    completed = counts["win"] + counts["loss"] + counts["draw"]
    decisive = counts["win"] + counts["loss"]
    timeouts = sum(1 for row in rows if row.get("error_type") == "TimeoutError")
    unknown_first = sum(
        1
        for row in rows
        if row.get("status") in {"win", "loss", "draw"}
        and not isinstance(row.get("actual_our_first"), bool)
    )
    actual_first = sum(
        1
        for row in rows
        if row.get("status") in {"win", "loss", "draw"}
        and row.get("actual_our_first") is True
    )
    actual_second = sum(
        1
        for row in rows
        if row.get("status") in {"win", "loss", "draw"}
        and row.get("actual_our_first") is False
    )
    return {
        "requested": len(rows),
        "completed": completed,
        "decisive": decisive,
        "wins": counts["win"],
        "losses": counts["loss"],
        "draws": counts["draw"],
        "errors": counts["error"],
        "unknown": counts["unknown"],
        "timeouts": timeouts,
        "unknown_first": unknown_first,
        "actual_first": actual_first,
        "actual_second": actual_second,
        "win_rate_decisive": counts["win"] / decisive if decisive else None,
        "wdl_score_rate": (counts["win"] + 0.5 * counts["draw"]) / completed if completed else None,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _candidate_environment() -> dict[str, str]:
    """Capture policy switches that materially define a benchmark candidate."""
    return {
        key: os.environ[key]
        for key in _CANDIDATE_ENVIRONMENT_KEYS
        if key in os.environ
    }


def _display_path(path: Path) -> str:
    """Prefer a repository-relative path without rejecting external outputs."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _engine_provenance() -> dict[str, str]:
    from cg.sim import lib

    raw_name = str(getattr(lib, "_name", ""))
    engine_path = Path(raw_name).resolve() if raw_name else None
    return {
        "path": str(engine_path) if engine_path else raw_name,
        "sha256": _sha256(engine_path) if engine_path and engine_path.is_file() else "",
    }


def _row_template(
    *,
    opponent_id: str,
    archetype: str,
    game_index: int,
    our_player_index: int,
) -> dict[str, Any]:
    return {
        "opponent_id": opponent_id,
        "archetype": archetype,
        "game_index": game_index,
        "our_win": False,
        "steps": -1,
        "error": "",
        # Legacy meaning: our agent occupied player index 0, not guaranteed first.
        "our_first": our_player_index == 0,
        "our_player_index": our_player_index,
        "result": "",
        "status": "error",
        "finished": False,
        "draw": False,
        "elapsed_sec": 0.0,
        "first_player": "",
        "actual_our_first": "",
        "error_type": "",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--candidate-main", required=True)
    parser.add_argument("--our-deck", required=True)
    parser.add_argument("--registry", default="analysis/opponents/registry.json")
    parser.add_argument("--games-per-opponent", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument(
        "--candidate-config",
        default="",
        help="Human-readable candidate policy configuration recorded in provenance.",
    )
    parser.add_argument(
        "--candidate-dependency",
        action="append",
        default=[],
        help=(
            "Repeatable transitive candidate source path. Each file is hashed at "
            "start and finish and participates in the promotion source-drift gate."
        ),
    )
    parser.add_argument(
        "--force-player-zero-first",
        action="store_true",
        help=(
            "Legacy lane: force engine player 0 to act first. With alternating "
            "candidate seats, even game counts also balance candidate actual order."
        ),
    )
    parser.add_argument(
        "--balance-actual-order",
        action="store_true",
        help=(
            "Force a four-game candidate seat/order cycle (p0-first, p1-second, "
            "p0-second, p1-first). Requires games-per-opponent to be a multiple of 4."
        ),
    )
    parser.add_argument("--include", default="", help="Comma-separated substring filter on id/archetype.")
    parser.add_argument("--exclude-official-sample", action="store_true")
    parser.add_argument(
        "--promotion-mode",
        action="store_true",
        help=(
            "Require balanced observed order, complete/error-free games, and stable "
            "sources; use --balance-actual-order for deterministic promotion scheduling."
        ),
    )
    parser.add_argument(
        "--reuse-agent-modules",
        action="store_true",
        help=(
            "Exploratory speed mode only. Reuse candidate/opponent modules across games; "
            "stateful agents may leak state between battles."
        ),
    )
    parser.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    runner_path = Path(__file__).resolve()
    candidate_path = (ROOT / args.candidate_main).resolve()
    deck_path = (ROOT / args.our_deck).resolve()
    registry_path = (ROOT / args.registry).resolve()
    out_path = (ROOT / args.out).resolve()
    candidate_dependency_paths = [
        (ROOT / dependency).resolve() for dependency in args.candidate_dependency
    ]
    missing_dependencies = [
        path for path in candidate_dependency_paths if not path.is_file()
    ]
    if missing_dependencies:
        raise FileNotFoundError(
            "Candidate dependency is not a file: "
            + ", ".join(_display_path(path) for path in missing_dependencies)
        )
    source_hashes_at_start = {
        "runner": _sha256(runner_path),
        "candidate_main": _sha256(candidate_path),
        "our_deck": _sha256(deck_path),
        "registry": _sha256(registry_path),
    }
    source_hashes_at_start.update(
        {
            f"candidate_dependency_{index}": _sha256(path)
            for index, path in enumerate(candidate_dependency_paths)
        }
    )

    # Validate once up front. Trustworthy runs reload both policy modules for
    # every battle: several public agents keep module-level turn/opponent state
    # and cannot be reset through the minimal select=None deck-query payload.
    candidate = load_agent(candidate_path, "proxy_candidate_probe")
    reusable_candidate_agent = candidate.agent
    our_deck = read_deck_csv(deck_path)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    opponents = registry.get("runnable_opponents", [])
    if args.exclude_official_sample:
        opponents = [item for item in opponents if item.get("id") != "official_sample_agent"]
    if args.include:
        substrings = [value.strip() for value in args.include.split(",") if value.strip()]
        opponents = [
            item
            for item in opponents
            if any(value in item.get("id", "") or value in item.get("archetype", "") for value in substrings)
        ]
    if not opponents:
        raise ValueError("No runnable opponents matched the requested registry/filter.")

    if args.games_per_opponent <= 0:
        raise ValueError("--games-per-opponent must be positive")
    if args.max_steps <= 0:
        raise ValueError("--max-steps must be positive")
    if args.promotion_mode and args.reuse_agent_modules:
        raise ValueError("--promotion-mode forbids --reuse-agent-modules")
    _validate_actual_order_options(
        games_per_opponent=args.games_per_opponent,
        balance_actual_order=args.balance_actual_order,
        force_player_zero_first=args.force_player_zero_first,
    )
    odd_seat_allocation = args.games_per_opponent % 2 != 0
    if odd_seat_allocation:
        print("warning: games-per-opponent is odd; player-index allocation is not balanced", file=sys.stderr)

    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    opponent_sources: list[dict[str, str]] = []
    for opponent_index, opponent_entry in enumerate(opponents):
        opponent_id = opponent_entry.get("id", f"opp{opponent_index}")
        archetype = opponent_entry.get("archetype", "")
        opponent_main_path = (ROOT / opponent_entry.get("main", "")).resolve()
        opponent_deck_path = (ROOT / opponent_entry.get("deck", "")).resolve()
        opponent_sources.append(
            {
                "id": opponent_id,
                "main": _display_path(opponent_main_path),
                "main_sha256": _sha256(opponent_main_path) if opponent_main_path.is_file() else "",
                "deck": _display_path(opponent_deck_path),
                "deck_sha256": _sha256(opponent_deck_path) if opponent_deck_path.is_file() else "",
            }
        )
        opponent_rows: list[dict[str, Any]] = []
        try:
            opponent = load_agent(
                opponent_main_path,
                f"proxy_opponent_probe_{opponent_index}_{opponent_id}".replace("-", "_"),
            )
            reusable_opponent_agent = opponent.agent
            opponent_deck = read_deck_csv(opponent_deck_path)
        except Exception as exc:  # noqa: BLE001
            for game_index in range(args.games_per_opponent):
                row = _row_template(
                    opponent_id=opponent_id,
                    archetype=archetype,
                    game_index=game_index,
                    our_player_index=0 if game_index % 2 == 0 else 1,
                )
                row["error_type"] = type(exc).__name__
                row["error"] = f"LOAD_ERROR: {exc}"[:500]
                opponent_rows.append(row)
            rows.extend(opponent_rows)
            summary = summarize_rows(opponent_rows)
            summary.update({"opponent_id": opponent_id, "archetype": archetype})
            summaries.append(summary)
            print(f"[{opponent_id}] LOAD ERROR: {exc}", flush=True)
            continue

        for game_index in range(args.games_per_opponent):
            our_player_index = 0 if game_index % 2 == 0 else 1
            if args.balance_actual_order:
                force_first_player = _first_player_for_candidate_order(
                    our_player_index,
                    _balanced_actual_our_first(game_index),
                )
            elif args.force_player_zero_first:
                force_first_player = 0
            else:
                force_first_player = None
            row = _row_template(
                opponent_id=opponent_id,
                archetype=archetype,
                game_index=game_index,
                our_player_index=our_player_index,
            )
            try:
                if args.reuse_agent_modules:
                    our_agent = reusable_candidate_agent
                    opponent_agent = reusable_opponent_agent
                else:
                    game_candidate = load_agent(
                        candidate_path,
                        f"proxy_candidate_{opponent_index}_{game_index}",
                    )
                    game_opponent = load_agent(
                        opponent_main_path,
                        f"proxy_opponent_{opponent_index}_{game_index}_{opponent_id}".replace("-", "_"),
                    )
                    our_agent = game_candidate.agent
                    opponent_agent = game_opponent.agent
                if our_player_index == 0:
                    outcome = play_game_detailed(
                        our_agent,
                        opponent_agent,
                        our_deck,
                        opponent_deck,
                        args.max_steps,
                        force_first_player,
                    )
                else:
                    outcome = play_game_detailed(
                        opponent_agent,
                        our_agent,
                        opponent_deck,
                        our_deck,
                        args.max_steps,
                        force_first_player,
                    )
                status = classify_result(outcome.result, our_player_index)
                row.update(
                    {
                        "our_win": status == "win",
                        "steps": outcome.steps,
                        "result": outcome.result,
                        "status": status,
                        "finished": status in {"win", "loss", "draw"},
                        "draw": status == "draw",
                        "elapsed_sec": round(outcome.elapsed_sec, 6),
                        "first_player": outcome.first_player if outcome.first_player in (0, 1) else "",
                        "actual_our_first": (
                            outcome.first_player == our_player_index
                            if outcome.first_player in (0, 1)
                            else ""
                        ),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                row["error_type"] = type(exc).__name__
                row["error"] = str(exc)[:500]
            opponent_rows.append(row)
        rows.extend(opponent_rows)
        summary = summarize_rows(opponent_rows)
        summary.update({"opponent_id": opponent_id, "archetype": archetype})
        summaries.append(summary)
        print(
            "[{opponent_id:42}] W{wins}/D{draws}/L{losses}/E{errors} ({archetype})".format(
                **summary,
            ),
            flush=True,
        )

    fieldnames = [
        "opponent_id",
        "archetype",
        "game_index",
        "our_win",
        "steps",
        "error",
        "our_first",
        "our_player_index",
        "result",
        "status",
        "finished",
        "draw",
        "elapsed_sec",
        "first_player",
        "actual_our_first",
        "error_type",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    overall = summarize_rows(rows)
    source_hashes_at_finish = {
        "runner": _sha256(runner_path),
        "candidate_main": _sha256(candidate_path),
        "our_deck": _sha256(deck_path),
        "registry": _sha256(registry_path),
    }
    source_hashes_at_finish.update(
        {
            f"candidate_dependency_{index}": _sha256(path)
            for index, path in enumerate(candidate_dependency_paths)
        }
    )
    source_drift = {
        name: {
            "sha256_at_start": source_hashes_at_start[name],
            "sha256_at_finish": source_hashes_at_finish[name],
            "changed_during_run": source_hashes_at_start[name]
            != source_hashes_at_finish[name],
        }
        for name in source_hashes_at_start
    }
    source_changed_during_run = any(
        item["changed_during_run"] for item in source_drift.values()
    )
    actual_order_schedule_mismatches = sum(
        1
        for row in rows
        if args.balance_actual_order
        and row.get("status") in {"win", "loss", "draw"}
        and row.get("actual_our_first")
        is not _balanced_actual_our_first(int(row["game_index"]))
    )
    metadata = {
        "schema": "proxy_league_result.v2",
        "started_at": started_at,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "seed_locked": False,
        "pairing_warning": "Official BattleStart exposes no seed; repeated games are independent, not CRN-paired.",
        "candidate_main": _display_path(candidate_path),
        "candidate_main_sha256": source_hashes_at_start["candidate_main"],
        "candidate_config": args.candidate_config,
        "candidate_dependencies": [
            {
                "path": _display_path(path),
                "sha256": source_hashes_at_start[f"candidate_dependency_{index}"],
                "source_drift_key": f"candidate_dependency_{index}",
            }
            for index, path in enumerate(candidate_dependency_paths)
        ],
        "candidate_environment": _candidate_environment(),
        "our_deck": _display_path(deck_path),
        "our_deck_sha256": source_hashes_at_start["our_deck"],
        "registry": _display_path(registry_path),
        "registry_sha256": source_hashes_at_start["registry"],
        "opponent_sources_sha256": _sha256_json(opponent_sources),
        "opponent_sources": opponent_sources,
        "runner": {
            "path": _display_path(runner_path),
            "sha256": source_hashes_at_start["runner"],
        },
        "source_drift": source_drift,
        "source_changed_during_run": source_changed_during_run,
        "engine": _engine_provenance(),
        "games_per_opponent": args.games_per_opponent,
        "max_steps": args.max_steps,
        "include": args.include,
        "exclude_official_sample": args.exclude_official_sample,
        "promotion_mode": args.promotion_mode,
        "force_player_zero_first": args.force_player_zero_first,
        "balance_actual_order": args.balance_actual_order,
        "actual_order_plan": (
            {
                "mode": "candidate_seat_x_order_4_cycle",
                "cycle": [
                    {"our_player_index": 0, "actual_our_first": True, "first_player": 0},
                    {"our_player_index": 1, "actual_our_first": False, "first_player": 0},
                    {"our_player_index": 0, "actual_our_first": False, "first_player": 1},
                    {"our_player_index": 1, "actual_our_first": True, "first_player": 1},
                ],
            }
            if args.balance_actual_order
            else {
                "mode": "player_zero_first"
                if args.force_player_zero_first
                else "agent_decided"
            }
        ),
        "reload_agents_per_game": not args.reuse_agent_modules,
        "state_isolation": (
            "candidate and opponent modules reloaded before every battle"
            if not args.reuse_agent_modules
            else "UNSAFE exploratory reuse: module-level agent state may leak between battles"
        ),
        "opponent_count": len(opponents),
        "legacy_our_first_means_player_zero": True,
        "actual_order_schedule_mismatches": actual_order_schedule_mismatches,
        "overall": overall,
        "opponents": summaries,
    }
    metadata_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n===== PROXY LEAGUE SUMMARY =====")
    for item in sorted(summaries, key=lambda value: (value["wdl_score_rate"] or -1.0, value["opponent_id"])):
        print(
            "  W{wins}/D{draws}/L{losses}/E{errors}  {opponent_id} [{archetype}]".format(**item)
        )
    print(
        "TOTAL: W{wins}/D{draws}/L{losses}/E{errors}; completed={completed}/{requested}; "
        "WDL={score:.1%}".format(score=overall["wdl_score_rate"] or 0.0, **overall)
    )
    print(f"out={_display_path(out_path)}")
    print(f"meta={_display_path(metadata_path)}")

    actual_order_unbalanced = any(
        summary["actual_first"] != summary["actual_second"] for summary in summaries
    )
    promotion_failed = args.promotion_mode and (
        odd_seat_allocation
        or actual_order_unbalanced
        or actual_order_schedule_mismatches > 0
        or overall["errors"] > 0
        or overall["unknown"] > 0
        or overall["unknown_first"] > 0
        or overall["completed"] != overall["requested"]
        or source_changed_during_run
    )
    if promotion_failed:
        print(
            "promotion gate failed: unbalanced/mismatched order, incomplete/error games, or source drift",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
