from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from .models import Exchange


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        path: str,
        *,
        api_key: str | None = None,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Exchange:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        correlation_id = f"bbp:{uuid.uuid4()}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "aletheionagi-black-box-protocol/1.0.0",
            "X-Correlation-ID": correlation_id,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=payload, headers=headers, method=method
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                return self._exchange(
                    method,
                    path,
                    response.status,
                    started,
                    response.headers.get("X-Correlation-ID") or correlation_id,
                    body,
                    raw,
                )
        except urllib.error.HTTPError as error:
            return self._exchange(
                method,
                path,
                error.code,
                started,
                error.headers.get("X-Correlation-ID") or correlation_id,
                body,
                error.read(),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            return Exchange(
                method=method,
                path=path,
                status=None,
                duration_ms=round((time.monotonic() - started) * 1000),
                correlation_id=correlation_id,
                request_body=body,
                response_body=None,
                transport_error=f"{type(error).__name__}: {error}",
            )

    @staticmethod
    def _exchange(
        method: str,
        path: str,
        status: int,
        started: float,
        correlation_id: str,
        request_body: Any,
        raw: bytes,
    ) -> Exchange:
        try:
            response_body: Any = json.loads(raw) if raw else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            response_body = {"non_json_body": raw.decode("utf-8", errors="replace")[:1000]}
        return Exchange(
            method=method,
            path=path,
            status=status,
            duration_ms=round((time.monotonic() - started) * 1000),
            correlation_id=correlation_id,
            request_body=request_body,
            response_body=response_body,
        )


def error_code(exchange: Exchange) -> str | None:
    body = exchange.response_body
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    return (
        error.get("code")
        if isinstance(error, dict) and isinstance(error.get("code"), str)
        else None
    )
