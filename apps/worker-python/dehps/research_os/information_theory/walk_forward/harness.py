from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.probes import prepare_probe

from .artifacts import aggregate_settlements, build_run_artifact, settle_fold
from .checkpoint import build_prediction_checkpoint, persist_prediction_checkpoint
from .contracts import (
    FROZEN_METRIC_KERNEL_DIGEST,
    HarnessManifest,
    SyntheticDataset,
)
from .dataset import restrict_to_training_history, reveal_target
from .errors import WalkForwardError
from .feature_view import (
    build_blind_test_feature_view,
    build_train_feature_view,
    fold_feature_view_digest,
)
from .leakage import (
    guard_dataset_identity,
    guard_feature_timestamp,
    guard_number_event_rows,
    guard_train_test_overlap,
)
from .manifest import preprocessing_manifest_digest, probe_manifest_digest
from .split import build_fold_identity, expanding_outer_folds, validate_outer_fold


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise WalkForwardError("invalid_run_state", f"{path} is not an object")
    return value


def _persist_immutable(
    path: Path,
    payload: Mapping[str, Any],
    *,
    collision_code: str,
) -> None:
    if path.exists():
        if _load_json(path) != payload:
            raise WalkForwardError(collision_code, f"immutable artifact differs: {path}")
        return
    _write_json(path, payload)


def _run_identity(
    *,
    dataset: SyntheticDataset,
    manifest: HarnessManifest,
    probe_id: str,
    probe_digest: str,
    test_issues: tuple[int, ...],
    git_commit: str,
) -> str:
    return canonical_digest(
        {
            "dataset_digest": dataset.artifact_digest,
            "harness_manifest_digest": manifest.artifact_digest,
            "probe_id": probe_id,
            "probe_manifest_digest": probe_digest,
            "test_issues": list(test_issues),
            "outer_mode": "expanding_window",
            "test_horizon": 1,
            "seed_policy": dict(dataset.seed_policy),
            "replicate_seed": dataset.replicate_seed,
            "git_commit": git_commit,
        },
        domain="dehps.m4.walk-forward.run-identity.v1",
    )


def run_walk_forward(
    *,
    dataset: SyntheticDataset,
    manifest: HarnessManifest,
    probe_id: str,
    output_dir: Path,
    git_commit: str,
    working_tree_clean: bool,
    dataset_path: Path | None = None,
    manifest_path: Path | None = None,
    execution_order: Literal["forward", "reverse"] = "forward",
    worker_count: int = 1,
    stop_after: int | None = None,
) -> dict[str, Any]:
    if not working_tree_clean:
        raise WalkForwardError(
            "dirty_worktree", "formal P2.3 smoke requires a clean worktree"
        )
    if worker_count < 1:
        raise WalkForwardError("invalid_worker_count", "worker_count must be positive")
    if dataset.minimum_training_length != manifest.minimum_training_issues:
        raise WalkForwardError(
            "minimum_training_contract_mismatch",
            "dataset and preregistration minimum training lengths differ",
        )
    all_folds = expanding_outer_folds(dataset)
    selected = all_folds[: manifest.smoke_outer_fold_count]
    if len(selected) > 3:
        raise WalkForwardError(
            "large_synthetic_run_forbidden", "P2.3 smoke may use at most three folds"
        )
    probe_digest = probe_manifest_digest(manifest, probe_id=probe_id)
    preprocessor_manifest = preprocessing_manifest_digest(manifest)
    test_issues = tuple(fold.test_issue for fold in selected)
    run_digest = _run_identity(
        dataset=dataset,
        manifest=manifest,
        probe_id=probe_id,
        probe_digest=probe_digest,
        test_issues=test_issues,
        git_commit=git_commit,
    )
    run_dir = output_dir / "runs" / run_digest
    state_path = run_dir / "state.json"
    state: dict[str, Any]
    if state_path.exists():
        state = _load_json(state_path)
        expected = {
            "run_digest": run_digest,
            "dataset_digest": dataset.artifact_digest,
            "harness_manifest_digest": manifest.artifact_digest,
            "probe_id": probe_id,
            "probe_manifest_digest": probe_digest,
        }
        if any(state.get(key) != value for key, value in expected.items()):
            raise WalkForwardError(
                "run_resume_identity_mismatch", "resume inputs changed"
            )
    else:
        state = {
            "status": "RUNNING",
            "run_digest": run_digest,
            "dataset_digest": dataset.artifact_digest,
            "harness_manifest_digest": manifest.artifact_digest,
            "probe_id": probe_id,
            "probe_manifest_digest": probe_digest,
            "test_issues": list(test_issues),
            "completed": {},
            "failures": {},
            "dataset_path": None if dataset_path is None else str(dataset_path),
            "manifest_path": None if manifest_path is None else str(manifest_path),
            "git_commit": git_commit,
            "worker_count_contract": "scheduling_does_not_change_artifacts",
        }
        _write_json(state_path, state)
    fold_sequence = list(selected)
    if execution_order == "reverse":
        fold_sequence.reverse()
    processed_this_call = 0
    for fold in fold_sequence:
        test_key = str(fold.test_issue)
        if test_key in state["completed"] or test_key in state["failures"]:
            continue
        validate_outer_fold(
            fold,
            minimum_training_issues=manifest.minimum_training_issues,
            dataset_issue_count=dataset.issue_count,
        )
        guard_train_test_overlap(fold)
        training_dataset = restrict_to_training_history(
            dataset, available_through_issue=fold.train_issues[-1]
        )
        train_view = build_train_feature_view(
            training_dataset, fold.train_issues
        )
        blind_view = build_blind_test_feature_view(
            dataset, target_issue=fold.test_issue
        )
        guard_feature_timestamp(blind_view)
        guard_number_event_rows(
            issue_ids=train_view.issue_ids,
            red_numbers=train_view.red_numbers,
        )
        fold_feature_digest = fold_feature_view_digest(train_view, blind_view)
        feature_view_payload = {
            "schema_version": "dehps-m4-information-theory-feature-view.v1",
            "artifact_type": "fold_feature_view_identity",
            "feature_view_digest": fold_feature_digest,
            "feature_manifest_digest": train_view.feature_manifest_digest,
            "dataset_digest": dataset.artifact_digest,
            "train_view": {
                "feature_view_digest": train_view.feature_view_digest,
                "issue_ids": list(train_view.issue_ids),
                "available_through_by_issue": [
                    list(item) for item in train_view.available_through_by_issue
                ],
                "construction_start_issue": train_view.construction_start_issue,
                "construction_end_issue": train_view.construction_end_issue,
                "feature_names": list(train_view.feature_names),
                "target_access": "outer_training_targets_only",
            },
            "blind_test_view": {
                "feature_view_digest": blind_view.feature_view_digest,
                "target_issue": blind_view.target_issue,
                "available_through_issue": blind_view.available_through_issue,
                "construction_start_issue": blind_view.construction_start_issue,
                "construction_end_issue": blind_view.construction_end_issue,
                "feature_names": list(blind_view.feature_names),
                "red_numbers": list(blind_view.red_numbers),
                "target_access": "forbidden",
            },
            "parent_digests": [
                dataset.artifact_digest,
                train_view.feature_manifest_digest,
                train_view.feature_view_digest,
                blind_view.feature_view_digest,
            ],
        }
        feature_view_path = (
            output_dir
            / "feature-views"
            / fold_feature_digest
            / "feature-view.json"
        )
        _persist_immutable(
            feature_view_path,
            feature_view_payload,
            collision_code="feature_view_collision",
        )
        try:
            prepared = prepare_probe(
                probe_id=probe_id,
                dataset=training_dataset,
                train_view=train_view,
                probe_config=manifest.probe(probe_id),
                outer_test_issue=fold.test_issue,
            )
            if (
                prepared.state.training_end_issue is not None
                and prepared.state.training_end_issue > fold.train_issues[-1]
            ):
                raise WalkForwardError(
                    "probe_training_range_violation",
                    "probe training reaches beyond outer train",
                )
            probe_state_payload = {
                "schema_version": "dehps-m4-information-theory-probe-state.v1",
                "artifact_type": "immutable_probe_state",
                **prepared.state.to_dict(),
                "parent_digests": [
                    dataset.artifact_digest,
                    train_view.feature_manifest_digest,
                    probe_digest,
                    prepared.state.hyperparameter_selection_digest,
                    prepared.state.model_parameters_digest,
                ],
            }
            probe_state_path = (
                output_dir
                / "probe-states"
                / prepared.state.state_digest
                / "probe-state.json"
            )
            _persist_immutable(
                probe_state_path,
                probe_state_payload,
                collision_code="probe_state_collision",
            )
            preprocessing_state_path: Path | None = None
            preprocessor = getattr(prepared, "preprocessor", None)
            if preprocessor is not None:
                preprocessing_state_payload = {
                    "schema_version": "dehps-m4-information-theory-preprocessing-state.v1",
                    "artifact_type": "immutable_preprocessing_state",
                    **preprocessor.state.to_dict(),
                    "parent_digests": [
                        dataset.artifact_digest,
                        train_view.feature_manifest_digest,
                        preprocessor_manifest,
                    ],
                }
                preprocessing_state_path = (
                    output_dir
                    / "preprocessing-states"
                    / preprocessor.state.state_digest
                    / "preprocessing-state.json"
                )
                _persist_immutable(
                    preprocessing_state_path,
                    preprocessing_state_payload,
                    collision_code="preprocessing_state_collision",
                )
            fold_identity = build_fold_identity(
                dataset_digest=dataset.artifact_digest,
                fold=fold,
                feature_view_digest=fold_feature_digest,
                preprocessing_manifest_digest=preprocessor_manifest,
                probe_manifest_digest=probe_digest,
            )
            fold_payload = fold_identity.to_dict()
            fold_payload["parent_digests"] = [
                dataset.artifact_digest,
                manifest.artifact_digest,
                train_view.feature_manifest_digest,
                train_view.feature_view_digest,
                blind_view.feature_view_digest,
                fold_feature_digest,
                preprocessor_manifest,
                probe_digest,
            ]
            fold_path = (
                output_dir
                / "folds"
                / fold_identity.fold_digest
                / "fold-manifest.json"
            )
            _persist_immutable(
                fold_path,
                fold_payload,
                collision_code="fold_identity_collision",
            )
            probabilities = prepared.predict(blind_view)
            checkpoint = build_prediction_checkpoint(
                fold=fold_identity,
                probe_state=prepared.state,
                probabilities=probabilities,
                probe_manifest_digest=probe_digest,
                scenario=dataset.scenario_id,
                created_at=manifest.created_at,
                git_commit=git_commit,
                working_tree_clean=working_tree_clean,
            )
            checkpoint_path = persist_prediction_checkpoint(
                checkpoint, output_dir=output_dir
            )
            # This is the first legal target access after the immutable checkpoint exists.
            guard_dataset_identity(
                dataset, expected_digest=fold_identity.dataset_digest
            )
            target = reveal_target(
                dataset,
                test_issue=fold.test_issue,
                prediction_checkpoint=checkpoint,
            )
            settlement = settle_fold(
                fold=fold_identity,
                prediction_checkpoint=checkpoint,
                target_vector=target,
                metric_kernel_digest=FROZEN_METRIC_KERNEL_DIGEST,
            )
            settlement_path = (
                output_dir
                / "settlements"
                / settlement["artifact_digest"]
                / "settlement.json"
            )
            _persist_immutable(
                settlement_path,
                settlement,
                collision_code="fold_settlement_collision",
            )
            state["completed"][test_key] = {
                "fold_digest": fold_identity.fold_digest,
                "fold_path": str(fold_path),
                "feature_view_digest": fold_feature_digest,
                "feature_view_path": str(feature_view_path),
                "prediction_digest": checkpoint["artifact_digest"],
                "prediction_path": str(checkpoint_path),
                "settlement_digest": settlement["artifact_digest"],
                "settlement_path": str(settlement_path),
                "probe_state_digest": prepared.state.state_digest,
                "probe_state_path": str(probe_state_path),
                "preprocessing_state_digest": prepared.state.preprocessing_state_digest,
                "preprocessing_state_path": (
                    None
                    if preprocessing_state_path is None
                    else str(preprocessing_state_path)
                ),
                "convergence_status": prepared.state.convergence_status,
            }
        except WalkForwardError as exc:
            if exc.code in {
                "FAILED_CONVERGENCE",
                "INSUFFICIENT_CLASS_VARIATION",
                "INVALID_FEATURE_MATRIX",
            }:
                failure = {
                    "test_issue": fold.test_issue,
                    "code": exc.code,
                    "message": exc.message,
                    "fallback_used": False,
                    "silently_deleted": False,
                }
                failure["failure_digest"] = canonical_digest(
                    failure, domain="dehps.m4.walk-forward.fold-failure.v1"
                )
                state["failures"][test_key] = failure
            else:
                raise
        _write_json(state_path, state)
        processed_this_call += 1
        if stop_after is not None and processed_this_call >= stop_after:
            state["status"] = "INTERRUPTED"
            _write_json(state_path, state)
            return state
    settlement_records = [
        _load_json(Path(item["settlement_path"]))
        for _, item in sorted(
            state["completed"].items(), key=lambda pair: int(pair[0])
        )
    ]
    failures = [
        item
        for _, item in sorted(state["failures"].items(), key=lambda pair: int(pair[0]))
    ]
    aggregate = aggregate_settlements(
        settlement_records,
        failed_folds=failures,
        fallback_fold_count=0,
    )
    completed_records = [
        item
        for _, item in sorted(
            state["completed"].items(), key=lambda pair: int(pair[0])
        )
    ]
    artifact = build_run_artifact(
        run_digest=run_digest,
        dataset_digest=dataset.artifact_digest,
        harness_manifest_digest=manifest.artifact_digest,
        probe_id=probe_id,
        probe_manifest_digest=probe_digest,
        fold_digests=[item["fold_digest"] for item in completed_records],
        probe_state_digests=[
            item["probe_state_digest"] for item in completed_records
        ],
        preprocessing_state_digests=sorted(
            {
                item["preprocessing_state_digest"]
                for item in completed_records
                if item["preprocessing_state_digest"] != "none"
            }
        ),
        prediction_digests=[item["prediction_digest"] for item in completed_records],
        settlement_digests=[item["settlement_digest"] for item in completed_records],
        aggregate=aggregate,
        git_commit=git_commit,
        created_at=manifest.created_at,
        seed_policy={
            "dataset_seed_policy": dict(dataset.seed_policy),
            "replicate_seed": dataset.replicate_seed,
        },
    )
    artifact_path = run_dir / "run-artifact.json"
    _persist_immutable(
        artifact_path,
        artifact,
        collision_code="run_artifact_collision",
    )
    state["status"] = (
        "COMPLETED" if not failures else "COMPLETED_WITH_FAILURES"
    )
    state["artifact_digest"] = artifact["artifact_digest"]
    state["artifact_path"] = str(artifact_path)
    state["aggregate"] = aggregate
    _write_json(state_path, state)
    return artifact


def resume_walk_forward(
    *,
    run_digest: str,
    output_dir: Path,
    dataset: SyntheticDataset,
    manifest: HarnessManifest,
    git_commit: str,
    working_tree_clean: bool,
) -> dict[str, Any]:
    state_path = output_dir / "runs" / run_digest / "state.json"
    if not state_path.exists():
        raise WalkForwardError("walk_forward_run_not_found", run_digest)
    state = _load_json(state_path)
    if state.get("run_digest") != run_digest:
        raise WalkForwardError(
            "run_resume_identity_mismatch", "run digest changed"
        )
    return run_walk_forward(
        dataset=dataset,
        manifest=manifest,
        probe_id=str(state["probe_id"]),
        output_dir=output_dir,
        git_commit=git_commit,
        working_tree_clean=working_tree_clean,
    )


def inspect_fold(*, fold_digest: str, output_dir: Path) -> dict[str, Any]:
    path = output_dir / "folds" / fold_digest / "fold-manifest.json"
    if not path.exists():
        raise WalkForwardError("walk_forward_fold_not_found", fold_digest)
    return _load_json(path)


def show_run(*, run_digest: str, output_dir: Path) -> dict[str, Any]:
    path = output_dir / "runs" / run_digest / "run-artifact.json"
    if not path.exists():
        raise WalkForwardError("walk_forward_run_not_found", run_digest)
    return _load_json(path)
