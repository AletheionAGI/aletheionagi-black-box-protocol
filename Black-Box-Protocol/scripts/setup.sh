#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  INSTALL_SCRIPT="$(mktemp)"
  trap 'rm -f "$INSTALL_SCRIPT"' EXIT
  curl -LsSf https://astral.sh/uv/install.sh -o "$INSTALL_SCRIPT"
  sh "$INSTALL_SCRIPT"
fi

UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  for candidate in "$HOME/.local/bin/uv" "$HOME/snap/code/257/.local/bin/uv"; do
    if [[ -x "$candidate" ]]; then UV_BIN="$candidate"; break; fi
  done
fi
if [[ -z "$UV_BIN" ]]; then
  echo "uv was installed but could not be located" >&2
  exit 1
fi

python scripts/setup_providers.py --uv "$UV_BIN"
