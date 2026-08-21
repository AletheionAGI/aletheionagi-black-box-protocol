from __future__ import annotations

import argparse, json, os, sys, time, urllib.error, urllib.request, uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _bootstrap import ROOT
from adapters.aletheionagi import _raw_evidence_digest
from protocol.freeze import load_cases, verify_manifest

NETWORK_ATTEMPTS = 6


def request(method: str, path: str, body: dict[str, Any] | None = None, idem: str | None = None) -> tuple[int, Any]:
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {os.environ['ALETHEION_API_KEY']}", "Accept": "application/json"}
    if payload is not None: headers["Content-Type"] = "application/json"
    if idem: headers["Idempotency-Key"] = idem
    req = urllib.request.Request(os.getenv("ALETHEION_BASE_URL", "https://api.aletheionagi.com").rstrip("/") + path, data=payload, headers=headers, method=method)
    for attempt in range(NETWORK_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                raw = response.read(); return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raw = error.read()
            response = json.loads(raw) if raw else None
            if error.code != 429 and error.code < 500:
                return error.code, response
            last_error: BaseException = error
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
        if attempt + 1 == NETWORK_ATTEMPTS:
            raise last_error
        delay = min(2**attempt, 16)
        print(
            f"[provision] transient {method} {path} failure; retry "
            f"{attempt + 2}/{NETWORK_ATTEMPTS} in {delay}s",
            file=sys.stderr,
            flush=True,
        )
        time.sleep(delay)
    raise RuntimeError("unreachable")


def namespace(prefix: str, frozen: str, case_id: str, kind: str = "primary") -> str:
    return prefix + str(uuid.uuid5(uuid.NAMESPACE_URL, f"{frozen}:{case_id}:{kind}"))


def memory_id(digest: str, case_id: str, evidence_id: str) -> str:
    return f"bbp:{digest[:12]}:{case_id.lower()}:{evidence_id.replace('/', '-')}"


def wait_indexed(item_id: str) -> None:
    deadline = time.monotonic() + 120
    not_found_count = 0
    while time.monotonic() < deadline:
        status, body = request("GET", f"/v1/memories/{item_id}")
        state = body.get("state") if isinstance(body, dict) else None
        if status == 200 and state == "indexed": return
        if status == 404:
            not_found_count += 1
            if not_found_count >= 5:
                raise RuntimeError(f"{item_id} remained unavailable after an accepted write")
        elif 400 <= status < 500:
            raise RuntimeError(f"poll {item_id} returned HTTP {status}")
        if status >= 500 or state == "failed": raise RuntimeError(f"{item_id} failed to index")
        time.sleep(2)
    raise TimeoutError(f"{item_id} indexing timed out")


def provision(output: Path, execute: bool = False) -> dict[str, Any]:
    frozen = verify_manifest(ROOT); digest = frozen["combined_sha256"]
    prefix = os.getenv("ALETHEION_NAMESPACE_PREFIX", "")
    if not prefix.endswith(":"): raise ValueError("ALETHEION_NAMESPACE_PREFIX must end with ':'")
    if execute and not os.getenv("ALETHEION_API_KEY"): raise ValueError("ALETHEION_API_KEY is required")
    entries: dict[str, Any] = {}
    cases = load_cases(ROOT)
    for case_number, case in enumerate(cases, start=1):
        if execute:
            print(f"[provision] case {case_number}/{len(cases)}: {case.id}", flush=True)
        primary = namespace(prefix, digest, case.id); control = namespace(prefix, digest, case.id, "control")
        entries[case.id] = {
            "namespace_id": primary,
            "authorized_evidence_sha256": _raw_evidence_digest([asdict(x) for x in case.authorized_evidence]),
            "unauthorized_evidence_sha256": _raw_evidence_digest([asdict(x) for x in case.unauthorized_evidence]),
            "isolation_control": (f"foreign evidence is isolated in {control}" if case.category == "namespace_isolation" else "denied evidence uses bbp:unauthorized label" if case.category == "authorization_isolation" else None),
            "authorization_control_verified": False if case.category == "authorization_isolation" else None,
        }
        if not execute: continue
        for evidence, denied in [(x, False) for x in case.authorized_evidence] + [(x, True) for x in case.unauthorized_evidence]:
            target = control if denied and case.category == "namespace_isolation" else primary
            item_id = memory_id(digest, case.id, ("control-" if denied else "") + evidence.id)
            status, response = request("POST", "/v1/memories", {
                "memory_id": item_id, "namespace_id": target, "occurred_at": datetime.now(UTC).isoformat(),
                "content": evidence.text, "content_type": "text/plain", "source_id": "bbp:frozen-corpus",
                "authorization_labels": ["bbp:unauthorized"] if denied else [],
                "metadata": {"case_id": case.id, "control": "true" if denied else "false"},
            }, f"bbp:provision:{digest}:{item_id}")
            if status != 202:
                details = json.dumps(response, sort_keys=True, ensure_ascii=False)[:2000]
                raise RuntimeError(
                    f"write {case.id}/{evidence.id} returned HTTP {status}: {details}"
                )
            wait_indexed(item_id)
            if evidence.status == "revoked":
                status, _ = request("DELETE", f"/v1/memories/{item_id}", None, f"bbp:revoke:{item_id}")
                if status not in {200, 404}: raise RuntimeError(f"revoke {item_id} returned HTTP {status}")
    result = {"frozen_sha256": digest, "created_at": datetime.now(UTC).isoformat(), "cases": entries}
    if execute:
        if output.exists(): raise FileExistsError(f"refusing to overwrite {output}")
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--execute", action="store_true"); parser.add_argument("--output", type=Path, default=ROOT / "private-provisioning.json")
    args = parser.parse_args(); result = provision(args.output, args.execute)
    print(json.dumps({"mode": "EXECUTE" if args.execute else "DRY_RUN", "cases": len(result["cases"]), "traffic_sent": args.execute, "output": str(args.output) if args.execute else None}, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
