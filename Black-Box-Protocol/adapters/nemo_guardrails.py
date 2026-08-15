from __future__ import annotations

import os
import time
from typing import Any

from protocol.normalization import first_value, optional_bool, optional_float
from protocol.schema import Evidence, TargetResult

from .base import BlackBoxTarget, IntegrationProfile, TargetDescriptor, env_present, run_json_command


class NeMoGuardrailsTarget(BlackBoxTarget):
    name = "nemo_guardrails"
    capabilities = frozenset({"detection", "enforcement", "scoring"})

    def evaluate(
        self, question: str, evidence: list[Evidence], metadata: dict[str, Any]
    ) -> TargetResult:
        candidate = str(metadata.get("candidate_answer", ""))
        started = time.perf_counter()
        response = run_json_command(
            "NEMO_GUARDRAILS_COMMAND",
            {
                "question": question,
                "response": candidate,
                "relevant_chunks": [item.text for item in evidence],
                "case_id": metadata.get("case_id"),
                "frozen_sha256": metadata.get("frozen_sha256"),
            },
        )
        accuracy = optional_float(first_value(response, "accuracy", "score", "result.accuracy"))
        blocked = optional_bool(first_value(response, "blocked", "result.blocked"))
        if blocked is None and accuracy is not None:
            blocked = accuracy < float(os.getenv("NEMO_FACT_CHECK_THRESHOLD", "0.5"))
        return TargetResult(
            raw_output=str(first_value(response, "output", "result.output") or ""),
            delivered_answer=None if blocked else candidate,
            blocked=blocked,
            abstained=optional_bool(first_value(response, "abstained", "result.abstained")),
            grounded=None if accuracy is None else accuracy >= float(os.getenv("NEMO_FACT_CHECK_THRESHOLD", "0.5")),
            unsupported_claim_detected=blocked,
            confidence=accuracy,
            latency_ms=(time.perf_counter() - started) * 1000,
            raw_provider_response=response,
            capability_notes=("uses the configured fact-checking rail and its pre-frozen threshold",),
        )

    def descriptor(self) -> TargetDescriptor:
        return TargetDescriptor(
            self.name,
            os.getenv("NEMO_GUARDRAILS_VERSION", "local-command"),
            self.capabilities,
            {
                **env_present("NEMO_GUARDRAILS_COMMAND"),
                "fact_check_threshold": float(os.getenv("NEMO_FACT_CHECK_THRESHOLD", "0.5")),
            },
            IntegrationProfile(
                dependencies=("nemoguardrails", "configured LLM backend"),
                wrappers=("local NeMo command-contract wrapper",),
                required_secrets=("NVIDIA_API_KEY",),
                required_configuration=(
                    "NEMO_GUARDRAILS_COMMAND",
                    "NEMO_FACT_CHECK_THRESHOLD",
                    "NeMo rails config",
                ),
                external_services=("LLM backend when the selected rail is not fully local",),
                local_model_artifact="none (NVIDIA API backend)",
                setup_steps=("configure and freeze the fact-checking rail",),
            ),
        )
