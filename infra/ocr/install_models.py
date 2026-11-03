"""Lokální instalace pouze zamčených OCR modelů do ignorovaného .tools."""

import hashlib
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[2]
lock = json.loads(Path(__file__).with_name("dependencies.lock.json").read_text())
target = root / ".tools/ocr/tessdata"
target.mkdir(parents=True, exist_ok=True)
for name, spec in lock["models"].items():
    path = target / (name + ".traineddata")
    if (
        path.exists()
        and hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"]
    ):
        continue
    with urllib.request.urlopen(spec["url"], timeout=30) as response:
        data = response.read(16 * 1024**2)
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise SystemExit("OCR model má chybný SHA-256; nebyl použit.")
    path.write_bytes(data)
print("Zamčené ces/eng OCR modely byly ověřeny v .tools/ocr/tessdata.")
