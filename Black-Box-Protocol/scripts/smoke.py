from __future__ import annotations

import json

from _bootstrap import ROOT  # noqa: F401
from protocol.runner import run_targets


def main() -> int:
    run_dir = run_targets(ROOT, ["fake"])
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    fake = summary["targets"]["fake"]
    print(json.dumps(fake, indent=2))
    return 0 if fake["fail"] == 0 and fake["errors"] == 0 and fake["skipped"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
