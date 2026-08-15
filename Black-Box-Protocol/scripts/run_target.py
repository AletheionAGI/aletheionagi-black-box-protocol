from __future__ import annotations

import argparse

from _bootstrap import ROOT  # noqa: F401
from adapters import TARGETS
from protocol.runner import run_targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one target against the frozen corpus")
    parser.add_argument("--target", required=True, choices=sorted(TARGETS))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--categories", help="comma-separated category filter")
    args = parser.parse_args()
    categories = set(args.categories.split(",")) if args.categories else None
    print(run_targets(ROOT, [args.target], runs=args.runs, categories=categories))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
