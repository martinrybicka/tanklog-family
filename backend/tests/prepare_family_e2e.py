"""Vlastní syntetická rodina pouze v oddělené *_e2e databázi."""

import base64
import io
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.family.models import FamilyPreference  # noqa: E402
from apps.refuelings.models import Refueling  # noqa: E402
from apps.vehicles.models import Vehicle  # noqa: E402

if os.environ.get("TANKLOG_E2E") != "1" or not settings.DATABASES["default"]["NAME"].endswith("_e2e"):
    raise SystemExit("Pouze explicitní syntetická *_e2e DB.")
result = {}
for mode in ["desktop", "mobile"]:
    user, _ = User.objects.get_or_create(username=f"family-{mode}")
    user.display_name = "Alex"
    user.is_active = True
    user.must_change_password = False
    user.theme = "LIGHT"
    user.auth_epoch += 1
    user.set_password("Synthetic-Test-Account-2026!")
    user.save()
    car, _ = Vehicle.objects.get_or_create(
        owner=user,
        name="Naše Octavia",
        defaults={
            "make": "Škoda",
            "model": "Octavia",
            "fuel_type": "PETROL",
            "initial_odometer_km": 0,
            "registration_plate": "TEST AUTO",
        },
    )
    FamilyPreference.objects.update_or_create(user=user, defaults={"default_vehicle": car})
    if not Refueling.objects.filter(vehicle=car).exists():
        for day, liters, amount, station in [
            (1, "42.350", "1647.42", "ORLEN"),
            (2, "35.000", "1365.00", "SHELL"),
            (3, "20.500", "799.50", "MOL"),
        ]:
            Refueling.objects.create(
                vehicle=car,
                date=date(2026, 11, day),
                day_sequence=1,
                liters=Decimal(liters),
                total_amount=Decimal(amount),
                amount_source="ENTERED",
                fuel_type="PETROL",
                station_code=station,
                created_by=user,
                updated_by=user,
                odometer_km=10000 + day * 600,
            )
    result[mode] = {"user": user.username, "car": str(car.pk), "user_id": str(user.pk)}
font_path = next(
    p
    for p in [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    if p.exists()
)
image = Image.new("RGB", (1000, 700), "white")
font = ImageFont.truetype(str(font_path), 36)
draw = ImageDraw.Draw(image)
for n, line in enumerate(
    ["ORLEN", "DATUM 02.11.2026", "MNOŽSTVÍ 10,500 l", "CENA/L 40,0000", "CELKEM 420,00", "TACHOMETR 12345"]
):
    draw.text((40, 40 + n * 80), line, font=font, fill="black")
buffer = io.BytesIO()
image.save(buffer, "PNG")
if os.environ.get("FAMILY_E2E_IMAGE"):
    file = Path(os.environ["FAMILY_E2E_IMAGE"])
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(buffer.getvalue())
result["image_base64"] = base64.b64encode(buffer.getvalue()).decode()
print(json.dumps(result))
