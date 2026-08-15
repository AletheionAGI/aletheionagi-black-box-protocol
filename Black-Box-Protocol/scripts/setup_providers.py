from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _bootstrap import ROOT


PYTHON_VERSION = "3.12"
VENV_SPECS = {
    ".venv-lynx312": (
        "transformers==4.43.2",
        "accelerate==1.14.0",
        "torch==2.13.0",
    ),
    ".venv-nemo312": (
        "nemoguardrails==0.17.0",
        "langchain-nvidia-ai-endpoints",
    ),
    ".venv-guardrails312": ("guardrails-ai==0.10.2",),
}


def venv_python(name: str) -> Path:
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return ROOT / name / relative


def venv_command(name: str, command: str) -> Path:
    relative = Path(f"Scripts/{command}.exe") if os.name == "nt" else Path(f"bin/{command}")
    return ROOT / name / relative


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    display = ["<redacted>" if item == os.getenv("GUARDRAILS_AI_API_KEY") else item for item in command]
    print("+", " ".join(display), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def import_ok(python: Path, statement: str) -> bool:
    if not python.is_file():
        return False
    return subprocess.run(
        [str(python), "-c", statement],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def readiness() -> dict[str, bool]:
    return {
        "lynx": import_ok(
            venv_python(".venv-lynx312"),
            "import torch, accelerate, transformers; assert transformers.__version__ == '4.43.2'",
        ),
        "nemo": import_ok(
            venv_python(".venv-nemo312"),
            "import nemoguardrails, langchain_nvidia_ai_endpoints",
        ),
        "guardrails_ai": import_ok(
            venv_python(".venv-guardrails312"),
            "import guardrails; from guardrails.hub import GroundedAIHallucination",
        ),
    }


def find_uv(explicit: str | None) -> str:
    candidates = [
        explicit,
        shutil.which("uv"),
        str(Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv")),
        str(Path.home() / "snap" / "code" / "257" / ".local" / "bin" / "uv"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("uv is not installed; run scripts/setup.sh or scripts/setup.ps1 first")


def install(uv: str) -> None:
    run([uv, "python", "install", PYTHON_VERSION])
    for name, packages in VENV_SPECS.items():
        python = venv_python(name)
        if not python.is_file():
            run([uv, "venv", "--python", PYTHON_VERSION, str(ROOT / name)])
        run([uv, "pip", "install", "--python", str(python), *packages])

    guardrails_python = venv_python(".venv-guardrails312")
    if import_ok(guardrails_python, "from guardrails.hub import GroundedAIHallucination"):
        return
    token = os.getenv("GUARDRAILS_AI_API_KEY")
    if not token:
        raise RuntimeError("GUARDRAILS_AI_API_KEY is required to install the Guardrails Hub validator")
    cli = venv_command(".venv-guardrails312", "guardrails")
    run(
        [
            str(cli),
            "configure",
            "--token",
            token,
            "--disable-metrics",
            "--disable-remote-inferencing",
        ]
    )
    child_env = os.environ.copy()
    child_env["VIRTUAL_ENV"] = str(ROOT / ".venv-guardrails312")
    child_env["PATH"] = str(cli.parent) + os.pathsep + child_env.get("PATH", "")
    run(
        [str(cli), "hub", "install", "hub://groundedai/grounded_ai_hallucination", "--quiet"],
        env=child_env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/check all local comparison providers")
    parser.add_argument("--check", action="store_true", help="check only; do not install")
    parser.add_argument("--uv", help="explicit uv executable path")
    args = parser.parse_args()
    state = readiness()
    if args.check:
        print(state)
        return 0 if all(state.values()) else 1
    if not all(state.values()):
        install(find_uv(args.uv))
        state = readiness()
    print(state)
    if not all(state.values()):
        raise RuntimeError("one or more provider environments failed readiness checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
