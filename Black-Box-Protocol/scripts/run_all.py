from __future__ import annotations

import argparse

from _bootstrap import ROOT  # noqa: F401
from protocol.runner import FIRST_ROUND_TARGETS, run_targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the three comparison targets")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--categories", help="comma-separated category filter")
    parser.add_argument(
        "--include-galileo",
        action="store_true",
        help="include the preconfigured phase-2 Galileo target in this cohort",
    )
    args = parser.parse_args()
    categories = set(args.categories.split(",")) if args.categories else None
    targets = list(FIRST_ROUND_TARGETS)
    if args.include_galileo:
        targets.append("galileo")
    print(run_targets(ROOT, targets, runs=args.runs, categories=categories))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
