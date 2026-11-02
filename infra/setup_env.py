"""Vytvoří pouze chybějící lokální .env; existující konfiguraci nikdy nepřepisuje."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env"
values = (root / ".env.example").read_text()
values = values.replace(
    "DJANGO_SECRET_KEY=\n", f"DJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\n"
)
values = values.replace(
    "POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
)
try:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print(".env již existuje. Nebyl změněn.")
else:
    with os.fdopen(descriptor, "w") as stream:
        stream.write(values)
    print("Lokální .env byl vytvořen s náhodnými tajnými hodnotami a oprávněním 600.")
