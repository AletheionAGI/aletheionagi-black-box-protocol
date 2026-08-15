from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aletheion_black_box.models import CaseResult, Config, Outcome, aggregate_outcome


def valid_config() -> dict[str, object]:
    return {
        "protocol_version": "1.0.0",
        "base_url": "https://api.example.test",
        "tested_release": "release:test",
        "namespace_id": "poc:00000000-0000-4000-8000-000000000001",
        "attempts_per_organization": 10,
        "acknowledge_synthetic_data_only": True,
        "acknowledge_credit_usage": True,
        "manual_results": {"BB-02": "PASS", "BB-10": "INCONCLUSIVE"},
    }


class ConfigTests(unittest.TestCase):
    def test_loads_and_estimates_credit_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(valid_config()), encoding="utf-8")
            config = Config.load(path)
        self.assertEqual(config.estimated_grounding_requests, 27)
        self.assertEqual(config.estimated_credit_units, 24)

    def test_rejects_unknown_fields(self) -> None:
        raw = valid_config() | {"api_key": "must-not-be-here"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown configuration fields"):
                Config.load(path)

    def test_fail_dominates_aggregate(self) -> None:
        cases = [
            CaseResult("BB-01", "one", Outcome.PASS, "ok"),
            CaseResult("BB-02", "two", Outcome.FAIL, "foreign canary"),
            CaseResult("BB-03", "three", Outcome.INCONCLUSIVE, "timeout"),
        ]
        self.assertIs(aggregate_outcome(cases), Outcome.FAIL)


if __name__ == "__main__":
    unittest.main()
