"""Skip a timer retry only when the exact registered pre-mail was already sent.

Exit 0 lets the frozen mail service run. Exit 1 is a systemd ExecCondition
skip. Any inconsistent evidence exits 255 so the service fails visibly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/worker-python"))
sys.path.insert(0, str(ROOT / "apps/worker-python/scripts"))

import run_m4_p3_top100_notification as runner

from dehps.agents.repository import AgentRequestRepository
from dehps.notifications import p3_top100 as notification
from dehps.notifications.mail import QqMailConfig
from dehps.research_os.repository import PostgresResearchOSRepository


def decide(repository: PostgresResearchOSRepository, config: QqMailConfig) -> tuple[int, str]:
    source = notification.load_source_contract()
    notification.verify_governance(AgentRequestRepository())
    target = runner._goal_target(repository)
    recipient_digest = notification._recipient_digest(config.destination)
    if (
        target["source_contract_digest"] != source["artifact_digest"]
        or target["recipient_digest"] != recipient_digest
    ):
        raise RuntimeError("pre_mail_binding_changed")

    issue = runner._latest_issue(
        repository, phase="pre", minimum_issue=str(target["minimum_issue"])
    )
    if issue is None:
        return 0, "NO_SEALED_ISSUE_RUN_CANONICAL"

    ledger = notification.P3Top100DeliveryLedger()
    matches = [
        (key, row)
        for key, row in ledger._load()["deliveries"].items()
        if row.get("issue") == issue and row.get("kind") == "pre"
    ]
    if not matches:
        return 0, "UNSENT_RUN_CANONICAL"
    if len(matches) != 1:
        raise RuntimeError("pre_mail_ledger_identity_collision")

    key, row = matches[0]
    if row.get("status") != "sent" or row.get("recipient_digest") != recipient_digest:
        raise RuntimeError("pre_mail_ledger_requires_review")
    email = notification.registered_delivery_email(
        repository, issue=issue, kind="pre", recipient=config.destination
    )
    if (
        key != email.delivery_key
        or row.get("artifact_digest") != email.artifact_digest
        or row.get("replay_digest") != email.replay_digest
    ):
        raise RuntimeError("pre_mail_registered_identity_changed")
    return 1, "ALREADY_SENT_EXACT_REGISTERED_PRE_MAIL"


def main() -> int:
    try:
        code, status = decide(PostgresResearchOSRepository(), QqMailConfig.from_environment())
    # An uncaught exception exits 1, which systemd would mistake for a safe skip.
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"status": "PRE_MAIL_DEDUPE_BLOCKED", "error_type": type(exc).__name__}
            )
        )
        return 255
    print(json.dumps({"status": status}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
