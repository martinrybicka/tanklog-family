"""Kontrola produkční konfigurace bez přístupu na server a bez výpisu secrets."""

import argparse
import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


def validate(env):
    origin = env["TANKLOG_PUBLIC_ORIGIN"]
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.port
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", parsed.hostname)
        or parsed.hostname in {"localhost", "127.0.0.1"}
        or parsed.hostname.endswith(".invalid")
    ):
        raise ValueError("Produkce vyžaduje konkrétní HTTPS doménu bez cesty/portu.")
    if (
        env.get("TANKLOG_ENV") != "production"
        or env.get("DJANGO_DEBUG", "false") != "false"
        or env.get("DJANGO_SECURE_COOKIES", "true") != "true"
    ):
        raise ValueError("Produkce vyžaduje DEBUG=false a Secure cookies.")
    if (
        env.get("DJANGO_ALLOWED_HOSTS") != parsed.hostname
        or env.get("DJANGO_CSRF_TRUSTED_ORIGINS") != origin
    ):
        raise ValueError("Host a CSRF origin musí přesně odpovídat veřejné doméně.")
    network = ipaddress.ip_network(env["NPM_TRUSTED_CIDR"], strict=True)
    if network.prefixlen < (16 if network.version == 4 else 48):
        raise ValueError(
            "Důvěryhodný rozsah proxy je příliš široký; preferujte konkrétní IP NPM."
        )
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}", env["NPM_NETWORK_NAME"]):
        raise ValueError("Chybí konkrétní existující síť NPM.")
    for key in ["POSTGRES_USER", "POSTGRES_DB", "POSTGRES_ADMIN_USER"]:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", env.get(key, "")):
            raise ValueError(
                "Názvy DB a rolí musí být konkrétní jednoduché identifikátory."
            )
    for key, minimum in [
        ("DJANGO_SECRET_KEY", 50),
        ("POSTGRES_PASSWORD", 24),
        ("POSTGRES_ADMIN_PASSWORD", 24),
    ]:
        if (
            len(env.get(key, "")) < minimum
            or len(set(env[key])) < 8
            or not re.fullmatch(r"[A-Za-z0-9_-]+", env[key])
        ):
            raise ValueError(f"{key} nemá dostatečnou délku/rozmanitost.")
    if (
        len(
            {
                env[key]
                for key in [
                    "DJANGO_SECRET_KEY",
                    "POSTGRES_PASSWORD",
                    "POSTGRES_ADMIN_PASSWORD",
                ]
            }
        )
        != 3
    ):
        raise ValueError("Django, aplikace a bootstrap vyžadují tři různá tajemství.")
    if (
        not env.get("POSTGRES_ADMIN_USER")
        or env.get("POSTGRES_ADMIN_USER") == env.get("POSTGRES_USER", "tanklog")
        or env.get("POSTGRES_ADMIN_PASSWORD") == env.get("POSTGRES_PASSWORD")
    ):
        raise ValueError("Bootstrap a aplikace vyžadují oddělenou DB roli a heslo.")
    if not re.fullmatch(r"[a-f0-9]{40}", env.get("TANKLOG_REVISION", "")):
        raise ValueError("TANKLOG_REVISION musí být úplný commit nasazené aplikace.")
    if not env.get("TANKLOG_OPERATIONS_OWNER", "").strip():
        raise ValueError("Musí být určen konkrétní vlastník provozu a obnovy.")
    for key in ["BACKUP_DIRECTORY", "BACKUP_RECIPIENT_FILE"]:
        path = Path(env.get(key, ""))
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("Zálohovací cesty musí být absolutní a konkrétní.")
    if int(env.get("DJANGO_HSTS_SECONDS", "0")) < 0:
        raise ValueError("HSTS nemůže být záporné.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--require-backup-mount", action="store_true")
    args = parser.parse_args()
    path = args.env_file
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError(
                "Konfigurační soubor musí mít práva 600 a nesmí být odkaz."
            )
        env = {}
        for line in path.read_text().splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if key in env:
                    raise ValueError("Duplicitní proměnná v konfiguraci.")
                env[key] = value
        validate(env)
        if args.require_backup_mount:
            destination = Path(env["BACKUP_DIRECTORY"])
            if (
                destination.is_symlink()
                or not os.path.ismount(destination)
                or not Path(env["BACKUP_RECIPIENT_FILE"]).is_file()
            ):
                raise ValueError("Chybí skutečný mount záloh nebo veřejný klíč.")
    except (ValueError, KeyError, OSError):
        parser.exit(
            1,
            "Produkční konfigurace je neúplná nebo nebezpečná; hodnoty nebyly vypsány.\n",
        )
    print(
        "Konfigurace je staticky validní. DNS, certifikát, server, síť a úložiště tím nejsou ověřené."
    )


if __name__ == "__main__":
    main()
