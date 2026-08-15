from __future__ import annotations

import argparse
import json
import os
import subprocess

from _bootstrap import ROOT
from protocol.runner import FIRST_ROUND_TARGETS, run_targets
from provision_aletheion import provision
from setup_providers import install as install_providers
from setup_providers import find_uv, readiness as provider_readiness, venv_python


def configure_provider_commands() -> None:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    os.environ["NEMO_GUARDRAILS_COMMAND"] = (
        f".venv-nemo312/{scripts_dir}/{executable} providers/nemo_local.py --serve"
    )
    os.environ["GUARDRAILS_AI_COMMAND"] = (
        f".venv-guardrails312/{scripts_dir}/{executable} "
        "providers/guardrails_ai_local.py --serve"
    )


def ensure_provider_environments() -> dict[str, bool]:
    state = provider_readiness()
    if all(state.values()):
        return state
    try:
        uv = find_uv(None)
    except RuntimeError:
        if os.name == "nt":
            command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts" / "setup.ps1"),
            ]
        else:
            command = ["bash", str(ROOT / "scripts" / "setup.sh")]
        subprocess.run(command, cwd=ROOT, check=True)
    else:
        install_providers(uv)
    state = provider_readiness()
    if not all(state.values()):
        raise RuntimeError("provider setup did not pass readiness checks")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and run the Black-Box Protocol")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--include-galileo", action="store_true")
    parser.add_argument("--reuse-provisioning", action="store_true")
    parser.add_argument(
        "--skip-provider-setup",
        action="store_true",
        help="do not install/check NeMo and Guardrails AI environments",
    )
    args = parser.parse_args()
    provider_state = provider_readiness()
    if args.execute and not args.skip_provider_setup and not all(provider_state.values()):
        provider_state = ensure_provider_environments()
    configure_provider_commands()
    plan = provision(ROOT / "unused-dry-run.json", False)
    output = ROOT / f"private-provisioning-{plan['frozen_sha256'][:12]}.json"
    ready = {
        "aletheion_key": bool(os.getenv("ALETHEION_API_KEY")),
        "namespace_prefix": bool(os.getenv("ALETHEION_NAMESPACE_PREFIX")),
        "nvidia_key": bool(os.getenv("NVIDIA_API_KEY")),
        "guardrails_ai_key": bool(os.getenv("GUARDRAILS_AI_API_KEY")),
        "nemo_command": bool(os.getenv("NEMO_GUARDRAILS_COMMAND")),
        "guardrails_ai_command": bool(os.getenv("GUARDRAILS_AI_COMMAND")),
        "provider_environments": provider_state,
        "planned_cases": len(plan["cases"]),
    }
    if not args.execute:
        print(
            json.dumps(
                {"mode": "DRY_RUN", "readiness": ready, "traffic_sent": False}, indent=2
            )
        )
        return 0
    if args.reuse_provisioning:
        if not output.is_file():
            raise FileNotFoundError(f"no provisioning manifest to reuse: {output}")
        manifest = json.loads(output.read_text(encoding="utf-8"))
        if manifest.get("frozen_sha256") != plan["frozen_sha256"]:
            raise RuntimeError("provisioning manifest belongs to another frozen cohort")
    else:
        manifest = provision(output, True)
    os.environ["ALETHEION_CORPUS_FROZEN_SHA256"] = manifest["frozen_sha256"]
    os.environ["ALETHEION_PROVISIONING_MANIFEST"] = str(output)
    targets = list(FIRST_ROUND_TARGETS) + (["galileo"] if args.include_galileo else [])
    results = run_targets(ROOT, targets, runs=args.runs)
    graph = results / "RESULTS.png"
    subprocess.run(
        [str(venv_python(".venv-reporting312")), str(ROOT / "scripts" / "plot_results_png.py"), str(results), "--output", str(graph)],
        cwd=ROOT,
        check=True,
    )
    print(json.dumps({"manifest": str(output), "results": str(results), "graph": str(graph)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
