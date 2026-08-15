from pathlib import Path

import pytest

from adversarial.strix_config import StrixConfig, validate_target


@pytest.mark.parametrize(
    "target",
    [
        "https://aletheionagi.com",
        "https://www.aletheionagi.com/",
        "https://api.aletheionagi.com/v1/health",
    ],
)
def test_exact_owned_hosts_are_allowed(target: str) -> None:
    assert validate_target(target) == target


@pytest.mark.parametrize(
    "target",
    [
        "https://competitor.example",
        "https://evilaletheionagi.com",
        "https://aletheionagi.com.evil.example",
        "https://dev.aletheionagi.com",
        "http://api.aletheionagi.com",
        "https://api.aletheionagi.com:8443",
        "https://user:secret@api.aletheionagi.com",
        "https://api.aletheionagi.com/?next=https://evil.example",
        "https://api.aletheionagi.com;touch-pwned",
    ],
)
def test_external_subdomain_and_injection_targets_are_rejected(target: str) -> None:
    with pytest.raises(ValueError):
        validate_target(target)


def test_execution_requires_enabled_and_authorization_ack() -> None:
    config = StrixConfig(False, False, "https://api.aletheionagi.com", None, "model", "secret")
    with pytest.raises(PermissionError, match="STRIX_ENABLED"):
        config.validate_execution("strix")


def test_missing_openapi_is_rejected(tmp_path: Path) -> None:
    config = StrixConfig(
        False,
        False,
        "https://api.aletheionagi.com",
        tmp_path / "missing.yaml",
        "",
        "",
    )
    with pytest.raises(ValueError, match="OPENAPI"):
        config.validate_common()
