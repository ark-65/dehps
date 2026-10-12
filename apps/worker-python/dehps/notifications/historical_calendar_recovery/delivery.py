"""One incident summary; cross-version identity checks before any SMTP action."""

import json
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path

from dehps.execution.ledger import MainlineLedger
from dehps.notifications.historical_mail.delivery import Delivery as BaseDelivery

from .contract import EVENT, SCHEMA, digest, instant, require, utcnow


def registered_emails(engine):
    manifest = engine.replay(require_complete=False)
    output = []
    with engine.store.verification_scope():
        for task in manifest.tasks:
            d = json.loads(task.metric_contract)["recovery"]
            phase = d["phase"]
            if phase not in ("replay", "summary-replay", "pre-replay", "post-replay"):
                continue
            result = engine.store.result(engine.bindings[task.artifact_digest])
            if result is None:
                continue
            MainlineLedger(engine.store).verify(result.task["id"])
            value = json.loads(result.data)["value"]
            require(value["status"] == "REPLAY_VERIFIED", "registered replay required")
            kind = {
                "replay": "archive",
                "summary-replay": "summary",
                "pre-replay": "pre",
                "post-replay": "post",
            }[phase]
            output.append(
                {
                    "kind": kind,
                    "issue": d["issue"],
                    "artifact_sha256": value["envelope_sha256"],
                    "replay_sha256": result.artifact.sha256,
                    "seal_status": value.get("seal", {}).get("status"),
                    "report": value["report"],
                }
            )
    return output


class Delivery(BaseDelivery):
    def __init__(self, *args, prior_ledgers, **kwargs):
        super().__init__(*args, **kwargs)
        self.prior_ledgers = tuple(Path(p) for p in prior_ledgers)
        require(len(self.prior_ledgers) == 2, "both original ledgers required")

    def key(self, message):
        if message["kind"] == "summary":
            return digest(
                {
                    "protocol": SCHEMA,
                    "event_id": EVENT,
                    "recipient_sha256": self.contract["recipient_sha256"],
                }
            )
        return super().key(message)

    def deliver(self, message):
        require(
            message["kind"] in ("summary", "pre", "post"),
            "archive reports cannot be individually sent",
        )
        require(
            sha256(self.config.destination.strip().lower().encode()).hexdigest()
            == self.contract["recipient_sha256"],
            "recipient differs",
        )
        if message["kind"] == "summary":
            require(
                message["report"]["event_id"] == EVENT
                and message["issue"] == "2026114-2026116",
                "fixed summary event required",
            )
        else:
            require(message["issue"] == "2026117", "past individual delivery forbidden")
        with self.lock(), ExitStack() as locks:
            for path in sorted(self.prior_ledgers):
                prior = BaseDelivery(
                    path,
                    self.config,
                    self.contract,
                    reauthorize=self.reauthorize,
                    gate=self.gate,
                    mail=self.mail,
                )
                require(path.exists(), "prior delivery ledger missing")
                locks.enter_context(prior.lock())
                state = prior.read()
                require(
                    not any(
                        r.get("issue") in ("2026114", "2026115", "2026116", "2026117")
                        and r.get("status") in ("sending", "uncertain")
                        for r in state["deliveries"].values()
                    ),
                    "affected prior SMTP outcome uncertain; reconcile transport first",
                )
                if message["kind"] != "summary":
                    row = state["deliveries"].get(prior.key(message))
                    if row is not None:
                        require(
                            row.get("recipient_sha256")
                            == self.contract["recipient_sha256"]
                            and row["status"] == "sent",
                            "prior SMTP outcome uncertain; reconcile transport first",
                        )
                        return {
                            "status": "ALREADY_SENT",
                            "issue": message["issue"],
                            "kind": message["kind"],
                            "source": "original_ledger",
                        }
            self.reauthorize()
            moment = utcnow()
            require(
                moment < instant(self.contract["approved_until"]),
                "recovery delivery expired",
            )
            require(self.gate() is None, "source gate prevents delivery")
            state = self.read()
            key = self.key(message)
            row = state["deliveries"].get(key)
            if row is not None:
                require(
                    row["artifact_sha256"] == message["artifact_sha256"]
                    and row["replay_sha256"] == message["replay_sha256"]
                    and row["status"] == "sent",
                    "recovery SMTP outcome uncertain or identity changed",
                )
                return {
                    "status": "ALREADY_SENT",
                    "issue": message["issue"],
                    "kind": message["kind"],
                }
            target = self.contract["targets"][-1]
            if message["kind"] == "pre":
                if (
                    not instant(target["send_at"])
                    <= moment
                    < instant(target["draw_at"])
                ):
                    return {
                        "status": "PENDING_DELIVERY"
                        if moment < instant(target["send_at"])
                        else "MISSED_PRE_DELIVERY"
                    }
                require(
                    message["seal_status"] == "SEALED_BEFORE_DRAW", "real seal required"
                )
            if message["kind"] == "post":
                require(
                    moment >= instant(target["draw_at"]), "post delivery before draw"
                )
            row = {
                k: message[k]
                for k in ("kind", "issue", "artifact_sha256", "replay_sha256")
            }
            row.update(
                status="sending",
                started_at=moment.isoformat(),
                recipient_sha256=self.contract["recipient_sha256"],
            )
            state["deliveries"][key] = row
            self.write(state)
            try:
                self.reauthorize()
                require(
                    utcnow() < instant(self.contract["approved_until"]),
                    "expired before SMTP",
                )
                require(self.gate() is None, "source gate changed before SMTP")
                if message["kind"] == "pre":
                    require(
                        utcnow() < instant(target["draw_at"]),
                        "SMTP crossed draw boundary",
                    )
                receipt = self.mail.send(
                    subject=message["report"]["subject"],
                    text=message["report"]["text"],
                    html=message["report"]["html"],
                    recipient=self.config.destination,
                )
            except BaseException:
                row.update(status="uncertain", completed_at=utcnow().isoformat())
                self.write(state)
                raise
            row.update(
                status="sent",
                completed_at=utcnow().isoformat(),
                message_id=receipt.message_id,
            )
            self.write(state)
            return {
                "status": "SENT",
                "issue": message["issue"],
                "kind": message["kind"],
            }
