from protocol.normalization import first_value, optional_bool, optional_float


def test_normalization_preserves_unknowns() -> None:
    payload = {"result": {"score": 0.83, "blocked": "triggered"}}
    assert first_value(payload, "missing", "result.score") == 0.83
    assert optional_bool(first_value(payload, "result.blocked")) is True
    assert optional_bool("maybe") is None
    assert optional_float(3.0) is None
