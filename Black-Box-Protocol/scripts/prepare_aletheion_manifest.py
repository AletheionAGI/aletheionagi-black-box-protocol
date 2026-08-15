from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from _bootstrap import ROOT  # noqa: F401
from adapters.aletheionagi import _raw_evidence_digest
from protocol.freeze import load_cases, verify_manifest


def build_template() -> dict[str, object]:
    frozen = verify_manifest(ROOT)
    cases: dict[str, object] = {}
    for case in load_cases(ROOT):
        cases[case.id] = {
            "namespace_id": f"REPLACE_WITH_CONTROLLED_NAMESPACE_FOR_{case.id}",
            "authorized_evidence_sha256": _raw_evidence_digest(
                [asdict(item) for item in case.authorized_evidence]
            ),
            "unauthorized_evidence_sha256": _raw_evidence_digest(
                [asdict(item) for item in case.unauthorized_evidence]
            ),
            "isolation_control": (
                "REPLACE_WITH_CONTROL_DESCRIPTION"
                if case.category in {"namespace_isolation", "authorization_isolation"}
                else None
            ),
        }
    return {"frozen_sha256": frozen["combined_sha256"], "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a private Aletheion provisioning manifest template")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing manifest: {args.output}")
    args.output.write_text(json.dumps(build_template(), indent=2) + "\n", encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
