import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import provision_aletheion  # noqa: E402
from provision_aletheion import memory_id  # noqa: E402


def test_memory_ids_are_unique_per_frozen_cohort() -> None:
    first = memory_id("a" * 64, "VN-001", "atlas-policy")
    second = memory_id("b" * 64, "VN-001", "atlas-policy")
    assert first != second
    assert first == "bbp:aaaaaaaaaaaa:vn-001:atlas-policy"


def test_request_retries_a_transient_network_failure(monkeypatch) -> None:
    response = Mock()
    response.status = 202
    response.read.return_value = json.dumps({"state": "accepted"}).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    urlopen = Mock(side_effect=[urllib.error.URLError(ConnectionResetError(104)), response])
    sleep = Mock()
    monkeypatch.setattr(provision_aletheion.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(provision_aletheion.time, "sleep", sleep)

    status, body = provision_aletheion.request(
        "POST", "/v1/memories", {"memory_id": "bbp:test"}, "bbp:idem:test"
    )

    assert status == 202
    assert body == {"state": "accepted"}
    assert urlopen.call_count == 2
    sleep.assert_called_once_with(1)
