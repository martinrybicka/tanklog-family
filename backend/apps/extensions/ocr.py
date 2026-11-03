import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image, ImageOps

from apps.audit.models import record
from apps.core.errors import Problem
from apps.refuelings import services as fuel
from apps.refuelings.models import ReceiptAttachment
from apps.refuelings.selectors import refueling_for
from apps.vehicles.selectors import vehicle_for

from .integrations import reserve
from .models import IntegrationGate, ReceiptExtraction


def parse_tsv(tsv):
    lines = {}
    for token in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        text = token.get("text", "").strip()
        if not text:
            continue
        key = tuple(token.get(v, "") for v in ["page_num", "block_num", "par_num", "line_num"])
        try:
            confidence = max(0, min(100, float(token.get("conf", "0"))))
        except ValueError:
            confidence = 0
        line = lines.setdefault(key, [])
        line.append((text, confidence))
    raw = "\n".join(" ".join(word for word, _ in tokens) for tokens in lines.values())[:60000]
    suggestions = {}
    patterns = {
        "liters": r"(?:litry|litru|mnozstvi|množství|objem|benz[ií]n|nafta|diesel|natural)\s*[:=]?\s*(\d+[.,]\d{1,3})\s*(?:lit(?:ru|rů|ry)?|[lI1])\b",
        "unit_price_entered": r"(?:cena\s*(?:za\s*)?(?:litr|/l)|kc/l|kč/l)\s*[:=]?\s*(\d+[.,]\d{1,4})",
        "total_amount": r"(?:celkem|celkova castka|celková částka|total|k\s*[úu]hrad[eě])\s*[:=]?\s*(\d+(?:[.,]\d{1,2})?)",
        "odometer_km": r"(?:tachometr|stav km|km)\s*[:=]?\s*(\d{1,8})\b",
    }
    found = {}
    for tokens in lines.values():
        text = " ".join(word for word, _ in tokens)
        confidence = round(min(value for _, value in tokens), 1)
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.I)
            if match:
                value = match[1].replace(",", ".")
                found.setdefault(field, []).append(
                    {
                        "value": value,
                        "confidence": str(
                            min(confidence, 50)
                            if field == "liters" and re.search(r"\d\s*[I1]\b", text)
                            else confidence
                        ),
                        "source": text[:250],
                    }
                )
        match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
        if match:
            try:
                value = date(int(match[3]), int(match[2]), int(match[1]))
            except ValueError:
                continue
            if value <= timezone.localdate():
                found.setdefault("date", []).append(
                    {
                        "value": str(value),
                        "confidence": str(confidence),
                        "source": text[:250],
                    }
                )
        for code in ["ORLEN", "SHELL", "MOL", "OMV", "EUROOIL", "TANK ONO"]:
            if re.search(r"\b" + re.escape(code) + r"\b", text, re.I):
                found.setdefault("station_code", []).append(
                    {
                        "value": "TANK_ONO" if code == "TANK ONO" else code,
                        "confidence": str(confidence),
                        "source": text[:250],
                    }
                )
    for field, values in found.items():
        if len({item["value"] for item in values}) == 1:
            suggestions[field] = max(values, key=lambda item: Decimal(item["confidence"]))
    return raw, suggestions


@transaction.atomic
def acquire():
    now = timezone.now()
    for slot in range(2):
        gate, _ = IntegrationGate.objects.get_or_create(
            name=f"ocr-slot-{slot}", defaults={"window": now - timedelta(seconds=60)}
        )
        gate = IntegrationGate.objects.select_for_update().get(pk=gate.pk)
        if gate.window <= now:
            gate.window = now + timedelta(seconds=25)
            gate.save(update_fields=["window"])
            return gate.pk, gate.window
    raise Problem("ocr_busy", "OCR právě zpracovává jiné účtenky. Zkuste to později.", 429)


def engine(raw, psm=6):
    binary = shutil.which(settings.OCR_BINARY)
    data = Path(settings.OCR_DATA)
    if not binary or not data.exists():
        raise Problem(
            "ocr_not_configured",
            "Lokální OCR není nainstalované. Údaje lze zadat ručně.",
            503,
        )
    try:
        version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Problem(
            "ocr_not_configured", "OCR engine není dostupný. Údaje lze zadat ručně.", 503
        ) from error
    if "tesseract 5.5.4" not in version.stdout:
        raise Problem("ocr_not_configured", "OCR neodpovídá zamčené verzi 5.5.4.", 503)
    lock = json.loads(Path(settings.OCR_LOCK_FILE).read_text())
    for language, spec in lock["models"].items():
        path = data / (language + ".traineddata")
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise Problem("ocr_not_configured", "OCR modely neodpovídají zamčeným součtům.", 503)
    with tempfile.TemporaryDirectory(prefix="tanklog-ocr-") as folder:
        folder = Path(folder)
        source = folder / "receipt.png"
        output = folder / "output"
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image).convert("L")
            image.thumbnail((2000, 2000))
            image.save(source, "PNG")
        command = [
            sys.executable,
            str(Path(__file__).with_name("ocr_worker.py")),
            binary,
            str(source),
            str(output),
            "--tessdata-dir",
            str(data),
            "-l",
            "ces+eng",
            "--oem",
            "1",
            "--psm",
            str(psm),
            "-c",
            "tessedit_create_tsv=1",
        ]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "OMP_THREAD_LIMIT": "1",
                    "LANG": "C.UTF-8",
                },
            )
            deadline = time.monotonic() + 15
            try:
                while process.poll() is None:
                    if time.monotonic() > deadline:
                        raise subprocess.TimeoutExpired(command, 15)
                    if sys.platform == "darwin":
                        try:
                            memory = subprocess.check_output(
                                ["/bin/ps", "-o", "rss=", "-p", str(process.pid)],
                                text=True,
                            )
                            if int(memory.strip() or "0") > 512 * 1024:
                                raise Problem("ocr_limit", "OCR překročilo limit paměti.", 422)
                        except subprocess.CalledProcessError:
                            pass
                    time.sleep(0.05)
                if process.returncode != 0:
                    raise Problem(
                        "ocr_failed",
                        "OCR obrázek nezpracovalo. Zadejte údaje ručně.",
                        422,
                    )
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            tsv = output.with_suffix(".tsv")
            if tsv.stat().st_size > 2 * 1024**2:
                raise Problem("ocr_failed", "Výstup OCR je příliš velký.", 422)
            return parse_tsv(tsv.read_text())
        except subprocess.TimeoutExpired as error:
            raise Problem("ocr_timeout", "Rozpoznání překročilo časový limit.", 504) from error


def recognize(request, item_id):
    item = refueling_for(request.user, item_id)
    car = vehicle_for(request.user, item.vehicle_id)
    fuel.authorize(request.user, car, "edit", item)
    fuel.require_tag(request, fuel.etag(item))
    receipt = ReceiptAttachment.objects.filter(refueling=item).first()
    if not receipt:
        raise Problem("not_found", "Nejdříve nahrajte účtenku.", 404)
    reserve(request, "ocr", 3, 20)
    slot, lease = acquire()
    try:
        raw, suggestions = engine(bytes(receipt.original_bytes))
    finally:
        IntegrationGate.objects.filter(pk=slot, window=lease).update(window=timezone.now())
    with transaction.atomic():
        current, vehicle = fuel.locked_item(request, item_id)
        fuel.authorize(request.user, vehicle, "edit", current)
        actual = ReceiptAttachment.objects.filter(refueling=current).first()
        if not actual or (actual.sha256, actual.version) != (
            receipt.sha256,
            receipt.version,
        ):
            raise Problem("stale_extraction", "Účtenka se změnila. Spusťte OCR znovu.", 412)
        result = ReceiptExtraction.objects.create(
            refueling=current,
            applicant=request.user,
            receipt_hash=receipt.sha256,
            receipt_version=receipt.version,
            engine="Tesseract 5.5.4 / ces+eng fast / psm6",
            raw_text=raw,
            suggestions=suggestions,
        )

        record(
            request,
            "receipt.recognized",
            result,
            {"engine": result.engine},
            vehicle_id=current.vehicle_id,
        )
        return result


def extraction(request, item_id, result_id):
    item = refueling_for(request.user, item_id)
    result = get_object_or_404(ReceiptExtraction, pk=result_id, refueling=item)
    receipt = ReceiptAttachment.objects.filter(refueling=item).first()
    stale = not receipt or (receipt.sha256, receipt.version) != (
        result.receipt_hash,
        result.receipt_version,
    )
    return {
        "id": str(result.pk),
        "engine": result.engine,
        "suggestions": result.suggestions,
        "raw_text": result.raw_text,
        "stale": stale,
        "created_at": result.created_at,
    }
