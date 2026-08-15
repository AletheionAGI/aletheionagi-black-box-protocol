import shutil
from pathlib import Path

import pytest

from protocol.freeze import build_manifest, load_cases, verify_manifest, write_manifest
from protocol.schema import TestCase


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_corpus_has_all_differentiating_categories() -> None:
    cases = load_cases(ROOT)
    assert len(cases) == 500
    category_counts = {}
    for case in cases:
        category_counts[case.category] = category_counts.get(case.category, 0) + 1
    assert set(category_counts.values()) == {50}
    assert {case.category for case in cases} == {
        "supported_answer",
        "unsupported_claim",
        "insufficient_evidence",
        "contradictory_evidence",
        "irrelevant_evidence",
        "evidence_poisoning",
        "revoked_evidence",
        "namespace_isolation",
        "authorization_isolation",
        "fail_closed",
    }
    assert verify_manifest(ROOT)["combined_sha256"] == build_manifest(ROOT)["combined_sha256"]


def test_case_requires_known_category() -> None:
    with pytest.raises(ValueError, match="unsupported category"):
        TestCase.from_dict(
            {
                "id": "VN-999",
                "category": "marketing_score",
                "question": "Synthetic?",
                "authorized_evidence": [],
                "expected_behavior": ["none"],
                "forbidden_behavior": ["none"],
                "notes": "",
            }
        )


def test_case_rejects_fields_outside_frozen_schema() -> None:
    with pytest.raises(ValueError, match="unknown fields"):
        TestCase.from_dict(
            {
                "id": "VN-999",
                "category": "supported_answer",
                "question": "Synthetic?",
                "authorized_evidence": [],
                "expected_behavior": ["deliver"],
                "forbidden_behavior": ["invent"],
                "notes": "",
                "target_specific_exception": True,
            }
        )


def test_freeze_rejects_case_mutation(tmp_path: Path) -> None:
    for name in ("cases", "protocol"):
        shutil.copytree(ROOT / name, tmp_path / name)
    shutil.copy2(ROOT / "HYPOTHESES.md", tmp_path / "HYPOTHESES.md")
    (tmp_path / "cases" / "FROZEN_MANIFEST.json").unlink(missing_ok=True)
    write_manifest(tmp_path)
    with (tmp_path / "cases" / "unsupported_claims.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(RuntimeError, match="frozen inputs changed"):
        verify_manifest(tmp_path)
