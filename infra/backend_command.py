"""Spustí backendový příkaz lokálně s .env, bez vypisování tajných hodnot."""

import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
environment = {}
for line in (root / ".env").read_text().splitlines():
    if line and not line.startswith("#"):
        key, value = line.split("=", 1)
        environment[key] = value
environment.update(os.environ)
raise SystemExit(subprocess.call(sys.argv[1:], cwd=root / "backend", env=environment))
