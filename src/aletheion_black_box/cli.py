from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .models import Config
from .runner import ProtocolRunner


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        prog="aletheion-black-box",
        description="Plan or run the AletheionAGI black-box evaluation protocol.",
    )
    subcommands = command.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        subcommand = subcommands.add_parser(name)
        subcommand.add_argument("--config", type=Path, required=True)
        if name == "run":
            subcommand.add_argument("--execute", action="store_true")
            subcommand.add_argument("--output", type=Path, default=Path("evidence"))
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = Config.load(args.config)
        if args.command == "plan":
            _print_plan(config)
            return 0
        if not args.execute:
            raise ValueError("run requires --execute; use plan first")
        if not config.acknowledge_synthetic_data_only:
            raise ValueError("set acknowledge_synthetic_data_only to true")
        if not config.acknowledge_credit_usage:
            raise ValueError("set acknowledge_credit_usage to true")
        key_a = os.environ.get("ALETHEION_API_KEY_A", "")
        key_b = os.environ.get("ALETHEION_API_KEY_B", "")
        runner = ProtocolRunner(config, key_a, key_b, args.output)
        overall, evidence_directory = runner.run()
        print(f"Overall outcome: {overall.value}")
        print(f"Evidence: {evidence_directory.resolve()}")
        return 0 if overall.value == "PASS" else 2
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _print_plan(config: Config) -> None:
    print(f"Protocol: {config.protocol_version}")
    print(f"Target: {config.base_url}")
    print(f"Tested release: {config.tested_release}")
    print(f"Shared namespace: {config.namespace_id}")
    print(f"Attempts per organization: {config.attempts_per_organization}")
    print(f"Estimated grounding HTTP requests: {config.estimated_grounding_requests}")
    print(f"Estimated maximum credit units: {config.estimated_credit_units}")
    print("API keys: read only from ALETHEION_API_KEY_A and ALETHEION_API_KEY_B during run")
    print("No network request was sent.")


if __name__ == "__main__":
    raise SystemExit(main())
