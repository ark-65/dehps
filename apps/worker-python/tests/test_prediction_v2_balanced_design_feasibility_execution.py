from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict
from itertools import combinations, product
from pathlib import Path

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_feasibility_execution import (
    BOUNDED_NEGATIVE_OUTCOME,
    EXECUTION_HANDOFF_DIGEST,
    POSITIVE_OUTCOME,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_APPROVED_EVENT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_CAPABILITY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_COMPLETION_FACT,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
    PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY,
    PREREGISTRATION_COMPLETION_DIGEST,
    PREREGISTRATION_DIGEST,
    PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
    REPETITION_SCAN,
    BalancedDesignExecutionError,
    SignatureGroup,
    _choose_branch_coordinate,
    _coordinate_allocations,
    _SignatureCompatibilityIndex,
    build_balanced_design_execution_artifacts,
    build_positive_certificate,
    build_search_result_artifact,
    canonical_translation_representative,
    circular_distance_signature,
    compile_translation_orbit_inventory,
    lexicographic_combination_rank,
    lexicographic_combination_unrank,
    load_execution_source_contract,
    replay_balanced_design_execution,
    search_exact_signature_multicover,
    translation_orbit_size,
    verify_execution_source_bytes,
    verify_positive_certificate,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    PredictionV2BalancedDesignFeasibilityExecutionCapability,
    ResearchEvidenceSupervisor,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)
PREREGISTRATION_TASK_KEY = "prediction-v2-balanced-design-feasibility-preregistration"
SOURCE_FACT_PREFIX = "prediction-v2-balanced-design-feasibility-execution-source:"


def _toy_inventory():
    return compile_translation_orbit_inventory(
        point_count=7,
        block_size=3,
        require_formal_identity=False,
    )


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _source() -> dict:
    source = load_execution_source_contract(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    verify_execution_source_bytes(root_dir=ROOT_DIR, contract=source)
    return source


def _preregistration_parents() -> dict[str, dict]:
    preregistration = _artifact(
        {
            "status": "COMPLETE",
            "preregistration_status": "FROZEN_NOT_EXECUTED",
            "constructor_family": "Z33_TRANSLATION_ORBIT_EXACT_MULTICOVER_V1",
            "result_blind": True,
            "repetition_scan": REPETITION_SCAN,
        },
        domain=("dehps.prediction-v2.balanced-design-feasibility-preregistration.v1"),
    )
    handoff = _artifact(
        {
            "status": "COMPLETE",
            "preregistration_digest": preregistration["artifact_digest"],
            "constructor_family": "Z33_TRANSLATION_ORBIT_EXACT_MULTICOVER_V1",
            "result_blind": True,
            "repetition_scan": REPETITION_SCAN,
        },
        domain=("dehps.prediction-v2.balanced-design-feasibility-execution-handoff.v1"),
    )
    completion = _artifact(
        {
            "status": "COMPLETE",
            "completion_fact": (
                "prediction-v2-balanced-design-feasibility-preregistration:COMPLETE"
            ),
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": handoff["artifact_digest"],
            "repetition_scan": REPETITION_SCAN,
        },
        domain=(
            "dehps.prediction-v2.balanced-design-feasibility-"
            "preregistration-completion.v1"
        ),
    )
    execution = _artifact(
        {
            "status": "COMPLETE",
            "task_key": PREREGISTRATION_TASK_KEY,
            "preregistration_completion_digest": completion["artifact_digest"],
            "repetition_scan": REPETITION_SCAN,
            "production_action": "none",
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    return {
        "preregistration": preregistration,
        "execution_handoff": handoff,
        "preregistration_completion": completion,
        "preregistration_mainline_execution": execution,
    }


def _recursive_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def _dense_compatible_group_indices(
    *,
    groups: tuple[SignatureGroup, ...],
    residual: tuple[int, ...],
    selected_counts: tuple[tuple[int, int], ...],
    coordinate: int | None = None,
) -> tuple[int, ...]:
    selected = dict(selected_counts)
    return tuple(
        group_index
        for group_index, group in enumerate(groups)
        if (
            selected.get(group_index, 0) < group.multiplicity
            and (coordinate is None or group.signature[coordinate] > 0)
            and all(
                value <= available
                for value, available in zip(group.signature, residual)
            )
        )
    )


def _dense_branch_coordinate(
    *,
    groups: tuple[SignatureGroup, ...],
    residual: tuple[int, ...],
    selected_counts: tuple[tuple[int, int], ...],
) -> int:
    choices = [
        (
            len(
                _dense_compatible_group_indices(
                    groups=groups,
                    residual=residual,
                    selected_counts=selected_counts,
                    coordinate=coordinate,
                )
            ),
            coordinate,
        )
        for coordinate, need in enumerate(residual)
        if need > 0
    ]
    if not choices:
        return -1
    compatible_count, coordinate = min(choices)
    return coordinate if compatible_count else -1


def _dense_coordinate_allocations(
    *,
    groups: tuple[SignatureGroup, ...],
    residual: tuple[int, ...],
    remaining: int,
    selected_counts: tuple[tuple[int, int], ...],
    coordinate: int,
) -> tuple[tuple[tuple[int, int], ...], ...]:
    compatible = _dense_compatible_group_indices(
        groups=groups,
        residual=residual,
        selected_counts=selected_counts,
        coordinate=coordinate,
    )
    selected = dict(selected_counts)

    def walk(
        position: int,
        coordinate_need: int,
        slots: int,
        contribution: tuple[int, ...],
        allocation: tuple[tuple[int, int], ...],
    ):
        if coordinate_need == 0:
            yield allocation
            return
        if slots <= 0:
            return
        for compatible_position in range(position, len(compatible)):
            group_index = compatible[compatible_position]
            group = groups[group_index]
            maximum = min(
                group.multiplicity - selected.get(group_index, 0),
                slots,
                coordinate_need // group.signature[coordinate],
            )
            for count in range(1, maximum + 1):
                next_contribution = tuple(
                    current + count * value
                    for current, value in zip(contribution, group.signature)
                )
                if any(
                    value > available
                    for value, available in zip(next_contribution, residual)
                ):
                    break
                yield from walk(
                    compatible_position + 1,
                    coordinate_need - count * group.signature[coordinate],
                    slots - count,
                    next_contribution,
                    (*allocation, (group_index, count)),
                )

    return tuple(
        walk(
            0,
            residual[coordinate],
            remaining,
            (0,) * len(residual),
            (),
        )
    )


def test_lexicographic_rank_unrank_is_a_small_universe_bijection() -> None:
    blocks = tuple(combinations(range(7), 3))
    for expected_rank, block in enumerate(blocks):
        assert (
            lexicographic_combination_rank(
                block,
                point_count=7,
                block_size=3,
            )
            == expected_rank
        )
        assert (
            lexicographic_combination_unrank(
                expected_rank,
                point_count=7,
                block_size=3,
            )
            == block
        )


def test_toy_orbit_compiler_is_complete_and_signature_exact() -> None:
    inventory = _toy_inventory()
    assert inventory.legal_block_count == 35
    assert inventory.canonical_candidates_visited == 15
    assert len(inventory.full_representatives) == 5
    assert inventory.short_representatives == ()
    assert inventory.legal_block_ids_accounted == 35
    assert sum(group.multiplicity for group in inventory.signature_groups) == 5
    assert all(sum(item.signature) == 3 for item in inventory.full_representatives)
    assert canonical_translation_representative(
        (2, 3, 5),
        point_count=7,
    ) == (0, 1, 3)
    assert translation_orbit_size((0, 1, 3), point_count=7) == (7, 1)
    assert circular_distance_signature((0, 1, 3), point_count=7) == (1, 1, 1)


def test_signature_index_matches_dense_scan_on_exhaustive_toy_state_lattice() -> None:
    groups = _toy_inventory().signature_groups
    index = _SignatureCompatibilityIndex.build(groups)
    selected_states = (
        (),
        ((0, 1),),
        ((2, 1),),
        ((2, 2),),
        ((0, 1), (2, 1)),
    )
    for raw_residual in product(range(5), repeat=3):
        residual = tuple(raw_residual)
        for selected_counts in selected_states:
            expected_compatible = _dense_compatible_group_indices(
                groups=groups,
                residual=residual,
                selected_counts=selected_counts,
            )
            compatible_bits = index.compatible_bits(
                groups=groups,
                residual=residual,
                selected_counts=selected_counts,
            )
            actual_compatible = tuple(
                group_index
                for group_index in range(len(groups))
                if compatible_bits & (1 << group_index)
            )
            assert actual_compatible == expected_compatible
            assert _choose_branch_coordinate(
                groups=groups,
                residual=residual,
                selected_counts=selected_counts,
                compatibility_index=index,
                compatible_bits=compatible_bits,
            ) == _dense_branch_coordinate(
                groups=groups,
                residual=residual,
                selected_counts=selected_counts,
            )


def test_indexed_allocation_order_matches_dense_exhaustive_toy_frames() -> None:
    groups = _toy_inventory().signature_groups
    index = _SignatureCompatibilityIndex.build(groups)
    selected_states = ((), ((2, 1),), ((0, 1), (2, 1)))
    compared_frames = 0
    for raw_residual in product(range(5), repeat=3):
        residual = tuple(raw_residual)
        for remaining in range(1, 5):
            if sum(residual) != remaining * index.signature_weight:
                continue
            for selected_counts in selected_states:
                coordinate = _dense_branch_coordinate(
                    groups=groups,
                    residual=residual,
                    selected_counts=selected_counts,
                )
                if coordinate < 0:
                    continue
                expected = _dense_coordinate_allocations(
                    groups=groups,
                    residual=residual,
                    remaining=remaining,
                    selected_counts=selected_counts,
                    coordinate=coordinate,
                )
                actual = tuple(
                    _coordinate_allocations(
                        groups=groups,
                        residual=residual,
                        remaining=remaining,
                        selected_counts=selected_counts,
                        coordinate=coordinate,
                        compatibility_index=index,
                    )
                )
                assert actual == expected
                compared_frames += 1
    assert compared_frames == 98


def test_exact_multicover_finds_toy_fano_certificate_without_repetition_scan(
    tmp_path: Path,
) -> None:
    inventory = _toy_inventory()
    result = search_exact_signature_multicover(
        inventory=inventory,
        source_contract_digest="1" * 64,
        preregistration_digest="2" * 64,
        execution_id="3" * 64,
        checkpoint_path=tmp_path / "checkpoint.jsonl",
        target_signature=(1, 1, 1),
        profiles=((1, 0),),
        node_budget=100,
        checkpoint_interval=10,
    )
    assert result.outcome == POSITIVE_OUTCOME
    assert result.profile == (1, 0)
    assert len(result.selected_full_representative_ids) == 1
    certificate = build_positive_certificate(inventory=inventory, result=result)
    assert certificate["block_count"] == 7
    assert certificate["repetition_scan"] == REPETITION_SCAN
    verification = verify_positive_certificate(
        inventory=inventory,
        certificate=certificate,
        expected_block_count=7,
        point_replication_target=3,
        pair_replication_target=1,
    )
    assert verification.decoded_block_ids == (1, 8, 12, 16, 24, 26, 32)
    assert verification.point_counts == (3,) * 7
    assert verification.pair_counts == (1,) * 21
    result_artifact = build_search_result_artifact(
        inventory_artifact_digest=inventory.to_artifact()["artifact_digest"],
        result=result,
        certificate=certificate,
        peak_resident_bytes=1024,
    )
    assert result_artifact["outcome"] == POSITIVE_OUTCOME
    assert result_artifact["separate_duplicate_membership_or_uniqueness_scan"] is False
    assert not {
        "duplicate_validation",
        "duplicate_check",
        "uniqueness_validation",
        "duplicate_scan",
        "membership_scan",
        "membership_validation",
    }.intersection(_recursive_keys(result_artifact))


def test_checkpoint_resume_continues_same_deterministic_search(
    tmp_path: Path,
) -> None:
    inventory = _toy_inventory()
    path = tmp_path / "checkpoint.jsonl"
    bounded = search_exact_signature_multicover(
        inventory=inventory,
        source_contract_digest="4" * 64,
        preregistration_digest="5" * 64,
        execution_id="6" * 64,
        checkpoint_path=path,
        target_signature=(1, 3, 2),
        profiles=((2, 0),),
        node_budget=1,
        checkpoint_interval=1,
    )
    assert bounded.outcome == BOUNDED_NEGATIVE_OUTCOME
    assert bounded.search_exhausted is False
    resumed = search_exact_signature_multicover(
        inventory=inventory,
        source_contract_digest="4" * 64,
        preregistration_digest="5" * 64,
        execution_id="6" * 64,
        checkpoint_path=path,
        target_signature=(1, 3, 2),
        profiles=((2, 0),),
        node_budget=100,
        checkpoint_interval=1,
    )
    baseline = search_exact_signature_multicover(
        inventory=inventory,
        source_contract_digest="4" * 64,
        preregistration_digest="5" * 64,
        execution_id="7" * 64,
        checkpoint_path=tmp_path / "baseline.jsonl",
        target_signature=(1, 3, 2),
        profiles=((2, 0),),
        node_budget=100,
        checkpoint_interval=1,
    )
    assert resumed.outcome == baseline.outcome == POSITIVE_OUTCOME
    assert resumed.selected_full_representative_ids == (
        baseline.selected_full_representative_ids
    )
    assert resumed.transcript_digest == baseline.transcript_digest
    assert resumed.node_expansions == baseline.node_expansions


def test_checkpoint_identity_change_fails_closed(tmp_path: Path) -> None:
    inventory = _toy_inventory()
    path = tmp_path / "checkpoint.jsonl"
    search_exact_signature_multicover(
        inventory=inventory,
        source_contract_digest="8" * 64,
        preregistration_digest="9" * 64,
        execution_id="a" * 64,
        checkpoint_path=path,
        target_signature=(2, 2, 2),
        profiles=((2, 0),),
        node_budget=1,
        checkpoint_interval=1,
    )
    with pytest.raises(
        BalancedDesignExecutionError, match="checkpoint_identity_changed"
    ):
        search_exact_signature_multicover(
            inventory=inventory,
            source_contract_digest="b" * 64,
            preregistration_digest="9" * 64,
            execution_id="a" * 64,
            checkpoint_path=path,
            target_signature=(2, 2, 2),
            profiles=((2, 0),),
            node_budget=100,
            checkpoint_interval=1,
        )


def test_certificate_tamper_is_rejected_without_a_second_repetition_pass(
    tmp_path: Path,
) -> None:
    inventory = _toy_inventory()
    result = search_exact_signature_multicover(
        inventory=inventory,
        source_contract_digest="c" * 64,
        preregistration_digest="d" * 64,
        execution_id="e" * 64,
        checkpoint_path=tmp_path / "checkpoint.jsonl",
        target_signature=(1, 1, 1),
        profiles=((1, 0),),
        node_budget=100,
        checkpoint_interval=10,
    )
    certificate = build_positive_certificate(inventory=inventory, result=result)
    changed = copy.deepcopy(certificate)
    changed["gap_minus_one"][0] += 1
    identity = dict(changed)
    identity.pop("artifact_digest")
    changed["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.prediction-v2.balanced-design.certificate.v1",
    )
    with pytest.raises(
        BalancedDesignExecutionError,
        match="certificate_orbit_reconstruction_changed",
    ):
        verify_positive_certificate(
            inventory=inventory,
            certificate=changed,
            expected_block_count=7,
            point_replication_target=3,
            pair_replication_target=1,
        )


def test_source_contract_is_bound_and_source_tamper_fails_closed(
    tmp_path: Path,
) -> None:
    source = _source()
    assert source["registered_children"] == 3
    assert source["repetition_scan"] == REPETITION_SCAN
    for entry in source["source_entries"]:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], destination)
    verify_execution_source_bytes(root_dir=tmp_path, contract=source)
    source_path = tmp_path / source["source_entries"][0]["path"]
    source_path.write_text(
        source_path.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )
    with pytest.raises(
        BalancedDesignExecutionError,
        match="execution_source_bytes_changed",
    ):
        verify_execution_source_bytes(root_dir=tmp_path, contract=source)


def test_toy_execution_registers_proof_and_replays_without_search(
    tmp_path: Path,
) -> None:
    parents = _preregistration_parents()
    checkpoint_path = tmp_path / "checkpoint.jsonl"
    run = build_balanced_design_execution_artifacts(
        source_contract=_source(),
        inventory=_toy_inventory(),
        execution_id="f" * 64,
        checkpoint_path=checkpoint_path,
        target_signature=(1, 1, 1),
        profiles=((1, 0),),
        node_budget=100,
        checkpoint_interval=10,
        require_formal_identity=False,
        require_registered_identities=False,
        **parents,
    )
    assert run.result["outcome"] == POSITIVE_OUTCOME
    assert run.result["certificate"]["block_count"] == 7
    assert run.completion["registered_child_count"] == 3
    assert run.completion["repetition_scan"] == REPETITION_SCAN
    replay = replay_balanced_design_execution(
        source_contract=_source(),
        inventory_artifact=run.inventory,
        result_artifact=run.result,
        completion_artifact=run.completion,
        execution_id="f" * 64,
        checkpoint_path=checkpoint_path,
        require_formal_identity=False,
        require_registered_identities=False,
        **parents,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["solver_nodes_replayed"] == 0
    assert replay["terminal_checkpoint_verified"] is True
    assert replay["certificate_verified"] is True


def test_additive_migration_revises_execution_and_adds_only_result_decision() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    ]
    current = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    )
    current["requested_capability"] = None
    current["input_artifact_digests"] = []
    current["dependencies"] = [
        item
        for item in current["dependencies"]
        if item["dependency_type"] != "external_event"
    ]
    current["metric_contract"]["engineering_complete"] = False
    current["metric_contract"]["engineering_increment_percent"] = 0
    current["metric_contract"]["mainline_integration"]["runner"] = (
        "pending_a_separate_approved_engineering_execution_capability"
    )
    current["metric_contract"]["execution_authorized"] = False
    source_fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"] = [
        fact for fact in live["facts"]["artifacts"] if fact != source_fact
    ]
    live["facts"]["external_events"] = [
        event
        for event in live["facts"]["external_events"]
        if event != PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_APPROVED_EVENT
    ]
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_APPROVED_EVENT,
        ),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert len(migrated["tasks"]) == len(live["tasks"]) + 1


def test_manifest_status_and_index_bind_execution_then_stop_at_result_decision() -> (
    None
):
    source = _source()
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    task = tasks[PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY]
    assert task.requested_capability == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_CAPABILITY
    )
    assert task.input_artifact_digests == (
        source["artifact_digest"],
        PREREGISTRATION_DIGEST,
        EXECUTION_HANDOFF_DIGEST,
        PREREGISTRATION_COMPLETION_DIGEST,
        PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
    )
    next_task = tasks[
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    ]
    assert next_task.requested_capability is None
    assert next_task.input_artifact_digests == ()
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    assert index[manifest.artifact_digest]["identity_field"] == "manifest_digest"

    payload = manifest.to_dict(include_digest=False)
    for item in payload["tasks"]:
        if item["task_key"] in {PREREGISTRATION_TASK_KEY, task.task_key}:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            "prediction-v2-balanced-design-feasibility-preregistration:COMPLETE",
            PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_COMPLETION_FACT,
            mainline_completion_fact(
                task=tasks[PREREGISTRATION_TASK_KEY], execution_id="a" * 64
            ),
            mainline_completion_fact(task=task, execution_id="b" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": task.task_key,
            "outcome": POSITIVE_OUTCOME,
            "legal_block_ids_accounted": 35,
            "canonical_candidates_visited": 15,
            "node_expansions": 1,
            "checkpoint_count": 1,
            "existence_established_in_cyclic_scope": True,
        },
    )["measurement_system_v2"]
    assert status["phase"] == (
        "PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION"
    )
    assert status["next_consumer"] == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    )
    execution_status = status["prediction_v2_balanced_design_feasibility_execution"]
    assert execution_status["outcome"] == POSITIVE_OUTCOME
    assert execution_status["node_expansions"] == 1
    assert (
        status["prediction_v2_balanced_design_feasibility_result_decision"][
            "requested_capability"
        ]
        is None
    )


def test_supervisor_executes_and_replays_registered_toy_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source()
    for entry in source["source_entries"]:
        destination = tmp_path / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT_DIR / entry["path"], destination)
    contract_destination = (
        tmp_path
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    contract_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT_DIR
        / PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_SOURCE_CONTRACT_PATH,
        contract_destination,
    )
    parents = _preregistration_parents()
    synthetic = build_balanced_design_execution_artifacts(
        source_contract=source,
        inventory=_toy_inventory(),
        execution_id="c" * 64,
        checkpoint_path=tmp_path / "toy-checkpoint.jsonl",
        target_signature=(1, 1, 1),
        profiles=((1, 0),),
        node_budget=100,
        checkpoint_interval=10,
        require_formal_identity=False,
        require_registered_identities=False,
        **parents,
    )
    for key, digest in zip(
        (
            "preregistration",
            "execution_handoff",
            "preregistration_completion",
            "preregistration_mainline_execution",
        ),
        (
            PREREGISTRATION_DIGEST,
            EXECUTION_HANDOFF_DIGEST,
            PREREGISTRATION_COMPLETION_DIGEST,
            PREREGISTRATION_MAINLINE_EXECUTION_DIGEST,
        ),
        strict=True,
    ):
        parents[key]["artifact_digest"] = digest
    parent_by_type = {
        "prediction_v2_balanced_design_feasibility_preregistration": parents[
            "preregistration"
        ],
        "prediction_v2_balanced_design_feasibility_execution_handoff": parents[
            "execution_handoff"
        ],
        "prediction_v2_balanced_design_feasibility_preregistration_completion": (
            parents["preregistration_completion"]
        ),
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, parents["preregistration_mainline_execution"], []),
    )
    original_load_type = supervisor_module._load_registered_type

    def load_type(*, artifact_type: str, **kwargs: object) -> dict:
        if artifact_type in parent_by_type:
            return parent_by_type[artifact_type]
        return original_load_type(artifact_type=artifact_type, **kwargs)

    monkeypatch.setattr(supervisor_module, "_load_registered_type", load_type)
    monkeypatch.setattr(
        supervisor_module,
        "build_balanced_design_execution_artifacts",
        lambda **_: synthetic,
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_EXECUTION_TASK_KEY
    )
    result = PredictionV2BalancedDesignFeasibilityExecutionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert len(result.registrations) == 4
    assert result.execution_artifact["outcome"] == POSITIVE_OUTCOME
    assert result.execution_artifact["repetition_scan"] == REPETITION_SCAN
    assert result.execution_artifact["downstream_consumer"] == (
        PREDICTION_V2_BALANCED_DESIGN_FEASIBILITY_RESULT_DECISION_TASK_KEY
    )

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "c" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 4],
                    ],
                }
            ]

        def list_mainline_artifacts(self, **_: object) -> list[dict]:
            return [asdict(item) for item in result.registrations]

    monkeypatch.setattr(
        supervisor_module,
        "replay_balanced_design_execution",
        lambda **_: {
            "status": "REPLAY_VERIFIED",
            "same_registered_content": True,
            "workload_rerun": False,
            "solver_nodes_replayed": 0,
            "certificate_verified": True,
        },
    )
    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(task_key=task.task_key, execution_id="c" * 64)
    assert replay["capability_replay"]["status"] == "REPLAY_VERIFIED"
    assert replay["capability_replay"]["workload_rerun"] is False
    assert replay["capability_replay"]["solver_nodes_replayed"] == 0
