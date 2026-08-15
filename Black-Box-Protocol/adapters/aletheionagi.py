from __future__ import annotations

import json
import os
import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from protocol.normalization import first_value, optional_bool
from protocol.schema import Evidence, TargetResult

from .base import CaseSkipped, BlackBoxTarget, IntegrationProfile, TargetDescriptor, TargetSkipped, env_present


class AletheionAGITarget(BlackBoxTarget):
    name = "aletheionagi"
    capabilities = frozenset(
        {"enforcement", "grounding", "authorization", "namespace_isolation", "evidence_lifecycle"}
    )

    def evaluate(
        self, question: str, evidence: list[Evidence], metadata: dict[str, Any]
    ) -> TargetResult:
        key = os.getenv("ALETHEION_API_KEY")
        frozen = os.getenv("ALETHEION_CORPUS_FROZEN_SHA256")
        provisioning_path = os.getenv("ALETHEION_PROVISIONING_MANIFEST")
        expected_frozen = str(metadata.get("frozen_sha256", ""))
        if not key:
            raise TargetSkipped("ALETHEION_API_KEY is required")
        if not frozen or frozen != expected_frozen:
            raise TargetSkipped("Aletheion corpus attestation does not match the frozen case manifest")
        if not provisioning_path:
            raise TargetSkipped("ALETHEION_PROVISIONING_MANIFEST is required")
        provisioned = self._provisioned_case(provisioning_path, metadata, evidence, frozen)
        if metadata.get("category") == "authorization_isolation" and not provisioned.get(
            "authorization_control_verified"
        ):
            raise CaseSkipped("authorization case lacks a verified requester/label denial policy")
        namespace = provisioned["namespace_id"]
        base = os.getenv("ALETHEION_BASE_URL", "https://api.aletheionagi.com").rstrip("/")
        body = json.dumps({"input": question, "namespace_id": namespace, "top_k": 8}).encode()
        request = urllib.request.Request(
            f"{base}/v1/ground",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        payload = None
        last_error: str | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = json.loads(response.read().decode())
                break
            except urllib.error.HTTPError as exc:
                last_error = f"Aletheion HTTP {exc.code}"
                if exc.code != 429 and exc.code < 500:
                    break
            except urllib.error.URLError as exc:
                last_error = f"Aletheion network error: {exc.reason}"
            if attempt < 2:
                time.sleep(2**attempt)
        if payload is None:
            return TargetResult(
                error=last_error or "Aletheion request failed",
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        answer = first_value(payload, "grounded_answer", "answer", "output", "data.answer")
        decision = str(first_value(payload, "grounding_action", "decision", "status", "data.decision") or "").lower()
        blocked = decision in {"block", "blocked", "reject", "rejected"}
        abstained = decision in {"abstain", "abstained"}
        grounded = optional_bool(first_value(payload, "grounded", "data.grounded"))
        if grounded is None:
            grounded = decision == "deliver" and bool(answer)
            if blocked or abstained:
                grounded = False
        serialized = json.dumps(payload, sort_keys=True)
        forbidden_texts = [
            str(item.get("text", ""))
            for item in metadata.get("unauthorized_evidence", [])
            if item.get("text")
        ]
        authorization_violation = None
        if metadata.get("category") in {"authorization_isolation", "namespace_isolation"}:
            authorization_violation = any(text in serialized for text in forbidden_texts)
        markers = [str(item) for item in metadata.get("forbidden_output_markers", [])]
        unsafe_output_delivered = (
            any(marker.casefold() in str(answer or "").casefold() for marker in markers)
            if markers
            else None
        )
        contradiction_detected = None
        if metadata.get("category") == "contradictory_evidence":
            answer_text = str(answer or "").casefold()
            contradiction_detected = len(evidence) > 1 and all(
                item.text.casefold() in answer_text for item in evidence
            )
        return TargetResult(
            raw_output=str(answer) if answer is not None else None,
            delivered_answer=str(answer) if answer and not (blocked or abstained) else None,
            blocked=blocked,
            abstained=abstained,
            grounded=grounded,
            unsupported_claim_detected=blocked or abstained,
            contradiction_detected=contradiction_detected,
            authorization_violation=authorization_violation,
            unsafe_output_delivered=unsafe_output_delivered,
            latency_ms=(time.perf_counter() - started) * 1000,
            raw_provider_response=payload,
            capability_notes=("case namespace and evidence inventory verified against provisioning manifest",),
        )

    @staticmethod
    def _provisioned_case(
        manifest_path: str,
        metadata: dict[str, Any],
        evidence: list[Evidence],
        frozen_sha256: str,
    ) -> dict[str, Any]:
        try:
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TargetSkipped(f"invalid Aletheion provisioning manifest: {exc}") from exc
        if manifest.get("frozen_sha256") != frozen_sha256:
            raise TargetSkipped("provisioning manifest does not attest the frozen corpus")
        case_id = str(metadata.get("case_id", ""))
        provisioned = manifest.get("cases", {}).get(case_id)
        if not isinstance(provisioned, dict) or not provisioned.get("namespace_id"):
            raise TargetSkipped(f"provisioning manifest has no namespace for {case_id}")
        expected = _evidence_digest(evidence)
        if provisioned.get("authorized_evidence_sha256") != expected:
            raise TargetSkipped(f"provisioned authorized evidence does not match {case_id}")
        forbidden = metadata.get("unauthorized_evidence", [])
        if provisioned.get("unauthorized_evidence_sha256") != _raw_evidence_digest(forbidden):
            raise TargetSkipped(f"provisioned unauthorized evidence does not match {case_id}")
        if metadata.get("category") in {"namespace_isolation", "authorization_isolation"}:
            if not provisioned.get("isolation_control"):
                raise TargetSkipped(f"{case_id} lacks an explicit isolation control attestation")
        return provisioned

    def descriptor(self) -> TargetDescriptor:
        return TargetDescriptor(
            self.name,
            os.getenv("ALETHEION_RELEASE", "public-api-v1"),
            self.capabilities,
            env_present("ALETHEION_API_KEY", "ALETHEION_PROVISIONING_MANIFEST", "ALETHEION_CORPUS_FROZEN_SHA256"),
            IntegrationProfile(
                required_secrets=("ALETHEION_API_KEY",),
                required_configuration=(
                    "ALETHEION_PROVISIONING_MANIFEST",
                    "ALETHEION_CORPUS_FROZEN_SHA256",
                ),
                external_services=("AletheionAGI public Grounding API",),
                setup_steps=("provision every frozen case and record its namespace/evidence digests in the manifest",),
            ),
        )


def _raw_evidence_digest(items: list[Any]) -> str:
    normalized = [
        {key: item.get(key) for key in ("id", "text", "namespace", "authorized", "status")}
        for item in items
        if isinstance(item, dict)
    ]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _evidence_digest(items: list[Evidence]) -> str:
    return _raw_evidence_digest([
        {"id": item.id, "text": item.text, "namespace": item.namespace, "authorized": item.authorized, "status": item.status}
        for item in items
    ])
