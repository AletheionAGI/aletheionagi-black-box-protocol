from __future__ import annotations

import json

from _bootstrap import ROOT  # noqa: F401
from adversarial.strix_config import StrixConfig
from adversarial.strix_runner import run_strix


def main() -> int:
    config = StrixConfig.from_env()
    if not config.target:
        config = StrixConfig(
            enabled=config.enabled,
            authorization_ack=config.authorization_ack,
            target="https://api.aletheionagi.com",
            openapi_path=config.openapi_path,
            llm=config.llm,
            llm_api_key=config.llm_api_key,
            timeout_seconds=config.timeout_seconds,
        )
    run_dir = run_strix(ROOT, config, execute=False)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "status": manifest["status"],
        "target": manifest["target"],
        "strix_cli_version": manifest["strix_cli_version"],
        "scope_sha256": manifest["scope_sha256"],
        "sanitized_command": manifest["sanitized_command"],
        "result_directory": str(run_dir),
        "traffic_sent": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
