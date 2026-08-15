from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from protocol.normalization import first_value, optional_float
from protocol.schema import Evidence, TargetResult

from .base import BlackBoxTarget, IntegrationProfile, TargetDescriptor, TargetSkipped, env_present


class GalileoProtectTarget(BlackBoxTarget):
    name = "galileo"
    capabilities = frozenset({"detection", "enforcement", "scoring"})

    def evaluate(
        self, question: str, evidence: list[Evidence], metadata: dict[str, Any]
    ) -> TargetResult:
        key = os.getenv("GALILEO_API_KEY")
        project = os.getenv("GALILEO_PROJECT_NAME")
        stage = os.getenv("GALILEO_STAGE_NAME")
        if not key or not project or not stage:
            raise TargetSkipped("GALILEO_API_KEY, GALILEO_PROJECT_NAME and GALILEO_STAGE_NAME are required")
        context = "\n".join(f"[{item.id}] {item.text}" for item in evidence)
        candidate = str(metadata.get("candidate_answer", ""))
        body = {
            "payload": {"input": f"Question: {question}\nEvidence:\n{context}", "output": candidate},
            "project_name": project,
            "stage_name": stage,
            "metadata": {"case_id": metadata.get("case_id"), "freeze": metadata.get("frozen_sha256")},
            "timeout": 60,
        }
        base = os.getenv("GALILEO_BASE_URL", "https://api.galileo.ai").rstrip("/")
        request = urllib.request.Request(
            f"{base}/v2/protect/invoke",
            data=json.dumps(body).encode(),
            headers={"Galileo-API-Key": key, "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=70) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            return TargetResult(error=f"Galileo HTTP {exc.code}", latency_ms=(time.perf_counter() - started) * 1000)
        status = str(first_value(payload, "status", "data.status") or "").lower()
        triggered = status == "triggered"
        score = optional_float(first_value(payload, "score", "data.score", "metrics.hallucination"))
        return TargetResult(
            raw_output=str(first_value(payload, "text", "data.text") or candidate),
            delivered_answer=None if triggered else candidate,
            blocked=triggered,
            unsupported_claim_detected=triggered,
            confidence=score,
            latency_ms=(time.perf_counter() - started) * 1000,
            raw_provider_response=payload,
            capability_notes=("triggered is interpreted only for the configured hallucination stage",),
        )

    def descriptor(self) -> TargetDescriptor:
        return TargetDescriptor(
            self.name,
            "protect-v2",
            self.capabilities,
            {**env_present("GALILEO_API_KEY", "GALILEO_PROJECT_NAME", "GALILEO_STAGE_NAME"), "endpoint": "/v2/protect/invoke"},
            IntegrationProfile(
                required_secrets=("GALILEO_API_KEY",),
                required_configuration=("GALILEO_PROJECT_NAME", "GALILEO_STAGE_NAME"),
                external_services=("Galileo Protect SaaS",),
                setup_steps=("create and freeze the project, stage, rules and metrics",),
                notes=("phase-2 target; excluded from the default first-round cohort",),
            ),
        )
