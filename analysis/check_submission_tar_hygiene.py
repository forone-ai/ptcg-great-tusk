#!/usr/bin/env python3
"""Check a Kaggle submission tarball before upload.

This is a packaging gate, not a win-rate gate. It catches macOS metadata,
missing top-level files, invalid deck shape, path traversal, and optional
mismatch against a candidate directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_TOP_LEVEL = {"main.py", "deck.csv", "cg"}
ALLOWED_TOP_LEVEL = {"main.py", "deck.csv", "cg", "engine", "strategy"}


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def display(path: str | Path) -> str:
    p = resolve(path)
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_member(archive: tarfile.TarFile, name: str) -> bytes:
    member = archive.getmember(name)
    if not member.isfile():
        raise RuntimeError(f"{name} is not a file")
    file_obj = archive.extractfile(member)
    if file_obj is None:
        raise RuntimeError(f"could not read {name}")
    return file_obj.read()


def deck_rows(deck_bytes: bytes) -> list[str]:
    text = deck_bytes.decode("utf-8")
    return [row.strip() for row in text.splitlines() if row.strip()]


def invalid_paths(names: list[str]) -> list[str]:
    bad: list[str] = []
    for name in names:
        p = Path(name)
        if p.is_absolute() or ".." in p.parts:
            bad.append(name)
    return bad


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tar_path = resolve(args.tar)
    candidate_dir = resolve(args.candidate_dir) if args.candidate_dir else None
    failures: list[str] = []
    warnings: list[str] = []

    if not tar_path.exists():
        return {
            "status": "fail",
            "tar": display(tar_path),
            "failures": [f"tarball does not exist: {display(tar_path)}"],
            "warnings": [],
        }

    with tarfile.open(tar_path, "r:gz") as archive:
        names = archive.getnames()
        top_level = sorted({name.split("/")[0] for name in names if name})
        top_level_set = set(top_level)
        appledouble = [name for name in names if name.startswith("._") or "/._" in name]
        ds_store = [name for name in names if name.endswith(".DS_Store")]
        pycache = [name for name in names if "__pycache__" in Path(name).parts]
        traversal = invalid_paths(names)
        missing = sorted(REQUIRED_TOP_LEVEL - top_level_set)
        unexpected = sorted(top_level_set - ALLOWED_TOP_LEVEL)

        if missing:
            failures.append(f"missing top-level entries: {', '.join(missing)}")
        if appledouble:
            failures.append(f"contains AppleDouble metadata entries: {len(appledouble)}")
        if ds_store:
            failures.append(f"contains .DS_Store entries: {len(ds_store)}")
        if pycache:
            failures.append(f"contains __pycache__ entries: {len(pycache)}")
        if traversal:
            failures.append(f"contains unsafe paths: {', '.join(traversal[:5])}")
        if unexpected:
            warnings.append(f"unexpected top-level entries: {', '.join(unexpected)}")

        file_hashes: dict[str, dict[str, Any]] = {}
        for name in ["main.py", "deck.csv"]:
            if name in names:
                data = read_member(archive, name)
                file_hashes[name] = {"sha256": sha256_bytes(data), "size": len(data)}
                if name == "deck.csv":
                    rows = deck_rows(data)
                    file_hashes[name]["rows"] = len(rows)
                    invalid_deck_rows = [row for row in rows if not row.isdigit()]
                    if len(rows) != 60:
                        failures.append(f"deck.csv has {len(rows)} rows, expected 60")
                    if invalid_deck_rows:
                        failures.append("deck.csv contains non-integer rows")

        if candidate_dir:
            for name in ["main.py", "deck.csv"]:
                candidate_file = candidate_dir / name
                if not candidate_file.exists():
                    failures.append(f"candidate {name} missing: {display(candidate_file)}")
                    continue
                candidate_hash = sha256_bytes(candidate_file.read_bytes())
                tar_hash = file_hashes.get(name, {}).get("sha256")
                if tar_hash and candidate_hash != tar_hash:
                    failures.append(
                        f"{name} sha256 mismatch: tar={tar_hash} candidate={candidate_hash}"
                    )

    return {
        "schema": "submission_tar_hygiene.v1",
        "status": "fail" if failures else "pass",
        "tar": display(tar_path),
        "candidate_dir": display(candidate_dir) if candidate_dir else "",
        "tar_sha256": sha256_bytes(tar_path.read_bytes()),
        "tar_size": tar_path.stat().st_size,
        "top_level": top_level,
        "required_top_level": sorted(REQUIRED_TOP_LEVEL),
        "allowed_top_level": sorted(ALLOWED_TOP_LEVEL),
        "file_hashes": file_hashes,
        "counts": {
            "members": len(names),
            "appledouble": len(appledouble),
            "ds_store": len(ds_store),
            "pycache": len(pycache),
            "unsafe_paths": len(traversal),
            "unexpected_top_level": len(unexpected),
        },
        "failures": failures,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tar", required=True, help="Submission tar.gz to inspect.")
    parser.add_argument("--candidate-dir", help="Optional candidate dir containing main.py/deck.csv.")
    parser.add_argument("--out-json", help="Optional JSON report path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out_json:
        out = resolve(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if report.get("status") == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())

