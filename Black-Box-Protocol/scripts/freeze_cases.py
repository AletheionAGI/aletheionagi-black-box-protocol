from __future__ import annotations

import argparse

from _bootstrap import ROOT  # noqa: F401
from protocol.freeze import write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze case schema, corpus and scoring before target runs")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace the freeze only before observing any target result",
    )
    args = parser.parse_args()
    path = write_manifest(ROOT, refresh=args.refresh)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
