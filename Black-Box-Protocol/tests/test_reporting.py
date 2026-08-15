from protocol.reporting import summarize
from protocol.schema import CaseExecution, CaseOutcome, TargetResult


def test_skips_do_not_dilute_measurable_pass_rate() -> None:
    rows = [
        CaseExecution("t", "VN-1", "unsupported_claim", 1, CaseOutcome.PASS, "ok", TargetResult()),
        CaseExecution("t", "VN-2", "namespace_isolation", 1, CaseOutcome.SKIPPED, "n/a", TargetResult()),
    ]
    summary = summarize(rows)
    values = summary["protocol_performance"]["targets"]["t"]
    assert values["pass_rate"] == 1.0
    assert values["unauthorized_evidence_use_rate"] is None
    assert summary["integration_complexity"]["targets"] == {}


def test_integration_complexity_is_separate_from_protocol_performance() -> None:
    rows = [
        CaseExecution("t", "VN-1", "unsupported_claim", 1, CaseOutcome.PASS, "ok", TargetResult()),
    ]
    descriptors = [{"name": "t", "integration": {"counts": {"dependencies": 9}}}]

    summary = summarize(rows, descriptors)

    assert summary["protocol_performance"]["targets"]["t"]["pass"] == 1
    assert "integration" not in summary["protocol_performance"]["targets"]["t"]
    assert summary["integration_complexity"]["targets"]["t"]["counts"]["dependencies"] == 9
