import importlib.util
import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import psycopg
import pytest
from conftest import authority_fixture
from dehps.notifications.historical_calendar_recovery.contract import DATES, digest
from dehps.notifications.historical_calendar_recovery.delivery import registered_emails
from dehps.notifications.historical_calendar_recovery.plan import build_plan
from dehps.notifications.p3_top100 import _artifact
from dehps.prediction.forward_learning.publisher import signed
from historical_calendar_recovery_scenario import engine
from test_execution_mainline import mainline_fixture, records

spec = importlib.util.spec_from_file_location(
    "recovery_fixture",
    Path(__file__).resolve().parents[1]
    / "tests/historical_calendar_recovery_fixtures.py",
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.fixture
def authority():
    yield from authority_fixture("observer")


@pytest.fixture
def mainline(authority, tmp_path):
    for initial, admin, authorize in mainline_fixture(authority, tmp_path):
        yield initial, admin, lambda p, authorize=authorize: {**authorize(p), "domain": "observer"}


def setup(mainline):
    initial, admin, authorize = mainline
    c, _ = helper.fixture(Path(initial["root"]) / "inputs")
    return authorize(build_plan(c)), admin


def child(config, mode):
    path = Path(config["root"]) / "child.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    return [
        sys.executable,
        str(Path(__file__).with_name("historical_calendar_recovery_scenario.py")),
        str(path),
        mode,
    ]


def test_real_postgres_recovery_dag_new_process_readonly_replay(mainline):
    config, admin = setup(mainline)
    e = engine(config)
    e.run()
    assert not e.task_errors and records(admin)["execution_store.commits"] == 14
    messages = registered_emails(e)
    assert (
        len(messages) == 5 and len([m for m in messages if m["kind"] == "summary"]) == 1
    )
    assert all(
        m["report"]["settlement"]["cost_cny"] is None
        for m in messages
        if m["issue"] in ("2026115", "2026116")
    )
    before = records(admin)
    engine(config).run()
    assert records(admin) == before
    result = subprocess.run(
        child(config, "replay"), capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["completed"] == 14 and records(admin) == before


def test_interrupt_and_repeated_triggers_preserve_commits(mainline):
    config, admin = setup(mainline)
    result = subprocess.run(
        child(config, "kill-after-commit"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == -9 and records(admin)["execution_store.commits"] == 1
    for _ in range(2):
        e = engine(config)
        e.run()
        assert not e.task_errors
    assert records(admin)["execution_store.commits"] == 14


def test_lost_commit_acknowledgement_recovers_once(mainline, monkeypatch):
    config, admin = setup(mainline)
    e = engine(config)
    original = e.store.commit
    calls = []

    def lost(*args, **kw):
        result = original(*args, **kw)
        calls.append(1)
        if len(calls) == 1:
            raise psycopg.OperationalError("local simulated lost acknowledgement")
        return result

    monkeypatch.setattr(e.store, "commit", lost)
    e.run()
    assert (
        not e.task_errors
        and records(admin)["execution_store.commits"]
        == records(admin)["execution_store.attempts"]
        == 14
    )


def test_complete_seventeen_task_postdraw_dag_in_isolated_temporal_fixture(
    mainline, monkeypatch
):
    # Exercise the post-draw half now with a synthetic past calendar and a GAP.
    # This does not assert a genuine117 draw, seal, payout or delivery.
    monkeypatch.setitem(DATES, "2026117", "2026-10-11")
    initial, admin, authorize = mainline
    root = Path(initial["root"]) / "inputs"
    c, key = helper.fixture(root)
    source = json.loads((root / "sources/2026116.json").read_bytes())["body"]["source"]
    receipt = deepcopy(source["receipt"])
    receipt["rows"][0]["issue"] = "2026117"
    label = {**source["label"], "issue": "2026117", "audit_sha256": digest(receipt)}
    (root / "prospective/labels").mkdir(exist_ok=True)
    (root / "prospective/labels/2026117.json").write_bytes(
        signed(
            {
                "contract_sha256": digest(c["future_contract"]),
                "label": label,
                "receipt": receipt,
            },
            key,
            c["export_public_key"],
        )
    )
    old = source["payout"]["artifact"]
    prize = {
        **source["payout"],
        "registered_task": "fixture-2026117-post-return-report",
    }
    prize["artifact"] = _artifact(
        artifact_type=old["artifact_type"],
        body={**old["body"], "issue": "2026117"},
        parent_digests=tuple(old["parent_digests"]),
    )
    prize["registered_artifact_digest"] = prize["artifact"]["artifact_digest"]
    (root / "payouts").mkdir(exist_ok=True)
    (root / "payouts/2026117.json").write_bytes(
        signed(
            {"contract_sha256": digest(c), "issue": "2026117", "payout": prize},
            key,
            c["export_public_key"],
        )
    )
    config = authorize(build_plan(c))
    e = engine(config)
    e.run()
    assert not e.task_errors and records(admin)["execution_store.commits"] == 17
    before = records(admin)
    result = subprocess.run(
        child(config, "replay-past-fixture"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["completed"] == 17 and records(admin) == before


@pytest.mark.skipif(
    not os.environ.get("DEHPS_RECOVERY_VALIDATION_INPUTS"),
    reason="requires authenticated incident export",
)
def test_actual_registered_incident_export_in_disposable_postgres(mainline):
    initial, admin, authorize = mainline
    root = Path(initial["root"]) / "inputs"
    shutil.copytree(os.environ["DEHPS_RECOVERY_VALIDATION_INPUTS"], root)
    c = json.loads((root / "contract.json").read_bytes())
    config = authorize(build_plan(c))
    e = engine(config)
    e.run()
    assert not e.task_errors
    assert records(admin)["execution_store.commits"] == 14
    before = records(admin)
    result = subprocess.run(
        child(config, "replay"), capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["completed"] == 14 and records(admin) == before
