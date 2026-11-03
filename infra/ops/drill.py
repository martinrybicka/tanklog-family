"""Místní syntetické cvičení bez Dockeru. Založí nové DB, žádnou existující nemaže."""

import json
import os
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from backup import backup, connect, fingerprint, restore
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]


def main():
    if os.environ.get("TANKLOG_DRILL") != "1" or os.environ.get(
        "POSTGRES_HOST"
    ) not in {"localhost", "127.0.0.1"}:
        raise SystemExit("Pouze TANKLOG_DRILL=1 a místní syntetické cvičení.")
    os.umask(0o077)
    suffix = uuid.uuid4().hex[:12]
    source, target = f"tanklog_backup_{suffix}_e2e", f"tanklog_restore_{suffix}"
    runtime = ROOT / ".runtime" / ("phase7-drill-" + suffix)
    runtime.mkdir(parents=True, mode=0o700)
    identity = runtime / "identity.key"
    with identity.open("xb") as stream:
        subprocess.run(
            ["age-keygen"], stdout=stream, stderr=subprocess.DEVNULL, check=True
        )
    public = subprocess.check_output(
        ["age-keygen", "-y", str(identity)], text=True
    ).strip()
    recipient = runtime / "recipient.txt"
    recipient.write_text(public)
    with connect("postgres", autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                sql.Identifier(source)
            )
        )
    os.environ.update(
        POSTGRES_DB=source,
        TANKLOG_BACKEND_DIR=str(ROOT / "backend"),
        DJANGO_SETTINGS_MODULE="config.settings.production",
        DJANGO_DEBUG="false",
        DJANGO_SECURE_COOKIES="true",
        DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1",
        DJANGO_CSRF_TRUSTED_ORIGINS="https://localhost",
        TANKLOG_REVISION=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    )

    def django(*arguments):
        subprocess.run(
            [sys.executable, *map(str, arguments)], cwd=ROOT / "backend", check=True
        )

    django("manage.py", "migrate", "--noinput")
    django(ROOT / "infra/ops/drill_data.py", "seed")

    def concurrent_fingerprint(connection):
        # Zápis po pg_dump musí zůstat mimo původní sdílený snapshot i manifest.
        with connect(autocommit=True) as writer:
            writer.execute(
                "UPDATE refuelings_refueling SET note='Syntetická změna po snapshotu'"
            )
        return fingerprint(connection)

    with patch("backup.fingerprint", side_effect=concurrent_fingerprint):
        saved = backup(runtime / "backups", recipient)
    archive = Path(saved["archive"])
    rejected = []
    wrong = runtime / "wrong.key"
    with wrong.open("xb") as stream:
        subprocess.run(
            ["age-keygen"], stdout=stream, stderr=subprocess.DEVNULL, check=True
        )
    damaged = runtime / "damaged.tar.age"
    damaged.write_bytes(archive.read_bytes()[:-20])
    for label, candidate, key in [
        ("wrong_identity", archive, wrong),
        ("truncated_ciphertext", damaged, identity),
    ]:
        try:
            restore(candidate, key, target)
        except ValueError:
            rejected.append(label)
        else:
            raise SystemExit("Poškozená/nečitelná záloha nesměla projít.")
    # Druhý fyzicky oddělený cluster, nikdy původní datový adresář.
    bindir = Path(shutil.which("pg_dump")).resolve().parent
    cluster = runtime / "restored-postgres"
    password_file = runtime / "bootstrap-password.key"
    admin_password, app_password = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    password_file.write_text(admin_password)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    recovered_started = time.monotonic()
    subprocess.run(
        [
            str(bindir / "initdb"),
            "-D",
            str(cluster),
            "-U",
            "tanklog_bootstrap",
            "--auth-host=scram-sha-256",
            "--auth-local=scram-sha-256",
            "--pwfile",
            str(password_file),
            "--encoding=UTF8",
            "--locale=C",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            str(bindir / "pg_ctl"),
            "-D",
            str(cluster),
            "-l",
            str(runtime / "postgres.log"),
            "-o",
            shlex.join(["-h", "127.0.0.1", "-p", str(port), "-k", str(runtime)]),
            "-w",
            "start",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        os.environ.update(
            POSTGRES_PORT=str(port),
            POSTGRES_USER="tanklog_bootstrap",
            POSTGRES_PASSWORD=admin_password,
            POSTGRES_DB="postgres",
            RESTORE_OWNER="tanklog",
        )
        role_env = os.environ | {
            "PGHOST": "127.0.0.1",
            "PGPORT": str(port),
            "PGPASSWORD": admin_password,
            "TANKLOG_APP_DB_USER": "tanklog",
            "TANKLOG_APP_DB_PASSWORD": app_password,
        }
        subprocess.run(
            ["sh", str(ROOT / "infra/postgres/init-role.sh")],
            env=role_env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        result = restore(archive, identity, target)
        try:
            restore(archive, identity, target)
        except ValueError:
            rejected.append("existing_database")
        else:
            raise SystemExit("Existující cílová DB nesměla být přepsána.")
        os.environ.update(
            POSTGRES_DB=target, POSTGRES_USER="tanklog", POSTGRES_PASSWORD=app_password
        )
        with connect() as connection:
            role = connection.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user"
            ).fetchone()
            assert role == (False, False, False)
        django("manage.py", "migrate", "--check")
        django("manage.py", "check")
        django(ROOT / "infra/ops/drill_data.py", "verify")
        result["verified_rto_seconds"] = round(time.monotonic() - recovered_started, 3)
        result["negative_checks"] = rejected
        result["separate_cluster"] = True
        result["concurrent_snapshot_verified"] = True
        result["application_role_is_superuser"] = False
        result["backup_seconds"] = saved["duration_seconds"]
    finally:
        subprocess.run(
            [str(bindir / "pg_ctl"), "-D", str(cluster), "-m", "fast", "-w", "stop"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    result["source_database"] = source
    result["archive"] = saved["archive"]
    (runtime / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(
        "Obě syntetické DB zachované. Testovací klíč je pouze v ignorovaném .runtime; není produkční."
    )


if __name__ == "__main__":
    main()
