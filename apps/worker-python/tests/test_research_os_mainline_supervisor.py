from __future__ import annotations

import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.synthetic import (
    generate_null_dataset,
    load_synthetic_run_manifest,
)
from dehps.research_os.information_theory.calibration import (
    load_calibration_manifest,
    run_p24_calibration,
)
from dehps.research_os.information_theory.resampling.contracts import (
    P24_COMPLETION_DIGEST,
    P24_EXECUTION_ID,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    ControlPlaneManifest,
    ResearchOSValidationError,
    TaskStatus,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    P23_TASK_KEY,
    P24_TASK_KEY,
    P25_TASK_KEY,
    ResearchEvidenceSupervisor,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
DATASET_DIGEST = "5354b9f7f6c72996cff16d6c161b03ff49922bf92589bd43b823d107019ebd86"
TEST_COMMIT = "a" * 40


def manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    value["tasks"] = [
        task
        for task in value["tasks"]
        if task["task_key"] not in {
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
    p24["metric_contract"]["mainline_integration"]["ready_condition"] = (
        "P2.3 mainline execution completed"
    )
    p24["metric_contract"]["mainline_integration"]["upstream_artifacts"] = [
        "P2.3 mainline execution artifact"
    ]
    value["facts"]["artifacts"] = [
        fact
        for fact in value["facts"]["artifacts"]
        if not fact.startswith("mainline-execution:m4-p2-walk-forward-probe-harness:")
        and not fact.startswith(
            "mainline-execution:m4-p2-injected-signal-calibration:"
        )
        and fact
        != "m4-preregistration:a8da6bf2404d3bf213ac74d331917d5308195b7c3174b002378e1bbd849f6dfa"
        and fact
        != "m4-preregistration:4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
        and fact
        != "m4-p2-1-synthetic-run-manifest:f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c"
    ]
    return value


def source_manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    p24 = next(
        task
        for task in value["tasks"]
        if task["task_key"] == P24_TASK_KEY
    )
    p24["status"] = "draft"
    p24["completion_classification"] = "INTEGRATION_PENDING"
    value["facts"]["artifacts"] = [
        fact
        for fact in value["facts"]["artifacts"]
        if not fact.startswith(
            "mainline-execution:m4-p2-injected-signal-calibration:"
        )
    ]
    return value


def p25_source_manifest_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value.pop("manifest_digest", None)
    return value


class MemoryMainlineRepository:
    def __init__(self, payload: dict) -> None:
        self.control_plane = ResearchOSControlPlane()
        self.manifest = ControlPlaneManifest.from_dict(payload)
        self.events: list[dict] = []
        self.artifacts: list[dict] = []
        self.fail_completed_import_once = False

    def ensure_schema(self) -> None:
        return None

    def load_manifest(self, *, control_plane_key: str) -> ControlPlaneManifest:
        assert control_plane_key == "test-mainline"
        return self.manifest

    def import_manifest(self, *, control_plane_key: str, payload: dict, source: str):
        assert control_plane_key == "test-mainline"
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
            **{
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
            },
        }
        if any(item["event_digest"] == event.artifact_digest for item in self.events):
            return False
        self.events.append(payload)
        return True

    def register_mainline_artifact(self, *, registration) -> bool:
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


def prepare_root(tmp_path: Path) -> Path:
    for relative in (
        "configs/research-os/m4-information-theory-metric-kernel-v1.json",
        "configs/research-os/m4-information-theory-walk-forward-harness-v1.json",
        (
            "configs/research-os/"
            "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
        ),
        (
            "configs/research-os/"
            "m4-information-theory-p2-5-resampling-kernel-v1.json"
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
        root
        / "runtime/research-os/mainline/tasks"
        / P24_TASK_KEY
        / P24_EXECUTION_ID
    )
    run = run_p24_calibration(
        manifest=load_calibration_manifest(
            root
            / "configs/research-os/"
            "m4-information-theory-p2-4-calibration-run-manifest-v1.json"
        ),
        harness_path=(
            root
            / "configs/research-os/"
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

    assert [item.task_key for item in snapshot.ready_queue if item.goal_key == "M4_INFORMATION_THEORY_EVIDENCE"] == [
        P23_TASK_KEY
    ]
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
    raw_task = next(item for item in payload["tasks"] if item["task_key"] == P23_TASK_KEY)
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
            control_plane_key="test-mainline",
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
            control_plane_key="test-mainline",
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
        control_plane_key="test-mainline",
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
    assert (
        replay["execution_artifact_digest"]
        == result["execution_artifact_digest"]
    )
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
        control_plane_key="test-mainline",
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


def test_supervisor_executes_p2_4_unlocks_p2_5_and_replays(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(source_manifest_payload())
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key="test-mainline",
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
    assert (
        replay["execution_artifact_digest"]
        == result["execution_artifact_digest"]
    )
    assert replay["registered_artifact_count"] == result["registered_artifact_count"]
    assert len(repository.events) == event_count
    assert len(repository.artifacts) == artifact_count


def test_supervisor_executes_p2_5_unlocks_p2_6_and_replays(
    tmp_path: Path,
) -> None:
    repository = MemoryMainlineRepository(p25_source_manifest_payload())
    root = prepare_root(tmp_path)
    prepare_formal_p24_artifacts(root)
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,  # type: ignore[arg-type]
        control_plane_key="test-mainline",
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
    assert result["next_ready_task"] == "m4-p2-false-positive-and-power-runs"
    assert result["eligible_for_formal_inference"] is False
    assert states[P25_TASK_KEY] is TaskStatus.COMPLETED
    assert states["m4-p2-false-positive-and-power-runs"] is TaskStatus.READY
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["manual_input_assembly"] is False
    assert replay["registered_artifact_count"] == result["registered_artifact_count"]
    assert [item["event_type"] for item in repository.events] == [
        "started",
        "completed",
    ]
