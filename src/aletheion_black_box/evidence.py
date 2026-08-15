from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import CaseResult, Config, Exchange, Outcome

_SECRET_FIELD_PARTS = ("authorization", "api_key", "apikey", "password", "secret", "token")


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(part in key.casefold() for part in _SECRET_FIELD_PARTS)
            else redact(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, tuple):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value


class EvidenceWriter:
    def __init__(self, directory: Path, secrets: tuple[str, ...]) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=False)
        self.secrets = secrets
        self.exchange_path = directory / "exchanges.jsonl"

    def exchange(self, organization: str, exchange: Exchange) -> None:
        record = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "organization": organization,
            **asdict(exchange),
        }
        with self.exchange_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(redact(record, self.secrets), sort_keys=True) + "\n")

    def finalize(
        self,
        *,
        config: Config,
        run_id: str,
        started_at: str,
        finished_at: str,
        cases: list[CaseResult],
        overall: Outcome,
        canaries: dict[str, str],
    ) -> None:
        config_path = self.directory / "config.sanitized.json"
        config_path.write_text(
            json.dumps(config.sanitized(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = {
            "protocol_version": config.protocol_version,
            "tested_release": config.tested_release,
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "overall": overall.value,
            "attempts_per_organization": config.attempts_per_organization,
            "canaries": canaries,
            "cases": [case.as_dict() for case in cases],
        }
        result_path = self.directory / "result.json"
        result_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        report_path = self.directory / "report.md"
        report_path.write_text(_report(result), encoding="utf-8")
        files = [config_path, self.exchange_path, report_path, result_path]
        sums = [f"{_sha256(path)}  {path.name}" for path in sorted(files)]
        (self.directory / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _report(result: dict[str, Any]) -> str:
    lines = [
        "# AletheionAGI black-box evaluation report",
        "",
        f"- Protocol: {result['protocol_version']}",
        f"- Tested release: {result['tested_release']}",
        f"- Run ID: {result['run_id']}",
        f"- UTC interval: {result['started_at']} — {result['finished_at']}",
        f"- Attempts per organization: {result['attempts_per_organization']}",
        f"- Overall outcome: **{result['overall']}**",
        "",
        "## Cases",
        "",
        "| Case | Outcome | Reason |",
        "| --- | --- | --- |",
    ]
    for case in result["cases"]:
        reason = str(case["reason"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {case['case_id']} — {case['name']} | {case['outcome']} | {reason} |")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This result applies only to the recorded release, environment and attempts. A PASS",
            "means no forbidden canary was observed under these conditions; it is not a proof that",
            "prohibited behavior can never occur.",
            "",
        ]
    )
    return "\n".join(lines)
