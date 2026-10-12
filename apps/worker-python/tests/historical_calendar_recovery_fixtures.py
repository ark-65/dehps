"""Synthetic registrations for the bounded calendar incident; no SMTP."""

import base64
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dehps.execution.ledger import canonical_records
from dehps.execution.release import canonical
from dehps.notifications.historical_calendar_recovery.contract import (
    DATES,
    POLICY,
    SCHEMA,
    Inputs,
    digest,
)
from dehps.notifications.historical_mail.contract import POLICY as OLD_POLICY
from dehps.notifications.historical_mail.plan import build_plan
from dehps.notifications.historical_mail.publisher import gate
from dehps.notifications.historical_mail.reports import report
from dehps.notifications.p3_top100 import PAYOUT_SOURCE_ARTIFACT_TYPE, _artifact
from dehps.prediction.forward_learning.calculation import portfolio, probabilities
from dehps.prediction.forward_learning.publisher import append_bytes, signed


def fixture(root):
    now = datetime.now(UTC)
    key = Ed25519PrivateKey.generate()
    pub = base64.b64encode(key.public_key().public_bytes_raw()).decode()
    targets = [
        {
            "issue": i,
            "previous_issue": str(int(i) - 1),
            "draw_at": d + "T21:15:00+08:00",
            "send_at": d + "T17:00:00+08:00",
        }
        for i, d in DATES.items()
    ]
    old_targets = [
        {**t, "draw_at": d + "T21:15:00+08:00", "send_at": d + "T17:00:00+08:00"}
        for t, d in zip(
            targets,
            ["2026-10-01", "2026-10-04", "2026-10-06", "2026-10-08"],
            strict=True,
        )
    ]
    old = {
        "schema": "historical-learning-mail.v1",
        "policy": OLD_POLICY,
        "historical_contract_sha256": "a" * 64,
        "sources": {
            d: {"plan_digest": "b" * 64, "release_sha256": "c" * 64}
            for d in ("learning", "observer")
        },
        "targets": old_targets,
        "recipient_sha256": sha256(b"fixture@example.test").hexdigest(),
        "export_public_key": pub,
        "approved_until": max(
            now + timedelta(days=365), datetime(2026, 10, 15, tzinfo=UTC)
        ).isoformat(),
    }
    prior = build_plan(old)
    future = {**old, "targets": targets[-1:]}
    c = {
        "schema": SCHEMA,
        "policy": POLICY,
        "original_contract": old,
        "original_plan_digest": prior.digest,
        "original_release_sha256": "d" * 64,
        "original_returns_sha256": "e" * 64,
        "original_seals": {"2026114": "a" * 64, "2026115": "a" * 64, "2026116": None},
        "future_contract": future,
        "targets": targets,
        "recipient_sha256": old["recipient_sha256"],
        "export_public_key": pub,
        "approved_until": old["approved_until"],
        "calendar_sources": {i: "https://example.test/official/" + i for i in DATES},
    }
    append_bytes(root / "contract.json", canonical(c))
    append_bytes(root / "prospective/contract.json", canonical(future))
    inputs = Inputs(root, digest(c))
    gate(inputs, key, None)
    cp = {
        "count": 902,
        "counts": [164] * 33,
        "blue_counts": [57] * 6 + [56] * 10,
        "training_end_issue": "2026116",
        "last_input_sha256": "a" * 64,
    }
    snapshot = {
        "contract_sha256": digest(future),
        "target_issue": "2026117",
        "observed_at": "2026-10-12T00:00:00+00:00",
        "checkpoint": cp,
        "checkpoint_sha256": digest(cp),
        "audit_sha256": "b" * 64,
        "source_records": {
            p: {
                "artifact_sha256": "a" * 64,
                "registration_digest": "b" * 64,
                "completed_event_digest": "c" * 64,
                "committed_at": "2026-10-11T14:00:00+00:00",
            }
            for p in ("learn", "report", "summary", "observe", "observe-summary")
        },
    }
    append_bytes(
        root / "prospective/checkpoints/2026117.json", signed(snapshot, key, pub)
    )

    def registration(issue, phase, value):
        t = next(
            t
            for t in prior.payload["tasks"]
            if t["business_key"].endswith(issue + "-" + phase)
        )
        definition = next(
            v["value"]
            for v in prior.payload["canonical"]["tasks"]
            if v["digest"] == t["task_digest"]
        )
        task = {
            "id": 7,
            "spec": t,
            **t,
            "release_sha256": "d" * 64,
            "control_plane": "observer",
        }
        a = {
            "schema": old["schema"],
            "phase": phase,
            "issue": issue,
            "task_digest": t["task_digest"],
            "release_sha256": "d" * 64,
            "parents": {},
            "value": value,
        }
        commit_at = (
            "2026-09-29T15:40:00+00:00"
            if issue == "2026114"
            else "2026-10-04T14:02:00+00:00"
        )
        ctx = {
            "task": task,
            "commit": {
                "artifact_sha256": digest(a),
                "artifact_size": len(canonical(a)),
                "created_at": commit_at,
            },
            "attempt": {"id": str(uuid4()), "created_at": "2026-09-29T15:39:00+00:00"},
            "definition": definition,
            "parents": [],
            "event_count": 2,
            "registration_count": 1,
        }
        ctx["records"] = canonical_records(ctx)
        return {
            "artifact": a,
            "artifact_sha256": digest(a),
            "task": task,
            "mainline": ctx,
        }

    for t in targets[:-1]:
        issue = t["issue"]
        old_t = next(v for v in old_targets if v["issue"] == issue)
        seal = {
            "issue": issue,
            "status": "SEALED_BEFORE_DRAW",
            "sealed_at": "2026-09-29T15:39:56+00:00",
            "draw_at": old_t["draw_at"],
            "training_end_issue": t["previous_issue"],
            "model": "shrink900",
            "count": 902,
            "checkpoint_sha256": "a" * 64,
            "tickets": portfolio(
                probabilities([164] * 33, 902)["shrink900"],
                old["historical_contract_sha256"],
                issue,
            ),
        }
        if issue == "2026115":
            seal.update(
                status="MISSING_PREDRAW_SEAL",
                tickets=[],
                training_end_issue=None,
                sealed_at="2026-10-04T14:01:54+00:00",
            )
        seal_record = registration(issue, "seal", seal)
        if issue != "2026116":
            c["original_seals"][issue] = seal_record["artifact_sha256"]
        pre = registration(
            issue,
            "pre-replay",
            {
                "status": "REPLAY_VERIFIED",
                "seal": seal,
                "seal_sha256": seal_record["artifact_sha256"],
                "report": report(seal),
            },
        )
        absence = None
        if issue == "2026116":
            pre = seal_record = None
            t_spec = next(
                v
                for v in prior.payload["tasks"]
                if v["business_key"].endswith(issue + "-seal")
            )
            absence = {
                "task": {**t_spec, "spec": t_spec, "release_sha256": "d" * 64},
                "commit": None,
                "registration_count": 0,
                "event_count": 0,
                "definition": next(
                    v["value"]
                    for v in prior.payload["canonical"]["tasks"]
                    if v["digest"] == t_spec["task_digest"]
                ),
            }
        receipt = {
            "completed_at": now.isoformat(),
            "observed_at": now.isoformat(),
            "rows": [
                {
                    "issue": issue,
                    "red": [1, 2, 3, 4, 5, 6],
                    "blue": 1,
                    "draw_date": DATES[issue],
                }
            ],
        }
        label = {
            "issue": issue,
            "red": [1, 2, 3, 4, 5, 6],
            "blue": 1,
            "draw_at": t["draw_at"],
            "available_at": now.isoformat(),
            "audit_sha256": digest(receipt),
        }
        p = _artifact(
            artifact_type=PAYOUT_SOURCE_ARTIFACT_TYPE,
            body={
                "issue": issue,
                "status": "EXACT_ISSUE_PAYOUT_VALIDATED",
                "actual_red_numbers": label["red"],
                "actual_blue_number": 1,
                "source_url": "https://example.test/payout",
                "tiers": [
                    {
                        "tier": n,
                        "single_ticket_gross_cny": str(v),
                        "official_award_count": 1,
                    }
                    for n, v in enumerate([5000000, 100000, 3000, 200, 10, 5], 1)
                ],
            },
            parent_digests=("f" * 64,),
        )
        prize = {
            "artifact": p,
            "registered_artifact_digest": p["artifact_digest"],
            "registered_task": "fixture-" + issue + "-post-return-report",
            "file_sha256": sha256(canonical(p)).hexdigest(),
        }
        source = {
            "original": pre,
            "seal_registration": seal_record,
            "absence": absence,
            "label": label,
            "receipt": receipt,
            "payout": prize,
        }
        append_bytes(
            root / "sources" / (issue + ".json"),
            signed(
                {"contract_sha256": inputs.identity, "issue": issue, "source": source},
                key,
                pub,
            ),
        )
    (root / "contract.json").write_bytes(canonical(c))
    for path in (root / "sources").glob("*.json"):
        import json

        body = json.loads(path.read_bytes())["body"]
        body["contract_sha256"] = digest(c)
        path.write_bytes(signed(body, key, pub))
    gate(Inputs(root, digest(c)), key, None)
    return c, key
