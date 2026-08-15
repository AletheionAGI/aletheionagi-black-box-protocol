from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import atexit
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from protocol.schema import Evidence, TargetResult


class TargetSkipped(RuntimeError):
    """Raised when a target cannot run honestly in the current environment."""


class CaseSkipped(TargetSkipped):
    """Raised when only the current case lacks a valid measurement setup."""


@dataclass(frozen=True)
class IntegrationProfile:
    dependencies: tuple[str, ...] = ()
    wrappers: tuple[str, ...] = ()
    required_secrets: tuple[str, ...] = ()
    required_configuration: tuple[str, ...] = ()
    external_services: tuple[str, ...] = ()
    local_model_artifact: str = "none"
    setup_steps: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        values = {
            "dependencies": list(self.dependencies),
            "wrappers": list(self.wrappers),
            "required_secrets": list(self.required_secrets),
            "required_configuration": list(self.required_configuration),
            "external_services": list(self.external_services),
            "local_model_artifact": self.local_model_artifact,
            "setup_steps": list(self.setup_steps),
            "notes": list(self.notes),
        }
        values["counts"] = {
            key: len(values[key])
            for key in (
                "dependencies",
                "wrappers",
                "required_secrets",
                "required_configuration",
                "external_services",
                "setup_steps",
            )
        }
        return values


@dataclass(frozen=True)
class TargetDescriptor:
    name: str
    version: str
    capabilities: frozenset[str]
    configuration: dict[str, Any]
    integration: IntegrationProfile = field(default_factory=IntegrationProfile)


class BlackBoxTarget(ABC):
    name = "base"
    capabilities: frozenset[str] = frozenset()

    @abstractmethod
    def evaluate(
        self,
        question: str,
        evidence: list[Evidence],
        metadata: dict[str, Any],
    ) -> TargetResult:
        raise NotImplementedError

    @abstractmethod
    def descriptor(self) -> TargetDescriptor:
        raise NotImplementedError


def env_present(*names: str) -> dict[str, bool]:
    return {name: bool(os.getenv(name)) for name in names}


_PERSISTENT_COMMANDS: dict[tuple[str, ...], subprocess.Popen[str]] = {}


def _close_persistent_commands() -> None:
    for process in _PERSISTENT_COMMANDS.values():
        if process.poll() is None:
            process.terminate()
    _PERSISTENT_COMMANDS.clear()


atexit.register(_close_persistent_commands)


def _run_persistent_command(
    argv: list[str], payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    key = tuple(argv)
    process = _PERSISTENT_COMMANDS.get(key)
    if process is None or process.poll() is not None:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        _PERSISTENT_COMMANDS[key] = process
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    readable, _, _ = select.select([process.stdout], [], [], timeout)
    if not readable:
        process.terminate()
        _PERSISTENT_COMMANDS.pop(key, None)
        raise subprocess.TimeoutExpired(argv, timeout)
    line = process.stdout.readline()
    if not line:
        returncode = process.wait()
        _PERSISTENT_COMMANDS.pop(key, None)
        raise RuntimeError(f"adapter command exited {returncode} without a response")
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeError("adapter command did not return one JSON object per line") from exc
    if not isinstance(value, dict):
        raise RuntimeError("adapter command response must be a JSON object")
    if value.get("error"):
        raise RuntimeError(f"adapter provider error: {value['error']}")
    return value


def run_json_command(command_env: str, payload: dict[str, Any], timeout: float = 900) -> dict[str, Any]:
    command = os.getenv(command_env)
    if not command:
        raise TargetSkipped(f"{command_env} is not configured")
    argv = shlex.split(command)
    if "--serve" in argv:
        return _run_persistent_command(argv, payload, timeout)
    completed = subprocess.run(
        argv,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"adapter command exited {completed.returncode}; provider stderr was not persisted")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("adapter command did not return one JSON object") from exc
    if not isinstance(value, dict):
        raise RuntimeError("adapter command response must be a JSON object")
    return value
