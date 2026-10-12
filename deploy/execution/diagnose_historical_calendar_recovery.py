"""Root-only, read-only incident inventory; never prints credentials or sends mail."""

import json
import os
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path("/opt/dehps/releases/historical-mail-842/source/apps/worker-python")
sys.path.insert(0, str(ROOT))


def main():
    if os.geteuid() != 0:
        raise SystemExit(
            "Run through the authorized administrator; no credentials in chat."
        )
    from dehps.execution.ledger import MainlineLedger
    from dehps.notifications.historical_mail.host import config, reader

    output = {
        "schema": "historical-calendar-recovery-diagnostics.v1",
        "read_only": True,
        "sources": {},
    }
    for name in ("historical-mail-842", "historical-returns-846"):
        cfg, packet = config(Path("/etc/dehps") / name / "config.json")
        ledger_path = Path(cfg["ledger"])
        ledger_raw = ledger_path.read_bytes()
        state = json.loads(ledger_raw)
        rows = [
            {
                k: row.get(k)
                for k in (
                    "issue",
                    "kind",
                    "status",
                    "artifact_sha256",
                    "replay_sha256",
                    "started_at",
                    "completed_at",
                )
            }
            for row in state["deliveries"].values()
            if row.get("issue", "") >= "2026113"
        ]
        failures = sorted(Path(cfg["evidence"]).glob("failure-*.txt"))
        markers = (
            "registered official calendar differs",
            "official calendar differs",
            "published label correction",
            "source correction conflicts with learned prefix",
            "original source binding changed",
            "notification admission binding differs",
        )
        last = failures[-1].read_text() if failures else ""
        item = {
            "ledger_sha256": sha256(ledger_raw).hexdigest(),
            "deliveries": rows,
            "latest_failure_file": failures[-1].name if failures else None,
            "latest_failure_sha256": sha256(last.encode()).hexdigest()
            if failures
            else None,
            "failure_markers": [m for m in markers if m in last],
            "contract_sha256": packet["contract_sha256"],
            "plan_digest": packet["plan_digest"],
        }
        if name == "historical-mail-842":
            engine, _ = reader(cfg, packet)
            engine.replay(require_complete=False)
            seals = []
            for task in engine.plan.validate().tasks:
                definition = json.loads(task.metric_contract)["notification"]
                if (
                    definition["phase"] != "pre-replay"
                    or definition["issue"] < "2026114"
                ):
                    continue
                result = engine.store.result(engine.bindings[task.artifact_digest])
                if result is None:
                    continue
                MainlineLedger(engine.store).verify(result.task["id"])
                value = json.loads(result.data)["value"]
                seal = value["seal"]
                seals.append(
                    {
                        "issue": definition["issue"],
                        "status": seal["status"],
                        "sealed_at": seal.get("sealed_at"),
                        "draw_at": seal["draw_at"],
                        "training_end_issue": seal.get("training_end_issue"),
                        "tickets": len(seal["tickets"]),
                        "artifact_sha256": result.artifact.sha256,
                        "seal_sha256": value["seal_sha256"],
                    }
                )
            item["registered_seals"] = seals
        output["sources"][name] = item
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"read_only": True, "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
