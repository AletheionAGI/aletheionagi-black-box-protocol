from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from adversarial import strix_runner
from adversarial.strix_config import StrixConfig


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "suite"
    scope_dir = root / "adversarial"
    scope_dir.mkdir(parents=True)
    (scope_dir / "strix_scope.md").write_text("authorized exact-host scope\n", encoding="utf-8")
    return root


def _config(**overrides: object) -> StrixConfig:
    values = {
        "enabled": True,
        "authorization_ack": True,
        "target": "https://api.aletheionagi.com",
        "openapi_path": None,
        "llm": "provider/model",
        "llm_api_key": "top-secret-value",
        "timeout_seconds": 30,
    }
    values.update(overrides)
    return StrixConfig(**values)  # type: ignore[arg-type]


def _patch_metadata(monkeypatch: pytest.MonkeyPatch, cli: str | None = "C:/tools/strix.exe") -> None:
    monkeypatch.setattr(strix_runner, "detect_cli", lambda: (cli, "strix 1.2.3" if cli else "unavailable"))
    monkeypatch.setattr(strix_runner, "git_commit", lambda root: "abc123")


def test_dry_run_writes_manifest_without_invoking_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    _patch_metadata(monkeypatch)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("scan invoked"))

    run_dir = strix_runner.run_strix(root, _config(enabled=False, authorization_ack=False), execute=False)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "DRY_RUN_NOT_READY"
    assert "STRIX_ENABLED is false" in manifest["readiness_issues"]
    assert manifest["execute_requested"] is False
    assert manifest["scope_sha256"] == strix_runner.sha256_file(root / "adversarial" / "strix_scope.md")
    assert "top-secret-value" not in json.dumps(manifest)


def test_cli_missing_blocks_execution_before_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    _patch_metadata(monkeypatch, cli=None)
    with pytest.raises(FileNotFoundError, match="CLI"):
        strix_runner.run_strix(root, _config(), execute=True)


def test_nonzero_exit_is_recorded_and_shell_is_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    _patch_metadata(monkeypatch)
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=1, stdout="token=top-secret-value", stderr="failed")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_dir = strix_runner.run_strix(root, _config(), execute=True)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert captured["shell"] is False
    assert isinstance(captured["command"], list)
    assert manifest["status"] == "ERROR"
    assert manifest["exit_code"] == 1
    assert "top-secret-value" not in (run_dir / "stdout.log").read_text(encoding="utf-8")


def test_timeout_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    _patch_metadata(monkeypatch)

    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="strix", timeout=30, output="partial", stderr="late")

    monkeypatch.setattr(subprocess, "run", timeout)
    run_dir = strix_runner.run_strix(root, _config(), execute=True)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "TIMEOUT"
    assert (run_dir / "stdout.log").read_text(encoding="utf-8") == "partial"


def test_openapi_hash_and_findings_are_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    openapi = tmp_path / "openapi.yaml"
    openapi.write_text("openapi: 3.1.0\n", encoding="utf-8")
    _patch_metadata(monkeypatch)

    run_dir = strix_runner.run_strix(root, _config(openapi_path=openapi), execute=False)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    findings = json.loads((run_dir / "findings.json").read_text(encoding="utf-8"))

    assert manifest["openapi_sha256"] == strix_runner.sha256_file(openapi)
    assert findings["confirmed"] == []
    assert "--instruction-file" in manifest["sanitized_command"]
    assert str(openapi) in manifest["sanitized_command"]
    assert manifest["sanitized_command"].count("--target") == 2


def test_secret_sanitization_covers_headers_and_exact_values() -> None:
    value = "Authorization: Bearer abc123 api_key=xyz cookie=session-value direct-secret"
    sanitized = strix_runner.sanitize_text(value, ("direct-secret",))
    assert "abc123" not in sanitized
    assert "xyz" not in sanitized
    assert "session-value" not in sanitized
    assert "direct-secret" not in sanitized
