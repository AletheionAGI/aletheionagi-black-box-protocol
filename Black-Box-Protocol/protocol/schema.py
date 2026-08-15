from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class CaseOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


ALLOWED_CATEGORIES = {
    "supported_answer",
    "unsupported_claim",
    "insufficient_evidence",
    "contradictory_evidence",
    "irrelevant_evidence",
    "evidence_poisoning",
    "revoked_evidence",
    "namespace_isolation",
    "authorization_isolation",
    "fail_closed",
}


@dataclass(frozen=True)
class Evidence:
    id: str
    text: str
    namespace: str = "shared"
    authorized: bool = True
    status: str = "active"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Evidence:
        unknown = value.keys() - {"id", "text", "namespace", "authorized", "status"}
        if unknown:
            raise ValueError(f"evidence has unknown fields: {sorted(unknown)}")
        required = {"id", "text"}
        missing = required - value.keys()
        if missing:
            raise ValueError(f"evidence missing fields: {sorted(missing)}")
        status = str(value.get("status", "active"))
        if status not in {"active", "revoked"}:
            raise ValueError(f"invalid evidence status: {status}")
        return cls(
            id=str(value["id"]),
            text=str(value["text"]),
            namespace=str(value.get("namespace", "shared")),
            authorized=bool(value.get("authorized", True)),
            status=status,
        )


@dataclass(frozen=True)
class TestCase:
    __test__ = False

    id: str
    category: str
    question: str
    authorized_evidence: tuple[Evidence, ...]
    unauthorized_evidence: tuple[Evidence, ...]
    expected_behavior: tuple[str, ...]
    forbidden_behavior: tuple[str, ...]
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> TestCase:
        unknown = value.keys() - {
            "id",
            "category",
            "question",
            "authorized_evidence",
            "unauthorized_evidence",
            "expected_behavior",
            "forbidden_behavior",
            "notes",
            "metadata",
        }
        if unknown:
            raise ValueError(f"case has unknown fields: {sorted(unknown)}")
        required = {
            "id",
            "category",
            "question",
            "authorized_evidence",
            "expected_behavior",
            "forbidden_behavior",
            "notes",
        }
        missing = required - value.keys()
        if missing:
            raise ValueError(f"case missing fields: {sorted(missing)}")
        category = str(value["category"])
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"unsupported category: {category}")
        if not re.fullmatch(r"VN-[0-9]{3}", str(value["id"])):
            raise ValueError("case id must match VN-[0-9]{3}")
        authorized = tuple(Evidence.from_dict(item) for item in value["authorized_evidence"])
        unauthorized = tuple(
            Evidence.from_dict(item) for item in value.get("unauthorized_evidence", [])
        )
        if any(not item.authorized for item in authorized):
            raise ValueError("authorized_evidence cannot contain authorized=false")
        return cls(
            id=str(value["id"]),
            category=category,
            question=str(value["question"]),
            authorized_evidence=authorized,
            unauthorized_evidence=unauthorized,
            expected_behavior=tuple(map(str, value["expected_behavior"])),
            forbidden_behavior=tuple(map(str, value["forbidden_behavior"])),
            notes=str(value["notes"]),
            metadata=dict(value.get("metadata", {})),
        )


@dataclass
class TargetResult:
    raw_output: str | None = None
    delivered_answer: str | None = None
    blocked: bool | None = None
    abstained: bool | None = None
    grounded: bool | None = None
    unsupported_claim_detected: bool | None = None
    contradiction_detected: bool | None = None
    authorization_violation: bool | None = None
    unsafe_output_delivered: bool | None = None
    confidence: float | None = None
    latency_ms: float | None = None
    error: str | None = None
    raw_provider_response: dict[str, Any] | list[Any] | str | None = None
    capability_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseExecution:
    target: str
    case_id: str
    category: str
    run_number: int
    outcome: CaseOutcome
    reason: str
    result: TargetResult

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["outcome"] = self.outcome.value
        return data
