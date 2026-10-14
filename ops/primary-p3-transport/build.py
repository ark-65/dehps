"""Prepare an exact source-bound package; no production action or SMTP."""

from __future__ import annotations

import argparse
import json
import subprocess
from hashlib import sha256
from pathlib import Path

FILES = (
    "apps/worker-python/dehps/notifications/primary_transport.py",
    "apps/worker-python/scripts/run_primary_p3_transport.py",
    "ops/primary-p3-transport/launch.py",
    "deploy/execution/primary-p3-transport-operator.py",
    "deploy/execution/primary-p3-transport-runbook.md",
)


def write(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root).strip():
        raise ValueError("clean accepted source required")
    commit = (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    )
    destination = args.destination
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in FILES:
        raw = (root / name).read_bytes()
        if raw != subprocess.check_output(
            ["git", "show", commit + ":" + name], cwd=root
        ):
            raise ValueError("source commit differs: " + name)
        target_name = "launch.py" if name.endswith("/launch.py") else "source/" + name
        target = destination / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        hashes[target_name] = sha256(raw).hexdigest()
    template = {
        "schema": "primary-p3-transport-release.v1",
        "commit": commit,
        "engineering": {
            "key": "engineering-primary-p3-smtp-recovery-20261014-v1",
            "id": 855,
            "payload_sha256": "8d670b516b3c6c60d7dca42b2a2b2aa55859724d8e138ab34652b90f36895798",
        },
        "operator": {
            "key": "operator-primary-p3-smtp-recovery-20261014-v1",
            "id": None,
            "payload_sha256": None,
        },
        "reviewer_principal": "unix-host:d18e46810d6d611e19ee5d1c5f5b830dc9129a88cecebb25a36192063cfd70a6:uid:1000",
        "recipient_digest": "ee56ed78ef961d312641c8b8b8a05a96a131265a8c62d8860c8f2dadb5ef65bf",
        "presentation_bundle": "/opt/dehps/releases/primary-p3-style-850",
        "transport_source_sha256": hashes["source/" + FILES[0]],
        "acceptance_targets": [["2026117", "pre"], ["2026117", "post"]],
        "reconciliation": {},
    }
    write(destination / "release-template.json", template)
    hashes["release-template.json"] = sha256(
        (destination / "release-template.json").read_bytes()
    ).hexdigest()
    packet = {
        "schema": "primary-p3-transport-package.v1",
        "commit": commit,
        "files": hashes,
        "installation": "/opt/dehps/releases/primary-p3-transport-855",
        "rollback": "remove only primary-transport-855 pre/post user drop-ins; retain all receipts and old ledger rows",
        "test_mail": False,
        "old_uncertain_resend": False,
    }
    write(destination / "package.json", packet)
    print(
        json.dumps(
            {
                "package_sha256": sha256(
                    (destination / "package.json").read_bytes()
                ).hexdigest(),
                "commit": commit,
                "destination": str(destination),
            }
        )
    )


if __name__ == "__main__":
    main()
