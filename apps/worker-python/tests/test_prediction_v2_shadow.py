from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from dehps.draw_sync.models import DrawSyncResult, DrawSyncStatus
from dehps.draw_sync.scheduler import DrawSyncWatch
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.input_contracts.history_window import HistorySnapshotArtifact
from dehps.notifications.mainline_prediction import compile_mainline_prediction_email
from dehps.notifications.prediction_v2_shadow import (
    PredictionV2NotificationError,
    PredictionV2NotificationLedger,
    build_notification_envelope,
)
from dehps.optimization.next_candidates import refresh_training_prediction_lines_current
from dehps.prediction.v2.contracts import (
    ACTIVATION_FACT,
    ACTIVATION_SCHEMA,
    PredictionV2ContractError,
    load_legacy_baseline,
    load_shadow_contract,
    seal_artifact,
)
from dehps.prediction.v2.experts import (
    ExpertNotAuthorizedError,
    FusionRouter,
    MarginalExpert,
    TemporalExpert,
)
from dehps.prediction.v2.generator import UNIVERSE, generate_shadow_pool
from dehps.prediction.v2.issues import (
    build_history_artifact,
    build_issue_manifest,
    issue_facts,
    issue_task_keys,
)
from dehps.prediction.v2.mainline import (
    CONTROL_PLANE_KEY,
    REFERENCE_TASK_KEY,
    REPLAY_COMPLETION_FACT,
    REPLAY_TASK_KEY,
)
from dehps.prediction.v2.replay import replay_post_draw, replay_pre_draw
from dehps.prediction.v2.reports import build_post_draw_report, build_pre_draw_report
from dehps.prediction.v2.retirement import (
    LegacyPredictionRetiredError,
    legacy_retirement_status,
    load_cutover_plan,
    scheduler_cutover_dry_run,
)
from dehps.prediction.v2.scheduling import (
    additive_migration_dry_run,
    infer_target_issue,
    materialize_post_draw_extension,
    materialize_pre_draw_extension,
)
from dehps.prediction.v2.state import encode_state
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/prediction-v2/prediction-v2-shadow-mainline-v1.json"
TEST_COMMIT = "a" * 40


def reference_history(*, count: int = 120, salt: int = 0) -> HistorySnapshotArtifact:
    return HistorySnapshotArtifact.from_history(
        [
            (
                f"2026{index:03d}",
                None,
                candidate_unrank(
                    (index * 7_919 + 104_729 + salt) % UNIVERSE.cardinality,
                    universe=UNIVERSE,
                ),
            )
            for index in range(1, count + 1)
        ],
        source="test_fixture",
    )


@pytest.fixture(scope="module")
def shadow_bundle() -> dict:
    contract = load_shadow_contract(ROOT)
    history = reference_history()
    state = encode_state(history, as_of_issue="2026120", target_issue="2026121")
    pool, top100 = generate_shadow_pool(contract=contract, state=state)
    pre_draw = build_pre_draw_report(
        contract=contract,
        state=state,
        pool=pool,
        top100=top100,
    )
    return {
        "contract": contract,
        "history": history,
        "state": state,
        "pool": pool,
        "top100": top100,
        "pre_draw": pre_draw,
    }


def test_shadow_contract_forces_null_route_and_locks_signal_experts() -> None:
    contract = load_shadow_contract(ROOT)

    assert contract["route"] == "BASELINE_ONLY"
    assert contract["historical_evidence"] == "NOT_RUN"
    assert FusionRouter().select_route({})["signal_bearing_experts_used"] == []
    with pytest.raises(ExpertNotAuthorizedError):
        MarginalExpert().score({})
    with pytest.raises(ExpertNotAuthorizedError):
        TemporalExpert().score({})


def test_state_encoder_enforces_prior_only_30_60_120_boundary() -> None:
    history = reference_history()
    state = encode_state(history, as_of_issue="2026120", target_issue="2026121")

    assert state["state_windows"] == [30, 60, 120]
    assert [state["windows"][str(size)]["draw_count"] for size in (30, 60, 120)] == [30, 60, 120]
    assert state["historical_evidence"] == "NOT_RUN"
    with pytest.raises(ValueError, match="strictly after"):
        encode_state(history, as_of_issue="2026120", target_issue="2026120")
    with pytest.raises(ValueError, match="at least 120"):
        encode_state(reference_history(count=119), as_of_issue="2026119", target_issue="2026120")
    with pytest.raises(ValueError, match="end exactly"):
        encode_state(history, as_of_issue="2026119", target_issue="2026121")


def test_shadow_pool_is_deterministic_legal_unique_and_has_no_expert_effect(
    shadow_bundle: dict,
) -> None:
    pool, top100 = generate_shadow_pool(
        contract=shadow_bundle["contract"],
        state=shadow_bundle["state"],
    )

    assert pool == shadow_bundle["pool"]
    assert top100 == shadow_bundle["top100"]
    assert len(pool["ordered_lex_ids"]) == len(set(pool["ordered_lex_ids"])) == 10_000
    assert len(top100["candidates"]) == 100
    assert len({tuple(item["red_numbers"]) for item in top100["candidates"]}) == 100
    assert all(
        len(row) == 6 and row == sorted(row) and min(row) >= 1 and max(row) <= 33
        for row in (item["red_numbers"] for item in top100["candidates"])
    )
    assert pool["signal_bearing_experts_used"] == []
    assert pool["diversity_diagnostics"]["selection_effect"] is False
    assert top100["ranking_semantics"] == "DETERMINISTIC_LEGAL_NULL_ORDER"
    assert top100["promotion_gate_opened"] is False


def test_shadow_identity_changes_with_target_or_history(shadow_bundle: dict) -> None:
    target_state = encode_state(
        shadow_bundle["history"],
        as_of_issue="2026120",
        target_issue="2026122",
    )
    target_pool, _ = generate_shadow_pool(contract=shadow_bundle["contract"], state=target_state)
    changed_history = reference_history(salt=1)
    changed_state = encode_state(changed_history, as_of_issue="2026120", target_issue="2026121")
    history_pool, _ = generate_shadow_pool(contract=shadow_bundle["contract"], state=changed_state)

    assert target_pool["artifact_digest"] != shadow_bundle["pool"]["artifact_digest"]
    assert history_pool["artifact_digest"] != shadow_bundle["pool"]["artifact_digest"]


def test_pre_and_post_reports_bind_time_boundary_and_physically_replay(shadow_bundle: dict) -> None:
    pre_replay = replay_pre_draw(
        contract=shadow_bundle["contract"],
        history=shadow_bundle["history"],
        expected_state=shadow_bundle["state"],
        expected_pool=shadow_bundle["pool"],
        expected_top100=shadow_bundle["top100"],
        expected_report=shadow_bundle["pre_draw"],
    )
    actual = candidate_unrank((121 * 7_919 + 104_729) % UNIVERSE.cardinality, universe=UNIVERSE)
    post = build_post_draw_report(
        pre_draw_report=shadow_bundle["pre_draw"],
        actual_issue="2026121",
        actual_red_numbers=actual,
    )
    post_replay = replay_post_draw(
        pre_draw_report=shadow_bundle["pre_draw"],
        actual_issue="2026121",
        actual_red_numbers=actual,
        expected_report=post,
    )

    assert pre_replay["status"] == post_replay["status"] == "REPLAY_VERIFIED"
    assert post["pre_draw_report_digest"] == shadow_bundle["pre_draw"]["artifact_digest"]
    assert post["historical_evidence"] == "NOT_RUN"
    assert post["promotion_gate_opened"] is False
    with pytest.raises(ValueError, match="does not match"):
        build_post_draw_report(
            pre_draw_report=shadow_bundle["pre_draw"],
            actual_issue="2026122",
            actual_red_numbers=actual,
        )
    tampered = json.loads(json.dumps(shadow_bundle["pre_draw"]))
    tampered["top100"][0]["red_numbers"] = [1, 2, 3, 4, 5, 6]
    with pytest.raises(PredictionV2ContractError, match="digest mismatch"):
        build_post_draw_report(
            pre_draw_report=tampered,
            actual_issue="2026121",
            actual_red_numbers=actual,
        )


def valid_activation(path: Path) -> dict:
    baseline = load_legacy_baseline(ROOT)
    contract = load_shadow_contract(ROOT)
    plan = load_cutover_plan(ROOT)
    activation = seal_artifact(
        {
            "schema_version": ACTIVATION_SCHEMA,
            "artifact_type": "LegacyPredictionRetirementActivation.v1",
            "status": "ACTIVE",
            "activation_fact": ACTIVATION_FACT,
            "operator_request_id": "operator_prediction_v2_live_cutover_test",
            "activated_at": "2026-08-02T00:00:00+08:00",
            "legacy_baseline_digest": baseline["artifact_digest"],
            "prediction_v2_contract_digest": contract["artifact_digest"],
            "cutover_plan_digest": plan["artifact_digest"],
            "legacy_artifacts_preserved": True,
            "m4_state_changed": False,
        },
        domain="dehps.legacy-prediction-retirement-activation.v1",
    )
    path.write_text(json.dumps(activation), encoding="utf-8")
    return activation


def test_retirement_is_inactive_by_default_and_valid_activation_blocks_old_entrypoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    activation_path = tmp_path / "activation.json"
    assert legacy_retirement_status(activation_path=activation_path)["compute_allowed"] is True
    valid_activation(activation_path)
    assert legacy_retirement_status(activation_path=activation_path)["compute_allowed"] is False
    monkeypatch.setattr(
        "dehps.prediction.v2.retirement.DEFAULT_ACTIVATION_PATH",
        activation_path,
    )

    with pytest.raises(LegacyPredictionRetiredError, match="legacy_prediction_line_retired"):
        refresh_training_prediction_lines_current(object(), ranked_universe=[object()])
    with pytest.raises(LegacyPredictionRetiredError, match="legacy_prediction_line_retired"):
        compile_mainline_prediction_email({}, recipient="test@example.com")


def test_invalid_activation_fails_closed(tmp_path: Path) -> None:
    activation_path = tmp_path / "activation.json"
    payload = valid_activation(activation_path)
    payload["legacy_baseline_digest"] = "0" * 64
    activation_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PredictionV2ContractError):
        legacy_retirement_status(activation_path=activation_path)


def test_draw_sync_keeps_ingestion_but_skips_legacy_evaluation_after_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class SyncService:
        calls = 0

        def once(self):
            self.calls += 1
            return DrawSyncResult(
                status=DrawSyncStatus.NEW_ISSUE,
                previous_latest_issue="2026120",
                current_latest_issue="2026121",
                inserted_issues=("2026121",),
                updated_issues=(),
                audit_passed=True,
                history_fingerprint_before="before",
                history_fingerprint_after="after",
                event_key="draw:2026121",
            )

    class Evaluator:
        calls = 0

        def evaluate_pending(self):
            self.calls += 1
            raise AssertionError("legacy evaluator must not run")

    delivered: list[str] = []
    v2_delivered: list[str] = []
    service = SyncService()
    evaluator = Evaluator()
    monkeypatch.setattr(
        "dehps.draw_sync.scheduler.legacy_retirement_status",
        lambda: {"status": "ACTIVE", "compute_allowed": False},
    )
    watch = DrawSyncWatch(
        service=service,  # type: ignore[arg-type]
        forward_evaluator=evaluator,
        post_draw_report_notifier=lambda issue: delivered.append(issue) or {"status": "sent"},
        prediction_v2_shadow_notifier=lambda issue: v2_delivered.append(issue) or {"status": "sent"},
        state_path=tmp_path / "state.json",
        pid_path=tmp_path / "pid",
        code_commit="b" * 40,
    )

    watch.run(once=True)

    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert service.calls == 1
    assert evaluator.calls == 0
    assert delivered == []
    assert v2_delivered == ["2026121"]
    assert state["forward_evaluation"]["status"] == "skipped"
    assert state["legacy_prediction_lines"] == {
        "status": "LEGACY_FROZEN",
        "compute_scheduled": False,
    }
    assert state["prediction_v2_shadow_report"] == {"status": "sent"}
    assert state["resume_result"] is None


def test_scheduler_cutover_plan_is_non_mutating() -> None:
    before = {
        path: path.read_bytes()
        for path in (ROOT / "configs/prediction-v2").glob("*.json")
    }
    dry_run = scheduler_cutover_dry_run(root_dir=ROOT)
    after = {path: path.read_bytes() for path in before}

    assert before == after
    assert dry_run["status"] == "PLAN_VERIFIED_NO_OPERATION"
    assert dry_run["live_state_changed"] is False
    assert dry_run["service_operations_executed"] == []
    assert dry_run["m4_state_changed"] is False


def test_prediction_v2_control_plane_starts_ready_without_touching_m4() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)

    assert [item.task_key for item in snapshot.ready_queue] == [REFERENCE_TASK_KEY]
    state = {item.task_key: item.status.value for item in snapshot.resolutions}
    assert state[REPLAY_TASK_KEY] == "dependency_wait"
    assert state["prediction-v2-shadow-scheduler-cutover-operator"] == "approval_wait"
    m4_path = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
    assert hashlib.sha256(m4_path.read_bytes()).hexdigest() == (
        "316c8acd7e8d04a92410274600b999e626327bf74a3d256f9c7cc202612a17c0"
    )


class MemoryRepository:
    def __init__(self, payload: dict) -> None:
        self.control_plane = ResearchOSControlPlane()
        self.manifest = ControlPlaneManifest.from_dict(payload)
        self.events: list[dict] = []
        self.artifacts: list[dict] = []

    def ensure_schema(self) -> None:
        return None

    def load_manifest(self, *, control_plane_key: str) -> ControlPlaneManifest:
        assert control_plane_key == CONTROL_PLANE_KEY
        return self.manifest

    def import_manifest(self, *, control_plane_key: str, payload: dict, source: str):
        assert control_plane_key == CONTROL_PLANE_KEY
        assert source.startswith("research-evidence-supervisor")
        self.manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = self.control_plane.resolve(self.manifest)
        return SimpleNamespace(
            manifest_digest=self.manifest.artifact_digest,
            snapshot_digest=snapshot.snapshot_digest,
        )

    def record_mainline_execution_event(self, *, event) -> bool:
        value = {
            "event_digest": event.artifact_digest,
            "execution_id": event.execution_id,
            "control_plane_key": event.control_plane_key,
            "manifest_digest": event.manifest_digest,
            "task_key": event.task_key,
            "task_digest": event.task_digest,
            "capability": event.capability,
            "event_type": event.event_type,
            "sequence": event.sequence,
            "recorded_at": event.recorded_at,
            "payload": [list(item) for item in event.payload],
        }
        if any(item["event_digest"] == value["event_digest"] for item in self.events):
            return False
        self.events.append(value)
        return True

    def register_mainline_artifact(self, *, registration) -> bool:
        value = {
            "registration_digest": registration.registration_digest,
            "execution_id": registration.execution_id,
            "control_plane_key": registration.control_plane_key,
            "task_key": registration.task_key,
            "task_digest": registration.task_digest,
            "artifact_digest": registration.artifact_digest,
            "artifact_type": registration.artifact_type,
            "schema_version": registration.schema_version,
            "artifact_path": registration.artifact_path,
            "parent_digests": list(registration.parent_digests),
            "git_commit": registration.git_commit,
        }
        if any(item["registration_digest"] == value["registration_digest"] for item in self.artifacts):
            return False
        self.artifacts.append(value)
        return True

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict, ...]:
        return tuple(
            item
            for item in self.events
            if item["control_plane_key"] == control_plane_key
            and (task_key is None or item["task_key"] == task_key)
            and (execution_id is None or item["execution_id"] == execution_id)
        )

    def list_mainline_artifacts(
        self,
        *,
        control_plane_key: str,
        execution_id: str,
    ) -> tuple[dict, ...]:
        return tuple(
            item
            for item in self.artifacts
            if item["control_plane_key"] == control_plane_key
            and item["execution_id"] == execution_id
        )


def copy_prediction_configs(destination: Path) -> None:
    source = ROOT / "configs/prediction-v2"
    target = destination / "configs/prediction-v2"
    target.mkdir(parents=True)
    for path in source.glob("*.json"):
        shutil.copy2(path, target / path.name)


def test_unified_supervisor_executes_reference_then_replay_and_keeps_m4_absent(
    tmp_path: Path,
) -> None:
    copy_prediction_configs(tmp_path)
    repository = MemoryRepository(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=CONTROL_PLANE_KEY,
        root_dir=tmp_path,
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    first = supervisor.run_once()
    second = supervisor.run_once()

    assert first["task_key"] == REFERENCE_TASK_KEY
    assert second["task_key"] == REPLAY_TASK_KEY
    assert REPLAY_COMPLETION_FACT in repository.manifest.facts.artifacts
    assert second["evidence_progress_percent"] == 0
    assert (tmp_path / "runtime/logs/prediction-v2-shadow-status.json").is_file()
    assert not (tmp_path / "runtime/logs/m4-information-theory-status.json").exists()
    status = json.loads(
        (tmp_path / "runtime/logs/prediction-v2-shadow-status.json").read_text(encoding="utf-8")
    )
    assert status["replay_verified"] is True
    assert status["historical_evidence"] == "NOT_RUN"
    assert status["promotion_gate_opened"] is False
    assert supervisor.replay(task_key=REFERENCE_TASK_KEY)["status"] == "REPLAY_VERIFIED"
    assert supervisor.replay(task_key=REPLAY_TASK_KEY)["status"] == "REPLAY_VERIFIED"

    top100_registration = next(
        item for item in repository.artifacts if item["artifact_type"] == "PredictionV2ShadowTop100Artifact.v1"
    )
    top100_path = tmp_path / top100_registration["artifact_path"]
    top100 = json.loads(top100_path.read_text(encoding="utf-8"))
    top100["candidates"][0]["rank"] = 999
    top100_path.write_text(json.dumps(top100), encoding="utf-8")
    with pytest.raises(MainlineSupervisorError, match="content changed"):
        supervisor.replay(task_key=REFERENCE_TASK_KEY)


def test_issue_manifest_is_prior_only_additive_and_idempotent(tmp_path: Path) -> None:
    history = reference_history()
    history_artifact = build_history_artifact(history)
    issue_manifest = build_issue_manifest(
        history_artifact=history_artifact,
        target_issue="2026121",
    )
    assert issue_manifest["route"] == "BASELINE_ONLY"
    assert issue_manifest["historical_evidence"] == "NOT_RUN"
    with pytest.raises(ValueError, match="strictly later"):
        build_issue_manifest(history_artifact=history_artifact, target_issue="2026120")

    before = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    first, _ = materialize_pre_draw_extension(
        root_dir=tmp_path,
        base_manifest=before,
        history_rows=[record.as_history_draw() for record in history.records],
        target_issue="2026121",
    )
    second, _ = materialize_pre_draw_extension(
        root_dir=tmp_path,
        base_manifest=first,
        history_rows=[record.as_history_draw() for record in history.records],
        target_issue="2026121",
    )
    assert first == second
    assert additive_migration_dry_run(before=before, after=first)["status"] == "VERIFIED"
    assert len(first["tasks"]) == len(before["tasks"]) + 4

    dry_root = tmp_path / "dry-run"
    materialize_pre_draw_extension(
        root_dir=dry_root,
        base_manifest=before,
        history_rows=[record.as_history_draw() for record in history.records],
        target_issue="2026121",
        persist=False,
    )
    assert not dry_root.exists()


def test_target_issue_inference_handles_year_rollover() -> None:
    rows = [
        (
            "2026153",
            date(2026, 12, 31),
            candidate_unrank(153, universe=UNIVERSE),
        )
    ]
    assert infer_target_issue(rows) == "2027001"


def test_post_draw_materialization_is_idempotent_and_fails_closed_on_identity_drift(
    tmp_path: Path,
) -> None:
    history = reference_history()
    base = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pre_payload, _ = materialize_pre_draw_extension(
        root_dir=tmp_path,
        base_manifest=base,
        history_rows=[record.as_history_draw() for record in history.records],
        target_issue="2026121",
    )
    actual = candidate_unrank(121, universe=UNIVERSE)
    first, _ = materialize_post_draw_extension(
        root_dir=tmp_path,
        base_manifest=pre_payload,
        issue="2026121",
        red_numbers=actual,
        durable_event_key="draw-event-a",
        history_fingerprint="history-a",
    )
    second, _ = materialize_post_draw_extension(
        root_dir=tmp_path,
        base_manifest=first,
        issue="2026121",
        red_numbers=actual,
        durable_event_key="draw-event-a",
        history_fingerprint="history-a",
    )
    assert first == second
    with pytest.raises(ValueError, match="immutable artifact collision"):
        materialize_post_draw_extension(
            root_dir=tmp_path,
            base_manifest=first,
            issue="2026121",
            red_numbers=candidate_unrank(122, universe=UNIVERSE),
            durable_event_key="draw-event-b",
            history_fingerprint="history-b",
        )


def test_notification_envelope_requires_bound_replay_and_ledger_is_idempotent(
    shadow_bundle: dict,
    tmp_path: Path,
) -> None:
    replay = replay_pre_draw(
        contract=shadow_bundle["contract"],
        history=shadow_bundle["history"],
        expected_state=shadow_bundle["state"],
        expected_pool=shadow_bundle["pool"],
        expected_top100=shadow_bundle["top100"],
        expected_report=shadow_bundle["pre_draw"],
    )
    envelope = build_notification_envelope(
        report=shadow_bundle["pre_draw"],
        replay_artifact=replay,
        report_kind="pre_draw",
    )
    calls: list[str] = []
    ledger = PredictionV2NotificationLedger(tmp_path / "ledger.json")
    first = ledger.deliver(
        envelope,
        sender=lambda subject, body: calls.append(subject) or "message-1",
    )
    second = ledger.deliver(
        envelope,
        sender=lambda subject, body: calls.append(subject) or "message-2",
    )
    assert first["status"] == second["status"] == "sent"
    assert calls == [envelope["subject"]]
    ledger_payload = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert ledger_payload["artifact_type"] == "PredictionV2NotificationDeliveryLedger.v1"

    uncertain_ledger = PredictionV2NotificationLedger(tmp_path / "uncertain.json")
    with pytest.raises(RuntimeError, match="smtp"):
        uncertain_ledger.deliver(
            envelope,
            sender=lambda subject, body: (_ for _ in ()).throw(RuntimeError("smtp")),
        )
    with pytest.raises(PredictionV2NotificationError, match="manual review"):
        uncertain_ledger.deliver(envelope, sender=lambda subject, body: "must-not-send")


def test_unified_supervisor_executes_real_issue_pre_and_post_replay(
    tmp_path: Path,
) -> None:
    copy_prediction_configs(tmp_path)
    repository = MemoryRepository(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=CONTROL_PLANE_KEY,
        root_dir=tmp_path,
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )
    supervisor.run_once(task_key=REFERENCE_TASK_KEY)
    supervisor.run_once(task_key=REPLAY_TASK_KEY)

    history = reference_history()
    before = repository.manifest.to_dict(include_digest=False)
    pre_payload, _ = materialize_pre_draw_extension(
        root_dir=tmp_path,
        base_manifest=before,
        history_rows=[record.as_history_draw() for record in history.records],
        target_issue="2026121",
    )
    assert additive_migration_dry_run(before=before, after=pre_payload)["status"] == "VERIFIED"
    repository.manifest = ControlPlaneManifest.from_dict(pre_payload)
    keys = issue_task_keys("2026121")
    pre = supervisor.run_once(task_key=keys["pre"])
    pre_replay_result = supervisor.run_once(task_key=keys["pre_replay"])
    assert pre["historical_outcomes_read"] is False
    assert pre_replay_result["replay_status"] == "REPLAY_VERIFIED"
    assert issue_facts("2026121")["pre_replay"] in repository.manifest.facts.artifacts

    actual = candidate_unrank(
        (121 * 7_919 + 104_729) % UNIVERSE.cardinality,
        universe=UNIVERSE,
    )
    before_post = repository.manifest.to_dict(include_digest=False)
    post_payload, _ = materialize_post_draw_extension(
        root_dir=tmp_path,
        base_manifest=before_post,
        issue="2026121",
        red_numbers=actual,
        durable_event_key="draw-issue-2026121-test",
        history_fingerprint="history-fingerprint-test",
    )
    assert additive_migration_dry_run(before=before_post, after=post_payload)["status"] == "VERIFIED"
    repository.manifest = ControlPlaneManifest.from_dict(post_payload)
    post = supervisor.run_once(task_key=keys["post"])
    post_replay_result = supervisor.run_once(task_key=keys["post_replay"])
    assert post["historical_outcomes_read"] is True
    assert post_replay_result["replay_status"] == "REPLAY_VERIFIED"
    assert issue_facts("2026121")["post_replay"] in repository.manifest.facts.artifacts
    assert not repository.manifest.facts.evidence
    assert all(item.get("promotion_gate_opened") is not True for item in (pre, post))
    envelopes = [
        item for item in repository.artifacts
        if item["artifact_type"] == "PredictionV2NotificationEnvelope.v1"
    ]
    assert len(envelopes) == 2
    registered_types = {item["artifact_type"] for item in repository.artifacts}
    assert {
        "PredictionV2IssuePreDrawExecution.v1",
        "PredictionV2IssuePreDrawReplayArtifact.v1",
        "PredictionV2IssuePostDrawExecution.v1",
        "PredictionV2IssuePostDrawReplayArtifact.v1",
    } <= registered_types
    assert not (tmp_path / "runtime/logs/m4-information-theory-status.json").exists()


def test_prediction_v2_scheduler_sources_are_inactive_until_operator_install() -> None:
    pre_service = (ROOT / "deploy/systemd/dehps-prediction-v2-shadow-pre-draw.service").read_text(encoding="utf-8")
    pre_timer = (ROOT / "deploy/systemd/dehps-prediction-v2-shadow-pre-draw.timer").read_text(encoding="utf-8")
    draw_service = (ROOT / "deploy/systemd/dehps-draw-sync.service").read_text(encoding="utf-8")
    assert "run_prediction_v2_shadow_issue.py pre --apply --send" in pre_service
    assert "Tue,Thu,Sun" in pre_timer
    assert "--prediction-v2-shadow-notifications" in draw_service
    assert "systemctl" not in pre_service + pre_timer + draw_service
