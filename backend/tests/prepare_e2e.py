"""Výhradně syntetický účet pro izolovanou databázi končící na _e2e."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from apps.accounts.models import User  # noqa: E402

if os.environ.get("TANKLOG_E2E") != "1" or not settings.DATABASES["default"]["NAME"].endswith("_e2e"):
    raise SystemExit("Povoleno pouze s TANKLOG_E2E=1 v izolované *_e2e databázi.")
user, _ = User.objects.get_or_create(username="e2e-admin")
user.system_role = "ADMIN"
user.display_name = "Testovací správce"
user.is_active = True
user.must_change_password = False
user.auth_epoch += 1
user.set_password("Synthetic-Test-Account-2026!")
user.save()
print("Syntetický E2E správce byl připraven v izolované testovací databázi.")
