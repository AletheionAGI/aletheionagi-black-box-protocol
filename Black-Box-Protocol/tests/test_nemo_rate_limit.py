from __future__ import annotations

import pytest

from providers import nemo_local


def test_rate_limited_evaluator_retries_429(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def evaluate(request: dict[str, str]) -> dict[str, bool]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("[429] Too Many Requests")
        return {"blocked": False}

    monkeypatch.setenv("NEMO_MIN_REQUEST_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("NEMO_RATE_LIMIT_MAX_RETRIES", "3")
    monkeypatch.setenv("NEMO_RATE_LIMIT_BACKOFF_SECONDS", "0.1")
    monkeypatch.setenv("NEMO_RATE_LIMIT_MAX_BACKOFF_SECONDS", "0.1")
    monkeypatch.setattr(nemo_local.time, "sleep", lambda _: None)
    monkeypatch.setattr(nemo_local.random, "uniform", lambda _a, _b: 1.0)

    wrapped = nemo_local.RateLimitedEvaluator(evaluate)

    assert wrapped({"response": "answer"}) == {"blocked": False}
    assert attempts == 3


def test_rate_limited_evaluator_does_not_retry_other_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def evaluate(request: dict[str, str]) -> dict[str, bool]:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("authentication failed")

    monkeypatch.setenv("NEMO_MIN_REQUEST_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(nemo_local.time, "sleep", lambda _: None)
    wrapped = nemo_local.RateLimitedEvaluator(evaluate)

    with pytest.raises(RuntimeError, match="authentication failed"):
        wrapped({"response": "answer"})
    assert attempts == 1


def test_rate_limit_configuration_rejects_negative_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEMO_MIN_REQUEST_INTERVAL_SECONDS", "-1")

    with pytest.raises(ValueError, match="NEMO_MIN_REQUEST_INTERVAL_SECONDS"):
        nemo_local.RateLimitedEvaluator(lambda request: request)
