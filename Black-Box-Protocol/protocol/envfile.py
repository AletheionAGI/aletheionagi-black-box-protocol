from __future__ import annotations

import json
import os
import re
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(path: Path, *, override: bool = False) -> int:
    """Load a small, non-interpolating .env file and return the number of values set."""
    if not path.is_file():
        return 0
    loaded = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected NAME=VALUE")
        name, value = line.split("=", 1)
        name = name.strip()
        if not _NAME.fullmatch(name):
            raise ValueError(f"{path}:{line_number}: invalid environment variable name")
        value = _parse_value(value.strip(), path, line_number)
        if override or name not in os.environ:
            os.environ[name] = value
            loaded += 1
    return loaded


def _parse_value(value: str, path: Path, line_number: int) -> str:
    if not value:
        return ""
    if value[0] in {'"', "'"}:
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            raise ValueError(f"{path}:{line_number}: unterminated quoted value")
        inner = value[1:-1]
        if quote == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid quoted value") from exc
        return inner
    # Inline comments require whitespace before '#', matching common dotenv behavior.
    return re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
