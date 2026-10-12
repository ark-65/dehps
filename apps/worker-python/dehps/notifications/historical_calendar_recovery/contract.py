"""Frozen originals and an independently admitted, bounded corrected calendar."""

from pathlib import Path

from dehps.execution.ledger import canonical_records
from dehps.execution.release import canonical
from dehps.notifications.historical_mail.contract import (
    Inputs as OriginalInputs,
)
from dehps.notifications.historical_mail.contract import (
    digest,
    instant,
    require,
    utcnow,
)
from dehps.notifications.historical_mail.contract import (
    validate as original_validate,
)
from dehps.notifications.historical_mail.plan import build_plan as original_plan
from dehps.notifications.historical_mail.reports import report as original_report
from dehps.notifications.historical_returns.reports import settle
from dehps.prediction.forward_learning.contract import validate_label
from dehps.prediction.historical_learning.contract import sha

SCHEMA = "historical-mail-calendar-recovery.v1"
EVENT = "omission-calendar-recovery-20261012-2026114-2026116"
DATES = {
    "2026114": "2026-10-06",
    "2026115": "2026-10-08",
    "2026116": "2026-10-11",
    "2026117": "2026-10-13",
}
POLICY = {
    "training_performed": False,
    "model_changed": False,
    "scientific_credit": 0,
    "preserve_gaps": True,
    "summary_only": True,
    "event_id": EVENT,
}


def validate(c):
    require(
        set(c)
        == {
            "schema",
            "policy",
            "original_contract",
            "original_plan_digest",
            "original_release_sha256",
            "original_returns_sha256",
            "original_seals",
            "future_contract",
            "targets",
            "recipient_sha256",
            "export_public_key",
            "approved_until",
            "calendar_sources",
        },
        "closed recovery contract required",
    )
    require(c["schema"] == SCHEMA and c["policy"] == POLICY, "recovery policy differs")
    old = original_validate(c["original_contract"])
    future = original_validate(c["future_contract"])
    for field in ("recipient_sha256", "approved_until"):
        require(
            c[field] == old[field] == future[field],
            "recipient or original expiry changed",
        )
    require(
        c["export_public_key"] == future["export_public_key"],
        "recovery signing key differs",
    )
    require(
        {k: v for k, v in future.items() if k not in ("targets", "export_public_key")}
        == {k: v for k, v in old.items() if k not in ("targets", "export_public_key")},
        "frozen estimator/source binding changed",
    )
    require(original_plan(old).digest == c["original_plan_digest"], "old plan differs")
    require(
        set(c["original_seals"]) == {"2026114", "2026115", "2026116"},
        "original seal bindings required",
    )
    for identity in c["original_seals"].values():
        if identity is not None:
            sha(identity)
    sha(c["original_release_sha256"])
    sha(c["original_returns_sha256"])
    targets = []
    for issue, date in DATES.items():
        targets.append(
            {
                "issue": issue,
                "previous_issue": str(int(issue) - 1),
                "draw_at": date + "T21:15:00+08:00",
                "send_at": date + "T17:00:00+08:00",
            }
        )
    require(
        c["targets"] == targets and future["targets"] == targets[-1:],
        "corrected calendar differs",
    )
    require(
        set(c["calendar_sources"]) == set(DATES)
        and all(
            isinstance(v, str) and v.startswith("https://")
            for v in c["calendar_sources"].values()
        ),
        "authoritative calendar sources required",
    )
    return c


def registered(o, c, issue, phase):
    require(
        set(o) == {"artifact", "artifact_sha256", "task", "mainline"},
        "closed registration required",
    )
    a = o["artifact"]
    ctx = o["mainline"]
    task = o["task"]
    require(
        ctx["commit"] is not None
        and digest(a) == o["artifact_sha256"] == ctx["commit"]["artifact_sha256"]
        and ctx["commit"]["artifact_size"] == len(canonical(a))
        and task == ctx["task"]
        and ctx["records"] == canonical_records(ctx)
        and ctx["event_count"] == 2
        and ctx["registration_count"] == 1,
        "original registration differs",
    )
    old = original_plan(c["original_contract"])
    specs = {t["task_digest"]: t for t in old.payload["tasks"]}
    definitions = {t["digest"]: t["value"] for t in old.payload["canonical"]["tasks"]}
    require(
        a["phase"] == phase
        and a["issue"] == issue
        and a["task_digest"] == task["task_digest"]
        and a["release_sha256"]
        == task["release_sha256"]
        == c["original_release_sha256"]
        and task["scientific_contract_sha256"] == digest(c["original_contract"])
        and task["spec"] == specs.get(a["task_digest"])
        and ctx["definition"] == definitions.get(a["task_digest"])
        and task["business_key"].endswith(issue + "-" + phase),
        "original task binding differs",
    )
    return a["value"]


def missing_context(ctx, c, issue):
    require(
        ctx["commit"] is None and ctx["registration_count"] == ctx["event_count"] == 0,
        "missing seal has a durable registration",
    )
    old = original_plan(c["original_contract"])
    task = ctx["task"]
    specs = {t["task_digest"]: t for t in old.payload["tasks"]}
    definitions = {t["digest"]: t["value"] for t in old.payload["canonical"]["tasks"]}
    require(
        task["spec"] == specs.get(task["task_digest"])
        and ctx["definition"] == definitions.get(task["task_digest"])
        and task["release_sha256"] == c["original_release_sha256"]
        and task["business_key"].endswith(issue + "-seal"),
        "absence belongs to another seal task",
    )


class Inputs(OriginalInputs):
    def __init__(self, root, expected):
        self.root = Path(root)
        self.identity = sha(expected)
        self.contract = validate(self.read_contract())
        self.future = OriginalInputs(
            self.root / "prospective", digest(self.contract["future_contract"])
        )

    def source(self, issue):
        body = self.read("sources/" + issue + ".json")
        if body is None:
            return None
        require(
            set(body) == {"contract_sha256", "issue", "source"}
            and body["issue"] == issue,
            "source identity differs",
        )
        source = body["source"]
        target = next(t for t in self.contract["targets"] if t["issue"] == issue)
        require(
            set(source)
            == {
                "original",
                "seal_registration",
                "absence",
                "label",
                "receipt",
                "payout",
            },
            "closed recovery source required",
        )
        label = validate_label(source["label"])
        receipt = source["receipt"]
        require(
            label["issue"] == issue
            and instant(label["draw_at"]) == instant(target["draw_at"])
            and digest(receipt) == label["audit_sha256"],
            "actual draw identity differs",
        )
        rows = [r for r in receipt["rows"] if r["issue"] == issue]
        require(
            len(rows) == 1
            and rows[0]["red"] == label["red"]
            and rows[0]["blue"] == label["blue"]
            and rows[0]["draw_date"] == DATES[issue],
            "source audit conflict",
        )
        require(
            instant(receipt["completed_at"])
            <= instant(receipt["observed_at"])
            <= instant(label["available_at"])
            <= utcnow(),
            "audited label availability differs",
        )
        if source["original"] is None:
            require(
                source["seal_registration"] is None and source["absence"] is not None,
                "registered absence required",
            )
            require(
                self.contract["original_seals"][issue] is None,
                "expected original seal missing",
            )
            missing_context(source["absence"], self.contract, issue)
        else:
            require(source["absence"] is None, "seal and absence conflict")
            value = registered(source["original"], self.contract, issue, "pre-replay")
            seal = registered(source["seal_registration"], self.contract, issue, "seal")
            require(
                source["seal_registration"]["artifact_sha256"]
                == self.contract["original_seals"][issue],
                "original sealed digest differs",
            )
            require(
                value["status"] == "REPLAY_VERIFIED"
                and value["seal"] == seal
                and value["seal_sha256"]
                == source["seal_registration"]["artifact_sha256"]
                and value["report"] == original_report(seal),
                "original seal/replay differs",
            )
            old_target = next(
                t
                for t in self.contract["original_contract"]["targets"]
                if t["issue"] == issue
            )
            require(
                seal["draw_at"] == old_target["draw_at"], "old calendar was rewritten"
            )
            if seal["status"] == "SEALED_BEFORE_DRAW":
                require(
                    seal["training_end_issue"] == target["previous_issue"]
                    and instant(seal["sealed_at"])
                    <= instant(
                        source["seal_registration"]["mainline"]["commit"]["created_at"]
                    )
                    < instant(target["draw_at"]),
                    "genuine prior-only seal required",
                )
        payout = source["payout"]
        require(
            set(payout)
            == {
                "artifact",
                "registered_artifact_digest",
                "registered_task",
                "file_sha256",
            }
            and payout["artifact"]["artifact_digest"]
            == payout["registered_artifact_digest"]
            and payout["registered_task"].endswith(issue + "-post-return-report"),
            "registered payout differs",
        )
        sha(payout["file_sha256"])
        settle(self.seal(source, issue), label, payout["artifact"])
        return source

    @staticmethod
    def seal(source, issue):
        if source["original"] is not None:
            return source["original"]["artifact"]["value"]["seal"]
        return {
            "issue": issue,
            "status": "MISSING_PREDRAW_SEAL",
            "tickets": [],
            "sealed_at": None,
            "draw_at": DATES[issue] + "T21:15:00+08:00",
        }

    def payout(self, issue):
        body = self.read("payouts/" + issue + ".json")
        if body is None:
            return None
        require(
            set(body) == {"contract_sha256", "issue", "payout"}
            and body["issue"] == issue,
            "payout issue differs",
        )
        p = body["payout"]
        sha(p["file_sha256"])
        require(
            p["artifact"]["artifact_digest"] == p["registered_artifact_digest"]
            and p["registered_task"].endswith(issue + "-post-return-report"),
            "payout registration differs",
        )
        return p
