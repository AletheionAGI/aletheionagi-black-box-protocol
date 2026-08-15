#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

scripts/setup.sh
export LYNX_COMMAND=".venv-lynx312/bin/python providers/lynx_local.py --serve"
export NEMO_GUARDRAILS_COMMAND=".venv-nemo312/bin/python providers/nemo_local.py --serve"
export GUARDRAILS_AI_COMMAND=".venv-guardrails312/bin/python providers/guardrails_ai_local.py --serve"
python scripts/setup_and_run.py --execute "$@"
