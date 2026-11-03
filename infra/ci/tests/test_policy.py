"""Regrese podstatných hranic CI, ne kopie všech řádků YAML."""

import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from infra.ci.check_repository import private_path
from infra.ci.containers import local_docker
from infra.ci.database import require_ci_database
from infra.ci.run_checks import validate_deploy_result
from infra.ci.verify_workflow import verify

ROOT = Path(__file__).resolve().parents[3]


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load(
            (ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
        )

    def test_current_workflow_passes(self):
        verify(self.workflow)

    def test_privileged_trigger_and_write_token_are_rejected(self):
        changed = copy.deepcopy(self.workflow)
        changed["on"]["pull_request_target"] = {}
        with self.assertRaises(ValueError):
            verify(changed)
        self.workflow["permissions"] = {"contents": "write"}
        with self.assertRaises(ValueError):
            verify(self.workflow)

    def test_moving_action_tag_and_persisted_credentials_are_rejected(self):
        step = self.workflow["jobs"]["repository"]["steps"][0]
        original = step["uses"]
        step["uses"] = "actions/checkout@v7"
        with self.assertRaises(ValueError):
            verify(self.workflow)
        step["uses"] = original
        step["with"]["persist-credentials"] = "true"
        with self.assertRaises(ValueError):
            verify(self.workflow)

    def test_deploy_and_shell_interpolation_are_rejected(self):
        for command in [
            "docker push image",
            "echo '${{ github.event.pull_request.title }}'",
            "docker compose down -v",
        ]:
            changed = copy.deepcopy(self.workflow)
            changed["jobs"]["containers"]["steps"].append({"run": command})
            with self.assertRaises(ValueError):
                verify(changed)

    def test_public_database_and_shallow_audit_are_rejected(self):
        changed = copy.deepcopy(self.workflow)
        changed["jobs"]["backend"]["services"]["postgres"]["ports"] = ["5432:5432"]
        with self.assertRaises(ValueError):
            verify(changed)
        self.workflow["jobs"]["repository"]["steps"][0]["with"]["fetch-depth"] = "1"
        with self.assertRaises(ValueError):
            verify(self.workflow)

    def test_self_hosted_runner_and_secrets_are_rejected(self):
        changed = copy.deepcopy(self.workflow)
        changed["jobs"]["backend"]["runs-on"] = "self-hosted"
        with self.assertRaises(ValueError):
            verify(changed)
        self.workflow["jobs"]["backend"]["env"]["KEY"] = "${{ secrets.PRODUCTION_KEY }}"
        with self.assertRaises(ValueError):
            verify(self.workflow)

    def test_synthetic_database_guard_rejects_regular_or_remote_database(self):
        for overrides in [
            {"POSTGRES_DB": "tanklog"},
            {"POSTGRES_HOST": "production.invalid"},
            {"TANKLOG_CI": "0"},
        ]:
            environment = {
                "TANKLOG_CI": "1",
                "POSTGRES_DB": "tanklog_ci",
                "POSTGRES_HOST": "127.0.0.1",
            } | overrides
            with (
                patch.dict(os.environ, environment, clear=True),
                self.assertRaises(SystemExit),
            ):
                require_ci_database()
        with patch.dict(
            os.environ,
            {
                "TANKLOG_CI": "1",
                "POSTGRES_DB": "tanklog_ci",
                "POSTGRES_HOST": "127.0.0.1",
            },
            clear=True,
        ):
            require_ci_database()

    def test_remote_docker_is_rejected_before_connection(self):
        with (
            patch("shutil.which", return_value="docker"),
            patch.dict(os.environ, {"DOCKER_HOST": "ssh://production.invalid"}),
            patch("subprocess.run") as call,
            self.assertRaises(SystemExit),
        ):
            local_docker()
        call.assert_not_called()

    def test_history_path_policy_keeps_icons_but_rejects_receipts_and_keys(self):
        for path in [
            ".env",
            ".runtime/private.txt",
            "data/backup.dump",
            "receipt.png",
            "private.key",
            "frontend/public/receipt.jpg",
        ]:
            self.assertTrue(private_path(path), path)
        for path in [
            ".env.example",
            "frontend/public/icons/icon-192.png",
            "backend/tests/fixtures/refueling_scenarios.json",
        ]:
            self.assertFalse(private_path(path), path)

    def test_deploy_check_accepts_only_explicit_hsts_exception(self):
        validate_deploy_result(0, "")
        validate_deploy_result(1, "WARNINGS: (security.W004) HSTS=0")
        for output in [
            "(security.W004) (security.W005)",
            "(security.W008)",
            "Traceback (security.W004)",
            "neznámá chyba",
        ]:
            with self.assertRaises(SystemExit):
                validate_deploy_result(1, output)

    def test_ci_compose_cannot_attach_production_network_or_publish_database(self):
        data = yaml.load((ROOT / "compose.ci.yaml").read_text(), Loader=yaml.BaseLoader)
        self.assertNotIn("networks", data)
        self.assertNotIn("db", data["services"])
        self.assertEqual(data["services"]["web"]["ports"], ["127.0.0.1:18080:8080"])
        self.assertEqual(
            data["services"]["backend"]["volumes"], ["./backend/tests:/app/tests:ro"]
        )
        self.assertEqual(data["services"]["backend"]["environment"]["TANKLOG_E2E"], "1")


if __name__ == "__main__":
    unittest.main()
