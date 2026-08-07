from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2.compatibility import (
    P261_FROZEN_FIXTURE_DIGEST,
    P263_SUPERSEDING_FIXTURE_DIGEST,
)
from dehps.research_os.information_theory.measurement_system_v2.superseding_slot import (
    M4_V2_DESIGN_TASK_KEY,
    P263_COMPATIBILITY_CAPABILITY,
    P263_COMPATIBILITY_TASK_KEY,
    P263_FAILED_RUNTIME_CAPABILITY,
    P263_FAILED_RUNTIME_TASK_KEY,
    P263_GOLDEN_CAPABILITY,
    P263_GOLDEN_TASK_KEY,
    P263_RUNTIME_CAPABILITY,
    P263_RUNTIME_TASK_KEY,
    P263_SLOT_ELIGIBILITY_CAPABILITY,
    P263_SLOT_ELIGIBILITY_DOMAIN,
    P263_SLOT_ELIGIBILITY_FACT,
    P263_SLOT_ELIGIBILITY_TASK_KEY,
    P263_SLOT_GOVERNANCE_SOURCE_PATHS,
    P263_SLOT_SOURCE_CONTRACT_DOMAIN,
    P263_SLOT_SOURCE_CONTRACT_PATH,
    P263SlotSupersessionError,
    build_p263_post_stop_guard_decision,
    build_p263_slot_eligibility_artifact,
    build_p263_slot_release_manifest,
    load_p263_slot_source_contract,
    replay_p263_slot_eligibility_artifact,
    validate_p263_slot_eligibility_artifact,
    validate_p263_slot_release_guard_artifact,
    validate_p263_slot_source_contract,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import (
    ControlPlaneManifest,
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
    Task,
)
from dehps.research_os.supervisor import (
    M4P263RuntimeSlotEligibilityCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
CONTROL_PLANE_KEY = "m4-information-theory-mainline"
GIT_COMMIT = "f" * 40
ELIGIBILITY_EXECUTION_ID = "6" * 64
SOURCE_CONTRACT = load_p263_slot_source_contract(ROOT / P263_SLOT_SOURCE_CONTRACT_PATH)
EXECUTION_IDS = {
    P263_COMPATIBILITY_TASK_KEY: "1" * 64,
    P263_GOLDEN_TASK_KEY: "2" * 64,
    P263_RUNTIME_TASK_KEY: "3" * 64,
    P263_FAILED_RUNTIME_TASK_KEY: "4" * 64,
}
CAPABILITIES = {
    P263_COMPATIBILITY_TASK_KEY: P263_COMPATIBILITY_CAPABILITY,
    P263_GOLDEN_TASK_KEY: P263_GOLDEN_CAPABILITY,
    P263_RUNTIME_TASK_KEY: P263_RUNTIME_CAPABILITY,
    P263_FAILED_RUNTIME_TASK_KEY: P263_FAILED_RUNTIME_CAPABILITY,
}
ARTIFACT_CONTRACTS = {
    P263_COMPATIBILITY_TASK_KEY: (
        (
            "MeasurementCompatibilityAcceptanceArtifact",
            "dehps-m4-p2-measurement-compatibility-acceptance.v1",
        ),
        (
            "measurement_source_fixture_replay",
            "dehps-m4-p2-source-fixture-replay.v1",
        ),
        (
            "measurement_source_fixture_replay",
            "dehps-m4-p2-source-fixture-replay.v1",
        ),
        (
            "research_os_mainline_execution",
            "dehps-research-os-mainline-execution.v1",
        ),
    ),
    P263_GOLDEN_TASK_KEY: (
        (
            "GoldenReferencePlanArtifact",
            "dehps-m4-p2-9-golden-reference-plan.v1",
        ),
        (
            "GoldenReferenceReplayArtifact",
            "dehps-m4-p2-9-phase0-golden-equivalence.v1",
        ),
        (
            "Phase0GoldenReferenceFixture.v1",
            "dehps-m4-p2-9-phase0-golden-reference.v1",
        ),
        (
            "SourceIntegrityAttestationArtifact",
            "dehps-m4-p2-9-source-integrity-attestation.v1",
        ),
        (
            "research_os_mainline_execution",
            "dehps-research-os-mainline-execution.v1",
        ),
    ),
    P263_RUNTIME_TASK_KEY: (
        (
            "BenchmarkPlanArtifact",
            "dehps-m4-p2-9-measurement-runtime-audit-plan.v1",
        ),
        (
            "EquivalenceAttestationArtifact",
            "dehps-m4-p2-9-equivalence-attestation.v1",
        ),
        (
            "RuntimeBenchmarkAttemptArtifact",
            "dehps-m4-p2-9-runtime-benchmark-attempt.v1",
        ),
        (
            "RuntimeObservationArtifact",
            "dehps-m4-p2-9-runtime-observation.v1",
        ),
        (
            "SourceIntegrityAttestationArtifact",
            "dehps-m4-p2-9-source-integrity-attestation.v1",
        ),
        (
            "research_os_mainline_execution",
            "dehps-research-os-mainline-execution.v1",
        ),
    ),
}


def _source_payload() -> dict:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    value.pop("manifest_digest")
    return value


def _task(manifest: ControlPlaneManifest, key: str) -> Task:
    return next(task for task in manifest.tasks if task.task_key == key)


def _prepared_payload(*, eligibility_status: str) -> dict:
    payload = _source_payload()
    source = ControlPlaneManifest.from_dict(payload)
    completion_facts = []
    for key in (
        P263_COMPATIBILITY_TASK_KEY,
        P263_GOLDEN_TASK_KEY,
        P263_RUNTIME_TASK_KEY,
    ):
        raw = next(task for task in payload["tasks"] if task["task_key"] == key)
        raw["status"] = "completed"
        raw["completion_classification"] = "COMPLETE"
        completion_facts.append(
            mainline_completion_fact(
                task=_task(source, key),
                execution_id=EXECUTION_IDS[key],
            )
        )
    repair_key = "m4-p2-repair-measurement-system"
    repair = next(task for task in payload["tasks"] if task["task_key"] == repair_key)
    repair["status"] = "completed"
    repair["completion_classification"] = "COMPLETE"
    completion_facts.append(
        mainline_completion_fact(
            task=_task(source, repair_key),
            execution_id="7" * 64,
        )
    )
    eligibility = next(
        task
        for task in payload["tasks"]
        if task["task_key"] == P263_SLOT_ELIGIBILITY_TASK_KEY
    )
    eligibility["status"] = eligibility_status
    eligibility["completion_classification"] = (
        "INTEGRATED" if eligibility_status == "running" else "COMPLETE"
    )
    facts = set(payload["facts"]["artifacts"])
    facts.update(
        {
            *completion_facts,
            "m4-p2-6-3-compatibility:VERIFIED",
            "m4-p2-9-p263-golden-reference:VERIFIED",
            "m4-p2-9-p263-runtime-audit-arithmetic-fix:VERIFIED",
        }
    )
    if eligibility_status == "completed":
        facts.update(
            {
                P263_SLOT_ELIGIBILITY_FACT,
                mainline_completion_fact(
                    task=_task(source, P263_SLOT_ELIGIBILITY_TASK_KEY),
                    execution_id=ELIGIBILITY_EXECUTION_ID,
                ),
            }
        )
    payload["facts"]["artifacts"] = sorted(facts)
    return payload


def _event(
    *,
    task: Task,
    execution_id: str,
    event_type: str,
    recorded_at: str,
) -> dict:
    event = MainlineExecutionEvent(
        execution_id=execution_id,
        control_plane_key=CONTROL_PLANE_KEY,
        manifest_digest="a" * 64,
        task_key=task.task_key,
        task_digest=task.artifact_digest,
        capability=str(task.requested_capability),
        event_type=event_type,
        sequence=0 if event_type == "started" else 1,
        recorded_at=recorded_at,
    )
    return {
        "event_digest": event.artifact_digest,
        "execution_id": execution_id,
        "control_plane_key": CONTROL_PLANE_KEY,
        "manifest_digest": "a" * 64,
        "task_digest": task.artifact_digest,
        "task_key": task.task_key,
        "capability": task.requested_capability,
        "event_type": event_type,
        "sequence": event.sequence,
        "recorded_at": recorded_at,
    }


def _registrations(task: Task, execution_id: str) -> tuple[dict, ...]:
    output = []
    for index, (artifact_type, schema_version) in enumerate(
        ARTIFACT_CONTRACTS[task.task_key]
    ):
        artifact_digest = canonical_digest(
            {
                "task_key": task.task_key,
                "artifact_type": artifact_type,
                "index": index,
            },
            domain="dehps.test.p263-slot-artifact.v1",
        )
        registration = MainlineArtifactRegistration(
            execution_id=execution_id,
            control_plane_key=CONTROL_PLANE_KEY,
            task_key=task.task_key,
            task_digest=task.artifact_digest,
            artifact_digest=artifact_digest,
            artifact_type=artifact_type,
            schema_version=schema_version,
            artifact_path=(
                "runtime/research-os/mainline/tasks/"
                f"{task.task_key}/{execution_id}/artifacts/"
                f"{artifact_type}/{artifact_digest}/artifact.json"
            ),
            parent_digests=(),
            git_commit=GIT_COMMIT,
        )
        output.append(
            {
                "registration_digest": registration.registration_digest,
                "execution_id": registration.execution_id,
                "control_plane_key": registration.control_plane_key,
                "task_key": registration.task_key,
                "task_digest": registration.task_digest,
                "artifact_digest": registration.artifact_digest,
                "artifact_type": registration.artifact_type,
                "schema_version": registration.schema_version,
                "artifact_path": registration.artifact_path,
                "parent_digests": [],
                "git_commit": registration.git_commit,
            }
        )
    return tuple(output)


def _basis(*, eligibility_status: str = "running"):
    manifest = ControlPlaneManifest.from_dict(
        _prepared_payload(eligibility_status=eligibility_status)
    )
    events = []
    registrations = {}
    for index, key in enumerate(
        (
            P263_COMPATIBILITY_TASK_KEY,
            P263_GOLDEN_TASK_KEY,
            P263_RUNTIME_TASK_KEY,
        )
    ):
        task = _task(manifest, key)
        execution_id = EXECUTION_IDS[key]
        events.extend(
            (
                _event(
                    task=task,
                    execution_id=execution_id,
                    event_type="started",
                    recorded_at=f"2026-08-07T09:0{index}:00+00:00",
                ),
                _event(
                    task=task,
                    execution_id=execution_id,
                    event_type="completed",
                    recorded_at=f"2026-08-07T09:0{index}:30+00:00",
                ),
            )
        )
        registrations[execution_id] = _registrations(task, execution_id)
    failed = _task(manifest, P263_FAILED_RUNTIME_TASK_KEY)
    events.extend(
        (
            _event(
                task=failed,
                execution_id=EXECUTION_IDS[P263_FAILED_RUNTIME_TASK_KEY],
                event_type="started",
                recorded_at="2026-08-07T09:10:00+00:00",
            ),
            _event(
                task=failed,
                execution_id=EXECUTION_IDS[P263_FAILED_RUNTIME_TASK_KEY],
                event_type="failed",
                recorded_at="2026-08-07T09:10:30+00:00",
            ),
        )
    )
    eligibility = _task(manifest, P263_SLOT_ELIGIBILITY_TASK_KEY)
    events.append(
        _event(
            task=eligibility,
            execution_id=ELIGIBILITY_EXECUTION_ID,
            event_type="started",
            recorded_at="2026-08-07T10:00:00+00:00",
        )
    )
    return manifest, tuple(events), registrations


def _eligibility():
    manifest, events, registrations = _basis()
    artifact = build_p263_slot_eligibility_artifact(
        manifest=manifest,
        events=events,
        registrations_by_execution=registrations,
        execution_id=ELIGIBILITY_EXECUTION_ID,
        git_commit=GIT_COMMIT,
        p261_fixture_digest=P261_FROZEN_FIXTURE_DIGEST,
        p263_fixture_digest=P263_SUPERSEDING_FIXTURE_DIGEST,
        slot_source_contract_digest=SOURCE_CONTRACT["artifact_digest"],
        slot_source_set_digest=SOURCE_CONTRACT["source_set_digest"],
    )
    return artifact, manifest, events, registrations


def test_source_declares_canonical_slot_eligibility_task() -> None:
    assert validate_p263_slot_source_contract(SOURCE_CONTRACT) == SOURCE_CONTRACT
    manifest = ControlPlaneManifest.from_dict(
        json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    )
    task = _task(manifest, P263_SLOT_ELIGIBILITY_TASK_KEY)
    assert task.requested_capability == P263_SLOT_ELIGIBILITY_CAPABILITY
    assert task.goal_key == "M4_MEASUREMENT_RUNTIME_AUDIT"
    assert task.lane.value == "maintenance"
    assert task.input_artifact_digests == (
        "42d9583d2b333e171b99dfde27732b687e2deec2359a423d20d5d295103d1cec",
        P261_FROZEN_FIXTURE_DIGEST,
        P263_SUPERSEDING_FIXTURE_DIGEST,
        "8c97fd5fdc006cba6a4145dbd56acc566b9507e18279d06437d0aa472adb2cd2",
        SOURCE_CONTRACT["artifact_digest"],
    )
    supervisor = ResearchEvidenceSupervisor(require_clean_tree=False)
    assert P263_SLOT_ELIGIBILITY_CAPABILITY in supervisor.capabilities


def test_result_blind_eligibility_builds_and_replays_from_metadata() -> None:
    artifact, _, events, registrations = _eligibility()
    assert validate_p263_slot_eligibility_artifact(artifact) == artifact
    assert artifact["status"] == "ELIGIBLE_AFTER_OPERATOR_STOP"
    assert artifact["statistical_results_read"] is False
    assert artifact["evidence_created"] is False
    assert artifact["promotion_gate_opened"] is False
    assert artifact["slot_governance_source_contract_digest"] == SOURCE_CONTRACT[
        "artifact_digest"
    ]

    completed_manifest = ControlPlaneManifest.from_dict(
        _prepared_payload(eligibility_status="completed")
    )
    replay = replay_p263_slot_eligibility_artifact(
        payload=artifact,
        manifest=completed_manifest,
        events=events,
        registrations_by_execution=registrations,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["statistical_results_read"] is False
    assert replay["same_registration_metadata"] is True


def test_recomputed_digest_cannot_enable_statistical_reads() -> None:
    artifact, _, _, _ = _eligibility()
    tampered = deepcopy(artifact)
    tampered["statistical_results_read"] = True
    identity = dict(tampered)
    identity.pop("artifact_digest")
    tampered["artifact_digest"] = canonical_digest(
        identity,
        domain=P263_SLOT_ELIGIBILITY_DOMAIN,
    )
    with pytest.raises(
        P263SlotSupersessionError,
        match="p263_slot_eligibility_artifact_invalid",
    ):
        validate_p263_slot_eligibility_artifact(tampered)


def test_recomputed_source_contract_cannot_enable_result_reads() -> None:
    tampered = deepcopy(SOURCE_CONTRACT)
    tampered["statistical_results_read"] = True
    identity = dict(tampered)
    identity.pop("artifact_digest")
    tampered["artifact_digest"] = canonical_digest(
        identity,
        domain=P263_SLOT_SOURCE_CONTRACT_DOMAIN,
    )
    with pytest.raises(
        P263SlotSupersessionError,
        match="p263_slot_source_contract_invalid",
    ):
        validate_p263_slot_source_contract(tampered)


def test_missing_registration_and_preexisting_downstream_start_fail_closed() -> None:
    manifest, events, registrations = _basis()
    broken = dict(registrations)
    runtime_id = EXECUTION_IDS[P263_RUNTIME_TASK_KEY]
    broken[runtime_id] = broken[runtime_id][:-1]
    with pytest.raises(
        P263SlotSupersessionError,
        match="p263_slot_registered_artifacts_invalid",
    ):
        build_p263_slot_eligibility_artifact(
            manifest=manifest,
            events=events,
            registrations_by_execution=broken,
            execution_id=ELIGIBILITY_EXECUTION_ID,
            git_commit=GIT_COMMIT,
            p261_fixture_digest=P261_FROZEN_FIXTURE_DIGEST,
            p263_fixture_digest=P263_SUPERSEDING_FIXTURE_DIGEST,
            slot_source_contract_digest=SOURCE_CONTRACT["artifact_digest"],
            slot_source_set_digest=SOURCE_CONTRACT["source_set_digest"],
        )

    design = _task(manifest, M4_V2_DESIGN_TASK_KEY)
    raced_events = (
        *events,
        _event(
            task=design,
            execution_id="9" * 64,
            event_type="started",
            recorded_at="2026-08-07T09:59:59+00:00",
        ),
    )
    with pytest.raises(
        P263SlotSupersessionError,
        match="p263_slot_downstream_dispatch_race",
    ):
        build_p263_slot_eligibility_artifact(
            manifest=manifest,
            events=raced_events,
            registrations_by_execution=registrations,
            execution_id=ELIGIBILITY_EXECUTION_ID,
            git_commit=GIT_COMMIT,
            p261_fixture_digest=P261_FROZEN_FIXTURE_DIGEST,
            p263_fixture_digest=P263_SUPERSEDING_FIXTURE_DIGEST,
            slot_source_contract_digest=SOURCE_CONTRACT["artifact_digest"],
            slot_source_set_digest=SOURCE_CONTRACT["source_set_digest"],
        )


def test_post_stop_guard_and_slot_only_migration() -> None:
    eligibility, _, _, _ = _eligibility()
    active = build_p263_post_stop_guard_decision(
        eligibility=eligibility,
        service_active_state="active",
        worker_cgroup_empty=False,
        downstream_started_events=(),
    )
    assert active["state"] == "STOP_VERIFICATION_FAILED"
    assert active["publish_slot_event"] is False
    with pytest.raises(P263SlotSupersessionError):
        validate_p263_slot_release_guard_artifact(active)

    safe = build_p263_post_stop_guard_decision(
        eligibility=eligibility,
        service_active_state="inactive",
        worker_cgroup_empty=True,
        downstream_started_events=(),
    )
    assert validate_p263_slot_release_guard_artifact(safe) == safe
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    live = _prepared_payload(eligibility_status="completed")
    migrated, dry_run = build_p263_slot_release_manifest(
        live_payload=live,
        source_payload=source,
        eligibility_payload=eligibility,
        guard_payload=safe,
    )
    assert dry_run["added_external_events"] == [
        "m4-runtime-slot:p2-6-1-released"
    ]
    assert dry_run["ready_queue_after"] == [M4_V2_DESIGN_TASK_KEY]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0

    unrelated = deepcopy(eligibility)
    unrelated["execution_id"] = "8" * 64
    identity = dict(unrelated)
    identity.pop("artifact_digest")
    unrelated["artifact_digest"] = canonical_digest(
        identity,
        domain=P263_SLOT_ELIGIBILITY_DOMAIN,
    )
    with pytest.raises(
        P263SlotSupersessionError,
        match="p263_slot_guard_eligibility_lineage_invalid",
    ):
        build_p263_slot_release_manifest(
            live_payload=live,
            source_payload=source,
            eligibility_payload=unrelated,
            guard_payload=safe,
        )
    snapshot = ResearchOSControlPlane().resolve(
        ControlPlaneManifest.from_dict(migrated)
    )
    assert [item.task_key for item in snapshot.ready_queue] == [
        M4_V2_DESIGN_TASK_KEY
    ]


def test_capability_materializes_only_governance_artifacts(tmp_path: Path) -> None:
    manifest, events, registrations = _basis()

    class Repository:
        def load_manifest(self, *, control_plane_key: str):
            assert control_plane_key == CONTROL_PLANE_KEY
            return manifest

        def list_mainline_execution_event_metadata(
            self, *, control_plane_key: str, task_keys: tuple[str, ...]
        ):
            assert control_plane_key == CONTROL_PLANE_KEY
            return tuple(event for event in events if event["task_key"] in task_keys)

        def list_mainline_artifacts(
            self, *, control_plane_key: str, execution_id: str
        ):
            assert control_plane_key == CONTROL_PLANE_KEY
            return registrations.get(execution_id, ())

    for relative in (
        P263_SLOT_SOURCE_CONTRACT_PATH.as_posix(),
        "configs/research-os/fixtures/m4-p2.6.1/frozen/source-manifest-fixture-v1.json",
        "configs/research-os/fixtures/m4-p2.6.3/superseding/source-manifest-fixture-v1.json",
        *P263_SLOT_GOVERNANCE_SOURCE_PATHS,
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    capability = M4P263RuntimeSlotEligibilityCapability(
        repository=Repository(),  # type: ignore[arg-type]
        root_dir=tmp_path,
    )
    task = _task(manifest, P263_SLOT_ELIGIBILITY_TASK_KEY)
    result = capability.execute(
        control_plane_key=CONTROL_PLANE_KEY,
        task=task,
        execution_id=ELIGIBILITY_EXECUTION_ID,
        git_commit=GIT_COMMIT,
    )
    assert result.completion_facts == (P263_SLOT_ELIGIBILITY_FACT,)
    assert len(result.registrations) == 2
    assert result.execution_artifact["statistical_results_read"] is False
    assert result.execution_artifact["evidence_created"] is False
    child = next(
        registration
        for registration in result.registrations
        if registration.artifact_type == "p263_runtime_slot_release_eligibility"
    )
    validate_p263_slot_eligibility_artifact(
        json.loads((tmp_path / child.artifact_path).read_text(encoding="utf-8"))
    )
