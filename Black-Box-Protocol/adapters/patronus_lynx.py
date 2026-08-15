from __future__ import annotations

import os
import time
from typing import Any

from protocol.normalization import first_value, optional_bool, optional_float
from protocol.schema import Evidence, TargetResult

from .base import BlackBoxTarget, IntegrationProfile, TargetDescriptor, env_present, run_json_command


class PatronusLynxTarget(BlackBoxTarget):
    name = "patronus_lynx"
    capabilities = frozenset({"detection", "scoring"})

    def evaluate(
        self, question: str, evidence: list[Evidence], metadata: dict[str, Any]
    ) -> TargetResult:
        candidate = str(metadata.get("candidate_answer", ""))
        payload = {
            "question": question,
            "answer": candidate,
            "context": [item.text for item in evidence],
            "case_id": metadata.get("case_id"),
            "frozen_sha256": metadata.get("frozen_sha256"),
        }
        started = time.perf_counter()
        response = run_json_command("LYNX_COMMAND", payload)
        verdict = first_value(response, "unsupported", "hallucination", "result.unsupported")
        unsupported = optional_bool(verdict)
        label = str(first_value(response, "label", "result.label") or "").lower()
        if unsupported is None and label:
            unsupported = label in {"unsupported", "contradictory", "hallucinated", "fail"}
        return TargetResult(
            raw_output=label or str(verdict),
            delivered_answer=candidate,
            blocked=None,
            abstained=None,
            grounded=None if unsupported is None else not unsupported,
            unsupported_claim_detected=unsupported,
            contradiction_detected=label == "contradictory",
            confidence=optional_float(first_value(response, "confidence", "score", "result.score")),
            latency_ms=(time.perf_counter() - started) * 1000,
            raw_provider_response=response,
            capability_notes=("detector only; it does not enforce delivery",),
        )

    def descriptor(self) -> TargetDescriptor:
        return TargetDescriptor(
            self.name,
            os.getenv("LYNX_MODEL_ID", "PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1"),
            self.capabilities,
            {
                **env_present("LYNX_COMMAND"),
                "model_id": os.getenv("LYNX_MODEL_ID", "PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1"),
                "model_license": "CC-BY-NC-4.0",
            },
            IntegrationProfile(
                dependencies=("transformers", "torch", "accelerate"),
                wrappers=("providers/lynx_local.py",),
                required_configuration=("LYNX_COMMAND", "LYNX_MODEL_ID"),
                local_model_artifact="required (8B default)",
                setup_steps=("install a compatible local inference stack", "download/load the frozen model revision"),
                notes=("no service credential is required for a fully local run",),
            ),
        )
