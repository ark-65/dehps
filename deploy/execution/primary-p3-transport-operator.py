"""Exact-package Operator installation; no report or ledger rewriting."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path("/home/ark/workspace/dehps")
DEST = Path("/opt/dehps/releases/primary-p3-transport-855")
KEY = "operator-primary-p3-smtp-recovery-20261014-v1"
ACTOR = "codex-thread:01a11a4d-9d83-7ab2-828a-953a801198d9"
SUPPORT = Path(
    "/opt/dehps/releases/historical-learning-v1-d9c9899-r2/operator-support.py"
)
SUPPORT_SHA256 = "691c2ee3042b7d77c0cc35be0d1837bc58135b2a95f6c6e749dee80dea227c9c"
DROPIN = "z" * 64 + "-primary-transport-855.conf"
UNITS = ("dehps-p3-top100-pre-draw-mail", "dehps-p3-top100-post-draw-mail")


def digest(value) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def write(path: Path, raw: bytes, mode=0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("existing Operator file differs: " + str(path))
        return
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def user(*args: str) -> str:
    return subprocess.check_output(
        [
            "runuser",
            "-u",
            "ark",
            "--",
            "env",
            "XDG_RUNTIME_DIR=/run/user/1000",
            "OPENBLAS_NUM_THREADS=1",
            *args,
        ],
        text=True,
    )


def snapshot() -> dict:
    paths = [
        ROOT / "runtime/notifications/p3_top100_mail.json",
        ROOT / "apps/worker-python/scripts/run_m4_p3_top100_notification.py",
    ]
    for name in ("2026117-pre.html", "2026117-post.html"):
        paths.append(ROOT / "runtime/primary-p3-presentation/reports" / name)
    for task in (ROOT / "runtime/research-os/mainline/tasks").glob("*2026117*"):
        paths.extend(p for p in task.rglob("*") if p.is_file())
    hashes = {}
    for path in paths:
        with path.open("rb") as stream:
            import hashlib

            hashes[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "files": hashes,
        "timers": user("systemctl", "--user", "list-timers", "--all", "--no-pager"),
        "units": user(
            "systemctl",
            "--user",
            "show",
            *(u + ".service" for u in UNITS),
            "-p",
            "Id",
            "-p",
            "ExecStart",
            "-p",
            "DropInPaths",
            "-p",
            "ActiveState",
            "-p",
            "Result",
            "-p",
            "ExecMainStatus",
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("install", "replay", "activate", "proof", "rollback")
    )
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--package-sha256", required=True)
    parser.add_argument("--execution-id", required=True, type=int)
    args = parser.parse_args()
    if os.geteuid() != 0 or os.environ.get("SUDO_UID") != "1000":
        raise ValueError("authorized ark Operator authentication required")
    packet_raw = (args.stage / "package.json").read_bytes()
    if sha256(packet_raw).hexdigest() != args.package_sha256:
        raise ValueError("Operator package differs")
    packet = json.loads(packet_raw)
    if packet["installation"] != str(DEST):
        raise ValueError("Operator installation differs")
    files = {}
    for name, expected in packet["files"].items():
        path = args.stage / name
        if not path.resolve().is_relative_to(args.stage.resolve()):
            raise ValueError("Operator package path differs")
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError("Operator member differs: " + name)
        files[name] = raw
    template = json.loads(files["release-template.json"])
    # Established protected host support selects immutable request code and a
    # read-only transaction with actual formal database identity verification.
    for path in (SUPPORT, *SUPPORT.parents):
        info = path.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise ValueError("unprotected established Operator support")
    if sha256(SUPPORT.read_bytes()).hexdigest() != SUPPORT_SHA256:
        raise ValueError("established Operator support bytes differ")
    spec = importlib.util.spec_from_file_location("retained_operator_support", SUPPORT)
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    repository = support.metadata_repository()
    request = repository.get_request(KEY)
    records = repository.list_execution_metadata(KEY)
    if (
        request.request_type.value != "operator_release"
        or request.requested_by != ACTOR
        or request.status.value not in ("executing", "completed")
        or request.payload["version"] != args.package_sha256
        or request.payload["commit"] != packet["commit"]
        or not any(
            r.id == args.execution_id
            and r.executor_id == ACTOR
            and r.executor_role.value == "operator"
            and r.environment == "production"
            and r.status.value in ("running", "completed")
            for r in records
        )
        or not any(
            d.decision_code == "request_approved"
            and d.decided_by == template["reviewer_principal"]
            for d in repository.list_decisions(KEY)
        )
    ):
        raise ValueError("exact reviewed Operator execution required")
    if args.action == "install":
        for name, raw in files.items():
            write(DEST / name, raw)
        write(DEST / "package.json", packet_raw)
        release = template | {
            "package_sha256": args.package_sha256,
            "operator": {
                "key": KEY,
                "id": request.id,
                "payload_sha256": digest(request.payload),
            },
        }
        write(
            DEST / "release.json",
            (
                json.dumps(release, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
            ).encode(),
        )
        before = snapshot()
        write(
            DEST / "evidence/before.json",
            (json.dumps(before, sort_keys=True, indent=2) + "\n").encode(),
            0o600,
        )
        write(
            DEST / "evidence/original-ledger.json",
            (ROOT / "runtime/notifications/p3_top100_mail.json").read_bytes(),
            0o600,
        )
        print(
            json.dumps(
                {
                    "status": "INSTALLED_NO_SMTP",
                    "package_sha256": args.package_sha256,
                    "release_sha256": sha256(
                        (DEST / "release.json").read_bytes()
                    ).hexdigest(),
                }
            )
        )
    elif args.action == "replay":
        result = user(
            "/usr/bin/python3.14",
            "-I",
            "-B",
            str(DEST / "launch.py"),
            "--bundle",
            str(DEST),
            "--mode",
            "replay",
        )
        proof = json.loads(result)
        if proof["status"] != "REPLAY_VERIFIED" or proof["external_delivery"]:
            raise ValueError("exact read-only primary replay required")
        write(
            DEST / "evidence/replay.json",
            (json.dumps(proof, sort_keys=True, indent=2) + "\n").encode(),
            0o600,
        )
        print(
            json.dumps(
                {
                    "status": proof["status"],
                    "reports": [r["identity"] for r in proof["reports"]],
                    "external_delivery": False,
                }
            )
        )
    elif args.action in ("activate", "rollback"):
        if args.action == "activate" and not (DEST / "evidence/replay.json").is_file():
            raise ValueError("fresh exact replay required before switch")
        started = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        user("systemctl", "--user", "stop", UNITS[1] + ".service")
        for unit, mode in zip(UNITS, ("pre", "post")):
            path = (
                Path("/home/ark/.config/systemd/user") / (unit + ".service.d") / DROPIN
            )
            if args.action == "activate":
                raw = (
                    "[Service]\nExecStart=\nExecStart=/usr/bin/python3.14 -I -B "
                    + str(DEST / "launch.py")
                    + " --bundle "
                    + str(DEST)
                    + " --mode "
                    + mode
                    + " --deliver\n"
                ).encode()
                write(path, raw)
            elif path.exists():
                if str(DEST) not in path.read_text():
                    raise ValueError("rollback entry binding differs")
                path.unlink()
        user("systemctl", "--user", "daemon-reload")
        user("systemctl", "--user", "restart", *(u + ".timer" for u in UNITS))
        if args.action == "activate":
            write(
                DEST / "evidence/activation.json",
                json.dumps({"since": started}).encode(),
                0o600,
            )
            user("systemctl", "--user", "start", "--no-block", UNITS[1] + ".service")
        print(json.dumps({"status": args.action.upper(), "old_ledger_preserved": True}))
    else:
        before = json.loads((DEST / "evidence/before.json").read_bytes())
        after = snapshot()
        changed = [
            p for p, value in before["files"].items() if after["files"].get(p) != value
        ]
        if changed:
            raise ValueError(
                "protected issue117/report/ledger changed: " + str(changed)
            )
        activation = json.loads((DEST / "evidence/activation.json").read_bytes())
        output = user(
            "journalctl",
            "--user",
            "-u",
            UNITS[1] + ".service",
            "--since",
            activation["since"],
            "--no-pager",
            "-o",
            "cat",
        )
        results = []
        for line in output.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                results.append(value)
        if (
            not results
            or results[-1].get("status") != "WAITING_TRANSPORT_RECONCILIATION"
            or results[-1].get("issue") != "2026117"
            or results[-1].get("external_delivery") is not False
        ):
            raise ValueError("fresh exact primary wait execution not verified")
        for unit in UNITS:
            if (
                user("systemctl", "--user", "is-enabled", unit + ".timer").strip()
                != "enabled"
                or user("systemctl", "--user", "is-active", unit + ".timer").strip()
                != "active"
            ):
                raise ValueError("primary mail timer not enabled/active")
        result = user(
            "systemctl",
            "--user",
            "show",
            UNITS[1] + ".service",
            "-p",
            "Result",
            "-p",
            "ExecMainStatus",
        )
        if "Result=success" not in result or "ExecMainStatus=0" not in result:
            raise ValueError("primary mail wait execution failed")
        after["fresh_execution"] = results[-1]
        after["protected_files_unchanged"] = len(before["files"])
        after["delivery_status"] = results[-1]["status"]
        after["report_impact_verdict"] = "NO — INTEGRATION_PENDING"
        raw = (json.dumps(after, sort_keys=True, indent=2) + "\n").encode()
        path = DEST / "evidence" / (sha256(raw).hexdigest() + ".json")
        write(path, raw, 0o600)
        print(
            json.dumps(
                {
                    "status": "PROTECTED_EVIDENCE_UNCHANGED",
                    "files": len(before["files"]),
                    "evidence": str(path),
                    "delivery_status": after["delivery_status"],
                }
            )
        )


if __name__ == "__main__":
    main()
