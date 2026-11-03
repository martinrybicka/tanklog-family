"""Reprodukovatelné OCR srovnání na výhradně syntetické české účtence."""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django  # noqa: E402

django.setup()
from apps.extensions.ocr import engine  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

root = ROOT / ".runtime/phase8-ocr"
root.mkdir(parents=True, exist_ok=True)
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
if not font_file:
    raise SystemExit("Pro syntetický OCR benchmark chybí Arial/DejaVu Sans.")
image = Image.new("RGB", (1000, 700), "white")
draw = ImageDraw.Draw(image)
font = ImageFont.truetype(str(font_file), 36)
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
    draw.text((40, 40 + n * 80), line, fill="black", font=font)
file = root / "synthetic.png"
image.save(file)
expected = {
    "date": "2026-11-02",
    "liters": "10.500",
    "unit_price_entered": "40.0000",
    "total_amount": "420.00",
    "odometer_km": "12345",
    "station_code": "ORLEN",
}
results = {}
for psm in [6, 11]:
    raw, fields = engine(file.read_bytes(), psm)
    correct = []
    for key, value in expected.items():
        actual = fields.get(key, {}).get("value")
        if actual is not None and (
            Decimal(actual) == Decimal(value)
            if key not in ["date", "station_code"]
            else actual == value
        ):
            correct.append(key)
    results[str(psm)] = {
        "correct": len(correct),
        "total": len(expected),
        "fields": correct,
        "suggestions": fields,
        "raw_text": raw,
    }
(root / "result.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print(json.dumps(results, ensure_ascii=False, indent=2))
if results["6"]["correct"] != len(expected):
    raise SystemExit("Výchozí OCR nesplnilo očekávání syntetického benchmarku.")
