from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from dehps.config import ROOT_DIR
from dehps.prediction import error_learning_mainline as mainline
from dehps.prediction.error_learning import DecisionIntegrityError
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest
from test_prediction_error_learning import inputs, outcome
import test_research_os_mainline_supervisor as existing


def test_registered_record_report_and_replay_use_unified_supervisor(tmp_path, monkeypatch, inputs):
    monkeypatch.setattr(existing, "TEST_CONTROL_PLANE_KEY", mainline.CONTROL_PLANE_KEY)
    repo = existing.MemoryMainlineRepository(mainline.initial_manifest(
        minimum_issue="2026102", source=mainline.source_digest()))
    # Exercise the real dispatcher/publication/files/replay with memory storage.
    # Transaction SQL behavior is covered by repository tests separately.
    from dehps.research_os import supervisor as base
    class Cursor:
        def execute(self, sql, params):
            self.rows = ([{"event_digest": e["event_digest"], "event_json": e}
                          for e in repo.events if e["execution_id"] == params[1]]
                         if "event_digest, event_json" in sql else
                         [{"count": sum(r["execution_id"] == params[1] for r in repo.artifacts)}])
            return self
        def fetchall(self): return self.rows
        def fetchone(self): return self.rows[0]
    @contextmanager
    def cursor(**kwargs): yield Cursor()
    @contextmanager
    def connection(): yield SimpleNamespace(cursor=cursor, commit=lambda: None)
    repo.connection_factory = connection
    monkeypatch.setattr(base, "_atomic_insert_registration", lambda c, r: repo.register_mainline_artifact(registration=r))
    monkeypatch.setattr(base, "_atomic_insert_completed_event", lambda c, e: repo.record_mainline_execution_event(event=e))
    monkeypatch.setattr(base, "_atomic_import_completed_manifest", lambda **kw:
                        setattr(repo, "manifest", kw["completed_manifest"]))
    supervisor = mainline.ObservationSupervisor(repository=repo, root_dir=tmp_path,
        code_root=ROOT_DIR, require_clean_tree=False, git_commit="a" * 40)
    monkeypatch.setattr(supervisor.observer, "frozen", lambda issue: deepcopy(inputs))
    bundle, payout = outcome(inputs)
    monkeypatch.setattr(supervisor.observer, "opened", lambda issue:
        (bundle, payout, "2026-09-03T22:00:00+08:00", mainline.notification.build_post_report(
            bundle=bundle, payout=payout, recipient_digest="0" * 64)))
    frozen_before = deepcopy(inputs)
    ids = []
    for phase in ("record", "report"):
        payload = mainline.add_task(repo.manifest.to_dict(include_digest=True), issue="2026102", phase=phase,
                                   inputs=supervisor.observer.inputs("2026102", phase))
        repo.manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = repo.control_plane.resolve(repo.manifest)
        key = mainline.task_key("2026102", phase)
        assert key in [r.task_key for r in snapshot.ready_queue]
        result = supervisor.run_once(task_key=key)
        replay = supervisor.replay(task_key=key)
        assert replay["status"] == "REPLAY_VERIFIED"
        assert replay["execution_id"] == result["execution_id"]
        ids.append(result["execution_id"])
    assert len(set(ids)) == 2
    report = supervisor.observer.stored("2026102", "report")["body"]
    assert report["integration"] == "INTEGRATED"
    assert report["execution_path"] == "ResearchEvidenceSupervisor"
    assert len(report["sample"]["body"]["red_labels_1_to_33"]) == 33
    assert len(report["sample"]["body"]["blue_labels_1_to_16"]) == 16
    assert inputs == frozen_before
    events_before = deepcopy(repo.events)
    supervisor.replay(task_key=mainline.task_key("2026102", "report"))
    assert repo.events == events_before
    record = supervisor.observer.stored("2026102", "record")
    assert record["body"]["body"]["record_mode"] == "POST_HOC_DIAGNOSTIC_INDEX"


def test_report_dependency_and_source_drift_fail_closed():
    initial = mainline.initial_manifest(minimum_issue="2026102", source="f" * 64)
    first = mainline.add_task(initial, issue="2026102", phase="record", inputs=("f" * 64,))
    both = mainline.add_task(first, issue="2026102", phase="report", inputs=("f" * 64,))
    snapshot = ResearchOSControlPlane().resolve(ControlPlaneManifest.from_dict(both))
    ready = [r.task_key for r in snapshot.ready_queue]
    assert mainline.task_key("2026102", "record") in ready
    assert mainline.task_key("2026102", "report") not in ready
    value = mainline.wrap("record", {"safe": True})
    value["body"]["safe"] = False
    with pytest.raises(DecisionIntegrityError, match="observation_artifact_changed"):
        mainline.validate(value)


def test_observer_has_no_formal_or_delivery_capability(tmp_path):
    repo = SimpleNamespace()
    observer = mainline.ObservationSupervisor(repository=repo, root_dir=tmp_path)
    assert set(observer.capabilities) == set(mainline.CAPABILITIES.values())
    assert not set(observer.capabilities).intersection(mainline.notification.p3.CAPABILITIES)
    assert not set(observer.capabilities).intersection(mainline.notification.CAPABILITIES)
