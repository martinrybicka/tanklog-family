"""Společné příkazy CI a lokálního ověření. Nic nepublikuje a nemaže DB/volumes."""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / "backend/.venv/bin/python"
RUFF = ROOT / "backend/.venv/bin/ruff"


def run(*args, **kwargs):
    subprocess.run(
        [str(value) for value in args],
        cwd=kwargs.pop("cwd", ROOT),
        check=True,
        **kwargs,
    )


def backend():
    if (
        os.environ.get("TANKLOG_CI") != "1"
        or not os.environ.get("POSTGRES_DB", "").endswith("_ci")
        or os.environ.get("POSTGRES_HOST") not in {"127.0.0.1", "localhost"}
    ):
        raise SystemExit(
            "Backend CI vyžaduje TANKLOG_CI=1, samostatnou *_ci DB a místní PostgreSQL. Běžná data se nemění."
        )
    run(os.environ.get("UV_COMMAND", "uv"), "lock", "--check", "--project", "backend")
    run(RUFF, "check", "backend")
    run(RUFF, "format", "--check", "backend")
    run(
        RUFF,
        "check",
        "--config",
        "infra/ruff.toml",
        "infra/ci",
        "infra/ops",
        "infra/local_production_preview.py",
        "frontend/scripts/generate-icons.py",
    )
    run(
        RUFF,
        "format",
        "--check",
        "--config",
        "infra/ruff.toml",
        "infra/ci",
        "infra/ops",
        "infra/local_production_preview.py",
        "frontend/scripts/generate-icons.py",
    )
    run(PYTHON, "-m", "unittest", "discover", "-s", "infra/ci/tests", "-v")
    run(PYTHON, "-m", "unittest", "discover", "-s", "infra/ops/tests", "-v")
    helper = [sys.executable, "infra/backend_command.py", PYTHON]
    run(*helper, "-m", "pytest", "-q")
    run(*helper, "manage.py", "migrate", "--noinput")
    run(*helper, "manage.py", "check")
    run(*helper, "manage.py", "makemigrations", "--check", "--dry-run")
    with tempfile.TemporaryDirectory(prefix="tanklog-schema-") as folder:
        output = Path(folder) / "openapi.yaml"
        run(
            *helper,
            "manage.py",
            "spectacular",
            "--file",
            output,
            "--validate",
            "--fail-on-warn",
        )
        if output.read_bytes() != (ROOT / "docs/openapi.yaml").read_bytes():
            raise SystemExit("Generované OpenAPI neodpovídá docs/openapi.yaml.")
    env = os.environ.copy()
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": "config.settings.production",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECURE_COOKIES": "true",
            "DJANGO_ALLOWED_HOSTS": "tanklog.example.invalid,127.0.0.1",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://tanklog.example.invalid",
            "DJANGO_HSTS_SECONDS": "0",
        }
    )
    # ADR-027 nechává HSTS=0. Výslovně přijmeme jen známé W004, nic dalšího.
    result = subprocess.run(
        [
            str(value)
            for value in [
                *helper,
                "manage.py",
                "check",
                "--deploy",
                "--fail-level",
                "WARNING",
            ]
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    validate_deploy_result(result.returncode, result.stderr)


def validate_deploy_result(returncode, output):
    codes = set(re.findall(r"\(([a-z_]+\.[WE]\d+)\)", output))
    if returncode == 0 and not codes:
        return
    if returncode == 1 and codes == {"security.W004"} and "Traceback" not in output:
        print(
            "check --deploy: pouze očekávané security.W004 podle ADR-027; nové chyby/varování nejsou povolené."
        )
        return
    raise SystemExit("Produkční systémová kontrola hlásí neočekávaný problém.")


def frontend():
    for task in ["lint", "test", "build"]:
        run("npm", "run", task, cwd=ROOT / "frontend")
    run(
        "npm",
        "exec",
        "--",
        "prettier",
        "--check",
        "src",
        "e2e",
        "scripts/*.mjs",
        "scripts/worker.js",
        "public/*.html",
        "public/*.css",
        "public/manifest.webmanifest",
        ".oxlintrc.json",
        "index.html",
        "playwright.config.ts",
        cwd=ROOT / "frontend",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=["backend", "frontend"])
    target = parser.parse_args().target
    {"backend": backend, "frontend": frontend}[target]()


if __name__ == "__main__":
    main()
