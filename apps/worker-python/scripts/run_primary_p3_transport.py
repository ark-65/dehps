"""Run the unchanged primary presentation consumer with a reviewed transport."""

from __future__ import annotations

import argparse
import importlib.util
import json
import runpy
import sys
from hashlib import sha256
from pathlib import Path

from dehps.agents.repository import AgentRequestRepository
from dehps.config import ROOT_DIR
from dehps.notifications import p3_top100 as original
from dehps.notifications.mail import QqMailConfig
from dehps.research_os.repository import PostgresResearchOSRepository


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport-release", required=True, type=Path)
    args, retained_args = parser.parse_known_args()
    release = json.loads(args.transport_release.read_bytes())
    package = args.transport_release.parent
    source = (
        package / "source/apps/worker-python/dehps/notifications/primary_transport.py"
    )
    if sha256(source.read_bytes()).hexdigest() != release["transport_source_sha256"]:
        raise ValueError("primary transport source differs")
    spec = importlib.util.spec_from_file_location("primary_transport_fixed", source)
    transport = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = transport
    spec.loader.exec_module(transport)
    requests = AgentRequestRepository()
    for role in ("engineering", "operator"):
        binding = release[role]
        request = requests.get_request(binding["key"])
        if (
            request.id != binding["id"]
            or transport.digest(request.payload) != binding["payload_sha256"]
            or request.status.value not in ("executing", "completed")
            or not any(
                d.decision_code == "request_approved"
                and d.decided_by == release["reviewer_principal"]
                for d in requests.list_decisions(binding["key"])
            )
        ):
            raise ValueError("primary transport " + role + " admission differs")
        if (
            role == "operator"
            and request.payload["version"] != release["package_sha256"]
        ):
            raise ValueError("primary transport Operator package binding differs")
    source_contract = original.load_source_contract()
    original.verify_governance(requests)
    config = QqMailConfig.from_environment()
    if original._recipient_digest(config.destination) != release["recipient_digest"]:
        raise ValueError("primary transport recipient differs")

    # Fast wait before repeated expensive report compilation. Selecting the same
    # current issue still uses the frozen canonical selector and source target.
    sys.path.insert(0, str(ROOT_DIR / "apps/worker-python/scripts"))
    import run_m4_p3_top100_notification as canonical

    mode = retained_args[0] if retained_args else ""
    journal_root = ROOT_DIR / "runtime/notifications/primary-smtp-receipts"
    if mode in ("pre", "post") and "--deliver" in retained_args:
        repository = PostgresResearchOSRepository()
        target = canonical._goal_target(repository)
        if (
            target["source_contract_digest"] != source_contract["artifact_digest"]
            or target["recipient_digest"] != release["recipient_digest"]
        ):
            raise ValueError("primary transport canonical target differs")
        issue = canonical._latest_issue(
            repository, phase=mode, minimum_issue=str(target["minimum_issue"])
        )
        ledger = original.P3Top100DeliveryLedger()
        with ledger.exclusive():
            rows = [
                (key, row)
                for key, row in ledger._load()["deliveries"].items()
                if row.get("issue") == issue and row.get("kind") == mode
            ]
            if len(rows) > 1:
                raise ValueError("primary transport issue identity collision")
            if rows and rows[0][1].get("status") in ("sending", "uncertain"):
                key, row = rows[0]
                email = original.registered_delivery_email(
                    repository, issue=issue, kind=mode, recipient=config.destination
                )
                if key != email.delivery_key or any(
                    row.get(name) != getattr(email, name)
                    for name in ("artifact_digest", "replay_digest", "recipient_digest")
                ):
                    raise ValueError("primary transport registered identity differs")
                receipts = list((journal_root / key).glob("*.json"))
                # Any accepted/reconciled case proceeds through full registered
                # presentation replay and strict journal validation below.
                accepted = any(
                    json.loads(p.read_bytes()).get("phase") == "DATA_ACCEPTED"
                    for p in receipts
                )
                pre_data = any(
                    json.loads(p.read_bytes()).get("phase") == "NOT_SUBMITTED"
                    for p in receipts
                )
                if (
                    not accepted
                    and not pre_data
                    and key not in release.get("reconciliation", {})
                ):
                    print(
                        json.dumps(
                            {
                                "status": "WAITING_TRANSPORT_RECONCILIATION",
                                "issue": issue,
                                "kind": mode,
                                "delivery_key": key,
                                "external_delivery": False,
                            }
                        )
                    )
                    return
    original.P3Top100NotificationDeliveryService = transport.delivery_service(
        original,
        journal_root=journal_root,
        reconciliation=release.get("reconciliation", {}),
    )
    retained = Path(release["presentation_bundle"])
    if mode == "replay":
        # Exact current-issue read-only replay, using the retained presentation
        # verifier. Its original release's old acceptance targets are preserved.
        context = runpy.run_path(
            str(
                retained
                / "source/apps/worker-python/scripts/run_primary_p3_presentation.py"
            ),
            run_name="retained_primary_readonly",
        )
        retained_release = json.loads((retained / "release.json").read_bytes())
        context["authorize"](retained_release)
        style = context["style"]
        if style.source_identity() != retained_release["style_source_sha256"]:
            raise ValueError("retained primary style source differs")
        supervisor = style.PresentationSupervisor(
            repository=PostgresResearchOSRepository(),
            root_dir=ROOT_DIR,
            recipient=config.destination,
            git_commit=retained_release["commit"],
        )
        reports = []
        for issue, kind in release["acceptance_targets"]:
            email = style.consume(supervisor, issue, kind)
            proofs = [
                supervisor.replay(task_key=k) for k in style.keys(issue, kind).values()
            ]
            reports.append({"identity": transport.identity(email), "proofs": proofs})
        print(
            json.dumps(
                {
                    "status": "REPLAY_VERIFIED",
                    "reports": reports,
                    "external_delivery": False,
                },
                sort_keys=True,
            )
        )
        return
    sys.argv = [
        str(
            retained
            / "source/apps/worker-python/scripts/run_primary_p3_presentation.py"
        ),
        *retained_args,
    ]
    runpy.run_path(sys.argv[0], run_name="__main__")


if __name__ == "__main__":
    main()
