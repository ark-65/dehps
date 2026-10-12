"""Authenticated read-only archive export; originals are never prepared or edited."""

import json
from hashlib import sha256
from pathlib import Path

from dehps.execution.ledger import MainlineLedger
from dehps.notifications.historical_mail.host import config, reader
from dehps.notifications.historical_mail.publisher import gate
from dehps.notifications.historical_mail.publisher import publish as prospective_publish
from dehps.notifications.p3_top100 import validate_notification_artifact
from dehps.prediction.forward_learning.publisher import (
    append_bytes,
    audited_source,
    signed,
)

from .contract import digest, instant, require, utcnow


def payout(connection, issue, source_root):
    rows = connection.execute(
        "SELECT artifact_digest,artifact_path,task_key FROM research_os_mainline_artifacts "
        "WHERE artifact_type='P3Top100IssuePayoutSourceV1' AND task_key LIKE %s",
        ("%" + issue + "-post-return-report",),
    ).fetchall()
    if not rows:
        return None
    require(len(rows) == 1, "ambiguous payout registration")
    identity, relative, task = rows[0]
    path = Path(source_root) / relative
    require(
        path.is_relative_to(Path(source_root)) and path.resolve() == path,
        "payout path escaped",
    )
    raw = path.read_bytes()
    value = json.loads(raw)
    validate_notification_artifact(value)
    require(value["artifact_digest"] == identity, "payout artifact differs")
    return {
        "artifact": value,
        "registered_artifact_digest": identity,
        "registered_task": task,
        "file_sha256": sha256(raw).hexdigest(),
    }


def publish(inputs, readers, database, key, source_root):
    require(
        utcnow() < instant(inputs.contract["approved_until"]),
        "recovery publication expired",
    )
    cfg, packet = config(Path(readers["original_config"]))
    c = inputs.contract
    require(
        packet["plan_digest"] == c["original_plan_digest"]
        and packet["release_sha256"] == c["original_release_sha256"]
        and packet["contract_sha256"] == digest(c["original_contract"]),
        "original mail binding differs",
    )
    returns_cfg, _ = config(Path(readers["returns_config"]))
    require(
        sha256((Path(returns_cfg["inputs"]) / "contract.json").read_bytes()).hexdigest()
        == c["original_returns_sha256"],
        "original return contract differs",
    )
    engine, _ = reader(cfg, packet)
    manifest = engine.replay(require_complete=False)
    archived = {}
    absences = {}
    with engine.store.verification_scope():
        for task in manifest.tasks:
            d = json.loads(task.metric_contract)["notification"]
            if d["issue"] not in ("2026114", "2026115", "2026116") or d[
                "phase"
            ] not in ("seal", "pre-replay"):
                continue
            task_id = engine.bindings[task.artifact_digest]
            ledger = MainlineLedger(engine.store)
            result = engine.store.result(task_id)
            if result is None:
                if d["phase"] == "seal":
                    absences[d["issue"]] = ledger.context(task_id)
                continue
            ledger.verify(task_id)
            archived[(d["issue"], d["phase"])] = {
                "artifact": json.loads(result.data),
                "artifact_sha256": result.artifact.sha256,
                "task": result.task,
                "mainline": ledger.context(task_id),
            }
    try:
        with database.connect() as connection:
            connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            rows, receipt = audited_source(connection)
            by_issue = {r["issue"]: r for r in rows}
            for target in c["targets"]:
                issue = target["issue"]
                label = by_issue.get(issue)
                prize = payout(connection, issue, source_root)
                if issue == "2026117":
                    if prize is not None:
                        path = inputs.root / "payouts" / (issue + ".json")
                        if path.exists():
                            require(
                                inputs.payout(issue) == prize,
                                "registered payout changed",
                            )
                        else:
                            append_bytes(
                                path,
                                signed(
                                    {
                                        "contract_sha256": inputs.identity,
                                        "issue": issue,
                                        "payout": prize,
                                    },
                                    key,
                                    c["export_public_key"],
                                ),
                            )
                    continue
                require(
                    label is not None and prize is not None,
                    "historical draw and payout missing",
                )
                path = inputs.root / "sources" / (issue + ".json")
                if path.exists():
                    source = inputs.source(issue)
                    require(
                        all(
                            source["label"][k] == label[k]
                            for k in ("red", "blue", "draw_at")
                        )
                        and source["payout"] == prize,
                        "historical source corrected; preserve original recovery",
                    )
                    continue
                original = archived.get((issue, "pre-replay"))
                seal = archived.get((issue, "seal"))
                require(
                    (original is not None and seal is not None)
                    or (original is None and seal is None and issue in absences),
                    "incomplete seal registration requires investigation",
                )
                source = {
                    "original": original,
                    "seal_registration": seal,
                    "absence": None if seal else absences[issue],
                    "label": label,
                    "receipt": receipt,
                    "payout": prize,
                }
                append_bytes(
                    path,
                    signed(
                        {
                            "contract_sha256": inputs.identity,
                            "issue": issue,
                            "source": source,
                        },
                        key,
                        c["export_public_key"],
                    ),
                )
                inputs.source(issue)
        prospective = prospective_publish(
            inputs.future, readers, database, key, source_root
        )
        gate(inputs, key, None)
        return {
            "status": "SOURCE_VERIFIED",
            "recovery_issues": ["2026114", "2026115", "2026116"],
            "prospective": prospective,
        }
    except Exception:
        gate(inputs, key, "SOURCE_CONFLICT")
        raise
