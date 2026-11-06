"""Produkční start: pouze migrace schématu, nikdy demo data nebo výchozí účet."""

import os
import subprocess
import sys

subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
os.execvp(
    "gunicorn",
    [
        "gunicorn",
        "config.wsgi:application",
        "--bind",
        "0.0.0.0:8000",
        "--workers",
        "2",
        "--timeout",
        "35",
        "--access-logfile",
        "-",
        "--access-logformat",
        "%(m)s %(U)s %(s)s %(D)s",
    ],
)
