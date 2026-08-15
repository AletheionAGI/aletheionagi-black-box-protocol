from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from protocol.freeze import git_commit

from .reporting import write_strix_report
from .strix_config import StrixConfig, validate_target

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|cookie)\s*[:=]\s*)[^\s,;]+"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize_text(value: str, secrets: tuple[str, ...] = ()) -> str:
    sanitized = value
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        sanitized = sanitized.replace(secret, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


def detect_cli() -> tuple[str | None, str]:
    cli = shutil.which("strix")
    if not cli:
        return None, "unavailable"
    try:
        completed = subprocess.run(
            [cli, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return cli, "unknown"
    output = (completed.stdout or completed.stderr).strip()
    return cli, sanitize_text(output) or "unknown"


def build_command(
    cli_path: str,
    target: str,
    scope_path: Path,
    openapi_path: Path | None = None,
) -> list[str]:
    validate_target(target)
    command = [
        cli_path,
        "--non-interactive",
    ]
    if openapi_path is not None:
        command.extend(["--target", str(openapi_path)])
    command.extend(
        [
            "--target",
            target,
            "--scan-mode",
            "quick",
            "--instruction-file",
            str(scope_path),
        ]
    )
    return command


def _child_environment(config: StrixConfig) -> dict[str, str]:
    allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "DOCKER_HOST")
    child = {name: os.environ[name] for name in allowed if name in os.environ}
    child["STRIX_LLM"] = config.llm
    child["LLM_API_KEY"] = config.llm_api_key
    return child


def _new_run_dir(root: Path) -> Path:
    run_dir = root / "results" / "strix" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def run_strix(root: Path, config: StrixConfig, *, execute: bool = False) -> Path:
    config.validate_common()
    scope_path = root / "adversarial" / "strix_scope.md"
    if not scope_path.is_file():
        raise FileNotFoundError(f"Strix scope file is missing: {scope_path}")
    cli_path, cli_version = detect_cli()
    command = build_command(cli_path or "strix", config.target, scope_path, config.openapi_path)
    if execute:
        config.validate_execution(cli_path)
    readiness_issues = []
    if not config.enabled:
        readiness_issues.append("STRIX_ENABLED is false")
    if not config.authorization_ack:
        readiness_issues.append("STRIX_AUTHORIZATION_ACK is false")
    if not cli_path:
        readiness_issues.append("Strix CLI is unavailable")
    if not config.llm:
        readiness_issues.append("STRIX_LLM is unset")
    if not config.llm_api_key:
        readiness_issues.append("STRIX_LLM_API_KEY is unset")
    run_dir = _new_run_dir(root)
    before_runs = set((root / "strix_runs").glob("*")) if (root / "strix_runs").exists() else set()
    manifest: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "protocol_commit": git_commit(root),
        "target": config.target,
        "allowed_hostname": config.target.split("/", 3)[2].split(":", 1)[0].lower(),
        "scope_path": str(scope_path.relative_to(root)),
        "scope_sha256": sha256_file(scope_path),
        "openapi_path": str(config.openapi_path) if config.openapi_path else None,
        "openapi_sha256": sha256_file(config.openapi_path) if config.openapi_path else None,
        "strix_cli_path": cli_path,
        "strix_cli_version": cli_version,
        "scan_mode": config.scan_mode,
        "timeout_seconds": config.timeout_seconds,
        "enabled": config.enabled,
        "authorization_ack": config.authorization_ack,
        "execute_requested": execute,
        "sanitized_command": subprocess.list2cmdline(command),
        "secrets_recorded": False,
        "status": "DRY_RUN_READY" if not readiness_issues else "DRY_RUN_NOT_READY",
        "readiness_issues": readiness_issues,
        "exit_code": None,
        "duration_seconds": 0.0,
    }
    stdout = ""
    stderr = ""
    findings: dict[str, Any] = {
        "confirmed": [],
        "probable": [],
        "unconfirmed": [],
        "informational": [
            {
                "message": "Autonomous output requires human review and a reproducible proof of concept before confirmation."
            }
        ],
    }
    started = time.monotonic()
    if execute:
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                env=_child_environment(config),
                text=True,
                capture_output=True,
                timeout=config.timeout_seconds,
                check=False,
                shell=False,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            manifest["exit_code"] = completed.returncode
            if completed.returncode in {0, 2}:
                manifest["status"] = "COMPLETED_REVIEW_REQUIRED"
            else:
                manifest["status"] = "ERROR"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            manifest["status"] = "TIMEOUT"
    manifest["duration_seconds"] = round(time.monotonic() - started, 3)
    after_runs = set((root / "strix_runs").glob("*")) if (root / "strix_runs").exists() else set()
    manifest["external_run_directories"] = sorted(str(path.relative_to(root)) for path in after_runs - before_runs)
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    secrets = (config.llm_api_key,)
    (run_dir / "stdout.log").write_text(sanitize_text(stdout, secrets), encoding="utf-8")
    (run_dir / "stderr.log").write_text(sanitize_text(stderr, secrets), encoding="utf-8")
    (run_dir / "findings.json").write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_strix_report(run_dir, manifest, findings)
    return run_dir
