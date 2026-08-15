from __future__ import annotations

from typing import Any

from protocol.schema import Evidence, TargetResult

from .base import BlackBoxTarget, IntegrationProfile, TargetDescriptor


class FakeTarget(BlackBoxTarget):
    name = "fake"
    capabilities = frozenset(
        {"detection", "enforcement", "grounding", "authorization", "namespace_isolation", "evidence_lifecycle"}
    )

    def evaluate(
        self, question: str, evidence: list[Evidence], metadata: dict[str, Any]
    ) -> TargetResult:
        signal = metadata.get("fake_signal", "unsupported")
        answer = metadata.get("candidate_answer")
        if signal == "supported":
            return TargetResult(
                raw_output=str(answer),
                delivered_answer=str(answer),
                blocked=False,
                abstained=False,
                grounded=True,
                unsupported_claim_detected=False,
                authorization_violation=False,
                confidence=1.0,
            )
        if signal == "contradiction":
            return TargetResult(
                raw_output="conflicting evidence",
                blocked=True,
                abstained=True,
                grounded=False,
                contradiction_detected=True,
                authorization_violation=False,
                confidence=1.0,
            )
        if signal == "authorized":
            return TargetResult(grounded=False, authorization_violation=False, confidence=1.0)
        return TargetResult(
            raw_output="unsupported",
            blocked=True,
            abstained=True,
            grounded=False,
            unsupported_claim_detected=True,
            authorization_violation=False,
            confidence=1.0,
        )

    def descriptor(self) -> TargetDescriptor:
        return TargetDescriptor(
            self.name,
            "deterministic-1",
            self.capabilities,
            {},
            IntegrationProfile(notes=("test-only target; excluded from competitive reports",)),
        )
