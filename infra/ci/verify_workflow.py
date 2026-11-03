"""Lokální politika připraveného workflow. Nepotvrzuje nastavení repozitáře na GitHubu."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-node": "949feb2413d6458794dcd2491c4babbbce0c15c1",
    "astral-sh/setup-uv": "68559e99cc807c1eb7e9238fd43a15bba460eec2",
}


def verify(data):
    if set(data["on"]) != {"push", "pull_request", "workflow_dispatch"}:
        raise ValueError(
            "Nepovolený trigger; pull_request_target ani workflow_run nepatří do CI."
        )
    if data.get("permissions") != {"contents": "read"}:
        raise ValueError("Workflow smí mít jen contents:read.")
    if set(data["jobs"]) != {"repository", "backend", "frontend", "containers"}:
        raise ValueError("Chybí některá povinná CI kontrola.")
    for name, job in data["jobs"].items():
        if (
            job.get("runs-on") != "ubuntu-24.04"
            or "permissions" in job
            or "environment" in job
        ):
            raise ValueError(
                f"Nepovolený runner, token nebo deploy environment: {name}."
            )
        if not 1 <= int(job["timeout-minutes"]) <= 30:
            raise ValueError("Každý job musí mít konečný timeout.")
        for step in job["steps"]:
            if "uses" in step:
                action, sha = step["uses"].split("@")
                if not re.fullmatch("[a-f0-9]{40}", sha) or PINS.get(action) != sha:
                    raise ValueError("Akce musí mít ověřený úplný commit SHA.")
                if (
                    action == "actions/checkout"
                    and step.get("with", {}).get("persist-credentials") != "false"
                ):
                    raise ValueError("Checkout nesmí zachovat credentials.")
            code = step.get("run", "")
            if "${{" in code or re.search(r"\b(push|deploy|prune)\b|down\s+-v", code):
                raise ValueError(
                    "Run nesmí publikovat, mazat volumes nebo vkládat GitHub výraz přímo do shellu."
                )
    serialized = json.dumps(data)
    if (
        "secrets." in serialized
        or "self-hosted" in serialized
        or "id-token" in serialized
    ):
        raise ValueError("CI nepotřebuje secrets, OIDC ani self-hosted server.")
    postgres = data["jobs"]["backend"]["services"]["postgres"]
    if "@sha256:" not in postgres["image"] or postgres["ports"] != [
        "127.0.0.1:5432:5432"
    ]:
        raise ValueError("PostgreSQL musí mít digest a port jen na loopbacku.")
    checkouts = [
        step
        for step in data["jobs"]["repository"]["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    if checkouts[0]["with"].get("fetch-depth") != "0":
        raise ValueError(
            "Kontrola historie vyžaduje celý Git, nikoli shallow checkout."
        )


def main():
    data = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
    )
    verify(data)
    print(
        "CI politika: triggery, read-only oprávnění, SHA, runner, historie a izolace PostgreSQL OK."
    )


if __name__ == "__main__":
    main()
