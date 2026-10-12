import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.notifications.historical_calendar_recovery import contract
from dehps.notifications.historical_calendar_recovery.capabilities import (
    build_capabilities,
)
from dehps.notifications.historical_calendar_recovery.delivery import Delivery
from dehps.notifications.historical_calendar_recovery.plan import build_plan
from dehps.prediction.forward_learning.publisher import signed
from historical_calendar_recovery_fixtures import fixture


def test_closed_calendar_and_seventeen_tasks_keep_originals_and_gaps(tmp_path):
    c, _ = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    assert len(build_plan(c).validate().tasks) == 17
    assert (
        inputs.seal(inputs.source("2026114"), "2026114")["status"]
        == "SEALED_BEFORE_DRAW"
    )
    for issue in ("2026115", "2026116"):
        assert inputs.seal(inputs.source(issue), issue)["tickets"] == []
    bad = deepcopy(c)
    bad["targets"][0]["draw_at"] = c["original_contract"]["targets"][0]["draw_at"]
    with pytest.raises(BoundaryError, match="calendar"):
        contract.validate(bad)
    bad = deepcopy(c)
    bad["approved_until"] = (datetime.now(UTC) + timedelta(days=500)).isoformat()
    with pytest.raises(BoundaryError, match="expiry"):
        contract.validate(bad)


@pytest.mark.parametrize(
    "mode", ["seal", "registration", "label", "payout", "absence", "signature"]
)
def test_archived_sources_refuse_corruption_and_postdraw_seals(tmp_path, mode):
    c, key = fixture(tmp_path)
    inputs = contract.Inputs(tmp_path, contract.digest(c))
    issue = "2026116" if mode == "absence" else "2026114"
    path = tmp_path / "sources" / (issue + ".json")
    body = json.loads(path.read_bytes())["body"]
    source = body["source"]
    if mode == "seal":
        source["seal_registration"]["mainline"]["commit"]["created_at"] = (
            "2026-10-07T00:00:00+00:00"
        )
    elif mode == "registration":
        source["original"]["mainline"]["registration_count"] = 2
    elif mode == "label":
        source["label"]["red"] = [2, 3, 4, 5, 6, 7]
    elif mode == "payout":
        source["payout"]["registered_artifact_digest"] = "f" * 64
    elif mode == "absence":
        source["absence"]["registration_count"] = 1
    else:
        body["issue"] = "2026115"
    path.write_bytes(signed(body, key, c["export_public_key"]))
    with pytest.raises(BoundaryError):
        inputs.source(issue)


def delivery_fixture(root):
    c, _ = fixture(root)
    calls = []
    config = SimpleNamespace(destination="fixture@example.test")
    mail = SimpleNamespace(
        send=lambda **kw: (
            calls.append(kw) or SimpleNamespace(message_id="local-fake-only")
        )
    )
    paths = [root / "old.json", root / "returns.json"]
    for p in paths:
        p.write_bytes(
            canonical({"schema": "historical-learning-mail.v1", "deliveries": {}})
        )
    d = Delivery(
        root / "ledger.json",
        config,
        c,
        reauthorize=lambda: None,
        gate=lambda: None,
        mail=mail,
        prior_ledgers=paths,
    )
    m = {
        "kind": "summary",
        "issue": "2026114-2026116",
        "artifact_sha256": "a" * 64,
        "replay_sha256": "b" * 64,
        "report": {
            "event_id": contract.EVENT,
            "subject": "fixture",
            "text": "fixture",
            "html": "fixture",
        },
    }
    return d, m, calls


def test_fixed_incident_dedupe_and_no_individual_backfill(tmp_path):
    d, m, calls = delivery_fixture(tmp_path)
    assert d.deliver(m)["status"] == "SENT"
    assert d.deliver(m)["status"] == "ALREADY_SENT" and len(calls) == 1
    with pytest.raises(BoundaryError):
        d.deliver({**m, "kind": "post", "issue": "2026114"})
    with pytest.raises(BoundaryError):
        d.deliver({**m, "artifact_sha256": "c" * 64})


@pytest.mark.parametrize("outcome", ["sent", "sending", "uncertain"])
def test_both_old_ledgers_are_consulted_before_new_delivery(tmp_path, outcome):
    d, m, calls = delivery_fixture(tmp_path)
    m = {**m, "kind": "pre", "issue": "2026117", "seal_status": "SEALED_BEFORE_DRAW"}
    row = {
        "kind": "pre",
        "issue": "2026117",
        "status": outcome,
        "recipient_sha256": d.contract["recipient_sha256"],
    }
    d.prior_ledgers[1].write_bytes(
        canonical(
            {"schema": "historical-learning-mail.v1", "deliveries": {d.key(m): row}}
        )
    )
    if outcome == "sent":
        assert d.deliver(m)["status"] == "ALREADY_SENT"
    else:
        with pytest.raises(BoundaryError, match="uncertain"):
            d.deliver(m)
    assert calls == []


@pytest.mark.parametrize("failure", ["smtp", "crash_after_smtp", "expired", "source"])
def test_no_duplicate_after_uncertain_smtp_or_admission_loss(tmp_path, failure):
    d, m, calls = delivery_fixture(tmp_path)
    if failure == "smtp":

        def fail(**kw):
            calls.append(kw)
            raise OSError("local simulated ambiguity")

        d.mail = SimpleNamespace(send=fail)
    elif failure == "crash_after_smtp":
        original = d.write

        def fail(state):
            if next(iter(state["deliveries"].values()))["status"] == "sent":
                raise OSError("local simulated crash")
            original(state)

        d.write = fail
    elif failure == "expired":
        d.contract = {
            **d.contract,
            "approved_until": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        }
    else:
        d.gate = lambda: "SOURCE_CONFLICT"
    for _ in range(2):
        with pytest.raises((BoundaryError, OSError)):
            d.deliver(m)
    assert len(calls) <= 1


def test_commit_guard_draw_boundary_and_expiry(tmp_path):
    c, _ = fixture(tmp_path)
    p = build_plan(c)
    caps = build_capabilities(
        p,
        None,
        SimpleNamespace(inputs=tmp_path, release=SimpleNamespace(digest="a" * 64)),
    )
    cap = next(iter(caps.values()))
    draw = contract.instant(c["targets"][-1]["draw_at"])
    a = {"phase": "seal", "issue": "2026117", "value": {"status": "SEALED_BEFORE_DRAW"}}
    cap.commit_guard({}, canonical(a), draw - timedelta(microseconds=1))
    with pytest.raises(BoundaryError, match="boundary"):
        cap.commit_guard({}, canonical(a), draw)
    with pytest.raises(BoundaryError, match="expired"):
        cap.commit_guard({}, canonical(a), contract.instant(c["approved_until"]))


def test_concurrent_summary_triggers_send_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    d, m, calls = delivery_fixture(tmp_path)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: d.deliver(m), range(2)))
    assert (
        sorted(r["status"] for r in results) == ["ALREADY_SENT", "SENT"]
        and len(calls) == 1
    )


def test_uncertain_past_mail_blocks_summary_until_reconciled(tmp_path):
    d, m, calls = delivery_fixture(tmp_path)
    d.prior_ledgers[0].write_bytes(
        canonical(
            {
                "schema": "historical-learning-mail.v1",
                "deliveries": {
                    "old114": {"issue": "2026114", "kind": "pre", "status": "uncertain"}
                },
            }
        )
    )
    with pytest.raises(BoundaryError, match="uncertain"):
        d.deliver(m)
    assert calls == []
