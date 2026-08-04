from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import dehps.research_os.supervisor as supervisor_module
import pytest
from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.calibration import (
    load_calibration_manifest,
    run_p24_calibration,
)
from dehps.research_os.information_theory.resampling.contracts import (
    P24_COMPLETION_DIGEST,
    P24_EXECUTION_ID,
)
from dehps.research_os.information_theory.synthetic import (
    generate_null_dataset,
    load_synthetic_run_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    ResearchOSValidationError,
    TaskStatus,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    M4_P29_RUNTIME_AUDIT_CAPABILITY,
    M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,
    M4_P29_RUNTIME_AUDIT_TASK_KEY,
    P23_TASK_KEY,
    P24_TASK_KEY,
    P25_TASK_KEY,
    P26_CAPABILITY,
    P26_FAILED_RECOVERY_ERROR,
    P26_FAILED_RECOVERY_EVENT_DIGEST,
    P26_FAILED_RECOVERY_EXECUTION_ID,
    P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST,
    P26_PREFLIGHT_CAPABILITY,
    P26_PREFLIGHT_TASK_KEY,
    P26_REPAIR_TASK_KEY,
    P26_TASK_KEY,
    P27_TASK_KEY,
    CapabilityResult,
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
DATASET_DIGEST = "5354b9f7f6c72996cff16d6c161b03ff49922bf92589bd43b823d107019ebd86"
TEST_COMMIT = "a" * 40
TEST_CONTROL_PLANE_KEY = "m4-information-theory-mainline"


def reset_preflight_to_pending(value: dict) -> None:
    preflight = next(
        task for task in value["tasks"] if task["task_key"] == P26_PREFLIGHT_TASK_KEY
    )
    preflight["status"] = "draft"
    preflight["completion_classification"] = "INTEGRATION_PENDING"
    value["facts"]["artifacts"] = [
        fact
        for fact in value["facts"]["artifacts"]
        if not fact.startswith(
            "mainline-execution:m4-p2-measurement-identifiability-preflight:"
        )
        and fact
        != ("m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED")
    ]


def manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    value["tasks"] = [
        task
        for task in value["tasks"]
        if task["task_key"]
        not in {
            "m4-p1-repair-resampling-preregistration-contract",
            "m4-p1-repair-injected-signal-preregistration-contract",
        }
    ]
    p23 = next(
        task
        for task in value["tasks"]
        if task["task_key"] == "m4-p2-walk-forward-probe-harness"
    )
    p23["status"] = "draft"
    p23["completion_classification"] = "INTEGRATION_PENDING"
    p24 = next(
        task
        for task in value["tasks"]
        if task["task_key"] == "m4-p2-injected-signal-calibration"
    )
    p24["status"] = "draft"
    p24["completion_classification"] = "INTEGRATION_PENDING"
    p24["dependencies"] = [p24["dependencies"][0]]
    p24["input_artifact_digests"] = []
    p24["metric_contract"]["mainline_integration"][
        "ready_condition"
    ] = "P2.3 mainline execution completed"
    p24["metric_contract"]["mainline_integration"]["upstream_artifacts"] = [
        "P2.3 mainline execution artifact"
    ]
    p25 = next(task for task in value["tasks"] if task["task_key"] == P25_TASK_KEY)
    p25["status"] = "draft"
    p25["completion_classification"] = "INTEGRATION_PENDING"
    value["facts"]["artifacts"] = [
        fact
        for fact in value["facts"]["artifacts"]
        if not fact.startswith("mainline-execution:m4-p2-walk-forward-probe-harness:")
        and not fact.startswith("mainline-execution:m4-p2-injected-signal-calibration:")
        and fact
        != "m4-preregistration:a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa"
        and fact
        != "m4-preregistration:4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
        and fact
        != "m4-p2-1-synthetic-run-manifest:f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
        and not fact.startswith("mainline-execution:m4-p2-resampling:")
    ]
    reset_preflight_to_pending(value)
    return value


def source_manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    p24 = next(task for task in value["tasks"] if task["task_key"] == P24_TASK_KEY)
    p24["status"] = "draft"
    p24["completion_classification"] = "INTEGRATION_PENDING"
    p25 = next(task for task in value["tasks"] if task["task_key"] == P25_TASK_KEY)
    p25["status"] = "draft"
    p25["completion_classification"] = "INTEGRATION_PENDING"
    value["facts"]["artifacts"] = [
        fact
        for fact in value["facts"]["artifacts"]
        if not fact.startswith("mainline-execution:m4-p2-injected-signal-calibration:")
        and not fact.startswith("mainline-execution:m4-p2-resampling:")
    ]
    reset_preflight_to_pending(value)
    return value


def p25_source_manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    p25 = next(task for task in value["tasks"] if task["task_key"] == P25_TASK_KEY)
    p25["status"] = "draft"
    p25["completion_classification"] = "INTEGRATION_PENDING"
    value["facts"]["artifacts"] = [
        fact
        for fact in value["facts"]["artifacts"]
        if not fact.startswith("mainline-execution:m4-p2-resampling:")
    ]
    reset_preflight_to_pending(value)
    return value


def runtime_recovery_manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    runtime = next(
        task
        for task in value["tasks"]
        if task["task_key"] == M4_P29_RUNTIME_AUDIT_TASK_KEY
    )
    canonical_executor_event = next(
        dependency["target_key"]
        for dependency in runtime["dependencies"]
        if dependency["dependency_type"] == "external_event"
        and dependency["target_key"].startswith("m4-canonical-executor:")
    )
    runtime["status"] = "draft"
    runtime["completion_classification"] = "INTEGRATION_PENDING"
    runtime["dependencies"] = []
    value["facts"]["external_events"] = sorted(
        {
            *value["facts"]["external_events"],
            canonical_executor_event,
        }
    )
    return value


def p26_failed_manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    task = next(
        task for task in value["tasks"] if task["task_key"] == P26_TASK_KEY
    )
    task["status"] = "failed"
    task["completion_classification"] = "INTEGRATED"
    return value


class MemoryMainlineRepository:
    def __init__(self, payload: dict) -> None:
        self.control_plane = ResearchOSControlPlane()
        self.manifest = ControlPlaneManifest.from_dict(payload)
        self.events: list[dict] = []
        self.artifacts: list[dict] = []
        self.fail_completed_import_once = False
        self.fail_registration_after: int | None = None
        self.registration_failure_triggered = False

    def ensure_schema(self) -> None:
        return None

    def load_manifest(self, *, control_plane_key: str) -> ControlPlaneManifest:
        assert control_plane_key == TEST_CONTROL_PLANE_KEY
        return self.manifest

    def import_manifest(self, *, control_plane_key: str, payload: dict, source: str):
        assert control_plane_key == TEST_CONTROL_PLANE_KEY
        assert source.startswith("research-evidence-supervisor")
        if (
            source == "research-evidence-supervisor-completed"
            and self.fail_completed_import_once
        ):
            self.fail_completed_import_once = False
            raise RuntimeError("simulated crash before completion projection")
        self.manifest = ControlPlaneManifest.from_dict(payload)
        snapshot = self.control_plane.resolve(self.manifest)
        return SimpleNamespace(
            manifest_digest=self.manifest.artifact_digest,
            snapshot_digest=snapshot.snapshot_digest,
        )

    def record_mainline_execution_event(self, *, event) -> bool:
        payload = {
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
        if any(item["event_digest"] == event.artifact_digest for item in self.events):
            return False
        self.events.append(payload)
        return True

    def register_mainline_artifact(self, *, registration) -> bool:
        if (
            self.fail_registration_after is not None
            and not self.registration_failure_triggered
            and len(self.artifacts) >= self.fail_registration_after
        ):
            self.registration_failure_triggered = True
            raise RuntimeError("simulated crash during artifact registration")
        payload = {
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
        if any(
            item["registration_digest"] == registration.registration_digest
            for item in self.artifacts
        ):
            return False
        self.artifacts.append(payload)
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


class _ProjectedCapability:
    def __init__(
        self,
        *,
        root: Path,
        task_key: str,
        summary: dict,
        completion_facts: tuple[str, ...] = (),
    ) -> None:
        self.root = root
        self.task_key = task_key
        self.summary = summary
        self.completion_facts = completion_facts

    def execute(
        self,
        *,
        control_plane_key: str,
        task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        assert task.task_key == self.task_key
        path = (
            self.root
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
            / "execution.json"
        )
        payload = {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": "",
            "execution_id": execution_id,
            "control_plane_key": control_plane_key,
            "goal_key": task.goal_key,
            "task_key": task.task_key,
            "task_digest": task.artifact_digest,
            "capability": task.requested_capability,
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "input_artifact_digests": list(task.input_artifact_digests),
            "actual_fold_count": self.summary.get("actual_fold_count", 0),
            "registered_artifact_count": 1,
            "git_commit": git_commit,
            "working_tree_clean": True,
            "parent_digests": list(task.input_artifact_digests),
            **self.summary,
        }
        identity = dict(payload)
        identity.pop("artifact_digest")
        payload["artifact_digest"] = canonical_digest(
            identity,
            domain="dehps.research-os.mainline-execution.v1",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        registration = MainlineArtifactRegistration(
            execution_id=execution_id,
            control_plane_key=control_plane_key,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            artifact_digest=payload["artifact_digest"],
            artifact_type=payload["artifact_type"],
            schema_version=payload["schema_version"],
            artifact_path=str(path.relative_to(self.root)),
            parent_digests=tuple(payload["parent_digests"]),
            git_commit=git_commit,
        )
        return CapabilityResult(
            execution_artifact=payload,
            execution_artifact_path=path,
            registrations=(registration,),
            completion_facts=self.completion_facts,
        )


class _CommitMarkerRecoveryCapability:
    def __init__(self, *, root: Path) -> None:
        self.root = root
        self.timed_runs = 0

    def execute(
        self,
        *,
        control_plane_key: str,
        task,
        execution_id: str,
        git_commit: str,
    ) -> CapabilityResult:
        task_dir = (
            self.root
            / "runtime/research-os/mainline/tasks"
            / task.task_key
            / execution_id
        )
        execution_path = task_dir / "execution.json"
        child_payload = {
            "schema_version": "dehps-test-runtime-child.v1",
            "artifact_type": "test_runtime_child",
            "artifact_digest": "1" * 64,
            "parent_digests": list(task.input_artifact_digests),
        }
        child_path = task_dir / "artifacts/test-child/child.json"
        if execution_path.is_file():
            execution_payload = json.loads(execution_path.read_text(encoding="utf-8"))
        else:
            self.timed_runs += 1
            child_path.parent.mkdir(parents=True, exist_ok=True)
            child_path.write_text(
                json.dumps(child_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            execution_payload = {
                "schema_version": "dehps-research-os-mainline-execution.v1",
                "artifact_type": "research_os_mainline_execution",
                "artifact_digest": "",
                "execution_id": execution_id,
                "control_plane_key": control_plane_key,
                "goal_key": task.goal_key,
                "task_key": task.task_key,
                "task_digest": task.artifact_digest,
                "capability": task.requested_capability,
                "status": "COMPLETE",
                "completion_classification": "VALIDATED_IN_MAINLINE",
                "input_artifact_digests": list(task.input_artifact_digests),
                "actual_fold_count": 61,
                "audited_fold_count": 61,
                "correctness_replay_fold_count": 61,
                "total_execution_fold_count": 122,
                "correctness_boundary_snapshot_count": 45,
                "registered_artifact_count": 2,
                "runtime_benchmark_attempt_artifact_digest": "2" * 64,
                "source_integrity_attestation_artifact_digest": "3" * 64,
                "golden_source_integrity_attestation_artifact_digest": "4" * 64,
                "benchmark_attempt_id": "5" * 64,
                "reference_evaluator_is_oracle": False,
                "immutable_golden_fixture_is_oracle": True,
                "acceleration_boundary_independent": True,
                "acceleration_boundary_independence_scope": (
                    "literal_behavior_path_and_fresh_import_closure"
                ),
                "oracle_construction_process_isolated": False,
                "oracle_construction_fully_implementation_independent": False,
                "exact_golden_replay_verified": True,
                "journal_reused": False,
                "fresh_workdir": True,
                "shared_frozen_source_modified": False,
                "backend_source_modified": False,
                "acceleration_changed_paths": [],
                "backend_optimization_applied": False,
                "statistical_semantics_modified": False,
                "historical_outcomes_read": False,
                "evidence_progress_before": 0,
                "evidence_progress_after": 0,
                "production_action": "none",
                "git_commit": git_commit,
                "working_tree_clean": True,
                "parent_digests": [
                    *task.input_artifact_digests,
                    child_payload["artifact_digest"],
                ],
            }
            execution_payload["artifact_digest"] = canonical_digest(
                {
                    key: value
                    for key, value in execution_payload.items()
                    if key != "artifact_digest"
                },
                domain="dehps.research-os.mainline-execution.v1",
            )
            execution_path.parent.mkdir(parents=True, exist_ok=True)
            execution_path.write_text(
                json.dumps(execution_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        registrations = tuple(
            MainlineArtifactRegistration(
                execution_id=execution_id,
                control_plane_key=control_plane_key,
                task_key=task.task_key,
                task_digest=task.artifact_digest,
                artifact_digest=str(payload["artifact_digest"]),
                artifact_type=str(payload["artifact_type"]),
                schema_version=str(payload["schema_version"]),
                artifact_path=str(path.relative_to(self.root)),
                parent_digests=tuple(payload.get("parent_digests", ())),
                git_commit=git_commit,
            )
            for path, payload in (
                (child_path, child_payload),
                (execution_path, execution_payload),
            )
        )
        return CapabilityResult(
            execution_artifact=execution_payload,
            execution_artifact_path=execution_path,
            registrations=registrations,
            completion_facts=(M4_P29_RUNTIME_AUDIT_COMPLETION_FACT,),
        )


def prepare_root(tmp_path: Path) -> Path:
    for relative in (
        "configs/research-os/m4-information-theory-metric-kernel-v1.json",
        "configs/research-os/m4-information-theory-walk-forward-harness-v1.json",
        (
            "configs/research-os/"
            "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
        ),
        ("configs/research-os/m4-information-theory-p2-5-resampling-kernel-v1.json"),
        ("configs/research-os/m4-information-theory-preregistration-v1.0.3.json"),
        (
            "configs/research-os/"
            "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
        ),
        (
            "configs/research-os/"
            "m4-information-theory-p2-6-measurement-validation-v1.json"
        ),
        (
            "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-contract-repair-v1.json"
        ),
        (
            "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        ),
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    dataset_destination = (
        tmp_path
        / "runtime/research-os/information-theory/synthetic"
        / DATASET_DIGEST
        / "dataset.json"
    )
    dataset_destination.parent.mkdir(parents=True, exist_ok=True)
    dataset = generate_null_dataset(
        load_synthetic_run_manifest(
            ROOT
            / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.json"
        ),
        scale_id="FORWARD_61",
        seed=200000,
    ).to_dict()
    assert dataset["artifact_digest"] == DATASET_DIGEST
    dataset_destination.write_text(
        json.dumps(dataset, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return tmp_path


def prepare_formal_p24_artifacts(root: Path) -> None:
    task_dir = (
        root / "runtime/research-os/mainline/tasks" / P24_TASK_KEY / P24_EXECUTION_ID
    )
    run = run_p24_calibration(
        manifest=load_calibration_manifest(
            root / "configs/research-os/"
            "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
        ),
        harness_path=(
            root / "configs/research-os/"
            "m4-information-theory-walk-forward-harness-v1.json"
        ),
        output_dir=task_dir / "artifacts",
        execution_id=P24_EXECUTION_ID,
        git_commit="675ebbe5ded2f68f9cd73a5086024b359c94e835",
    )
    assert run.completion_artifact["artifact_digest"] == P24_COMPLETION_DIGEST
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "execution.json").write_text(
        json.dumps(
            {
                "execution_id": P24_EXECUTION_ID,
                "status": "COMPLETE",
                "completion_artifact_digest": P24_COMPLETION_DIGEST,
                "truth_artifact_digests": [
                    item["artifact_digest"] for item in run.truth_artifacts
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_p2_3_is_integration_pending_and_ready_before_mainline_execution() -> None:
    manifest = ControlPlaneManifest.from_dict(manifest_payload())
    snapshot = ResearchOSControlPlane().resolve(manifest)
    states = {item.task_key: item.status for item in snapshot.resolutions}

    assert [
        item.task_key
        for item in snapshot.ready_queue
        if item.goal_key == "M4_INFORMATION_THEORY_EVIDENCE"
    ] == [P23_TASK_KEY]
    assert states[P23_TASK_KEY] is TaskStatus.READY
    assert states["m4-p2-injected-signal-calibration"] is TaskStatus.DEPENDENCY_WAIT
    task = next(item for item in manifest.tasks if item.task_key == P23_TASK_KEY)
    state = manifest.task_state_by_digest[task.artifact_digest]
    assert state.completion_classification.value == "INTEGRATION_PENDING"


def test_completed_executable_task_without_mainline_fact_fails_closed() -> None:
    payload = manifest_payload()
    task = next(item for item in payload["tasks"] if item["task_key"] == P23_TASK_KEY)
    task["status"] = "completed"
    task["completion_classification"] = "COMPLETE"

    with pytest.raises(
        ResearchOSValidationError,
        match="requires exactly one immutable successful mainline execution fact",
    ):
        ResearchOSControlPlane().resolve(ControlPlaneManifest.from_dict(payload))


def test_repository_requires_physical_execution_and_artifact_records() -> None:
    payload = manifest_payload()
    initial = ControlPlaneManifest.from_dict(payload)
    task = next(item for item in initial.tasks if item.task_key == P23_TASK_KEY)
    raw_task = next(
        item for item in payload["tasks"] if item["task_key"] == P23_TASK_KEY
    )
    raw_task["status"] = "completed"
    raw_task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].append(
        mainline_completion_fact(task=task, execution_id="b" * 64)
    )
    completed = ControlPlaneManifest.from_dict(payload)
    ResearchOSControlPlane().resolve(completed)

    class MissingCursor:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return None

    with pytest.raises(
        ResearchOSValidationError,
        match="has no immutable completed mainline execution event",
    ):
        PostgresResearchOSRepository._verify_mainline_completion_records(
            MissingCursor(),
            control_plane_key=TEST_CONTROL_PLANE_KEY,
            manifest=completed,
        )


def test_repository_forbids_reimport_regression_after_mainline_completion() -> None:
    manifest = ControlPlaneManifest.from_dict(manifest_payload())
    task = next(item for item in manifest.tasks if item.task_key == P23_TASK_KEY)

    class CompletedCursor:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return {
                "declared_status": "completed",
                "completion_classification": "COMPLETE",
            }

    with pytest.raises(
        ResearchOSValidationError,
        match="mainline completion regression forbidden",
    ):
        PostgresResearchOSRepository._verify_no_mainline_completion_regression(
            CompletedCursor(),
            control_plane_key=TEST_CONTROL_PLANE_KEY,
            manifest=manifest,
            previous_tasks={task.task_key: task.artifact_digest},
        )


def test_supervisor_executes_p2_3_updates_status_unlocks_p2_4_and_replays(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(manifest_payload())
    root = prepare_root(tmp_path)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        now=lambda: datetime(2026, 7, 25, 8, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    result = supervisor.run_once()
    snapshot = repository.control_plane.resolve(repository.manifest)
    states = {item.task_key: item.status for item in snapshot.resolutions}
    replay = supervisor.replay(task_key=P23_TASK_KEY)

    assert result["status"] == "COMPLETE"
    assert result["completion_classification"] == "VALIDATED_IN_MAINLINE"
    assert result["actual_fold_count"] == 4
    assert result["registered_artifact_count"] >= 17
    assert result["engineering_progress_percent"] == 30
    assert result["evidence_progress_percent"] == 0
    assert result["next_ready_task"] == "m4-p2-injected-signal-calibration"
    assert states[P23_TASK_KEY] is TaskStatus.COMPLETED
    assert [
        item.task_key
        for item in snapshot.ready_queue
        if item.goal_key == "M4_INFORMATION_THEORY_EVIDENCE"
    ] == ["m4-p2-injected-signal-calibration"]
    assert [item["event_type"] for item in repository.events] == [
        "started",
        "completed",
    ]
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["execution_id"] == result["execution_id"]
    assert replay["execution_artifact_digest"] == result["execution_artifact_digest"]
    assert replay["manual_input_assembly"] is False
    assert replay["registered_artifact_count"] == result["registered_artifact_count"]
    assert (root / "runtime/logs/m4-information-theory-status.json").is_file()


def test_supervisor_resumes_after_completed_event_before_status_projection(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(manifest_payload())
    repository.fail_completed_import_once = True
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=prepare_root(tmp_path),
        now=lambda: datetime(2026, 7, 25, 8, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    with pytest.raises(RuntimeError, match="simulated crash"):
        supervisor.run_once()
    task = next(
        item for item in repository.manifest.tasks if item.task_key == P23_TASK_KEY
    )
    assert (
        repository.manifest.task_state_by_digest[task.artifact_digest].declared_status
        is TaskStatus.RUNNING
    )
    assert [item["event_type"] for item in repository.events] == [
        "started",
        "completed",
    ]

    resumed = supervisor.run_once()
    snapshot = repository.control_plane.resolve(repository.manifest)

    assert resumed["status"] == "COMPLETE"
    assert resumed["actual_fold_count"] == 4
    assert [item["event_type"] for item in repository.events] == [
        "started",
        "completed",
    ]
    assert [
        item.task_key
        for item in snapshot.ready_queue
        if item.goal_key == "M4_INFORMATION_THEORY_EVIDENCE"
    ] == ["m4-p2-injected-signal-calibration"]


def test_supervisor_rejects_stale_completed_event_manifest_on_resume(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(manifest_payload())
    repository.fail_completed_import_once = True
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=prepare_root(tmp_path),
        now=lambda: datetime(2026, 7, 25, 8, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    with pytest.raises(RuntimeError, match="simulated crash"):
        supervisor.run_once()
    stale_event_manifest_digest = repository.manifest.artifact_digest
    evolved = repository.manifest.to_dict(include_digest=False)
    evolved["facts"]["external_events"].append(
        "test-only:manifest-evolved-after-completed-event"
    )
    repository.manifest = ControlPlaneManifest.from_dict(evolved)
    assert repository.manifest.artifact_digest != stale_event_manifest_digest

    with pytest.raises(
        MainlineSupervisorError,
        match="mainline parent event provenance changed",
    ):
        supervisor.run_once()


def test_supervisor_recovers_only_pinned_p26_pre_dispatch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = p26_failed_manifest_payload()
    monkeypatch.setenv(
        supervisor_module.P26_FAILED_RECOVERY_EVENT_ENV,
        P26_FAILED_RECOVERY_EVENT_DIGEST,
    )
    repository = MemoryMainlineRepository(payload)
    task = next(
        item for item in repository.manifest.tasks if item.task_key == P26_TASK_KEY
    )
    started = MainlineExecutionEvent(
        execution_id=P26_FAILED_RECOVERY_EXECUTION_ID,
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        manifest_digest=P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST,
        task_key=P26_TASK_KEY,
        task_digest=task.artifact_digest,
        capability=P26_CAPABILITY,
        event_type="started",
        sequence=0,
        recorded_at="2026-07-31T08:10:59.912185+00:00",
        payload=(
            ("input_artifact_digests", list(task.input_artifact_digests)),
            ("git_commit", "e6dedaf9c835672a5e17007653ee6e8fe55b67d9"),
        ),
    )
    failed = MainlineExecutionEvent(
        execution_id=P26_FAILED_RECOVERY_EXECUTION_ID,
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        manifest_digest=P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST,
        task_key=P26_TASK_KEY,
        task_digest=task.artifact_digest,
        capability=P26_CAPABILITY,
        event_type="failed",
        sequence=1,
        recorded_at="2026-08-04T09:23:06.717682+00:00",
        payload=(
            ("error", P26_FAILED_RECOVERY_ERROR),
            ("git_commit", "e6dedaf9c835672a5e17007653ee6e8fe55b67d9"),
        ),
    )
    assert failed.artifact_digest == P26_FAILED_RECOVERY_EVENT_DIGEST
    repository.record_mainline_execution_event(event=started)
    repository.record_mainline_execution_event(event=failed)
    original_import = repository.import_manifest

    def import_with_production_running_digest(
        *, control_plane_key: str, payload: dict, source: str
    ):
        result = original_import(
            control_plane_key=control_plane_key,
            payload=payload,
            source=source,
        )
        if source.endswith("recoverable-pre-dispatch-failure"):
            return SimpleNamespace(
                manifest_digest=P26_FAILED_RECOVERY_RUNNING_MANIFEST_DIGEST,
                snapshot_digest=result.snapshot_digest,
            )
        return result

    monkeypatch.setattr(repository, "import_manifest", import_with_production_running_digest)
    root = prepare_root(tmp_path)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        now=lambda: datetime(2026, 8, 4, 10, 0, tzinfo=timezone.utc),
        git_commit="e6dedaf9c835672a5e17007653ee6e8fe55b67d9",
        require_clean_tree=False,
    )
    supervisor.capabilities[P26_CAPABILITY] = _ProjectedCapability(
        root=root,
        task_key=P26_TASK_KEY,
        summary={"actual_fold_count": 61},
    )
    monkeypatch.setattr(
        supervisor,
        "_record_p26_failed_recovery",
        lambda **_: {"artifact_digest": "9" * 64},
    )

    result = supervisor.run_once(task_key=P26_TASK_KEY)
    completed_task = next(
        item for item in repository.manifest.tasks if item.task_key == P26_TASK_KEY
    )

    assert result["status"] == "COMPLETE"
    assert [event["event_type"] for event in repository.events] == [
        "started",
        "failed",
        "completed",
    ]
    assert repository.events[-1]["sequence"] == 2
    assert repository.events[-1]["execution_id"] == P26_FAILED_RECOVERY_EXECUTION_ID
    assert (
        repository.manifest.task_state_by_digest[
            completed_task.artifact_digest
        ].declared_status
        is TaskStatus.COMPLETED
    )


def test_supervisor_rejects_wrong_p26_failed_recovery_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = p26_failed_manifest_payload()
    repository = MemoryMainlineRepository(payload)
    task = next(
        item for item in repository.manifest.tasks if item.task_key == P26_TASK_KEY
    )
    repository.events.append(
        {
            "event_digest": P26_FAILED_RECOVERY_EVENT_DIGEST,
            "execution_id": P26_FAILED_RECOVERY_EXECUTION_ID,
            "control_plane_key": TEST_CONTROL_PLANE_KEY,
            "manifest_digest": "2" * 64,
            "task_key": P26_TASK_KEY,
            "task_digest": task.artifact_digest,
            "capability": P26_CAPABILITY,
            "event_type": "failed",
            "sequence": 1,
            "recorded_at": "2026-08-04T09:23:06+00:00",
            "payload": [["error", P26_FAILED_RECOVERY_ERROR]],
        }
    )
    monkeypatch.setenv(supervisor_module.P26_FAILED_RECOVERY_EVENT_ENV, "f" * 64)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=prepare_root(tmp_path),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    with pytest.raises(
        MainlineSupervisorError,
        match="authorization does not match the incident",
    ):
        supervisor.run_once(task_key=P26_TASK_KEY)


def test_p26_failed_recovery_artifact_requires_and_binds_preserved_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = prepare_root(tmp_path)
    manifest = ControlPlaneManifest.from_dict(p26_failed_manifest_payload())
    task = next(item for item in manifest.tasks if item.task_key == P26_TASK_KEY)
    contract = json.loads(
        (
            root
            / "configs/research-os/"
            "m4-information-theory-p2-6-1-measurement-validation-v1.json"
        ).read_text(encoding="utf-8")
    )
    repair_root = (
        root
        / "runtime/research-os/mainline/tasks/"
        "m4-p2-repair-measurement-system/test-repair/artifacts/truth"
    )
    for truth in contract["truth_artifacts"]:
        path = repair_root / truth["artifact_digest"] / "truth.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "artifact_digest": truth["artifact_digest"],
                    "artifact_type": "repaired_marginal_truth",
                    "measurement_repair_manifest_digest": task.input_artifact_digests[
                        0
                    ],
                    "truth_estimand": (
                        "sum_number_event_mutual_information_with_prior_state"
                    ),
                    "scenario_id": truth["scenario_id"],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    task_dir = (
        root
        / "runtime/research-os/mainline/tasks"
        / P26_TASK_KEY
        / P26_FAILED_RECOVERY_EXECUTION_ID
    )
    for path in (
        task_dir / "artifacts/checkpoint-journals",
        task_dir / "artifacts/replicates",
    ):
        path.mkdir(parents=True, exist_ok=True)
    (task_dir / "artifacts/checkpoint-journals/preserved.jsonl").write_text(
        "{}\n", encoding="utf-8"
    )
    (task_dir / "artifacts/replicates/preserved.json").write_text(
        "{}\n", encoding="utf-8"
    )
    coordinator = task_dir / "artifacts/coordinator-state.json"
    coordinator.write_text(
        json.dumps(
            {
                "schema_version": "dehps-m4-p2-analysis-coordinator-state.v1",
                "parent_execution_id": P26_FAILED_RECOVERY_EXECUTION_ID,
                "measurement_validation_manifest_digest": contract[
                    "artifact_digest"
                ],
                "total_replicates": 31_000,
                "status": "RUNNING",
                "failed_replicates": 0,
                "result_selection_used": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report = root / "docs/experiments/p26-recovery-test.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("result-blind incident recovery\n", encoding="utf-8")
    monkeypatch.setenv(
        supervisor_module.P26_FAILED_RECOVERY_REPORT_ENV,
        str(report.relative_to(root)),
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=MemoryMainlineRepository(p26_failed_manifest_payload()),  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    recovered = supervisor._record_p26_failed_recovery(
        task=task,
        execution_id=P26_FAILED_RECOVERY_EXECUTION_ID,
        failed_event={"event_digest": P26_FAILED_RECOVERY_EVENT_DIGEST},
        runtime_git_commit=TEST_COMMIT,
    )
    replayed = supervisor._record_p26_failed_recovery(
        task=task,
        execution_id=P26_FAILED_RECOVERY_EXECUTION_ID,
        failed_event={"event_digest": P26_FAILED_RECOVERY_EVENT_DIGEST},
        runtime_git_commit=TEST_COMMIT,
    )

    assert replayed == recovered
    assert recovered["repaired_truth_count"] == 12
    assert recovered["failed_event_digest"] == P26_FAILED_RECOVERY_EVENT_DIGEST
    assert recovered["next_terminal_sequence"] == 2
    assert recovered["statistical_results_read"] is False
    recovery_path = (
        task_dir
        / "incident-recoveries"
        / recovered["artifact_digest"]
        / "recovery.json"
    )
    assert json.loads(recovery_path.read_text(encoding="utf-8")) == recovered


def test_runtime_commit_marker_recovers_after_partial_registration_without_rerun(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(runtime_recovery_manifest_payload())
    repository.fail_registration_after = 1
    root = prepare_root(tmp_path)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        now=lambda: datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )
    capability = _CommitMarkerRecoveryCapability(root=root)
    supervisor.capabilities[M4_P29_RUNTIME_AUDIT_CAPABILITY] = capability

    with pytest.raises(
        RuntimeError,
        match="simulated crash during artifact registration",
    ):
        supervisor.run_once(task_key=M4_P29_RUNTIME_AUDIT_TASK_KEY)

    runtime_task = next(
        task
        for task in repository.manifest.tasks
        if task.task_key == M4_P29_RUNTIME_AUDIT_TASK_KEY
    )
    state = json.loads(supervisor.state_path.read_text(encoding="utf-8"))
    assert capability.timed_runs == 1
    assert len(repository.artifacts) == 1
    assert [event["event_type"] for event in repository.events] == ["started"]
    assert (
        repository.manifest.task_state_by_digest[
            runtime_task.artifact_digest
        ].declared_status
        is TaskStatus.RUNNING
    )
    assert state["status"] == "RECOVERY_REQUIRED"
    assert state["task_key"] == M4_P29_RUNTIME_AUDIT_TASK_KEY
    assert state["commit_marker_path"].endswith("/execution.json")

    resumed = supervisor.run_once(task_key=M4_P29_RUNTIME_AUDIT_TASK_KEY)
    completed_task = next(
        task
        for task in repository.manifest.tasks
        if task.task_key == M4_P29_RUNTIME_AUDIT_TASK_KEY
    )
    assert resumed["status"] == "COMPLETE"
    assert capability.timed_runs == 1
    assert len(repository.artifacts) == 2
    assert [event["event_type"] for event in repository.events] == [
        "started",
        "completed",
    ]
    assert (
        repository.manifest.task_state_by_digest[
            completed_task.artifact_digest
        ].declared_status
        is TaskStatus.COMPLETED
    )


def test_revised_p2_6_definition_cannot_resume_superseded_execution(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(p25_source_manifest_payload())
    root = prepare_root(tmp_path)
    prepare_formal_p24_artifacts(root)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        now=lambda: datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )
    supervisor.run_once()
    snapshot = repository.control_plane.resolve(repository.manifest)
    states = {item.task_key: item.status for item in snapshot.resolutions}
    task = next(
        item for item in repository.manifest.tasks if item.task_key == P26_TASK_KEY
    )

    assert task.artifact_digest != (
        "975a8e0bf859bad1e7f5f33411471878dd731134ee1f3b81948bd8c8503dc4c0"
    )
    assert task.requested_capability == "m4_p2_6_1_false_positive_and_power"
    assert states[P26_PREFLIGHT_TASK_KEY] is TaskStatus.READY
    assert states[P26_TASK_KEY] is TaskStatus.DEPENDENCY_WAIT
    assert not any(item["task_key"] == P26_TASK_KEY for item in repository.events)


def test_supervisor_executes_p2_4_unlocks_p2_5_and_replays(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(source_manifest_payload())
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=prepare_root(tmp_path),
        now=lambda: datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    result = supervisor.run_once()
    snapshot = repository.control_plane.resolve(repository.manifest)
    states = {item.task_key: item.status for item in snapshot.resolutions}
    replay = supervisor.replay(task_key=P24_TASK_KEY)
    event_count = len(repository.events)
    artifact_count = len(repository.artifacts)

    assert result["status"] == "COMPLETE"
    assert result["completion_classification"] == "VALIDATED_IN_MAINLINE"
    assert result["actual_fold_count"] == 8
    assert result["truth_artifact_count"] == 12
    assert result["engineering_progress_percent"] == 34
    assert result["evidence_progress_percent"] == 0
    assert result["next_ready_task"] == "m4-p2-resampling"
    assert result["registered_artifact_count"] >= 40
    assert states[P24_TASK_KEY] is TaskStatus.COMPLETED
    assert states["m4-p2-resampling"] is TaskStatus.READY
    assert [
        item.task_key
        for item in snapshot.ready_queue
        if item.goal_key == "M4_INFORMATION_THEORY_EVIDENCE"
    ] == ["m4-p2-resampling"]
    assert [item["event_type"] for item in repository.events] == [
        "started",
        "completed",
    ]
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["execution_id"] == result["execution_id"]
    assert replay["execution_artifact_digest"] == result["execution_artifact_digest"]
    assert replay["registered_artifact_count"] == result["registered_artifact_count"]
    assert len(repository.events) == event_count
    assert len(repository.artifacts) == artifact_count


def test_supervisor_executes_p2_5_unlocks_identifiability_preflight_and_replays(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(p25_source_manifest_payload())
    root = prepare_root(tmp_path)
    prepare_formal_p24_artifacts(root)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        now=lambda: datetime(2026, 7, 27, 9, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )

    result = supervisor.run_once()
    snapshot = repository.control_plane.resolve(repository.manifest)
    states = {item.task_key: item.status for item in snapshot.resolutions}
    replay = supervisor.replay(task_key=P25_TASK_KEY)

    assert result["status"] == "COMPLETE"
    assert result["completion_classification"] == "VALIDATED_IN_MAINLINE"
    assert result["actual_fold_count"] == 0
    assert result["replicate_count"] == 22
    assert result["aggregate_count"] == 9
    assert result["engineering_progress_percent"] == 37
    assert result["evidence_progress_percent"] == 0
    assert result["next_ready_task"] == P26_PREFLIGHT_TASK_KEY
    assert result["eligible_for_formal_inference"] is False
    assert states[P25_TASK_KEY] is TaskStatus.COMPLETED
    assert states[P26_PREFLIGHT_TASK_KEY] is TaskStatus.READY
    assert states[P26_TASK_KEY] is TaskStatus.DEPENDENCY_WAIT
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["manual_input_assembly"] is False
    assert replay["registered_artifact_count"] == result["registered_artifact_count"]
    assert [item["event_type"] for item in repository.events] == [
        "started",
        "completed",
    ]


def test_supervisor_projects_preflight_and_fail_closed_repair_branch_with_replay(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(p25_source_manifest_payload())
    root = prepare_root(tmp_path)
    prepare_formal_p24_artifacts(root)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key=TEST_CONTROL_PLANE_KEY,
        root_dir=root,
        now=lambda: datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc),
        git_commit=TEST_COMMIT,
        require_clean_tree=False,
    )
    supervisor.run_once()
    repair_fact = "m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
    supervisor.capabilities[P26_PREFLIGHT_CAPABILITY] = _ProjectedCapability(
        root=root,
        task_key=P26_PREFLIGHT_TASK_KEY,
        summary={
            "actual_fold_count": 0,
            "identifiability_preflight_manifest_digest": "9" * 64,
            "identifiability_preflight_report_digest": "8" * 64,
            "superseded_run_archive_digest": "7" * 64,
            "decision": "MEASUREMENT_CONTRACT_REPAIR_REQUIRED",
            "decision_fact": repair_fact,
            "failed_requirements": [
                "NOT_IDENTIFIABLE_BY_CURRENT_METRIC",
                "STATE_NOT_EXPOSED_TO_PROBE",
                "TRUTH_METRIC_ESTIMAND_MISMATCH",
            ],
            "scenario_count": 12,
            "p2_6_partial_statistical_results_inspected": False,
            "old_p2_6_execution_resumable": False,
            "replay_status": "DETERMINISTIC",
        },
        completion_facts=(repair_fact,),
    )
    preflight = supervisor.run_once()
    snapshot = repository.control_plane.resolve(repository.manifest)
    states = {item.task_key: item.status for item in snapshot.resolutions}
    replay = supervisor.replay(task_key=P26_PREFLIGHT_TASK_KEY)

    assert preflight["status"] == "COMPLETE"
    assert preflight["next_ready_task"] == "m4-p2-repair-measurement-system"
    assert preflight["engineering_progress_percent"] == 38
    assert preflight["evidence_progress_percent"] == 0
    assert states[P26_PREFLIGHT_TASK_KEY] is TaskStatus.COMPLETED
    assert states[P26_TASK_KEY] is TaskStatus.DEPENDENCY_WAIT
    assert states[P27_TASK_KEY] is TaskStatus.DEPENDENCY_WAIT
    assert states["m4-p2-repair-measurement-system"] is TaskStatus.READY
    assert states["m4-p3-strict-historical-walk-forward"] is not TaskStatus.READY
    assert repair_fact in repository.manifest.facts.artifacts
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["execution_id"] == preflight["execution_id"]

    repair = supervisor.run_once()
    repair_replay = supervisor.replay(task_key=P26_REPAIR_TASK_KEY)
    projected = json.loads(
        (root / "runtime/logs/m4-information-theory-status.json").read_text(
            encoding="utf-8"
        )
    )
    assert repair["status"] == "COMPLETE"
    assert repair["next_ready_task"] == P26_TASK_KEY
    assert repair["engineering_progress_percent"] == 40
    assert repair["evidence_progress_percent"] == 0
    assert repair["old_p2_6_partial_statistical_results_inspected"] is False
    assert repair["outer_fold_fit_count_before"] == 46
    assert repair["outer_fold_fit_count_after"] == 4
    assert repair_replay["status"] == "REPLAY_VERIFIED"
    assert repair_replay["capability_replay"]["status"] == "REPLAY_VERIFIED"
    assert projected["synthetic_validation"] == "P2.6.1_REPAIRED_CONTRACT_READY"
    assert projected["current_state"] == "RUNNING"
    assert projected["p2_subphase"]["current"] == "M4-P2.6.1"
    assert projected["mainline_integration"]["task_key"] == P26_REPAIR_TASK_KEY
    assert projected["current_statistics"]["power"] == "NOT_EVALUATED"
    assert projected["current_statistics"]["runtime_progress_path"] is None
