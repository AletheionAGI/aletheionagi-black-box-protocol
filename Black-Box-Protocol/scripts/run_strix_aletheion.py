from __future__ import annotations

import argparse

from _bootstrap import ROOT  # noqa: F401
from adversarial.strix_config import StrixConfig
from adversarial.strix_runner import run_strix


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorized AletheionAGI-only Strix wrapper")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate and write artifacts without traffic (default)")
    mode.add_argument("--execute", action="store_true", help="run only when every authorization gate is configured")
    args = parser.parse_args()
    run_dir = run_strix(ROOT, StrixConfig.from_env(), execute=args.execute)
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
