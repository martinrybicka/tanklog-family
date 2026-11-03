"""Stáhne pouze přesně zamčené veřejné zdroje/modely pro OCR build."""

import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

lock = json.loads(Path(__file__).with_name("dependencies.lock.json").read_text())
for name, spec in [("source", lock["engine"]), *lock["models"].items()]:
    with urllib.request.urlopen(spec["url"], timeout=60) as response:
        data = response.read(64 * 1024**2)
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise SystemExit("Nesouhlasí kontrolní součet OCR vstupu.")
    if name == "source":
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall("/tmp/ocr-source", filter="data")
    else:
        target = Path("/opt/ocr/tessdata")
        target.mkdir(parents=True, exist_ok=True)
        (target / (name + ".traineddata")).write_bytes(data)
