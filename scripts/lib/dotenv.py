"""
Minimal .env loader (no external dependencies).

Loads environment variables from `.env.local` then `.env` in the current working
directory. Lines are KEY=VALUE, with optional quotes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


def _parse_line(line: str) -> Optional[tuple[str, str]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if line.startswith("export "):
        line = line[len("export ") :].lstrip()

    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        return None

    if (len(value) >= 2) and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        value = value[1:-1]

    return key, value


def load_dotenv(paths: Iterable[str] = (".env.local", ".env"), *, override: bool = False) -> int:
    """Load env vars from a list of dotenv file paths. Returns count of variables set."""
    set_count = 0
    for p in paths:
        path = Path(p)
        if not path.exists() or not path.is_file():
            continue

        try:
            for raw in path.read_text().splitlines():
                parsed = _parse_line(raw)
                if not parsed:
                    continue
                key, value = parsed
                if not override and key in os.environ:
                    continue
                os.environ[key] = value
                set_count += 1
        except Exception:
            # Best-effort: dotenv should never make scripts fail to start.
            continue

    return set_count

