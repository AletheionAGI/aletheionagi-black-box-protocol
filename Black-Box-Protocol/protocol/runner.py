from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters import TARGETS
from adapters.base import BlackBoxTarget, CaseSkipped, TargetDescriptor, TargetSkipped

from .freeze import git_commit, load_cases, verify_manifest
from .reporting import write_report
from .schema import CaseExecution, CaseOutcome, TargetResult
from .scoring import SCORING_POLICY_VERSION, score_case

FIRST_ROUND_TARGETS = ("aletheionagi", "patronus_lynx", "nemo_guardrails", "guardrails_ai")


def descriptor_dict(descriptor: TargetDescriptor) -> dict[str, Any]:
    return {
        "name": descriptor.name,
        "version": descriptor.version,
        "capabilities": sorted(descriptor.capabilities),
        "configuration": descriptor.configuration,
        "integration": descriptor.integration.to_dict(),
    }


def run_targets(
    root: Path,
    target_names: list[str],
    *,
    runs: int = 1,
    categories: set[str] | None = None,
) -> Path:
    if runs < 1:
        raise ValueError("runs must be at least 1")
    frozen = verify_manifest(root)
    cases = [case for case in load_cases(root) if not categories or case.category in categories]
    unknown = sorted(set(target_names) - TARGETS.keys())
    if unknown:
        raise ValueError(f"unknown targets: {unknown}")
    targets: list[BlackBoxTarget] = [TARGETS[name]() for name in target_names]
    frozen_descriptors = {target.name: descriptor_dict(target.descriptor()) for target in targets}
    started = datetime.now(UTC)
    run_dir = root / "results" / started.strftime("%Y%m%dT%H%M%S.%fZ")
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "started_at": started.isoformat(),
        "protocol_commit": git_commit(root),
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "runs_per_case": runs,
        "categories": sorted(categories) if categories else "all",
        "frozen_cases": frozen,
        "targets": list(frozen_descriptors.values()),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    executions: list[CaseExecution] = []

    for target in targets:
        verify_manifest(root)
        if descriptor_dict(target.descriptor()) != frozen_descriptors[target.name]:
            raise RuntimeError(f"{target.name} configuration changed after run manifest was frozen")
        raw_path = raw_dir / f"{target.name}.jsonl"
        with raw_path.open("w", encoding="utf-8") as raw_handle:
            target_unavailable: str | None = None
            for case in cases:
                for run_number in range(1, runs + 1):
                    metadata = dict(case.metadata)
                    metadata.update(
                        {
                            "case_id": case.id,
                            "category": case.category,
                            "frozen_sha256": frozen["combined_sha256"],
                            "authorized_evidence": [asdict(item) for item in case.authorized_evidence],
                            "unauthorized_evidence": [asdict(item) for item in case.unauthorized_evidence],
                        }
                    )
                    try:
                        if target_unavailable:
                            raise TargetSkipped(target_unavailable)
                        result = target.evaluate(case.question, list(case.authorized_evidence), metadata)
                        outcome, reason = score_case(case, result, target.capabilities)
                    except CaseSkipped as exc:
                        result = TargetResult(error=None, capability_notes=(str(exc),))
                        outcome, reason = CaseOutcome.SKIPPED, str(exc)
                    except TargetSkipped as exc:
                        target_unavailable = str(exc)
                        result = TargetResult(error=None, capability_notes=(target_unavailable,))
                        outcome, reason = CaseOutcome.SKIPPED, target_unavailable
                    except subprocess.TimeoutExpired:
                        result = TargetResult(error="target command timed out")
                        outcome, reason = CaseOutcome.ERROR, result.error
                    except Exception as exc:  # provider isolation boundary
                        result = TargetResult(error=f"{type(exc).__name__}: {exc}")
                        outcome, reason = CaseOutcome.ERROR, result.error
                    execution = CaseExecution(
                        target.name,
                        case.id,
                        case.category,
                        run_number,
                        outcome,
                        reason,
                        result,
                    )
                    executions.append(execution)
                    raw_handle.write(json.dumps(execution.to_dict(), sort_keys=True) + "\n")

    manifest["finished_at"] = datetime.now(UTC).isoformat()
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_report(run_dir, manifest, executions)
    return run_dir
