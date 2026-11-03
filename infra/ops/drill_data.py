"""Syntetická data a API kontrola obnovy, výhradně ve vyhrazených cvičných DB."""

import hashlib
import io
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Příkaz se spouští z backend/ nebo explicitním TANKLOG_BACKEND_DIR.
sys.path.insert(0, str(Path(os.environ.get("TANKLOG_BACKEND_DIR", Path.cwd()))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
import django  # noqa: E402

django.setup()
from apps.accounts.models import User  # noqa: E402
from apps.refuelings.models import ReceiptAttachment, Refueling  # noqa: E402
from apps.vehicles.models import Vehicle, VehicleAccess  # noqa: E402
from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402
from PIL import Image  # noqa: E402

PASSWORD = "Synthetic-Restore-Only-2026!"
name = settings.DATABASES["default"]["NAME"]
if os.environ.get("TANKLOG_DRILL") != "1" or not name.startswith(
    ("tanklog_backup_", "tanklog_restore_")
):
    raise SystemExit("Pouze explicitní izolované obnovovací cvičení.")


def seed():
    if User.objects.exists():
        raise SystemExit("Zdroj již obsahuje účty; syntetická příprava odmítnuta.")
    owner = User.objects.create_user(
        username="drill-owner", password=PASSWORD, system_role="ADMIN"
    )
    viewer = User.objects.create_user(username="drill-viewer", password=PASSWORD)
    User.objects.create_user(username="drill-outsider", password=PASSWORD)
    car = Vehicle.objects.create(
        owner=owner,
        name="Syntetické auto obnovy",
        make="Test",
        model="Restore",
        fuel_type="PETROL",
        initial_odometer_km=0,
    )
    VehicleAccess.objects.create(
        vehicle=car, user=viewer, role="VIEWER", granted_by=owner
    )
    for day, liters, km, full in [
        (date(2026, 1, 31), "50", 10000, True),
        (date(2026, 2, 1), "20", 10300, False),
        (date(2026, 2, 5), "25", 10600, True),
    ]:
        record = Refueling.objects.create(
            vehicle=car,
            date=day,
            liters=liters,
            total_amount=Decimal(liters) * 40,
            unit_price_entered="40",
            amount_source="ENTERED",
            day_sequence=1,
            fuel_type="PETROL",
            odometer_km=km,
            is_full_tank=full,
            created_by=owner,
            updated_by=owner,
        )
        original, preview = io.BytesIO(), io.BytesIO()
        Image.new("RGB", (20, 10), "blue").save(original, "PNG")
        Image.new("RGB", (20, 10), "blue").save(preview, "JPEG")
        raw = original.getvalue()
        ReceiptAttachment.objects.create(
            refueling=record,
            original_bytes=raw,
            preview_bytes=preview.getvalue(),
            content_type="image/png",
            size_bytes=len(raw),
            width=20,
            height=10,
            sha256=hashlib.sha256(raw).hexdigest(),
            original_filename="synteticka.png",
            uploaded_by=owner,
        )
    print("Syntetická data: 3 účty, sdílení, 3 tankování a 3 účtenky s náhledy.")


def login(username):
    client = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
    token = client.get("/api/v1/auth/csrf/", secure=True).json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login/",
        {"username": username, "password": PASSWORD},
        content_type="application/json",
        secure=True,
        HTTP_X_CSRFTOKEN=token,
        HTTP_ORIGIN="https://localhost",
    )
    assert response.status_code == 200
    assert (
        client.cookies["sessionid"]["secure"]
        and client.cookies["sessionid"]["httponly"]
    )
    return client


def verify():
    assert name.startswith("tanklog_restore_")
    assert not Refueling.objects.exclude(note="").exists()
    receipt = ReceiptAttachment.objects.first()
    assert receipt is not None
    url = f"/api/v1/refuelings/{receipt.refueling_id}/receipt/"
    anonymous = Client(HTTP_HOST="localhost")
    assert anonymous.get(url, secure=True).status_code in {401, 403}
    owner = login("drill-owner")
    for variant, expected in [
        ("", bytes(receipt.original_bytes)),
        ("?variant=preview", bytes(receipt.preview_bytes)),
    ]:
        response = owner.get(url + variant, secure=True)
        assert response.status_code == 200
        actual = (
            b"".join(response.streaming_content)
            if response.streaming
            else response.content
        )
        assert hashlib.sha256(actual).digest() == hashlib.sha256(expected).digest()
    viewer = login("drill-viewer")
    assert viewer.get(url, secure=True).status_code == 200
    assert login("drill-outsider").get(url, secure=True).status_code == 404
    car = receipt.refueling.vehicle_id
    data = owner.get(
        f"/api/v1/dashboard/?period=custom&date_from=2026-02-01&date_to=2026-02-28&vehicle_id={car}",
        secure=True,
    ).json()
    assert data["consumption_l_100km"] == "7.500000"
    assert data["purchases"]["amount"] == "1800.00"
    assert data["purchases"]["liters"] == "45.000"
    print(
        "Obnovené API: skutečný login/CSRF/Secure session, originál+náhled, VIEWER a odmítnutí cizího účtu; 45 l / 1800 Kč / 7,50 l/100 km."
    )


if __name__ == "__main__":
    {"seed": seed, "verify": verify}[sys.argv[1]]()
