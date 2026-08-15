from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .schema import TestCase

FREEZE_VERSION = "1.1.0"
MANIFEST_NAME = "FROZEN_MANIFEST.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cases(root: Path) -> list[TestCase]:
    cases: list[TestCase] = []
    seen: set[str] = set()
    for path in sorted((root / "cases").glob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                case = TestCase.from_dict(json.loads(line))
            except (ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path.name}:{line_number}: {exc}") from exc
            if case.id in seen:
                raise ValueError(f"duplicate case id: {case.id}")
            seen.add(case.id)
            cases.append(case)
    if not cases:
        raise ValueError("no cases found")
    return sorted(cases, key=lambda case: case.id)


def _tracked_inputs(root: Path) -> list[Path]:
    inputs = sorted((root / "cases").glob("*.jsonl"))
    inputs.extend(
        [
            root / "cases" / "case.schema.json",
            root / "protocol" / "schema.py",
            root / "protocol" / "normalization.py",
            root / "protocol" / "scoring.py",
            root / "HYPOTHESES.md",
        ]
    )
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        raise ValueError(f"freeze inputs missing: {missing}")
    return inputs


def build_manifest(root: Path) -> dict[str, Any]:
    cases = load_cases(root)
    files = {
        path.relative_to(root).as_posix(): sha256_file(path) for path in _tracked_inputs(root)
    }
    combined = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "freeze_version": FREEZE_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "combined_sha256": combined,
        "case_ids": [case.id for case in cases],
        "files": files,
    }


def write_manifest(root: Path, *, refresh: bool = False) -> Path:
    output = root / "cases" / MANIFEST_NAME
    if output.exists() and not refresh:
        raise FileExistsError("frozen manifest exists; use --refresh only before observing target results")
    output.write_text(json.dumps(build_manifest(root), indent=2) + "\n", encoding="utf-8")
    return output


def verify_manifest(root: Path) -> dict[str, Any]:
    path = root / "cases" / MANIFEST_NAME
    if not path.is_file():
        raise RuntimeError("cases are not frozen; run scripts/freeze_cases.py before any target")
    expected = json.loads(path.read_text(encoding="utf-8"))
    current = build_manifest(root)
    if expected.get("files") != current["files"] or expected.get("case_ids") != current["case_ids"]:
        raise RuntimeError("frozen inputs changed; refusing to run any target")
    if expected.get("combined_sha256") != current["combined_sha256"]:
        raise RuntimeError("frozen manifest digest mismatch")
    return expected


def git_commit(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
