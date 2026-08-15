from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED_HOSTS = frozenset(
    {
        "aletheionagi.com",
        "www.aletheionagi.com",
        "api.aletheionagi.com",
    }
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{name} must be true or false")


def validate_target(value: str) -> str:
    if not value:
        raise ValueError("STRIX_TARGET is required")
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        raise ValueError("Strix target must use HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Strix target must not contain credentials")
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Strix target hostname is not allowlisted: {hostname or '<missing>'}")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Strix target contains an invalid port") from exc
    if port not in {None, 443}:
        raise ValueError("Strix target may only use the default HTTPS port")
    if parsed.query or parsed.fragment:
        raise ValueError("Strix target must not contain a query or fragment")
    return value


@dataclass(frozen=True)
class StrixConfig:
    enabled: bool
    authorization_ack: bool
    target: str
    openapi_path: Path | None
    llm: str
    llm_api_key: str
    timeout_seconds: int = 3600
    scan_mode: str = "quick"

    @classmethod
    def from_env(cls) -> "StrixConfig":
        timeout_raw = os.getenv("STRIX_TIMEOUT_SECONDS", "3600")
        try:
            timeout = int(timeout_raw)
        except ValueError as exc:
            raise ValueError("STRIX_TIMEOUT_SECONDS must be an integer") from exc
        if timeout < 1:
            raise ValueError("STRIX_TIMEOUT_SECONDS must be positive")
        openapi = os.getenv("STRIX_OPENAPI_PATH", "").strip()
        return cls(
            enabled=_env_bool("STRIX_ENABLED"),
            authorization_ack=_env_bool("STRIX_AUTHORIZATION_ACK"),
            target=os.getenv("STRIX_TARGET", "").strip(),
            openapi_path=Path(openapi).resolve() if openapi else None,
            llm=os.getenv("STRIX_LLM", "").strip(),
            llm_api_key=os.getenv("STRIX_LLM_API_KEY", ""),
            timeout_seconds=timeout,
        )

    def validate_common(self) -> None:
        validate_target(self.target)
        if self.scan_mode != "quick":
            raise ValueError("Only Strix quick mode is permitted by this wrapper")
        if self.openapi_path is not None and not self.openapi_path.is_file():
            raise ValueError(f"STRIX_OPENAPI_PATH does not exist or is not a file: {self.openapi_path}")

    def validate_execution(self, cli_path: str | None) -> None:
        self.validate_common()
        if not self.enabled:
            raise PermissionError("STRIX_ENABLED=true is required for a real scan")
        if not self.authorization_ack:
            raise PermissionError("STRIX_AUTHORIZATION_ACK=true is required for a real scan")
        if not cli_path:
            raise FileNotFoundError("Strix CLI was not found on PATH")
        if not self.llm:
            raise ValueError("STRIX_LLM is required for a real scan")
        if not self.llm_api_key:
            raise ValueError("STRIX_LLM_API_KEY is required for a real scan")
