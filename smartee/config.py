"""Minimal `.env` loader — no dependency.

Reads `KEY=VALUE` lines (ignoring blanks and `#` comments), strips one layer
of surrounding quotes, and sets each key in `os.environ` **only if it is not
already set** — a real environment variable always wins. Values never touch
logs or the repo (`.env` is gitignored).
"""

import os
from pathlib import Path


def load_env(path: Path | str = ".env") -> list[str]:
    """Load `path` into the environment. Returns the names that were set
    (not those skipped because already present or the file is missing)."""
    file = Path(path)
    if not file.is_file():
        return []

    loaded: list[str] = []
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
