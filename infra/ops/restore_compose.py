"""Obnovovací cvičení ve vždy novém místním Compose projektu. Nemaže svazky."""

import argparse
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from infra.ci.containers import local_docker  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument(
        "--synthetic-check",
        action="store_true",
        help="Pouze záloha ze syntetického drill.py.",
    )
    args = parser.parse_args()
    local_docker()
    if args.identity.is_symlink():
        raise SystemExit("Soukromý klíč nesmí být symbolický odkaz.")
    archive, identity = (
        args.archive.resolve(strict=True),
        args.identity.resolve(strict=True),
    )
    if (
        not archive.is_file()
        or not identity.is_file()
        or identity.stat().st_mode & 0o077
    ):
        raise SystemExit("Vyžadován existující archiv a soukromý klíč s právy 600.")
    if any(
        "\n" in str(path) or "\r" in str(path) or "$" in str(path) or "'" in str(path)
        for path in [archive, identity]
    ):
        raise SystemExit("Cesty nesmějí obsahovat nové řádky, dolar ani apostrof.")
    project = "tanklog-restore-" + uuid.uuid4().hex[:12]
    database = project.replace("-", "_")
    runtime = ROOT / ".runtime" / project
    runtime.mkdir(parents=True, mode=0o700)
    envfile = runtime / "restore.env"
    values = {
        "RESTORE_PROJECT": project,
        "RESTORE_DATABASE": database,
        "RESTORE_PASSWORD": secrets.token_urlsafe(32),
        "RESTORE_APP_PASSWORD": secrets.token_urlsafe(32),
        "RESTORE_SECRET_KEY": secrets.token_urlsafe(64),
        "BACKUP_DIRECTORY": str(archive.parent),
        "RESTORE_IDENTITY_FILE": str(identity),
    }
    with os.fdopen(
        os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        for key, value in values.items():
            stream.write(f"{key}='{value}'\n")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("POSTGRES_", "DJANGO_", "COMPOSE_", "RESTORE_", "BACKUP_", "TANKLOG_")
        )
    }
    compose = [
        "docker",
        "compose",
        "--project-name",
        project,
        "--env-file",
        str(envfile),
        "-f",
        "compose.restore.yaml",
    ]

    def run(*command):
        subprocess.run([*compose, *command], cwd=ROOT, env=environment, check=True)

    try:
        run("config", "--quiet")
        run("build", "operations", "backend")
        run("up", "--detach", "--wait", "--wait-timeout", "120", "db")
        run(
            "run",
            "--rm",
            "--no-deps",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "operations",
            "restore",
            "--archive",
            "/backups/" + archive.name,
            "--identity",
            "/identity.key",
            "--database",
            database,
        )
        run(
            "run",
            "--rm",
            "--no-deps",
            "backend",
            "python",
            "manage.py",
            "migrate",
            "--check",
        )
        run("run", "--rm", "--no-deps", "backend", "python", "manage.py", "check")
        if args.synthetic_check:
            run(
                "run",
                "--rm",
                "--no-deps",
                "-e",
                "TANKLOG_DRILL=1",
                "backend",
                "python",
                "/ops/drill_data.py",
                "verify",
            )
    finally:
        subprocess.run(
            [*compose, "down", "--remove-orphans"],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        print(f"Izolovaný projekt {project}: zastavený, nový svazek zůstává zachovaný.")


if __name__ == "__main__":
    main()
