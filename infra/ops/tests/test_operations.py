"""Bezpečnostní a retenční očekávání fáze 7."""

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from infra.ops.backup import restore_name, retention_keep, unpack
from infra.ops.preflight import validate


class OperationsTests(unittest.TestCase):
    def test_restore_never_accepts_ordinary_database(self):
        for name in [
            "tanklog",
            "tanklog_e2e",
            "postgres",
            "tanklog_restore_x;DROP DATABASE x",
            "../tanklog",
        ]:
            with self.assertRaises(ValueError):
                restore_name(name)
        restore_name("tanklog_restore_trial_1")

    def test_retention_keeps_daily_weekly_monthly_recovery_points(self):
        now = datetime(2026, 11, 3, tzinfo=UTC)
        dates = [now - timedelta(days=n) for n in range(240)]
        keep = retention_keep(dates)
        self.assertTrue(set(dates[:7]).issubset(keep))
        self.assertIn(datetime(2026, 6, 30, tzinfo=UTC), keep)
        self.assertNotIn(datetime(2026, 3, 9, tzinfo=UTC), keep)
        self.assertLessEqual(len(keep), 17)

    def test_archive_rejects_traversal_and_links_before_extracting(self):
        import io
        import tarfile

        for name, kind in [
            ("../escape", tarfile.REGTYPE),
            ("database.dump", tarfile.SYMTYPE),
        ]:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "bad.tar"
                with tarfile.open(source, "w") as archive:
                    entry = tarfile.TarInfo(name)
                    entry.type = kind
                    entry.size = 1 if kind == tarfile.REGTYPE else 0
                    archive.addfile(entry, io.BytesIO(b"x") if entry.size else None)
                with self.assertRaises(ValueError):
                    unpack(source, Path(directory))

    def environment(self):
        return {
            "TANKLOG_ENV": "production",
            "TANKLOG_OPERATIONS_OWNER": "Testovací provozovatel",
            "BACKUP_DIRECTORY": "/mnt/tanklog-backups",
            "BACKUP_RECIPIENT_FILE": "/etc/tanklog/recipient.txt",
            "TANKLOG_PUBLIC_ORIGIN": "https://fuel.example.org",
            "DJANGO_ALLOWED_HOSTS": "fuel.example.org",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://fuel.example.org",
            "DJANGO_SECRET_KEY": "synthetic-only-" + "abcDEF0123456789" * 4,
            "POSTGRES_USER": "tanklog",
            "POSTGRES_DB": "tanklog",
            "POSTGRES_ADMIN_USER": "bootstrap",
            "POSTGRES_ADMIN_PASSWORD": "synthetic-admin-only-" + "abcDEF0123456789" * 2,
            "POSTGRES_PASSWORD": "synthetic-only-" + "abcDEF0123456789" * 2,
            "NPM_NETWORK_NAME": "existing_proxy",
            "NPM_TRUSTED_CIDR": "172.30.1.4/32",
            "TANKLOG_REVISION": "a" * 40,
        }

    def test_preflight_rejects_http_wildcards_broad_proxy_and_insecure_cookies(self):
        validate(self.environment())
        for key, value in [
            ("TANKLOG_PUBLIC_ORIGIN", "http://fuel.example.org"),
            ("DJANGO_ALLOWED_HOSTS", "*"),
            ("NPM_TRUSTED_CIDR", "0.0.0.0/0"),
            ("DJANGO_SECURE_COOKIES", "false"),
            ("DJANGO_DEBUG", "true"),
            ("TANKLOG_PUBLIC_ORIGIN", "https://fuel.example.org/path"),
            ("DJANGO_CSRF_TRUSTED_ORIGINS", "https://evil.example.org"),
            ("TANKLOG_REVISION", "latest"),
            ("BACKUP_DIRECTORY", "relative/backups"),
            ("TANKLOG_OPERATIONS_OWNER", ""),
            ("POSTGRES_ADMIN_USER", "tanklog"),
            ("POSTGRES_PASSWORD", self.environment()["DJANGO_SECRET_KEY"]),
        ]:
            with self.assertRaises(ValueError, msg=key):
                validate(self.environment() | {key: value})

    def test_existing_restore_database_is_refused_before_pg_restore(self):
        from infra.ops.backup import create_database

        with patch("infra.ops.backup.connect") as connect:
            connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
                1,
            )
            with self.assertRaises(ValueError):
                create_database("tanklog_restore_existing")

    def test_checksum_mismatch_is_rejected_before_database_creation(self):
        import json
        import tarfile

        from infra.ops.backup import restore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = root / "identity.key"
            identity.write_text("synthetic-only")
            identity.chmod(0o600)
            (root / "database.dump").write_bytes(b"corrupted")
            (root / "manifest.json").write_text(
                json.dumps({"format": 1, "dump_sha256": "0" * 64})
            )
            archive = root / "archive.tar"
            with tarfile.open(archive, "w") as output:
                for member in ["database.dump", "manifest.json"]:
                    output.add(root / member, arcname=member)

            def decrypt(source, key, destination):
                destination.write_bytes(source.read_bytes())

            with (
                patch("infra.ops.backup.tools"),
                patch("infra.ops.backup.decrypt", side_effect=decrypt),
                patch("infra.ops.backup.create_database") as create,
            ):
                with self.assertRaises(ValueError):
                    restore(archive, identity, "tanklog_restore_mismatch")
                create.assert_not_called()

    def test_decryption_stops_at_size_limit(self):
        import io

        from infra.ops.backup import decrypt

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict("os.environ", {"TANKLOG_MAX_RESTORE_BYTES": "3"}),
                patch("infra.ops.backup.subprocess.Popen") as process,
            ):
                process.return_value.stdout = io.BytesIO(b"1234")
                process.return_value.poll.return_value = None
                with self.assertRaises(ValueError):
                    decrypt(
                        Path("archive.age"),
                        Path("identity.key"),
                        Path(directory) / "plain.tar",
                    )
                process.return_value.kill.assert_called_once()

    def test_private_identity_permissions_are_enforced_before_decryption(self):
        from infra.ops.backup import restore

        with tempfile.TemporaryDirectory() as directory:
            identity = Path(directory) / "identity.key"
            identity.write_text("synthetic-only")
            identity.chmod(0o644)
            with (
                patch("infra.ops.backup.tools"),
                patch("infra.ops.backup.decrypt") as decrypt,
            ):
                with self.assertRaises(ValueError):
                    restore(
                        Path("archive.age"), identity, "tanklog_restore_permissions"
                    )
                decrypt.assert_not_called()

    def test_restore_orchestration_cannot_reuse_production_project_or_environment(self):
        import os

        from infra.ops import restore_compose

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, identity = root / "sample.tar.age", root / "identity.key"
            archive.write_bytes(b"synthetic-only")
            identity.write_text("synthetic-only")
            identity.chmod(0o600)
            with (
                patch.object(restore_compose, "ROOT", root),
                patch.object(restore_compose, "local_docker"),
                patch(
                    "sys.argv",
                    ["restore", "--archive", str(archive), "--identity", str(identity)],
                ),
                patch.dict(
                    os.environ,
                    {
                        "COMPOSE_FILE": "compose.prod.yaml",
                        "RESTORE_PROJECT": "tanklog-prod",
                        "POSTGRES_DB": "ordinary-data",
                    },
                ),
                patch.object(restore_compose.subprocess, "run") as calls,
            ):
                restore_compose.main()
            for call in calls.call_args_list:
                command = call.args[0]
                self.assertIn("compose.restore.yaml", command)
                self.assertNotIn("compose.prod.yaml", command)
                project = command[command.index("--project-name") + 1]
                self.assertTrue(project.startswith("tanklog-restore-"))
                self.assertNotIn("POSTGRES_DB", call.kwargs["env"])
                self.assertNotIn("COMPOSE_FILE", call.kwargs["env"])
                self.assertNotIn("-v", command)
                self.assertNotIn("prune", command)

    def test_readiness_uses_configured_host_without_relaxing_allowed_hosts(self):
        import os
        import subprocess
        import sys
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        import yaml

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(
                    200 if self.headers["Host"] == "fuel.example.org" else 400
                )
                self.end_headers()

            def log_message(self, *_):
                pass

        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                root = Path(__file__).resolve().parents[3]
                command = yaml.safe_load((root / "compose.yaml").read_text())[
                    "services"
                ]["backend"]["healthcheck"]["test"][3]
                command = command.replace(
                    "127.0.0.1:8000", f"127.0.0.1:{server.server_port}"
                )
                result = subprocess.run(
                    [sys.executable, "-c", command],
                    env=os.environ | {"DJANGO_ALLOWED_HOSTS": "fuel.example.org"},
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0)
            finally:
                server.shutdown()
                thread.join()
