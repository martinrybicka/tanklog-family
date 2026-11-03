"""Sestaví a otestuje izolovaný Compose. Nepřipojuje NPM ani nemaže volumes."""

import json
import os
import secrets
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def local_docker():
    if not shutil.which("docker"):
        raise SystemExit(
            "Chybí Docker CLI/daemon. Kontejnerový CI průchod nelze provést."
        )
    endpoint = os.environ.get("DOCKER_HOST")
    if not endpoint:
        endpoint = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "context",
                    "inspect",
                    "--format",
                    "{{json .Endpoints.docker.Host}}",
                ],
                text=True,
            )
        )
    if not endpoint.startswith("unix://"):
        raise SystemExit(
            "CI ověření smí používat pouze místní unixový Docker socket, nikoli vzdálený server."
        )
    subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def main():
    local_docker()
    project = "tanklog-ci-" + uuid.uuid4().hex[:12]
    runtime = ROOT / ".runtime" / project
    runtime.mkdir(parents=True)
    envfile = runtime / "config.env"
    # Tento soubor je nový, soukromý a nezávislý na uživatelově .env.
    descriptor = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("POSTGRES_DB=tanklog_ci_e2e\nPOSTGRES_USER=tanklog\n")
        stream.write(f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n")
        stream.write(f"DJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n")
        stream.write(
            "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1\nDJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:18080,http://127.0.0.1:18080\n"
        )
    env = os.environ.copy()
    for key in [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "COMPOSE_FILE",
        "COMPOSE_PROJECT_NAME",
        "COMPOSE_PROFILES",
        "E2E_PRODUCTION",
        "E2E_HTTPS",
    ]:
        env.pop(key, None)
    compose = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(envfile),
        "-f",
        "compose.yaml",
        "-f",
        "compose.ci.yaml",
    ]

    def run(*args):
        subprocess.run([*compose, *args], cwd=ROOT, env=env, check=True)

    try:
        run("config", "--quiet")
        run("build", "backend", "web")
        subprocess.run(
            [
                "docker",
                "build",
                "--file",
                "infra/operations.Dockerfile",
                "--tag",
                "tanklog-operations:ci",
                ".",
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        run("up", "--detach", "--wait", "--wait-timeout", "120", "db")
        run(
            "run",
            "--rm",
            "--no-deps",
            "backend",
            "python",
            "manage.py",
            "migrate",
            "--noinput",
        )
        run("run", "--rm", "--no-deps", "backend", "python", "tests/prepare_e2e.py")
        fixture = subprocess.check_output(
            [
                *compose,
                "run",
                "--rm",
                "--no-deps",
                "backend",
                "python",
                "tests/prepare_extensions_e2e.py",
            ],
            cwd=ROOT,
            env=env,
            text=True,
        )
        json.loads(fixture)
        fixture_file = runtime / "extensions.json"
        fixture_file.write_text(fixture)
        fixture_file.chmod(0o600)
        run("up", "--detach", "--wait", "--wait-timeout", "180")
        browser_env = env | {
            "E2E_EXTENSIONS_FIXTURE": str(fixture_file),
            "E2E_BASE_URL": "http://127.0.0.1:18080",
            "E2E_BROWSER_CHANNEL": os.environ.get("E2E_BROWSER_CHANNEL", "chromium"),
        }
        subprocess.run(
            [
                "npm",
                "run",
                "test:e2e",
                "--",
                "--grep-invert",
                "produkční nginx:|PWA:",
            ],
            cwd=ROOT / "frontend",
            env=browser_env,
            check=True,
        )
    finally:
        # Jen kontejnery/sítě tohoto náhodného CI projektu, nikdy down -v nebo prune.
        subprocess.run(
            [*compose, "down", "--remove-orphans"], cwd=ROOT, env=env, check=False
        )
        print(
            f"CI projekt {project}: kontejnery zastavené; jeho databázový svazek se nemaže."
        )


if __name__ == "__main__":
    main()
