"""Instalace age pouze z archivu uzamčeného SHA-256, pro operations image."""

import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path


def main():
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine())
    if platform.system() != "Linux" or not architecture:
        raise SystemExit("Podporován pouze Linux amd64/arm64.")
    spec = json.loads(Path(__file__).with_name("tools.json").read_text())["age"][
        "linux-" + architecture
    ]
    with urllib.request.urlopen(spec["url"], timeout=60) as response:
        data = response.read(32 * 1024**2)
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise SystemExit("SHA-256 age nesouhlasí; nic se nespustilo.")
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for name in ["age", "age-keygen"]:
            entry = archive.getmember("age/" + name)
            if not entry.isfile():
                raise SystemExit("Neplatný obsah age archivu.")
            target = Path("/usr/local/bin") / name
            target.write_bytes(archive.extractfile(entry).read())
            target.chmod(0o755)


if __name__ == "__main__":
    main()
