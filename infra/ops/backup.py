"""Šifrovaná konzistentní záloha a obnova jen do nové izolované místní DB."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql

FORMAT = 1


def connect(database=None, **kwargs):
    host = os.environ.get("POSTGRES_HOST", "db")
    if host not in {"127.0.0.1", "localhost", "db"}:
        raise ValueError("Povolená je pouze místní DB nebo interní Compose služba db.")
    return psycopg.connect(
        host=host,
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=database or os.environ["POSTGRES_DB"],
        options="-c timezone=UTC -c extra_float_digits=3 -c bytea_output=hex -c datestyle=ISO,YMD",
        **kwargs,
    )


def command_env(database=None):
    env = os.environ.copy()
    env.update(
        PGHOST=env.get("POSTGRES_HOST", "db"),
        PGPORT=env.get("POSTGRES_PORT", "5432"),
        PGUSER=env["POSTGRES_USER"],
        PGPASSWORD=env["POSTGRES_PASSWORD"],
        PGDATABASE=database or env["POSTGRES_DB"],
        PGCLIENTENCODING="UTF8",
    )
    env.pop("PGOPTIONS", None)
    return env


def run(command, **kwargs):
    result = subprocess.run(command, stderr=subprocess.PIPE, check=False, **kwargs)
    if result.returncode:
        # Výstup PostgreSQL může obsahovat soukromé hodnoty; do provozního logu nepatří.
        raise ValueError(
            f"Příkaz {Path(command[0]).name} selhal; soukromý výstup nebyl vypsán."
        )
    return result


def tools():
    version = run(["age", "--version"], stdout=subprocess.PIPE).stdout.decode().strip()
    if version != "v1.3.2":
        raise ValueError("Vyžadováno age v1.3.2 podle infra/ops/tools.json.")
    for name in ["pg_dump", "pg_restore"]:
        version = run([name, "--version"], stdout=subprocess.PIPE).stdout.decode()
        if not re.search(r"\b18\.6\b", version):
            raise ValueError("Vyžadovány PostgreSQL klientské nástroje 18.6.")


def fingerprint(connection):
    """Hash každého řádku včetně bytea a migrací, v deterministickém pořadí."""
    tables = connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ).fetchall()
    result = {}
    for (table,) in tables:
        digest = hashlib.sha256()
        count = 0
        query = sql.SQL(
            "SELECT encode(sha256(convert_to(row_to_json(t)::text, 'UTF8')), 'hex') AS h "
            "FROM {} AS t ORDER BY h"
        ).format(sql.Identifier("public", table))
        with connection.cursor(name="fingerprint_" + uuid.uuid4().hex) as cursor:
            cursor.execute(query)
            for (row_hash,) in cursor:
                digest.update(row_hash.encode() + b"\n")
                count += 1
        result[table] = {"rows": count, "sha256": digest.hexdigest()}
    if "refuelings_receiptattachment" in result:
        invalid = connection.execute(
            "SELECT count(*) FROM refuelings_receiptattachment "
            "WHERE sha256 <> encode(sha256(original_bytes), 'hex') "
            "OR size_bytes <> octet_length(original_bytes)"
        ).fetchone()[0]
        if invalid:
            raise ValueError(
                "Kontrolní součet nebo velikost uložené účtenky nesouhlasí."
            )
    return result


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def restore_name(name):
    if not re.fullmatch(r"tanklog_restore_[a-z0-9_]{1,40}", name):
        raise ValueError(
            "Obnova vyžaduje nové jméno tanklog_restore_*; běžná DB je zakázaná."
        )


def create_database(name):
    restore_name(name)
    with connect("postgres", autocommit=True) as connection:
        if connection.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", [name]
        ).fetchone():
            raise ValueError("Cílová DB už existuje. Nic se nemaže ani nepřepisuje.")
        owner = os.environ.get("RESTORE_OWNER")
        if owner:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", owner):
                raise ValueError("Neplatná cílová aplikační role.")
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template0").format(
                    sql.Identifier(name), sql.Identifier(owner)
                )
            )
        else:
            connection.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )


def backup(directory, recipient_file):
    tools()
    recipient = recipient_file.read_text().strip()
    if not re.fullmatch(r"age1[a-z0-9]{58}", recipient):
        raise ValueError(
            "Soubor příjemce musí obsahovat jeden veřejný X25519 age klíč."
        )
    revision = os.environ.get("TANKLOG_REVISION", "")
    if not re.fullmatch("[a-f0-9]{40}", revision):
        raise ValueError("Nastavte TANKLOG_REVISION na úplný commit nasazené aplikace.")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise ValueError("Zálohovací adresář nesmí být symbolický odkaz.")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="tanklog-backup-") as folder:
        folder = Path(folder)
        dump = folder / "database.dump"
        with connect() as connection:
            connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            snapshot = connection.execute("SELECT pg_export_snapshot()").fetchone()[0]
            created = connection.execute("SELECT transaction_timestamp()").fetchone()[0]
            with dump.open("xb") as stream:
                run(
                    [
                        "pg_dump",
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                        "--snapshot",
                        snapshot,
                    ],
                    stdout=stream,
                    env=command_env(),
                )
            evidence = fingerprint(connection)
        manifest = {
            "format": FORMAT,
            "snapshot_at": created.isoformat(),
            "revision": revision,
            "postgres": "18.6",
            "dump_sha256": sha256(dump),
            "tables": evidence,
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        name = (
            "tanklog-"
            + created.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:12]
            + ".tar.age"
        )
        partial = directory / (name + ".partial")
        partial_created = False
        try:
            with partial.open("xb") as output:
                partial_created = True
                partial.chmod(0o600)
                with tempfile.TemporaryFile() as errors:
                    process = subprocess.Popen(
                        ["age", "--encrypt", "--recipient", recipient],
                        stdin=subprocess.PIPE,
                        stdout=output,
                        stderr=errors,
                    )
                    try:
                        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
                            for member in ["database.dump", "manifest.json"]:
                                archive.add(
                                    folder / member, arcname=member, recursive=False
                                )
                        process.stdin.close()
                        if process.wait() != 0:
                            raise ValueError(
                                "Šifrování age selhalo; záloha nebyla publikována."
                            )
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                output.flush()
                os.fsync(output.fileno())
            # Hardlink odmítne přepsat jakýkoli existující cíl; stejný filesystem.
            final = directory / name
            os.link(partial, final)
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if partial_created:
                partial.unlink(missing_ok=True)
    return {
        "archive": str(final),
        "snapshot_at": created.isoformat(),
        "encrypted_sha256": sha256(final),
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def unpack(path, destination):
    maximum = int(os.environ.get("TANKLOG_MAX_RESTORE_BYTES", str(10 * 1024**3)))
    if path.stat().st_size > maximum:
        raise ValueError("Dešifrovaný archiv překračuje limit obnovy.")
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if len(members) != 2 or {m.name for m in members} != {
            "database.dump",
            "manifest.json",
        }:
            raise ValueError("Neočekávaný obsah archivu.")
        for member in members:
            limit = 1024**2 if member.name == "manifest.json" else maximum
            if not member.isfile() or not 0 < member.size <= limit:
                raise ValueError(
                    "Archiv obsahuje odkaz, chybný typ nebo nepovolenou velikost."
                )
        archive.extractall(destination, members=members, filter="data")


def decrypt(archive, identity, target):
    maximum = int(os.environ.get("TANKLOG_MAX_RESTORE_BYTES", str(10 * 1024**3)))
    with tempfile.TemporaryFile() as errors, target.open("xb") as output:
        process = subprocess.Popen(
            ["age", "--decrypt", "--identity", str(identity), str(archive)],
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        try:
            total = 0
            while chunk := process.stdout.read(1024**2):
                total += len(chunk)
                if total > maximum:
                    raise ValueError("Dešifrovaný archiv překračuje limit obnovy.")
                output.write(chunk)
            if process.wait() != 0:
                raise ValueError("Dešifrování selhalo; DB nebyla vytvořena.")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()


def restore(archive, identity, database):
    restore_name(database)
    tools()
    if identity.is_symlink() or identity.stat().st_mode & 0o077:
        raise ValueError("Soukromý age klíč vyžaduje práva 600 a nesmí být odkaz.")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="tanklog-restore-") as folder:
        folder = Path(folder)
        tar = folder / "decrypted.tar"
        decrypt(archive, identity, tar)
        unpack(tar, folder)
        manifest = json.loads((folder / "manifest.json").read_text())
        if (
            manifest.get("format") != FORMAT
            or sha256(folder / "database.dump") != manifest["dump_sha256"]
        ):
            raise ValueError(
                "Formát nebo kontrolní součet dumpu nesouhlasí; DB nebyla vytvořena."
            )
        snapshot_at = datetime.fromisoformat(manifest["snapshot_at"])
        if (
            snapshot_at.tzinfo is None
            or not re.fullmatch(r"[a-f0-9]{40}", manifest["revision"])
            or manifest["postgres"] != "18.6"
            or not isinstance(manifest["tables"], dict)
            or "django_migrations" not in manifest["tables"]
        ):
            raise ValueError("Metadata zálohy nejsou platná; DB nebyla vytvořena.")
        create_database(database)
        # Žádné --clean/--create; při chybě zůstane nový cíl pro kontrolu, stará DB se nemění.
        run(
            [
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                *(
                    ["--role", os.environ["RESTORE_OWNER"]]
                    if os.environ.get("RESTORE_OWNER")
                    else []
                ),
                "--dbname",
                database,
                str(folder / "database.dump"),
            ],
            env=command_env(database),
            stdout=subprocess.DEVNULL,
        )
        with connect(database) as connection:
            connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            if fingerprint(connection) != manifest["tables"]:
                raise ValueError(
                    "Obnovené řádky/účtenky/migrace neodpovídají snapshotu."
                )
    now = datetime.now(UTC)
    return {
        "database": database,
        "verified": True,
        "revision": manifest["revision"],
        "snapshot_at": manifest["snapshot_at"],
        "restored_at": now.isoformat(),
        "rto_seconds": round(time.monotonic() - started, 3),
        "snapshot_age_seconds": round(
            (now - datetime.fromisoformat(manifest["snapshot_at"])).total_seconds(), 3
        ),
        "tables_verified": len(manifest["tables"]),
    }


def retention_keep(dates):
    """7 denních + 4 týdenní + 6 měsíčních bodů; pouze plán, žádné mazání."""
    keep = set()
    for key, limit in [
        (lambda d: d.date(), 7),
        (lambda d: d.isocalendar()[:2], 4),
        (lambda d: (d.year, d.month), 6),
    ]:
        buckets = set()
        for date in sorted(dates, reverse=True):
            bucket = key(date)
            if bucket not in buckets and len(buckets) < limit:
                keep.add(date)
                buckets.add(bucket)
    return keep


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("backup")
    save.add_argument("--directory", type=Path, required=True)
    save.add_argument("--recipient-file", type=Path, required=True)
    recover = commands.add_parser("restore")
    recover.add_argument("--archive", type=Path, required=True)
    recover.add_argument("--identity", type=Path, required=True)
    recover.add_argument("--database", required=True)
    keep = commands.add_parser("retention-plan")
    keep.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = backup(args.directory, args.recipient_file)
        elif args.command == "restore":
            result = restore(args.archive, args.identity, args.database)
        else:
            archives = {}
            for path in args.directory.glob("tanklog-*.tar.age"):
                match = re.fullmatch(
                    r"tanklog-(\d{8}T\d{6}Z)-[a-f0-9]{12}\.tar\.age", path.name
                )
                if match:
                    archives[path.name] = datetime.strptime(
                        match[1], "%Y%m%dT%H%M%SZ"
                    ).replace(tzinfo=UTC)
            retained = retention_keep(archives.values())
            result = {
                "keep": [n for n, d in archives.items() if d in retained],
                "review_only": [n for n, d in archives.items() if d not in retained],
                "deleted": 0,
            }
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, psycopg.Error, KeyError, tarfile.TarError) as error:
        # DB výjimky mohou obsahovat data nebo přístupové údaje.
        if isinstance(error, ValueError):
            parser.exit(1, str(error) + "\n")
        parser.exit(
            1,
            "Operace selhala; soukromý výstup nebyl vypsán. Zkontrolujte nástroje, konfiguraci a místo.\n",
        )


if __name__ == "__main__":
    main()
