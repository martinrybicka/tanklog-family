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

# Mezery tisíců se přijímají jen ve skupinách po třech, ne jako oddělovač sloupců.
MONEY_NUMBER = r"(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d{1,2})?(?![\d.,])"


def decimal_text(value):
    return re.sub(r"\s", "", value).replace(",", ".")


FUEL_PATTERNS = {
    "PETROL": r"\b(?:benz[ií]n|natural)\b",
    "DIESEL": r"\b(?:nafta|diesel)\b",
    "LPG": r"\b(?:lpg|autoplyn)\b",
    "ETHANOL": r"\b(?:ethanol|e85)\b",
}


def table_suggestions(lines, found):
    """U tabulky bez jednotek použijeme jen dvojici ověřenou částkou platby."""
    if "total_amount" in found:
        amounts = {Decimal(item["value"]): item for item in found["total_amount"]}
    else:
        amounts = {}
        for text, confidence in lines:
            match = re.search(r"\bPRODEJ\s*[:=]?\s*(" + MONEY_NUMBER + r")\s*(?:K[čc]|CZK)\b", text, re.I)
            if match:
                value = decimal_text(match[1])
                amounts[Decimal(value)] = {
                    "value": value,
                    "confidence": str(min(confidence, 50)),
                    "source": text[:250],
                }
    if len(amounts) != 1:
        return {}
    amount, payment = next(iter(amounts.items()))
    candidates = {}
    for i, (text, confidence) in enumerate(lines):
        if not re.search(r"\b(?:množství|mnozstvi)\b", text, re.I):
            continue
        # OCR může oddělit název paliva a číselné sloupce do několika řádků.
        window = lines[i + 1 : i + 6]
        kinds = {
            kind
            for line, _ in window
            for kind, pattern in FUEL_PATTERNS.items()
            if re.search(pattern, line, re.I)
        }
        if len(kinds) != 1:
            continue
        for line, row_confidence in window:
            columns = re.search(r"(?<![\d.,+-])(\d{1,4}[.,]\d{1,3})\s+(\d{1,3}[.,]\d{2})(?![\d.,])", line)
            if not columns:
                continue
            quantity, price = (Decimal(decimal_text(value)) for value in columns.groups())
            # Cena v tiskovém sloupci může být zaokrouhlená na haléře.
            if (
                quantity > 0
                and price > 0
                and abs(quantity * price - amount) <= quantity * Decimal("0.005") + Decimal("0.01")
            ):
                kind = next(iter(kinds))
                candidates[(quantity, kind)] = {
                    "value": decimal_text(columns[1]),
                    "source": line[:250],
                    "confidence": str(min(confidence, row_confidence, 50)),
                }
    if len(candidates) != 1:
        return {}
    (_, kind), quantity = next(iter(candidates.items()))
    return {"liters": quantity, "fuel_type": {**quantity, "value": kind}, "total_amount": payment}


def fuel_row(text):
    """Množství za názvem paliva; nejednoznačnou číslici 1 ověřuje cena × litry."""
    if not re.search(r"\b(?:benz[ií]n|nafta|diesel|natural|lpg|autoplyn|ethanol|e85)\b", text, re.I):
        return {}
    quantity = re.search(
        r"(?<![\d.,+-])(\d{1,4}[.,]\d{1,3})\s*(lit(?:ru|rů|ry)?|[lI1|])\.?(?=\s|$)", text, re.I
    )
    if not quantity:
        return {}
    liters = decimal_text(quantity[1])
    if Decimal(liters) <= 0:
        return {}
    money = re.findall(r"(?<![\d.,])(" + MONEY_NUMBER + r")\s*(?:K[čc]|CZK)\b", text[quantity.end() :], re.I)
    consistent = False
    if len(money) == 2:
        price, amount = (Decimal(decimal_text(value)) for value in money)
        consistent = price > 0 and abs(Decimal(liters) * price - amount) <= Decimal("0.01")
    ambiguous = quantity[2] in ["1", "I", "i", "|"]
    if quantity[2] == "1" and not consistent:
        return {}
    result = {"liters": (liters, ambiguous)}
    if consistent:
        result["unit_price_entered"] = (decimal_text(money[0]), ambiguous)
    return result


def parse_tsv(tsv):
    lines = {}
    for token in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
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
        "liters": r"(?:litry|litru|mnozstvi|množství|objem)\s*[:=]?\s*(\d+[.,]\d{1,3})\s*(?:lit(?:ru|rů|ry)?|[lI1|])(?=\s|$|[.,;])",
        "unit_price_entered": r"(?:cena\s*(?:za\s*)?(?:litr|/l)|kc/l|kč/l)\s*[:=]?\s*(\d+[.,]\d{1,4})",
        "total_amount": (
            r"\b(?:celkem(?:\s+k\s*[úu]hrad[eě])?|celkova castka|celková částka|total|k\s*[úu]hrad[eě])\s*[:=]?\s*("
            + MONEY_NUMBER
            + r")(?=\s*(?:K[čc]\b|CZK\b|$|[|&=]))"
        ),
        "odometer_km": r"(?:tachometr|stav km|km)\s*[:=]?\s*(\d{1,8})\b",
    }
    found = {}
    receipt_lines = []
    merchant_header = True
    for tokens in lines.values():
        text = " ".join(word for word, _ in tokens)
        confidence = round(min(value for _, value in tokens), 1)
        receipt_lines.append((text, confidence))
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.I)
            if match:
                value = decimal_text(match[1])
                found.setdefault(field, []).append(
                    {
                        "value": value,
                        "confidence": str(
                            min(confidence, 50)
                            if field == "liters" and re.search(r"\d\s*[I1|](?=\s|$|[.,;])", text)
                            else confidence
                        ),
                        "source": text[:250],
                    }
                )
        row = fuel_row(text)
        if row or re.search(r"\b(?:palivo|produkt)\s*[:=]", text, re.I):
            for kind, pattern in FUEL_PATTERNS.items():
                if re.search(pattern, text, re.I):
                    found.setdefault("fuel_type", []).append(
                        {
                            "value": kind,
                            "confidence": str(confidence),
                            "source": text[:250],
                        }
                    )
        if row:
            merchant_header = False
        if merchant_header:
            merchant = re.search(
                r"(?<!\w)([^\W\d_][\w&'’.-]*(?:\s+[\w&'’.-]+){0,6})\s+"
                r"(?:s\.?\s*r\.?\s*o\.?|a\.?\s*s\.?)(?=\s|$|[|=])",
                re.sub(r"(?i)\b(?:provozovatel|prodávající|dodavatel)\s*[:=-]?\s*", "", text),
            )
            explicit = re.search(r"název\s+(?:čerpací\s+)?stanice\s*[:=]\s*([^|=]{3,80})", text, re.I)
            name = (merchant[1] if merchant else explicit[1].strip() if explicit else "").strip()
            if name and len(name) <= 120:
                found.setdefault("station_custom_name", []).append(
                    {
                        "value": name,
                        "confidence": str(confidence),
                        "source": text[:250],
                    }
                )
        for field, (value, ambiguous) in row.items():
            found.setdefault(field, []).append(
                {
                    "value": value,
                    "confidence": str(min(confidence, 50) if ambiguous else confidence),
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
    if "liters" not in found:
        for field, candidate in table_suggestions(receipt_lines, found).items():
            if field not in found:
                suggestions[field] = candidate
    # Známý řetězec a vlastní název jsou v API vzájemně výlučné.
    if "station_code" in found:
        suggestions.pop("station_custom_name", None)
    elif "station_custom_name" in suggestions:
        suggestions["station_code"] = {**suggestions["station_custom_name"], "value": "OTHER"}
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
    deadline = time.monotonic() + 15
    with tempfile.TemporaryDirectory(prefix="tanklog-ocr-") as folder:
        folder = Path(folder)
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image).convert("L")
        text, fields = scan(image, folder, binary, data, psm, 2000, deadline)
        if psm == 6 and not {"date", "liters", "total_amount"} <= fields.keys():
            try:
                extra_text, extra_fields = scan(image, folder, binary, data, 4, 3800, deadline)
            except Problem:
                # Dílčí výsledek prvního průchodu zůstane dostupný i při vyčerpání limitu.
                return text, fields
            if (
                "total_amount" in fields
                and "total_amount" in extra_fields
                and Decimal(fields["total_amount"]["value"]) != Decimal(extra_fields["total_amount"]["value"])
            ):
                # Číselné údaje z různých průchodů nespojujeme, pokud se částky rozcházejí.
                for key in ("liters", "unit_price_entered", "fuel_type"):
                    extra_fields.pop(key, None)
            if "station_code" in fields:
                extra_fields.pop("station_custom_name", None)
            fields = {**extra_fields, **fields}
            if extra_fields:
                text = (text + "\n" + extra_text)[:60000]
        return text, fields


def scan(image, folder, binary, data, psm, max_side, deadline):
    source = folder / "receipt.png"
    output = folder / "output"
    tsv = output.with_suffix(".tsv")
    tsv.unlink(missing_ok=True)
    prepared = image.copy()
    prepared.thumbnail((max_side, max_side))
    prepared.save(source, "PNG")
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
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
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
        if not tsv.is_file() or tsv.stat().st_size > 2 * 1024**2:
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
