from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "1.0.0"
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Config:
    protocol_version: str
    base_url: str
    tested_release: str
    namespace_id: str
    attempts_per_organization: int
    timeout_seconds: float = 40.0
    poll_interval_seconds: float = 2.0
    poll_timeout_seconds: float = 90.0
    top_k: int = 5
    acknowledge_synthetic_data_only: bool = False
    acknowledge_credit_usage: bool = False
    manual_results: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Config:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("configuration must be a JSON object")
        raw.pop("$schema", None)
        allowed = set(cls.__dataclass_fields__)
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"unknown configuration fields: {', '.join(unknown)}")
        try:
            config = cls(**raw)
        except TypeError as error:
            raise ValueError(f"invalid configuration: {error}") from error
        config.validate()
        return config

    def validate(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(f"protocol_version must be {PROTOCOL_VERSION}")
        if not self.base_url.startswith("https://") or self.base_url.rstrip("/").count("/") != 2:
            raise ValueError("base_url must be an HTTPS origin without a path")
        if not self.tested_release.strip():
            raise ValueError("tested_release is required")
        if not _STABLE_ID.fullmatch(self.namespace_id):
            raise ValueError("namespace_id is not a valid public stable identifier")
        if not 10 <= self.attempts_per_organization <= 100:
            raise ValueError("attempts_per_organization must be between 10 and 100")
        if not 5 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 5 and 120")
        if not 0.25 <= self.poll_interval_seconds <= 30:
            raise ValueError("poll_interval_seconds must be between 0.25 and 30")
        if not 10 <= self.poll_timeout_seconds <= 600:
            raise ValueError("poll_timeout_seconds must be between 10 and 600")
        if not 1 <= self.top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        unknown_manual = sorted(set(self.manual_results) - {"BB-02", "BB-10"})
        if unknown_manual:
            raise ValueError(f"unknown manual cases: {', '.join(unknown_manual)}")
        for case_id, outcome in self.manual_results.items():
            if outcome not in Outcome:
                raise ValueError(f"manual result {case_id} must be PASS, FAIL or INCONCLUSIVE")

    @property
    def estimated_grounding_requests(self) -> int:
        return self.attempts_per_organization * 2 + 7

    @property
    def estimated_credit_units(self) -> int:
        return self.attempts_per_organization * 2 + 4

    def sanitized(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Exchange:
    method: str
    path: str
    status: int | None
    duration_ms: int
    correlation_id: str | None
    request_body: Any
    response_body: Any
    transport_error: str | None = None


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    name: str
    outcome: Outcome
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["outcome"] = self.outcome.value
        return value


def aggregate_outcome(cases: list[CaseResult]) -> Outcome:
    if any(case.outcome is Outcome.FAIL for case in cases):
        return Outcome.FAIL
    if any(case.outcome is Outcome.INCONCLUSIVE for case in cases):
        return Outcome.INCONCLUSIVE
    return Outcome.PASS
