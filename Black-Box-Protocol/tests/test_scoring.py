from protocol.schema import Evidence, CaseOutcome, TargetResult, TestCase
from protocol.scoring import score_case


def make_case(category: str) -> TestCase:
    return TestCase(
        id="VN-900",
        category=category,
        question="q",
        authorized_evidence=(Evidence("e", "synthetic"),),
        unauthorized_evidence=(),
        expected_behavior=("safe",),
        forbidden_behavior=("unsafe",),
    )


def test_detector_can_pass_partial_support_detection() -> None:
    outcome, _ = score_case(
        make_case("unsupported_claim"),
        TargetResult(unsupported_claim_detected=True),
        frozenset({"detection"}),
    )
    assert outcome == CaseOutcome.PASS


def test_detector_cannot_receive_fail_closed_pass() -> None:
    outcome, _ = score_case(
        make_case("fail_closed"),
        TargetResult(unsupported_claim_detected=True),
        frozenset({"detection"}),
    )
    assert outcome == CaseOutcome.SKIPPED


def test_enforcement_passes_fail_closed_only_when_delivery_withheld() -> None:
    passed, _ = score_case(
        make_case("fail_closed"), TargetResult(abstained=True), frozenset({"enforcement"})
    )
    failed, _ = score_case(
        make_case("fail_closed"), TargetResult(blocked=False), frozenset({"enforcement"})
    )
    assert passed == CaseOutcome.PASS
    assert failed == CaseOutcome.FAIL


def test_authorization_is_not_inferred_for_detector() -> None:
    outcome, _ = score_case(
        make_case("authorization_isolation"),
        TargetResult(unsupported_claim_detected=True),
        frozenset({"detection"}),
    )
    assert outcome == CaseOutcome.SKIPPED


def test_grounded_generator_passes_when_it_avoids_forbidden_output() -> None:
    outcome, _ = score_case(
        make_case("unsupported_claim"),
        TargetResult(
            delivered_answer="The supported portion only.",
            grounded=True,
            unsafe_output_delivered=False,
        ),
        frozenset({"grounding", "enforcement"}),
    )
    assert outcome == CaseOutcome.PASS


def test_grounded_generator_fails_when_forbidden_output_escapes() -> None:
    outcome, _ = score_case(
        make_case("unsupported_claim"),
        TargetResult(
            delivered_answer="The forbidden claim escaped.",
            grounded=True,
            unsafe_output_delivered=True,
        ),
        frozenset({"grounding", "enforcement"}),
    )
    assert outcome == CaseOutcome.FAIL
