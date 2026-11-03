"""Kontrola cest v celé Git historii a aktuálním indexu, bez výpisu obsahů nebo remote URL."""

import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]


def private_path(path):
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    name = parts[-1]
    if any(
        part
        in {
            ".runtime",
            ".tools",
            ".venv",
            "node_modules",
            "backups",
            "private_media",
            "media",
            "uploads",
            "staticfiles",
            "test-results",
            "playwright-report",
        }
        for part in parts
    ):
        return True
    if name.startswith(".env") and not name.endswith(".example"):
        return True
    if name.endswith(
        (".pem", ".key", ".dump", ".sqlite3", ".sql", ".log", ".xlsx", ".age")
    ):
        return True
    return name.endswith((".png", ".jpg", ".jpeg", ".webp")) and not path.startswith(
        "frontend/public/icons/"
    )


def main():
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    history = (
        subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=ROOT)
        .decode()
        .splitlines()
    )
    paths = {path for path in tracked if path}
    paths.update(line.split(" ", 1)[1] for line in history if " " in line)
    rejected = sorted(path for path in paths if private_path(path))
    if rejected:
        raise SystemExit(
            "V indexu/historii jsou zakázané soukromé nebo provozní cesty: "
            + ", ".join(rejected)
        )
    examples = [
        ".env",
        ".runtime/ci.env",
        ".tools/tool",
        "backend/.venv/file",
        "frontend/node_modules/file",
        "backups/data.dump",
    ]
    for path in examples:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", path], cwd=ROOT, check=False
        )
        if result.returncode != 0:
            raise SystemExit(f"Ignore nechrání cestu {path}.")
    print(
        "Index a cesty celé historie: bez zakázaných dat; ignore chrání secrets/provozní soubory."
    )
    print("Obsahové tajné údaje samostatně ověřuje Gitleaks s redakcí výstupu.")


if __name__ == "__main__":
    main()
