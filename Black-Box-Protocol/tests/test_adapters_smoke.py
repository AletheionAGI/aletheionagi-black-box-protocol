import json
import subprocess

import pytest

from adapters.aletheionagi import AletheionAGITarget, _evidence_digest, _raw_evidence_digest
from adapters.base import CaseSkipped, TargetSkipped, run_json_command
from adapters.fake import FakeTarget
from protocol.schema import Evidence


def test_fake_target_is_deterministic() -> None:
    result = FakeTarget().evaluate(
        "q", [Evidence("e", "synthetic")], {"fake_signal": "unsupported"}
    )
    assert result.blocked is True
    assert result.unsupported_claim_detected is True


def test_missing_local_provider_command_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LYNX_COMMAND", raising=False)
    with pytest.raises(TargetSkipped):
        run_json_command("LYNX_COMMAND", {"question": "q"})


def test_case_skip_is_distinct_from_target_unavailability() -> None:
    assert issubclass(CaseSkipped, TargetSkipped)
    assert CaseSkipped is not TargetSkipped


def test_provider_error_and_timeout_are_not_fabricated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_COMMAND", "provider")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "provider failed"),
    )
    with pytest.raises(RuntimeError, match="stderr was not persisted"):
        run_json_command("TEST_COMMAND", {})


def test_timeout_is_propagated_for_runner_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_COMMAND", "provider")

    def timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("provider", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        run_json_command("TEST_COMMAND", {})


def test_command_output_must_be_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_COMMAND", "provider")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps([1]), ""),
    )
    with pytest.raises(RuntimeError, match="JSON object"):
        run_json_command("TEST_COMMAND", {})


def test_aletheion_provisioning_manifest_verifies_isolation(tmp_path) -> None:
    evidence = [Evidence("a", "allowed", namespace="team-a")]
    forbidden = [{"id": "b", "text": "forbidden", "namespace": "team-b", "authorized": False, "status": "active"}]
    manifest = {
        "frozen_sha256": "frozen",
        "cases": {
            "VN-009": {
                "namespace_id": "team-a-controlled",
                "authorized_evidence_sha256": _evidence_digest(evidence),
                "unauthorized_evidence_sha256": _raw_evidence_digest(forbidden),
                "isolation_control": "team-b is separate",
            }
        },
    }
    path = tmp_path / "provisioning.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = AletheionAGITarget._provisioned_case(
        str(path),
        {"case_id": "VN-009", "category": "namespace_isolation", "unauthorized_evidence": forbidden},
        evidence,
        "frozen",
    )
    assert result["namespace_id"] == "team-a-controlled"


def test_aletheion_isolation_requires_control_attestation(tmp_path) -> None:
    path = tmp_path / "provisioning.json"
    path.write_text(json.dumps({"frozen_sha256": "frozen", "cases": {"VN-009": {
        "namespace_id": "team-a", "authorized_evidence_sha256": _evidence_digest([]),
        "unauthorized_evidence_sha256": _raw_evidence_digest([]), "isolation_control": ""
    }}}), encoding="utf-8")
    with pytest.raises(TargetSkipped, match="isolation control"):
        AletheionAGITarget._provisioned_case(
            str(path), {"case_id": "VN-009", "category": "namespace_isolation", "unauthorized_evidence": []}, [], "frozen"
        )
