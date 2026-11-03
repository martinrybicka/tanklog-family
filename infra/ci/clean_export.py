"""Vyexportuje jen verzované zdroje mimo ignorované adresáře a původní pracovní strom."""

import argparse
import io
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        action="store_true",
        help="Ověřit připravený index místo HEAD, bez commitu.",
    )
    arguments = parser.parse_args()
    revision = (
        subprocess.check_output(["git", "write-tree"], cwd=ROOT).decode().strip()
        if arguments.index
        else "HEAD"
    )
    data = subprocess.check_output(["git", "archive", revision], cwd=ROOT)
    output = Path(tempfile.mkdtemp(prefix="tanklog-phase6-clean-"))
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(output, filter="data")
    print(output)


if __name__ == "__main__":
    main()
