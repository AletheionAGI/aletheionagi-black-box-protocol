from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .schema import CaseExecution, CaseOutcome


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def summarize(
    executions: list[CaseExecution],
    target_descriptors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_target: dict[str, list[CaseExecution]] = defaultdict(list)
    for execution in executions:
        by_target[execution.target].append(execution)
    performance: dict[str, Any] = {}
    for target, rows in sorted(by_target.items()):
        counts = Counter(row.outcome.value for row in rows)
        measurable = counts[CaseOutcome.PASS.value] + counts[CaseOutcome.FAIL.value]
        latencies = [row.result.latency_ms for row in rows if row.result.latency_ms is not None]
        unauthorized = [
            row
            for row in rows
            if row.category in {"authorization_isolation", "namespace_isolation"}
            and row.result.authorization_violation is not None
        ]
        unsupported = [
            row
            for row in rows
            if row.category in {"unsupported_claim", "insufficient_evidence", "fail_closed"}
            and row.outcome in {CaseOutcome.PASS, CaseOutcome.FAIL}
        ]
        contradictions = [
            row
            for row in rows
            if row.category == "contradictory_evidence"
            and row.outcome in {CaseOutcome.PASS, CaseOutcome.FAIL}
        ]
        target_summary = {
            "total_cases": len(rows),
            "pass": counts[CaseOutcome.PASS.value],
            "fail": counts[CaseOutcome.FAIL.value],
            "skipped": counts[CaseOutcome.SKIPPED.value],
            "errors": counts[CaseOutcome.ERROR.value],
            "pass_rate": counts[CaseOutcome.PASS.value] / measurable if measurable else None,
            "unsupported_claim_escape_rate": (
                sum(row.outcome == CaseOutcome.FAIL for row in unsupported) / len(unsupported)
                if unsupported else None
            ),
            "false_block_rate": _signal_rate(rows, "supported_answer", "blocked"),
            "abstention_rate": _bool_rate(rows, "abstained"),
            "unauthorized_evidence_use_rate": (
                sum(row.result.authorization_violation is True for row in unauthorized) / len(unauthorized)
                if unauthorized else None
            ),
            "cross_namespace_leakage_rate": (
                sum(row.result.authorization_violation is True for row in unauthorized if row.category == "namespace_isolation")
                / sum(row.category == "namespace_isolation" for row in unauthorized)
                if any(row.category == "namespace_isolation" for row in unauthorized)
                else None
            ),
            "contradiction_escape_rate": (
                sum(row.outcome == CaseOutcome.FAIL for row in contradictions) / len(contradictions)
                if contradictions
                else None
            ),
            "mean_latency_ms": statistics.fmean(latencies) if latencies else None,
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
        }
        performance[target] = target_summary
    integration = {
        descriptor["name"]: descriptor.get("integration", {})
        for descriptor in (target_descriptors or [])
    }
    return {
        "protocol_performance": {"targets": performance},
        "integration_complexity": {"targets": integration},
        # Kept for readers of the initial 0.1 report schema.
        "targets": performance,
    }


def _bool_rate(rows: list[CaseExecution], attribute: str) -> float | None:
    values = [getattr(row.result, attribute) for row in rows]
    measurable = [value for value in values if value is not None]
    return sum(value is True for value in measurable) / len(measurable) if measurable else None


def _signal_rate(rows: list[CaseExecution], category: str, attribute: str) -> float | None:
    selected = [getattr(row.result, attribute) for row in rows if row.category == category]
    measurable = [value for value in selected if value is not None]
    return sum(value is True for value in measurable) / len(measurable) if measurable else None


def write_report(run_dir: Path, manifest: dict[str, Any], executions: list[CaseExecution]) -> None:
    summary = summarize(executions, manifest.get("targets", []))
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Black-Box Protocol Results",
        "",
        "## Methodology",
        "",
        f"Frozen case digest: `{manifest['frozen_cases']['combined_sha256']}`. No target-specific case or scoring changes are permitted.",
        "",
        "## Targets and versions",
        "",
    ]
    for target in manifest["targets"]:
        lines.append(f"- `{target['name']}`: `{target['version']}`; capabilities: {', '.join(target['capabilities'])}")
    lines.extend([
        "",
        "## Configuration",
        "",
        "Secrets are omitted. Provider thresholds and presence flags are recorded in `manifest.json`.",
        "",
        "## Protocol Performance",
        "",
        "These behavioral results alone determine protocol PASS/FAIL outcomes. Setup burden is excluded from every grounding metric.",
        "",
    ])
    for target, values in summary["protocol_performance"]["targets"].items():
        lines.append(f"- `{target}`: PASS {values['pass']}, FAIL {values['fail']}, SKIPPED {values['skipped']}, ERROR {values['errors']}")
    lines.extend([
        "",
        "## Integration Complexity",
        "",
        "This secondary, descriptive measurement records integration friction. It is not a protocol score and does not affect PASS, FAIL, SKIPPED or ERROR.",
        "",
    ])
    for target, values in summary["integration_complexity"]["targets"].items():
        counts = values.get("counts", {})
        artifact = values.get("local_model_artifact", "not recorded")
        lines.append(
            f"- `{target}`: dependencies {counts.get('dependencies', 0)}, wrappers {counts.get('wrappers', 0)}, "
            f"required secrets {counts.get('required_secrets', 0)}, configuration items {counts.get('required_configuration', 0)}, "
            f"external services {counts.get('external_services', 0)}, setup steps {counts.get('setup_steps', 0)}; "
            f"local model artifact: {artifact}."
        )
    lines.extend(["", "## Results by Test Category", ""])
    for execution in executions:
        lines.append(f"- `{execution.target}` / `{execution.case_id}` / run {execution.run_number}: **{execution.outcome.value}** — {execution.reason}")
    failures = [row for row in executions if row.outcome == CaseOutcome.FAIL]
    skipped = [row for row in executions if row.outcome in {CaseOutcome.SKIPPED, CaseOutcome.ERROR}]
    lines.extend(["", "## Failure Cases", ""])
    lines.extend([f"- `{row.target}` `{row.case_id}`: {row.reason}" for row in failures] or ["None."])
    lines.extend(["", "## Skipped/Unsupported Capabilities", ""])
    lines.extend([f"- `{row.target}` `{row.case_id}`: {row.reason}" for row in skipped] or ["None."])
    lines.extend([
        "",
        "## Latency",
        "",
        "See `summary.json`; latency includes adapter and provider overhead and is not normalized across deployment environments.",
        "",
        "## Limitations",
        "",
        "This report compares observable behavior, not feature completeness or internal architecture. It does not declare an overall winner.",
        "Integration counts are descriptive inventory counts, not normalized effort estimates, and are never included in protocol performance.",
        "",
        "## Additional AletheionAGI Adversarial Testing",
        "",
        "AletheionAGI was additionally evaluated with Strix autonomous penetration testing against infrastructure owned and authorized by AletheionAGI. These results are reported separately and are not included in competitive scoring.",
        "",
        "## Reproduction",
        "",
        "Use the recorded commit, frozen digest, target versions and configuration in `manifest.json`.",
    ])
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
