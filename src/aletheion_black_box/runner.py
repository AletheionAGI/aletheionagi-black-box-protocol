from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .client import ApiClient, error_code
from .evidence import EvidenceWriter
from .models import CaseResult, Config, Exchange, Outcome, aggregate_outcome

CASE_NAMES = {
    "BB-01": "Public readiness",
    "BB-02": "Workspace identity",
    "BB-03": "Colliding writes and idempotency",
    "BB-04": "Cross-organization grounding collision",
    "BB-05": "Unauthorized namespace",
    "BB-06": "Correction",
    "BB-07": "Completed query ID reuse",
    "BB-08": "Metering isolation",
    "BB-09": "Deletion and no-evidence grounding",
    "BB-10": "API-key revocation",
    "BB-11": "Cleanup",
}


class ProtocolRunner:
    def __init__(
        self,
        config: Config,
        api_key_a: str,
        api_key_b: str,
        output_root: Path,
        *,
        client: ApiClient | None = None,
    ) -> None:
        if not api_key_a or not api_key_b:
            raise ValueError("both organization API keys are required")
        if api_key_a == api_key_b:
            raise ValueError("organization A and B must use different API keys")
        self.config = config
        self.keys = {"A": api_key_a, "B": api_key_b}
        self.client = client or ApiClient(config.base_url, config.timeout_seconds)
        self.run_uuid = str(uuid.uuid4())
        self.run_id = f"bbp:{self.run_uuid}"
        self.memory_id = f"poc:shared-fact:{self.run_uuid}"
        self.source_id = "poc:evaluator"
        self.canaries = {
            "A": f"ORANGE-{uuid.uuid4()}",
            "B": f"VIOLET-{uuid.uuid4()}",
            "A_CORRECTED": f"AMBER-{uuid.uuid4()}",
        }
        self.writer = EvidenceWriter(
            output_root / self.run_id.replace(":", "-"), tuple(self.keys.values())
        )
        self.cases: dict[str, CaseResult] = {}
        self.deleted = {"A": False, "B": False}
        self.halt_for_foreign_canary = False

    def run(self) -> tuple[Outcome, Path]:
        started_at = datetime.now(UTC).isoformat()
        try:
            self._run_readiness()
            self._manual_case("BB-02")
            self._run_writes()
            if not self.halt_for_foreign_canary:
                self._run_collision()
            if not self.halt_for_foreign_canary:
                self._run_unauthorized_namespace()
                self._run_correction()
                self._run_replay_and_metering()
                self._run_deletion_and_no_evidence()
            self._manual_case("BB-10")
        finally:
            self._run_cleanup()
        for case_id, name in CASE_NAMES.items():
            self.cases.setdefault(
                case_id,
                CaseResult(
                    case_id,
                    name,
                    Outcome.INCONCLUSIVE,
                    "case was not completed because the run stopped earlier",
                ),
            )
        cases = [self.cases[case_id] for case_id in sorted(self.cases)]
        overall = aggregate_outcome(cases)
        finished_at = datetime.now(UTC).isoformat()
        self.writer.finalize(
            config=self.config,
            run_id=self.run_id,
            started_at=started_at,
            finished_at=finished_at,
            cases=cases,
            overall=overall,
            canaries=self.canaries,
        )
        return overall, self.writer.directory

    def _send(
        self,
        organization: str,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        authenticated: bool = True,
    ) -> Exchange:
        exchange = self.client.request(
            method,
            path,
            api_key=self.keys.get(organization) if authenticated else None,
            body=body,
            idempotency_key=idempotency_key,
        )
        self.writer.exchange(organization, exchange)
        return exchange

    def _result(
        self,
        case_id: str,
        outcome: Outcome,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.cases[case_id] = CaseResult(
            case_id, CASE_NAMES[case_id], outcome, reason, details or {}
        )

    def _manual_case(self, case_id: str) -> None:
        raw = self.config.manual_results.get(case_id, Outcome.INCONCLUSIVE.value)
        outcome = Outcome(raw)
        reason = (
            "operator recorded the manual checklist as PASS"
            if outcome is Outcome.PASS
            else "manual checklist reported a prohibited observation"
            if outcome is Outcome.FAIL
            else "manual checklist and sanitized evidence are not complete"
        )
        self._result(case_id, outcome, reason)

    def _run_readiness(self) -> None:
        health = self._send("PUBLIC", "GET", "/v1/health", authenticated=False)
        ready = self._send("PUBLIC", "GET", "/v1/ready", authenticated=False)
        if health.status == ready.status == 200:
            self._result(
                "BB-01",
                Outcome.PASS,
                "health and readiness returned HTTP 200",
                {"health_ms": health.duration_ms, "ready_ms": ready.duration_ms},
            )
        else:
            self._result(
                "BB-01",
                Outcome.INCONCLUSIVE,
                "health or readiness was unavailable",
                {"health_status": health.status, "ready_status": ready.status},
            )

    def _memory_body(self, organization: str, canary: str | None = None) -> dict[str, Any]:
        marker = canary or self.canaries[organization]
        return {
            "memory_id": self.memory_id,
            "namespace_id": self.config.namespace_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "content": f"The exact synthetic evaluation marker is {marker}",
            "content_type": "text/plain",
            "source_id": self.source_id,
            "authorization_labels": [],
            "metadata": {"protocol": self.config.protocol_version, "run_id": self.run_id},
        }

    def _run_writes(self) -> None:
        bodies = {organization: self._memory_body(organization) for organization in ("A", "B")}
        writes: dict[str, Exchange] = {}
        for organization in ("A", "B"):
            writes[organization] = self._send(
                organization,
                "POST",
                "/v1/memories",
                body=bodies[organization],
                idempotency_key=f"bbp:{self.run_uuid}:write:{organization}",
            )
        if any(exchange.status != 202 for exchange in writes.values()):
            self._result(
                "BB-03",
                Outcome.INCONCLUSIVE,
                "one or both initial writes were not accepted",
                {key: value.status for key, value in writes.items()},
            )
            return
        indexed: dict[str, Exchange | None] = {
            organization: self._wait_for_indexed(organization) for organization in ("A", "B")
        }
        for organization, exchange in indexed.items():
            if exchange is not None and self._contains_foreign(exchange, organization):
                self.halt_for_foreign_canary = True
                self._result(
                    "BB-03",
                    Outcome.FAIL,
                    f"Organization {organization} read the foreign canary after its write",
                )
                return
        if any(exchange is None for exchange in indexed.values()):
            self._result(
                "BB-03", Outcome.INCONCLUSIVE, "one or both memories did not reach indexed"
            )
            return
        original_revision = _field(writes["A"].response_body, "revision")
        retry = self._send(
            "A",
            "POST",
            "/v1/memories",
            body=bodies["A"],
            idempotency_key=f"bbp:{self.run_uuid}:write:A",
        )
        changed_body = {**bodies["A"], "content": "Changed replay must be rejected"}
        conflict = self._send(
            "A",
            "POST",
            "/v1/memories",
            body=changed_body,
            idempotency_key=f"bbp:{self.run_uuid}:write:A",
        )
        retry_revision = _field(retry.response_body, "revision")
        if (
            retry.status == 202
            and retry_revision == original_revision
            and conflict.status == 409
            and error_code(conflict) == "idempotency_conflict"
        ):
            self._result(
                "BB-03",
                Outcome.PASS,
                "colliding memories indexed independently and idempotency behavior matched",
                {"revision": original_revision},
            )
        else:
            self._result(
                "BB-03",
                Outcome.FAIL,
                "idempotency retry or conflict behavior violated the protocol",
                {
                    "retry_status": retry.status,
                    "original_revision": original_revision,
                    "retry_revision": retry_revision,
                    "conflict_status": conflict.status,
                    "conflict_code": error_code(conflict),
                },
            )

    def _wait_for_indexed(self, organization: str) -> Exchange | None:
        deadline = time.monotonic() + self.config.poll_timeout_seconds
        while time.monotonic() < deadline:
            exchange = self._send(organization, "GET", f"/v1/memories/{self.memory_id}")
            if exchange.status == 200 and _field(exchange.response_body, "state") == "indexed":
                return exchange
            if exchange.status == 200 and _field(exchange.response_body, "state") == "failed":
                return None
            if exchange.status is None or (exchange.status is not None and exchange.status >= 500):
                return None
            time.sleep(self.config.poll_interval_seconds)
        return None

    def _ground_body(self, query_id: str, question: str | None = None) -> dict[str, Any]:
        return {
            "namespace_id": self.config.namespace_id,
            "input": question
            or "What exact synthetic evaluation marker is stored in trusted memory?",
            "query_id": query_id,
            "asked_at": datetime.now(UTC).isoformat(),
            "top_k": self.config.top_k,
        }

    def _run_collision(self) -> None:
        pass_count = 0
        inconclusive_count = 0
        utility_failures = 0
        for organization in ("A", "B"):
            for attempt in range(1, self.config.attempts_per_organization + 1):
                exchange = self._send(
                    organization,
                    "POST",
                    "/v1/ground",
                    body=self._ground_body(
                        f"query:{self.run_uuid}:collision:{organization}:{attempt}"
                    ),
                )
                outcome, reason = classify_positive_ground(
                    exchange,
                    permitted_canary=self.canaries[organization],
                    forbidden_canary=self.canaries["B" if organization == "A" else "A"],
                    memory_id=self.memory_id,
                )
                if outcome is Outcome.FAIL and reason.startswith("foreign canary"):
                    self.halt_for_foreign_canary = True
                    self._result(
                        "BB-04",
                        Outcome.FAIL,
                        "foreign canary observed in "
                        f"Organization {organization}, attempt {attempt}",
                        {
                            "completed_attempts": pass_count
                            + inconclusive_count
                            + utility_failures
                            + 1
                        },
                    )
                    return
                if outcome is Outcome.PASS:
                    pass_count += 1
                elif outcome is Outcome.INCONCLUSIVE:
                    inconclusive_count += 1
                else:
                    utility_failures += 1
        details = {
            "expected_attempts": self.config.attempts_per_organization * 2,
            "passed": pass_count,
            "inconclusive": inconclusive_count,
            "utility_failures": utility_failures,
            "foreign_canary_occurrences": 0,
        }
        if inconclusive_count:
            self._result(
                "BB-04",
                Outcome.INCONCLUSIVE,
                "one or more grounding attempts were unavailable",
                details,
            )
        elif utility_failures:
            self._result(
                "BB-04",
                Outcome.FAIL,
                "one or more positive grounding attempts failed utility",
                details,
            )
        else:
            self._result(
                "BB-04",
                Outcome.PASS,
                "all attempts returned only the permitted canary with complete citations",
                details,
            )

    def _run_unauthorized_namespace(self) -> None:
        body = self._ground_body(f"query:{self.run_uuid}:unauthorized")
        body["namespace_id"] = f"poc:unauthorized:{uuid.uuid4()}"
        exchange = self._send("A", "POST", "/v1/ground", body=body)
        serialized = _serialized(exchange.response_body)
        if any(canary in serialized for canary in self.canaries.values()):
            self._result("BB-05", Outcome.FAIL, "unauthorized response disclosed a run canary")
        elif exchange.status in {403, 404}:
            self._result("BB-05", Outcome.PASS, "unauthorized namespace failed closed")
        elif exchange.status is None or (exchange.status is not None and exchange.status >= 500):
            self._result("BB-05", Outcome.INCONCLUSIVE, "request failed operationally")
        else:
            self._result(
                "BB-05",
                Outcome.FAIL,
                "unauthorized namespace did not return a generic denial",
                {"status": exchange.status},
            )

    def _run_correction(self) -> None:
        old_canary = self.canaries["A"]
        corrected = self.canaries["A_CORRECTED"]
        write = self._send(
            "A",
            "POST",
            "/v1/memories",
            body=self._memory_body("A", corrected),
            idempotency_key=f"bbp:{self.run_uuid}:correction:A",
        )
        indexed = self._wait_for_indexed("A") if write.status == 202 else None
        if indexed is None:
            self._result("BB-06", Outcome.INCONCLUSIVE, "corrected revision did not index")
            return
        exchange = self._send(
            "A",
            "POST",
            "/v1/ground",
            body=self._ground_body(f"query:{self.run_uuid}:correction"),
        )
        serialized = _serialized(exchange.response_body)
        if old_canary in serialized or self.canaries["B"] in serialized:
            self._result(
                "BB-06", Outcome.FAIL, "obsolete or foreign canary appeared after correction"
            )
        elif exchange.status != 200:
            self._result("BB-06", Outcome.INCONCLUSIVE, "corrected value could not be grounded")
        elif corrected not in _serialized(_field(exchange.response_body, "grounded_answer")):
            self._result("BB-06", Outcome.FAIL, "corrected canary was not delivered")
        else:
            self._result("BB-06", Outcome.PASS, "only the corrected canary was delivered")

    def _run_replay_and_metering(self) -> None:
        before_a = self._send("A", "GET", "/v1/usage/credits")
        before_b = self._send("B", "GET", "/v1/usage/credits")
        query_id = f"query:{self.run_uuid}:replay"
        body = self._ground_body(query_id)
        initial = self._send("A", "POST", "/v1/ground", body=body)
        exact = self._send("A", "POST", "/v1/ground", body=body)
        changed = self._send(
            "A",
            "POST",
            "/v1/ground",
            body={**body, "input": "A changed question must not execute."},
        )
        if (
            initial.status == 200
            and exact.status == changed.status == 409
            and error_code(exact) == error_code(changed) == "idempotency_replay_unavailable"
        ):
            self._result("BB-07", Outcome.PASS, "both completed query ID reuses were rejected")
        elif initial.status is None or (initial.status is not None and initial.status >= 500):
            self._result("BB-07", Outcome.INCONCLUSIVE, "initial query failed operationally")
        else:
            self._result(
                "BB-07",
                Outcome.FAIL,
                "completed query ID reuse did not match the 409 contract",
                {
                    "initial_status": initial.status,
                    "exact_status": exact.status,
                    "changed_status": changed.status,
                    "exact_code": error_code(exact),
                    "changed_code": error_code(changed),
                },
            )
        after_a = self._send("A", "GET", "/v1/usage/credits")
        after_b = self._send("B", "GET", "/v1/usage/credits")
        consumed = [
            _field(before_a.response_body, "consumed"),
            _field(after_a.response_body, "consumed"),
            _field(before_b.response_body, "consumed"),
            _field(after_b.response_body, "consumed"),
        ]
        if any(not isinstance(value, int) for value in consumed):
            self._result("BB-08", Outcome.INCONCLUSIVE, "credit balances were unavailable")
            return
        a_before, a_after, b_before, b_after = consumed
        details = {
            "a_before": a_before,
            "a_after": a_after,
            "b_before": b_before,
            "b_after": b_after,
        }
        if a_after - a_before == 1 and b_after == b_before:
            self._result(
                "BB-08", Outcome.PASS, "one A credit was consumed and B was unchanged", details
            )
        else:
            self._result(
                "BB-08", Outcome.FAIL, "credit attribution did not match the protocol", details
            )

    def _run_deletion_and_no_evidence(self) -> None:
        deletion_ok = True
        for organization in ("A", "B"):
            deleted = self._delete(organization)
            self.deleted[organization] = deleted
            deletion_ok = deletion_ok and deleted
        if not deletion_ok:
            self._result("BB-09", Outcome.INCONCLUSIVE, "deletion could not be confirmed")
            return
        for organization in ("A", "B"):
            exchange = self._send(
                organization,
                "POST",
                "/v1/ground",
                body=self._ground_body(f"query:{self.run_uuid}:empty:{organization}"),
            )
            serialized = _serialized(exchange.response_body)
            if any(canary in serialized for canary in self.canaries.values()):
                self._result("BB-09", Outcome.FAIL, "a deleted run canary reappeared")
                return
            if exchange.status != 200:
                self._result(
                    "BB-09", Outcome.INCONCLUSIVE, "post-deletion grounding was unavailable"
                )
                return
            if _field(exchange.response_body, "grounding_action") not in {"block", "abstain"}:
                self._result(
                    "BB-09", Outcome.FAIL, "no-evidence grounding did not block or abstain"
                )
                return
        self._result(
            "BB-09", Outcome.PASS, "deleted canaries stayed absent and both calls failed closed"
        )

    def _delete(self, organization: str) -> bool:
        exchange = self._send(
            organization,
            "DELETE",
            f"/v1/memories/{self.memory_id}",
            idempotency_key=f"bbp:{self.run_uuid}:delete:{organization}",
        )
        if exchange.status not in {200, 404}:
            return False
        check = self._send(organization, "GET", f"/v1/memories/{self.memory_id}")
        return check.status == 404 or (
            check.status == 200 and _field(check.response_body, "state") == "deleted"
        )

    def _run_cleanup(self) -> None:
        results: dict[str, bool] = {}
        for organization in ("A", "B"):
            results[organization] = self.deleted[organization] or self._delete(organization)
            self.deleted[organization] = results[organization]
        if all(results.values()):
            self._result("BB-11", Outcome.PASS, "test memories are deleted in both organizations")
        else:
            self._result("BB-11", Outcome.INCONCLUSIVE, "cleanup could not be confirmed", results)

    def _contains_foreign(self, exchange: Exchange, organization: str) -> bool:
        foreign = self.canaries["B" if organization == "A" else "A"]
        return foreign in _serialized(exchange.response_body)


def classify_positive_ground(
    exchange: Exchange,
    *,
    permitted_canary: str,
    forbidden_canary: str,
    memory_id: str,
) -> tuple[Outcome, str]:
    serialized = _serialized(exchange.response_body)
    if forbidden_canary in serialized:
        return Outcome.FAIL, "foreign canary appeared anywhere in the response"
    if exchange.status is None or (exchange.status is not None and exchange.status >= 500):
        return Outcome.INCONCLUSIVE, "grounding failed operationally"
    if exchange.status != 200:
        return Outcome.INCONCLUSIVE, f"grounding returned HTTP {exchange.status}"
    body = exchange.response_body
    if _field(body, "grounding_action") != "deliver":
        return Outcome.FAIL, "positive grounding did not deliver"
    answer = _field(body, "grounded_answer")
    if permitted_canary not in _serialized(answer):
        return Outcome.FAIL, "permitted canary was absent from the grounded answer"
    evidence = _field(_field(body, "evidence"), "evidence")
    if not isinstance(evidence, list):
        return Outcome.FAIL, "evidence list was absent"
    evidence_ids = {
        item.get("memory_id")
        for item in evidence
        if isinstance(item, dict) and item.get("memory_id")
    }
    if memory_id not in evidence_ids:
        return Outcome.FAIL, "expected memory was absent from disclosed evidence"
    claims = _field(body, "claims")
    if not isinstance(claims, list) or not claims:
        return Outcome.FAIL, "delivered answer had no claims"
    for claim in claims:
        cited = claim.get("cited_memory_ids") if isinstance(claim, dict) else None
        if not isinstance(cited, list) or not cited or not set(cited).issubset(evidence_ids):
            return Outcome.FAIL, "claim citations were incomplete or undisclosed"
    return Outcome.PASS, "permitted canary was delivered with disclosed evidence"


def _field(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, dict) else None


def _serialized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False) if value is not None else ""
