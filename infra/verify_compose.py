"""Ověří sloučené Compose konfigurace bez přístupu k Docker daemonu či výpisu secrets."""

import json
import os
import shlex
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
command = shlex.split(os.environ.get("COMPOSE_COMMAND", "docker compose"))
environment = os.environ.copy()
# Pouze syntetické hodnoty pro konfiguraci budoucí produkční topologie.
environment.update(
    {
        "NPM_TRUSTED_CIDR": "172.30.0.0/24",
        "NPM_NETWORK_NAME": "tanklog-verification-only",
        "DJANGO_ALLOWED_HOSTS": "tanklog.example.invalid,127.0.0.1",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://tanklog.example.invalid",
    }
)

for mode in ("dev", "prod"):
    arguments = [
        *command,
        "--env-file",
        ".env",
        "-f",
        "compose.yaml",
        "-f",
        f"compose.{mode}.yaml",
        "config",
    ]
    subprocess.run([*arguments, "--quiet"], cwd=root, env=environment, check=True)
    config = json.loads(
        subprocess.check_output(
            [*arguments, "--format", "json"], cwd=root, env=environment
        )
    )
    services = config["services"]
    assert not services["db"].get("ports"), "Databáze nesmí publikovat port."
    assert not services["backend"].get("ports"), "Backend nesmí publikovat port."
    assert config["networks"]["database"]["internal"]
    assert services["db"]["volumes"][0]["target"] == "/var/lib/postgresql"
    assert "@sha256:" in services["db"]["image"]
    assert not services["backend"].get("volumes") or mode == "dev"
    assert set(config["volumes"]) == (
        {"postgres_data", "frontend_modules"} if mode == "dev" else {"postgres_data"}
    )
    if mode == "dev":
        ports = services["web"]["ports"]
        assert (
            len(ports) == 1
            and ports[0]["host_ip"] == "127.0.0.1"
            and str(ports[0]["published"]) == "8080"
        )
        assert "frontend" in services and not services["web"].get("build")
        assert services["backend"]["build"]["target"] == "development"
        assert (
            services["backend"]["environment"]["DJANGO_SETTINGS_MODULE"]
            == "config.settings.development"
        )
    else:
        assert "frontend" not in services
        assert all(not service.get("ports") for service in services.values())
        assert services["backend"]["build"]["target"] == "production"
        assert services["web"]["build"]["target"] == "production"
        assert not any(
            volume["type"] == "bind"
            for service in services.values()
            for volume in service.get("volumes", [])
        )
        assert config["networks"]["proxy"]["external"]
        assert "proxy" not in services["backend"]["networks"]
    print(f"Compose {mode}: syntaxe, porty, sítě, svazky a build targety OK.")
print("Tato kontrola nespouští kontejnery, nepřipojuje síť NPM a neověřuje běh image.")
