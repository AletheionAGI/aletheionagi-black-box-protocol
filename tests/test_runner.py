from __future__ import annotations

import unittest

from aletheion_black_box.models import Exchange, Outcome
from aletheion_black_box.runner import classify_positive_ground


def exchange(body: object, status: int = 200) -> Exchange:
    return Exchange("POST", "/v1/ground", status, 10, "correlation:test", {}, body)


class GroundClassificationTests(unittest.TestCase):
    def test_passes_delivered_canary_with_disclosed_citation(self) -> None:
        body = {
            "grounding_action": "deliver",
            "grounded_answer": "Marker ORANGE-safe",
            "evidence": {"evidence": [{"memory_id": "memory:test", "content": "ORANGE-safe"}]},
            "claims": [{"text": "ORANGE-safe", "cited_memory_ids": ["memory:test"]}],
        }
        result, _ = classify_positive_ground(
            exchange(body),
            permitted_canary="ORANGE-safe",
            forbidden_canary="VIOLET-forbidden",
            memory_id="memory:test",
        )
        self.assertIs(result, Outcome.PASS)

    def test_foreign_canary_is_immediate_fail_even_in_metadata(self) -> None:
        body = {
            "grounding_action": "abstain",
            "grounded_answer": None,
            "experimental": {"debug": "VIOLET-forbidden"},
        }
        result, reason = classify_positive_ground(
            exchange(body),
            permitted_canary="ORANGE-safe",
            forbidden_canary="VIOLET-forbidden",
            memory_id="memory:test",
        )
        self.assertIs(result, Outcome.FAIL)
        self.assertIn("foreign canary", reason)

    def test_timeout_is_inconclusive(self) -> None:
        timed_out = Exchange(
            "POST", "/v1/ground", None, 40000, "correlation:test", {}, None, "timeout"
        )
        result, _ = classify_positive_ground(
            timed_out,
            permitted_canary="ORANGE-safe",
            forbidden_canary="VIOLET-forbidden",
            memory_id="memory:test",
        )
        self.assertIs(result, Outcome.INCONCLUSIVE)


if __name__ == "__main__":
    unittest.main()
