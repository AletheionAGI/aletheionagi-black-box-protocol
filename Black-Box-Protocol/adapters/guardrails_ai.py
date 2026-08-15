from __future__ import annotations

import os
import time
from typing import Any

from protocol.normalization import first_value, optional_bool, optional_float
from protocol.schema import Evidence, TargetResult

from .base import BlackBoxTarget, IntegrationProfile, TargetDescriptor, env_present, run_json_command


class GuardrailsAITarget(BlackBoxTarget):
    name = "guardrails_ai"
    capabilities = frozenset({"detection", "validation", "scoring"})

    def evaluate(
        self, question: str, evidence: list[Evidence], metadata: dict[str, Any]
    ) -> TargetResult:
        candidate = str(metadata.get("candidate_answer", ""))
        started = time.perf_counter()
        response = run_json_command(
            "GUARDRAILS_AI_COMMAND",
            {
                "question": question,
                "answer": candidate,
                "context": [item.text for item in evidence],
                "case_id": metadata.get("case_id"),
                "frozen_sha256": metadata.get("frozen_sha256"),
            },
        )
        valid = optional_bool(first_value(response, "valid", "validation_passed", "result.valid"))
        return TargetResult(
            raw_output=str(first_value(response, "output", "result.output") or ""),
            delivered_answer=candidate,
            blocked=None,
            grounded=valid,
            unsupported_claim_detected=None if valid is None else not valid,
            confidence=optional_float(first_value(response, "confidence", "score", "result.score")),
            latency_ms=(time.perf_counter() - started) * 1000,
            raw_provider_response=response,
            capability_notes=("validator only; it does not enforce delivery",),
        )

    def descriptor(self) -> TargetDescriptor:
        return TargetDescriptor(
            self.name,
            os.getenv("GUARDRAILS_AI_VALIDATOR", "provenance-nli/local-command"),
            self.capabilities,
            {
                **env_present("GUARDRAILS_AI_COMMAND"),
                "validator": os.getenv("GUARDRAILS_AI_VALIDATOR", "provenance-nli/local-command"),
            },
            IntegrationProfile(
                dependencies=("guardrails-ai", "selected validator package"),
                wrappers=("providers/guardrails_ai_local.py",),
                required_configuration=("GUARDRAILS_AI_COMMAND", "GUARDRAILS_AI_VALIDATOR"),
                local_model_artifact="microsoft/Phi-3.5-mini-instruct plus GroundedAI adapter",
                setup_steps=("install and freeze the selected validator and its threshold",),
            ),
        )
