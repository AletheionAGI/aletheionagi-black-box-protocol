from __future__ import annotations

from pathlib import Path
from typing import Any


def write_strix_report(run_dir: Path, manifest: dict[str, Any], findings: dict[str, Any]) -> None:
    counts = {
        name: len(findings.get(name, []))
        for name in ("confirmed", "probable", "unconfirmed", "informational")
    }
    lines = [
        "# AletheionAGI Strix Adversarial Assessment",
        "",
        "## Scope",
        "",
        f"Scope SHA-256: `{manifest['scope_sha256']}`",
        "",
        "## Authorization Boundary",
        "",
        "This assessment is restricted to infrastructure owned and explicitly authorized by AletheionAGI.",
        "This assessment applies only to AletheionAGI-controlled infrastructure and is not part of the vendor-neutral competitive benchmark.",
        "",
        "## Strix Version",
        "",
        f"`{manifest['strix_cli_version']}`",
        "",
        "## Target",
        "",
        f"Target: `{manifest['target']}`",
        "",
        "## Configuration",
        "",
        f"Status: **{manifest['status']}**",
        f"Sanitized command: `{manifest['sanitized_command']}`",
        f"Exit code: `{manifest.get('exit_code')}`",
        f"Duration seconds: `{manifest.get('duration_seconds')}`",
        "",
        "Readiness issues: " + (", ".join(manifest.get("readiness_issues", [])) or "none"),
        "",
        "## Confirmed Findings",
        "",
        f"Count: {counts['confirmed']}. Only human-reviewed findings with a reproducible proof of concept qualify.",
        "",
        "## Probable Findings",
        "",
        f"Count: {counts['probable']}.",
        "",
        "## Unconfirmed Findings",
        "",
        f"Count: {counts['unconfirmed']}. Informational observations: {counts['informational']}.",
        "",
        "Only findings reviewed and accompanied by a reproducible proof of concept may be classified as confirmed. Raw autonomous output is never promoted automatically.",
        "",
        "## Grounding / Isolation Findings",
        "",
        "These adversarial results are reported separately and are not included in competitive scoring or protocol performance.",
        "",
        "## Reproduction",
        "",
        "Use the recorded target, commit, Strix version, scope hash, sanitized command and preserved external run-directory references. Secrets are intentionally omitted.",
        "",
        "## Exclusions",
        "",
        "Denial of service, destructive testing, brute force, persistence, real-user data and all third-party infrastructure are excluded by the recorded scope.",
        "",
        "## Limitations",
        "",
        "The wrapper validates the initial hostname exactly. Redirect handling inside the external Strix process cannot be intercepted by this wrapper; the scope instruction requires an immediate stop if a redirect leaves the allowlist.",
        "An OpenAPI input is included only when explicitly configured; its existence and SHA-256 digest are recorded before execution.",
    ]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
