"""Pouze syntetická data v explicitní *_e2e DB; stdout je strojové JSON pro Playwright."""

import hashlib
import io
import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.extensions.models import VehicleDataSnapshot, VehicleImage  # noqa: E402
from apps.refuelings.models import ReceiptAttachment, Refueling  # noqa: E402
from apps.vehicles.models import Vehicle  # noqa: E402

if os.environ.get("TANKLOG_E2E") != "1" or not settings.DATABASES["default"]["NAME"].endswith("_e2e"):
    raise SystemExit("Syntetická příprava je povolená jen nad explicitní *_e2e DB.")
user = User.objects.get(username="e2e-admin")
font_file = next(
    (
        p
        for p in [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        if p.exists()
    ),
    None,
)
# CI image má zamčený DejaVu font. Nativní běh používá dostupný Arial.
font = ImageFont.truetype(str(font_file), 36) if font_file else ImageFont.load_default(size=36)
results = {}
for mode in ["desktop", "mobile"]:
    suffix = uuid.uuid4().hex[:8]
    vin = "TST" + str(uuid.uuid4().int)[:14]
    car = Vehicle.objects.create(
        owner=user,
        name=f"000 Rozšíření {mode} {suffix}",
        make="Původní",
        model="Původní",
        vin=vin,
        fuel_type="PETROL",
        initial_odometer_km=0,
    )
    suggestions = {"make": "Testovací značka", "model": "Testovací model"}
    snapshot = VehicleDataSnapshot.objects.create(
        applicant=user,
        vehicle=car,
        vin=vin,
        raw={"Status": 1, "Data": {"VIN": vin}},
        suggestions=suggestions,
    )
    image = Image.new("RGB", (1000, 700), "white")
    draw = ImageDraw.Draw(image)
    for n, line in enumerate(
        [
            "ORLEN",
            "DATUM 02.11.2026",
            "MNOŽSTVÍ 10,500 l",
            "CENA/L 40,0000",
            "CELKEM 420,00",
            "TACHOMETR 12345",
        ]
    ):
        draw.text((40, 40 + n * 80), line, font=font, fill="black")
    original = io.BytesIO()
    image.save(original, "PNG")
    preview = io.BytesIO()
    image.save(preview, "JPEG")
    raw = original.getvalue()
    item = Refueling.objects.create(
        vehicle=car,
        date=date(2026, 11, 2),
        day_sequence=1,
        liters="10",
        unit_price_entered="40",
        total_amount="400",
        amount_source="ENTERED",
        odometer_km=12000,
        fuel_type="PETROL",
        created_by=user,
        updated_by=user,
    )
    ReceiptAttachment.objects.create(
        refueling=item,
        original_bytes=raw,
        preview_bytes=preview.getvalue(),
        content_type="image/png",
        size_bytes=len(raw),
        width=1000,
        height=700,
        sha256=hashlib.sha256(raw).hexdigest(),
        original_filename="synteticky-test.png",
        uploaded_by=user,
    )
    photo = Image.new("RGB", (200, 120), "#b4c8e0")
    body = io.BytesIO()
    photo.save(body, "JPEG")
    metadata = {
        "author": "Syntetický testovací autor",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "source": "https://commons.wikimedia.org/wiki/File:Synthetic_test.jpg",
        "title": "Syntetický test; není skutečný snímek auta",
        "modified": "Pouze automatizovaný fixture test",
    }
    candidate = VehicleImage.objects.create(
        vehicle=car,
        applicant=user,
        original=body.getvalue(),
        preview=body.getvalue(),
        content_type="image/jpeg",
        metadata=metadata,
        match={
            "make": suggestions["make"],
            "model": suggestions["model"],
            "vin_hash": hashlib.sha256(vin.encode()).hexdigest(),
        },
    )
    results[mode] = {
        "car": str(car.pk),
        "name": car.name,
        "vin": vin,
        "refueling": str(item.pk),
        "photo": {
            "id": str(candidate.pk),
            "metadata": metadata,
            "url": f"/api/v1/vehicle-images/{candidate.pk}/",
        },
    }
print(json.dumps(results, ensure_ascii=False))
