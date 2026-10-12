"""Single canonical calculation, commit and deterministic replay path."""

import json

from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from dehps.notifications.historical_mail.reports import report as pre_report
from dehps.prediction.forward_learning.calculation import portfolio, probabilities

from .contract import SCHEMA, Inputs, digest, instant, require, utcnow
from .plan import CAPABILITIES, build_plan
from .reports import report, summary


def build_capabilities(plan, store, context):
    definitions = {
        t.artifact_digest: json.loads(t.metric_contract)["recovery"]
        for t in plan.validate().tasks
    }
    identities = {d["contract_sha256"] for d in definitions.values()}
    require(len(identities) == 1, "one recovery contract required")
    inputs = Inputs(context.inputs, identities.pop())
    c = inputs.contract
    require(build_plan(c).payload == plan.payload, "recovery plan differs")
    targets = {t["issue"]: t for t in c["targets"]}
    captured = {}

    def parent(parents):
        require(len(parents) == 1, "one upstream artifact required")
        p = next(iter(parents.values()))
        return json.loads(p.data)["value"], p.artifact.sha256

    def expected(d, parents, stamp=None):
        phase = d["phase"]
        issue = d["issue"]
        if phase == "source":
            require(not parents, "source has unexpected parents")
            source = inputs.source(issue)
            require(source is not None, "registered recovery source missing")
            return {"issue": issue, "source": source, "source_sha256": digest(source)}
        if phase == "summary":
            values = [json.loads(p.data)["value"] for p in parents.values()]
            require(
                sorted(v["issue"] for v in values) == ["2026114", "2026115", "2026116"],
                "all three replayed reports required",
            )
            require(
                all(v["status"] == "REPLAY_VERIFIED" for v in values),
                "summary requires replay",
            )
            return {"issue": issue, "report": summary(values)}
        if phase == "seal":
            require(not parents and stamp is not None, "fresh seal timestamp required")
            target = targets[issue]
            base = {
                "issue": issue,
                "draw_at": target["draw_at"],
                "sealed_at": stamp,
                "model": "shrink900",
                "blue_training": False,
                "promotion": False,
                "evidence": "EXPLORATORY_PROSPECTIVE",
            }
            if instant(stamp) >= instant(target["draw_at"]):
                return {**base, "status": "MISSING_PREDRAW_SEAL", "tickets": []}
            source = inputs.future.snapshot(target)
            require(source is not None, "registered checkpoint missing")
            require(
                instant(source["observed_at"]) <= instant(stamp),
                "source observed after seal",
            )
            cp = source["checkpoint"]
            q = probabilities(cp["counts"], cp["count"])["shrink900"]
            return {
                **base,
                "status": "SEALED_BEFORE_DRAW",
                "checkpoint_sha256": source["checkpoint_sha256"],
                "source_snapshot_sha256": digest(source),
                "source_records": source["source_records"],
                "training_end_issue": cp["training_end_issue"],
                "count": cp["count"],
                "probabilities": q,
                "tickets": portfolio(
                    q, c["original_contract"]["historical_contract_sha256"], issue
                ),
            }
        prior, identity = parent(parents)
        if phase in ("replay", "summary-replay", "pre-replay", "post-replay"):
            return {**prior, "status": "REPLAY_VERIFIED", "envelope_sha256": identity}
        if phase == "report":
            source = prior["source"]
            seal = inputs.seal(source, issue)
            return {
                **prior,
                "seal": seal,
                "report": report(
                    seal,
                    source["label"],
                    source["payout"],
                    planned_at=next(
                        t["draw_at"]
                        for t in c["original_contract"]["targets"]
                        if t["issue"] == issue
                    ),
                    source_sha256=identity,
                ),
            }
        if phase == "pre-report":
            return {
                "issue": issue,
                "seal": prior,
                "seal_sha256": identity,
                "report": pre_report(prior),
            }
        if phase == "result":
            label = inputs.future.label(targets[issue])
            payout = inputs.payout(issue)
            require(
                label is not None and payout is not None,
                "audited label and registered payout required",
            )
            return {
                "issue": issue,
                "seal": prior["seal"],
                "pre_replay_sha256": identity,
                "label": label["label"],
                "payout": payout,
            }
        require(phase == "post-report", "unknown recovery phase")
        return {
            **prior,
            "report": report(
                prior["seal"], prior["label"], prior["payout"], source_sha256=identity
            ),
        }

    def ready(task, parents):
        reason = inputs.gate()
        if reason:
            return reason
        d = definitions[task.artifact_digest]
        phase = d["phase"]
        issue = d["issue"]
        if phase == "source" and inputs.source(issue) is None:
            return "WAITING_FOR_REGISTERED_RECOVERY_SOURCE"
        if (
            phase == "seal"
            and utcnow() < instant(targets[issue]["draw_at"])
            and inputs.future.snapshot(targets[issue]) is None
        ):
            return "WAITING_FOR_REGISTERED_CHECKPOINT116"
        if phase == "result" and (
            inputs.future.label(targets[issue]) is None or inputs.payout(issue) is None
        ):
            return "WAITING_FOR_AUDITED_DRAW_AND_PAYOUT"
        return None

    def verify(binding, data):
        inputs.read_contract()
        a = json.loads(data)
        d = definitions[binding["task_digest"]]
        require(
            set(a)
            == {
                "schema",
                "phase",
                "issue",
                "task_digest",
                "release_sha256",
                "parents",
                "value",
            },
            "closed recovery artifact required",
        )
        require(
            a["schema"] == binding["artifact_schema"] == SCHEMA
            and a["phase"] == d["phase"]
            and a["issue"] == d["issue"]
            and a["task_digest"] == binding["task_digest"]
            and a["release_sha256"]
            == binding["release_sha256"]
            == context.release.digest
            and binding["scientific_contract_sha256"] == inputs.identity,
            "recovery artifact identity differs",
        )
        ctx = MainlineLedger(store).context(binding["id"])
        parents = {}
        for row in ctx["parents"]:
            p = store.result(row["task_id"])
            require(p is not None, "registered parent missing")
            parents[p.task["business_key"]] = p
        require(
            a["parents"] == {k: p.artifact.sha256 for k, p in parents.items()},
            "recovery parent differs",
        )
        stamp = a["value"].get("sealed_at") if d["phase"] == "seal" else None
        require(
            a["value"] == expected(d, parents, stamp), "deterministic recovery differs"
        )
        if ctx["commit"] is not None:
            commit_guard(binding, data, instant(ctx["commit"]["created_at"]))
        if d["phase"] == "seal":
            if ctx["commit"] is None:
                require(
                    captured.get(binding["task_digest"]) == digest(a),
                    "seal must come from this attempt",
                )
            else:
                commit = instant(ctx["commit"]["created_at"])
                require(
                    instant(ctx["attempt"]["created_at"]) <= instant(stamp) <= commit,
                    "seal timestamp outside attempt",
                )
                if a["value"]["status"] == "SEALED_BEFORE_DRAW":
                    require(
                        commit < instant(targets[d["issue"]]["draw_at"]),
                        "seal committed after draw",
                    )

    def execute(task, parents, artifacts):
        d = definitions[task.artifact_digest]
        a = {
            "schema": SCHEMA,
            "phase": d["phase"],
            "issue": d["issue"],
            "task_digest": task.artifact_digest,
            "release_sha256": context.release.digest,
            "parents": {k: p.artifact.sha256 for k, p in parents.items()},
            "value": expected(d, parents, utcnow().isoformat()),
        }
        captured[task.artifact_digest] = digest(a)
        return canonical(a)

    def commit_guard(binding, data, server_time):
        require(
            server_time < instant(c["approved_until"]), "recovery authorization expired"
        )
        a = json.loads(data)
        if a["phase"] == "seal":
            draw = instant(targets[a["issue"]]["draw_at"])
            require(
                (server_time < draw) == (a["value"]["status"] == "SEALED_BEFORE_DRAW"),
                "seal crossed draw boundary",
            )
        if a["phase"] in ("result", "post-report", "post-replay"):
            require(
                server_time >= instant(targets[a["issue"]]["draw_at"]),
                "result preceded draw",
            )

    def progress(manifest):
        states = manifest.task_state_by_digest
        done = [
            definitions[t.artifact_digest]
            for t in manifest.tasks
            if states[t.artifact_digest].declared_status.value == "completed"
        ]
        return {
            "schema": SCHEMA,
            "completed_phases": done,
            "scientific_credit": 0,
            "training_performed": False,
            "approved_until": c["approved_until"],
            "next_consumer": "registered replay-gated summary and117 mail",
        }

    return {
        name: Capability(
            name,
            verify,
            execute,
            ready,
            failure_isolated=True,
            commit_guard=commit_guard,
            progress=progress,
        )
        for name in CAPABILITIES.values()
    }
