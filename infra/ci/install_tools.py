"""Nainstaluje připnuté kontrolní nástroje pro Linux x64 po kontrole SHA-256."""

import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        raise SystemExit(
            "Instalátor je určený pro CI Linux x64; lokálně použijte gitleaks a actionlint stejné verze."
        )
    tools = json.loads((ROOT / "infra/ci/tools.json").read_text())
    target = ROOT / ".tools/ci"
    target.mkdir(parents=True, exist_ok=True)
    for name, spec in tools.items():
        request = urllib.request.Request(
            spec["url"], headers={"User-Agent": "TankLog-CI"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(100 * 1024 * 1024 + 1)
        if hashlib.sha256(data).hexdigest() != spec["sha256"]:
            raise SystemExit(f"Nesouhlasí SHA-256 archivu {name}; nic se nespustilo.")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            member = archive.getmember(name)
            if not member.isfile():
                raise SystemExit(f"Neplatný obsah archivu {name}.")
            binary = archive.extractfile(member).read()
        path = target / name
        path.write_bytes(binary)
        path.chmod(0o755)
        print(f"Připraven {name} {spec['version']} s ověřeným archivem.")


if __name__ == "__main__":
    main()
