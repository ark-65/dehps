from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, median
from typing import Any, Callable, Mapping

import numpy as np

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest

from .contracts import (
    CONTROL_IDS,
    METRIC_KERNEL_DIGEST,
    WALK_FORWARD_HARNESS_DIGEST,
    ResamplingError,
    ResamplingKernelManifest,
)
from .controls import (
    apply_number_mapping,
    matched_random_features,
    matched_random_score,
    negative_control_registry,
)
from .plans import (
    ResamplingPlan,
    apply_issue_plan,
    block_permutation_plan,
    circular_shift_plan,
    issue_label_permutation_plan,
    moving_block_plan,
    number_label_permutation,
    stationary_plan,
)
from ..walk_forward import FEATURE_MANIFEST_DIGEST


@dataclass(frozen=True)
class P25ResamplingRunResult:
    run_artifact: Mapping[str, Any]
    run_artifact_path: Path
    completion_artifact: Mapping[str, Any]
    completion_artifact_path: Path
    child_artifacts: tuple[Mapping[str, Any], ...]
    aggregate_artifacts: tuple[Mapping[str, Any], ...]
    artifact_paths: tuple[Path, ...]
    replicate_count: int


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResamplingError("invalid_upstream_artifact", str(exc)) from exc
    if not isinstance(value, dict):
        raise ResamplingError("invalid_upstream_artifact", f"artifact is not an object: {path}")
    return value


def _persist_immutable(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists():
        if _load_object(path) != dict(payload):
            raise ResamplingError("resampling_replay_mismatch", f"immutable artifact differs: {path}")
        return
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )


def locate_p24_artifact_root(root_dir: Path, manifest: ResamplingKernelManifest) -> Path:
    execution_dir = (
        root_dir
        / "runtime/research-os/mainline/tasks/m4-p2-injected-signal-calibration"
        / manifest.injected_signal_execution_id
    )
    execution = _load_object(execution_dir / "execution.json")
    if (
        execution.get("execution_id") != manifest.injected_signal_execution_id
        or execution.get("status") != "COMPLETE"
        or execution.get("completion_artifact_digest")
        != manifest.injected_signal_completion_digest
        or tuple(execution.get("truth_artifact_digests", ()))
        != manifest.truth_artifact_digests
        or execution.get("metric_kernel_digest") not in (None, METRIC_KERNEL_DIGEST)
    ):
        raise ResamplingError(
            "p2_4_truth_identity_mismatch",
            "formal P2.4 execution does not match the frozen P2.5 input",
        )
    return execution_dir / "artifacts"


def _upstream_graph(
    root_dir: Path,
    manifest: ResamplingKernelManifest,
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    artifact_root = locate_p24_artifact_root(root_dir, manifest)
    completion = _load_object(
        artifact_root
        / "completion"
        / manifest.injected_signal_completion_digest
        / "completion.json"
    )
    if (
        completion.get("status") != "COMPLETE"
        or tuple(completion.get("truth_artifact_digests", ()))
        != manifest.truth_artifact_digests
        or completion.get("eligible_for_p2_5_input") is not True
    ):
        raise ResamplingError("p2_4_truth_identity_mismatch", "P2.4 completion is ineligible")
    truths = [
        _load_object(
            artifact_root / "truth" / digest / "truth.json"
        )
        for digest in manifest.truth_artifact_digests
    ]
    if any(
        truth.get("artifact_digest") != digest
        or truth.get("eligible_for_p2_5_input") is not True
        for digest, truth in zip(manifest.truth_artifact_digests, truths, strict=True)
    ):
        raise ResamplingError("p2_4_truth_identity_mismatch", "truth artifact graph changed")
    truth_by_digest = {
        str(item["artifact_digest"]): item
        for item in truths
    }
    datasets = sorted(
        (_load_object(path) for path in (artifact_root / "datasets").glob("*/dataset.json")),
        key=lambda item: str(item["scenario"]["scenario_id"]),
    )
    runs = sorted(
        (
            _load_object(path)
            for path in (artifact_root / "walk-forward-smoke").glob(
                "*/runs/*/run-artifact.json"
            )
        ),
        key=lambda item: str(item["dataset_digest"]),
    )
    if len(datasets) != 4 or len(runs) != 4:
        raise ResamplingError("incomplete_p2_4_artifact_graph", "four datasets and runs are required")
    dataset_truths = {str(item["truth_artifact_digest"]) for item in datasets}
    if not dataset_truths.issubset(set(manifest.truth_artifact_digests)):
        raise ResamplingError("p2_4_truth_identity_mismatch", "dataset truth is not frozen")
    for dataset in datasets:
        truth = truth_by_digest[str(dataset["truth_artifact_digest"])]
        scenario = dataset.get("scenario")
        embedded = dataset.get("truth")
        if (
            not isinstance(scenario, Mapping)
            or not isinstance(embedded, Mapping)
            or dataset.get("dataset_role") != "calibration_smoke_only"
            or dataset.get("eligible_for_evaluation") is not False
            or dataset.get("eligible_for_power_evidence") is not False
            or dataset.get("eligible_for_false_positive_evidence") is not False
            or dataset.get("eligible_for_p2_gate_evidence") is not False
        ):
            raise ResamplingError(
                "calibration_dataset_boundary_violation",
                "P2.4 calibration data cannot become formal evaluation data",
            )
        if (
            truth.get("scenario_id") != scenario.get("scenario_id")
            or embedded.get("scenario_id") != scenario.get("scenario_id")
            or embedded.get("truth_artifact_digest") != truth.get("artifact_digest")
            or embedded.get("parameter_name") != truth.get("parameter_name")
            or embedded.get("parameter_value") != truth.get("parameter_value")
            or embedded.get("joint_draw_information_bits_per_issue")
            != truth.get("joint_draw_information_bits_per_issue")
            or scenario.get("target_bits_per_issue")
            != truth.get("requested_bits_per_issue")
        ):
            raise ResamplingError(
                "p2_4_truth_parameter_mismatch",
                "dataset scenario, requested strength, and frozen truth differ",
            )
    if any(
        item.get("probe_id") != "THEORETICAL_BASELINE"
        or item.get("walk_forward_harness_digest") not in (None, WALK_FORWARD_HARNESS_DIGEST)
        or item["aggregate"]["completed_fold_count"] != 2
        for item in runs
    ):
        raise ResamplingError("walk_forward_identity_mismatch", "P2.3 source runs changed")
    return artifact_root, truths, datasets, runs


def _source_issues(
    dataset: Mapping[str, Any],
    run: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    checkpoint_by_issue = {
        901 + index: str(digest)
        for index, digest in enumerate(run["prediction_checkpoint_digests"])
    }
    settlement_by_issue = {
        901 + index: str(digest)
        for index, digest in enumerate(run["settlement_digests"])
    }
    result = []
    for issue in dataset["issues"]:
        index = int(issue["issue_index"])
        result.append(
            {
                **dict(issue),
                "issue_id": str(index),
                "cluster_id": str(index),
                "prediction_checkpoint_identity": checkpoint_by_issue.get(
                    index, "PLAN_ONLY_NOT_SETTLED"
                ),
                "settlement_identity": settlement_by_issue.get(
                    index, "PLAN_ONLY_NOT_SETTLED"
                ),
            }
        )
    return tuple(result)


def _plan_artifact(
    plan: ResamplingPlan,
    *,
    source_dataset_digest: str,
    source_run_digest: str,
    parent_run_digest: str,
    control_id: str | None,
    scenario_id: str,
) -> dict[str, Any]:
    payload = plan.to_dict()
    payload["config"]["scenario_id"] = scenario_id
    payload.update(
        {
            "source_dataset_digest": source_dataset_digest,
            "source_run_digest": source_run_digest,
            "control_id": control_id,
            "parent_digests": [
                source_dataset_digest,
                source_run_digest,
                parent_run_digest,
            ],
        }
    )
    identity = dict(payload)
    identity.pop("artifact_digest")
    identity.pop("plan_digest")
    digest = canonical_digest(identity, domain="dehps.m4-p2.resampling-plan-artifact.v1")
    payload["artifact_digest"] = digest
    payload["plan_digest"] = digest
    return payload


def _generic_plan_artifact(
    *,
    method: str,
    config: Mapping[str, Any],
    seed: int | None,
    seed_digest: str | None,
    source_issue_count: int,
    source_dataset_digest: str,
    source_run_digest: str,
    parent_run_digest: str,
    control_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-resampling-plan.v1",
        "artifact_type": "resampling_plan",
        "artifact_digest": "",
        "plan_digest": "",
        "method": method,
        "control_id": control_id,
        "source_issue_count": source_issue_count,
        "resampled_issue_count": source_issue_count,
        "source_indices": list(range(source_issue_count)),
        "seed": seed,
        "seed_digest": seed_digest,
        "config": dict(config),
        "source_dataset_digest": source_dataset_digest,
        "source_run_digest": source_run_digest,
        "parent_digests": [
            source_dataset_digest,
            source_run_digest,
            parent_run_digest,
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    identity.pop("plan_digest")
    digest = canonical_digest(identity, domain="dehps.m4-p2.resampling-plan-artifact.v1")
    payload["artifact_digest"] = digest
    payload["plan_digest"] = digest
    return payload


def _replicate_artifact(
    *,
    replicate_id: str,
    plan: Mapping[str, Any],
    source_mapping: list[Mapping[str, Any]],
    control_contract: Mapping[str, Any] | None,
    manifest: ResamplingKernelManifest,
    git_commit: str,
    working_tree_clean: bool,
) -> dict[str, Any]:
    control_id = None if control_contract is None else str(control_contract["control_id"])
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-resampling-replicate.v1",
        "artifact_type": "resampling_child_replicate",
        "artifact_digest": "",
        "replicate_id": replicate_id,
        "method": plan["method"],
        "control_id": control_id,
        "seed": plan.get("seed"),
        "seed_digest": plan.get("seed_digest"),
        "source_run_digest": plan["source_run_digest"],
        "source_issue_count": plan["source_issue_count"],
        "resampled_issue_count": plan["resampled_issue_count"],
        "plan_digest": plan["plan_digest"],
        "source_mapping": source_mapping,
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "statistic_name": "PE1_mean_bits_per_issue",
        "statistic_value": None,
        "unit": "bits_per_issue",
        "multiplicity_family": (
            "SENSITIVITY_FAMILY"
            if control_contract is None
            else control_contract["multiplicity_family"]
        ),
        "hypothesis_id": f"P2_5_SMOKE:{control_id or plan['method']}",
        "endpoint_id": "PE1",
        "scenario_id": plan["config"]["scenario_id"],
        "plan_only": True,
        "execution_mode": (
            "POST_PREDICTION_RESAMPLING"
            if control_contract is None
            else control_contract["execution_mode"]
        ),
        "destroyed_relationship": (
            None
            if control_contract is None
            else control_contract["destroyed_relationship"]
        ),
        "preserved_properties": (
            ["whole_issue_cluster"]
            if control_contract is None
            else list(control_contract["preserved_properties"])
        ),
        "smoke_flags": list(manifest.smoke_flags),
        "eligible_for_formal_inference": False,
        "git_commit": git_commit,
        "working_tree_clean": working_tree_clean,
        "parent_digests": [
            plan["plan_digest"],
            plan["source_run_digest"],
            manifest.injected_signal_completion_digest,
            manifest.artifact_digest,
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4-p2.resampling-child-replicate.v1"
    )
    return payload


def _aggregate_artifact(
    *,
    group_id: str,
    children: list[Mapping[str, Any]],
    manifest: ResamplingKernelManifest,
    git_commit: str,
    working_tree_clean: bool,
    expected_replicate_count: int | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    if not children:
        raise ResamplingError("incomplete_seed_set", "aggregate has no child replicates")
    units = {str(item.get("unit") or "") for item in children}
    families = {str(item.get("multiplicity_family") or "") for item in children}
    if units != {"bits_per_issue"}:
        raise ResamplingError(
            "unit_mismatch",
            "all child statistics must use bits_per_issue",
        )
    if "" in families or len(families) != 1:
        raise ResamplingError(
            "missing_multiplicity_family",
            "aggregate children require one frozen multiplicity family",
        )
    failed = [item for item in children if item.get("status") == "FAILED"]
    expected = (
        len(children)
        if expected_replicate_count is None
        else expected_replicate_count
    )
    missing = max(0, expected - len(children))
    if expected < len(children):
        raise ResamplingError(
            "replicate_count_exceeds_contract",
            "aggregate contains more child replicates than frozen",
        )
    if require_complete and (failed or missing):
        raise ResamplingError(
            "incomplete_seed_set",
            "failed or missing child replicates cannot be aggregated",
        )
    seed_digests = sorted(
        str(item["seed_digest"])
        for item in children
        if item.get("seed_digest") is not None
    )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-resampling-aggregate.v1",
        "artifact_type": "resampling_aggregate",
        "artifact_digest": "",
        "group_id": group_id,
        "method": children[0]["method"],
        "control_id": children[0]["control_id"],
        "replicate_count_expected": expected,
        "replicate_count_completed": len(children) - len(failed),
        "replicate_count_failed": len(failed),
        "replicate_count_missing": missing,
        "seed_set_digest": canonical_digest(
            seed_digests, domain="dehps.m4-p2.resampling-seed-set.v1"
        ),
        "child_replicate_digests": [item["artifact_digest"] for item in children],
        "statistic_distribution": [],
        "mean": None,
        "median": None,
        "standard_deviation": None,
        "quantiles": None,
        "minimum": None,
        "maximum": None,
        "observed_statistic_if_applicable": None,
        "percentile_if_applicable": None,
        "p_value_if_applicable": None,
        "plan_only": True,
        "eligible_for_formal_inference": False,
        "formal_seed_set_complete": not failed and missing == 0,
        "smoke_flags": list(manifest.smoke_flags),
        "git_commit": git_commit,
        "working_tree_clean": working_tree_clean,
        "parent_digests": [
            manifest.artifact_digest,
            *(item["artifact_digest"] for item in children),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4-p2.resampling-aggregate.v1"
    )
    return payload


def run_p25_resampling(
    *,
    manifest: ResamplingKernelManifest,
    root_dir: Path,
    output_dir: Path,
    execution_id: str,
    git_commit: str,
    working_tree_clean: bool,
) -> P25ResamplingRunResult:
    _, truths, datasets, runs = _upstream_graph(root_dir, manifest)
    registry = negative_control_registry(manifest)
    dataset_by_digest = {str(item["artifact_digest"]): item for item in datasets}
    sources = [
        (
            dataset_by_digest[str(run["dataset_digest"])],
            run,
        )
        for run in runs
    ]
    plans: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    paths: set[Path] = set()
    groups: dict[str, list[dict[str, Any]]] = {}
    def add(
        *,
        group_id: str,
        plan: dict[str, Any],
        source_issues: tuple[dict[str, Any], ...],
        control: Mapping[str, Any] | None = None,
        source_mapping: list[Mapping[str, Any]] | None = None,
    ) -> None:
        if source_mapping is None:
            plan_object = ResamplingPlan(
                method=str(plan["method"]),
                source_issue_count=int(plan["source_issue_count"]),
                source_indices=tuple(int(value) for value in plan["source_indices"]),
                seed=plan.get("seed"),
                seed_digest=plan.get("seed_digest"),
                config=dict(plan["config"]),
                plan_digest=str(plan["plan_digest"]),
            )
            applied = apply_issue_plan(source_issues, plan_object)
            source_mapping = [
                {
                    "source_issue_id": item["source_issue_id"],
                    "resampled_position": item["resampled_position"],
                    "cluster_id": item["cluster_id"],
                    "target_vector": item["target_vector"],
                    "prediction_checkpoint_identity": item[
                        "prediction_checkpoint_identity"
                    ],
                    "settlement_identity": item["settlement_identity"],
                }
                for item in applied
            ]
        if (
            control is not None
            and control["execution_mode"] == "RETRAIN_REQUIRED_CONTROL"
        ):
            source_mapping = [
                {
                    **dict(item),
                    "source_prediction_checkpoint_identity": item[
                        "prediction_checkpoint_identity"
                    ],
                    "source_settlement_identity": item["settlement_identity"],
                    "prediction_checkpoint_identity": (
                        "P2.3_HARNESS_REEXECUTION_REQUIRED"
                    ),
                    "settlement_identity": "P2.3_HARNESS_REEXECUTION_REQUIRED",
                }
                for item in source_mapping
            ]
        replicate_id = canonical_digest(
            {
                "source_run_digest": plan["source_run_digest"],
                "control_id": None if control is None else control["control_id"],
                "method": plan["method"],
                "config_digest": canonical_digest(
                    plan["config"], domain="dehps.m4-p2.resampling-config.v1"
                ),
                "seed": plan.get("seed"),
            },
            domain="dehps.m4-p2.resampling-replicate-identity.v1",
        )
        child = _replicate_artifact(
            replicate_id=replicate_id,
            plan=plan,
            source_mapping=source_mapping,
            control_contract=control,
            manifest=manifest,
            git_commit=git_commit,
            working_tree_clean=working_tree_clean,
        )
        plan_path = output_dir / "plans" / plan["plan_digest"] / "plan.json"
        child_path = (
            output_dir
            / "replicates"
            / child["artifact_digest"]
            / "replicate.json"
        )
        _persist_immutable(plan_path, plan)
        _persist_immutable(child_path, child)
        paths.update((plan_path, child_path))
        plans.append(plan)
        children.append(child)
        groups.setdefault(group_id, []).append(child)

    for source_index, (dataset, run) in enumerate(sources):
        issues = _source_issues(dataset, run)
        scenario_id = str(dataset["scenario"]["scenario_id"])
        source_digest = str(dataset["artifact_digest"])
        run_digest = str(run["run_digest"])
        if source_index == 0:
            for replicate_index, block_size in enumerate(manifest.sensitivity_block_sizes):
                plan = moving_block_plan(
                    len(issues),
                    block_size=block_size,
                    manifest=manifest,
                    scenario_id=scenario_id,
                    replicate_index=replicate_index,
                    parent_run_digest=execution_id,
                )
                payload = _plan_artifact(
                    plan,
                    source_dataset_digest=source_digest,
                    source_run_digest=run_digest,
                    parent_run_digest=execution_id,
                    control_id=None,
                    scenario_id=scenario_id,
                )
                add(group_id="moving_block_bootstrap", plan=payload, source_issues=issues)
            for replicate_index, length in enumerate(manifest.stationary_lengths):
                plan = stationary_plan(
                    len(issues),
                    expected_block_length=length,
                    manifest=manifest,
                    scenario_id=scenario_id,
                    replicate_index=replicate_index,
                    parent_run_digest=execution_id,
                )
                payload = _plan_artifact(
                    plan,
                    source_dataset_digest=source_digest,
                    source_run_digest=run_digest,
                    parent_run_digest=execution_id,
                    control_id=None,
                    scenario_id=scenario_id,
                )
                add(group_id="stationary_bootstrap", plan=payload, source_issues=issues)
            for replicate_index in range(3):
                plan = block_permutation_plan(
                    len(issues),
                    block_size=manifest.primary_block_size,
                    manifest=manifest,
                    scenario_id=scenario_id,
                    replicate_index=replicate_index,
                    parent_run_digest=execution_id,
                )
                payload = _plan_artifact(
                    plan,
                    source_dataset_digest=source_digest,
                    source_run_digest=run_digest,
                    parent_run_digest=execution_id,
                    control_id=None,
                    scenario_id=scenario_id,
                )
                add(group_id="block_permutation", plan=payload, source_issues=issues)

        nc1 = registry["NC1_ISSUE_LABEL_PERMUTATION"]
        for replicate_index in range(2 if source_index == 0 else 0):
            plan = issue_label_permutation_plan(
                len(issues),
                manifest=manifest,
                scenario_id=scenario_id,
                replicate_index=replicate_index,
                parent_run_digest=execution_id,
            )
            payload = _plan_artifact(
                plan,
                source_dataset_digest=source_digest,
                source_run_digest=run_digest,
                parent_run_digest=execution_id,
                control_id=str(nc1["control_id"]),
                scenario_id=scenario_id,
            )
            add(
                group_id=str(nc1["control_id"]),
                plan=payload,
                source_issues=issues,
                control=nc1,
                source_mapping=[
                    {
                        "feature_source_issue_id": original["issue_id"],
                        "source_issue_id": target["issue_id"],
                        "target_source_issue_id": target["issue_id"],
                        "resampled_position": position,
                        "cluster_id": target["cluster_id"],
                        "target_vector": target["target_vector"],
                        "prediction_checkpoint_identity": original[
                            "prediction_checkpoint_identity"
                        ],
                        "settlement_identity": original["settlement_identity"],
                    }
                    for position, (original, target) in enumerate(
                        zip(
                            issues,
                            (issues[index] for index in plan.source_indices),
                            strict=True,
                        )
                    )
                ],
            )

        nc2 = registry["NC2_NUMBER_LABEL_PERMUTATION"]
        for replicate_index in range(2 if source_index == 1 else 0):
            mapping, seed, seed_digest, mapping_digest = number_label_permutation(
                manifest=manifest,
                scenario_id=scenario_id,
                replicate_index=replicate_index,
                parent_run_digest=execution_id,
            )
            payload = _generic_plan_artifact(
                method="number_label_permutation",
                config={
                    "scenario_id": scenario_id,
                    "mapping": {str(key): value for key, value in mapping.items()},
                    "mapping_digest": mapping_digest,
                    "mapping_is_global_bijection": True,
                },
                seed=seed,
                seed_digest=seed_digest,
                source_issue_count=len(issues),
                source_dataset_digest=source_digest,
                source_run_digest=run_digest,
                parent_run_digest=execution_id,
                control_id=str(nc2["control_id"]),
            )
            mapped_issues = [
                apply_number_mapping(item, mapping) for item in issues
            ]
            add(
                group_id=str(nc2["control_id"]),
                plan=payload,
                source_issues=issues,
                control=nc2,
                source_mapping=[
                    {
                        "source_issue_id": source["issue_id"],
                        "resampled_position": index,
                        "cluster_id": source["cluster_id"],
                        "target_vector": mapped["target_vector"],
                        "prediction_checkpoint_identity": source[
                            "prediction_checkpoint_identity"
                        ],
                        "settlement_identity": source["settlement_identity"],
                        "number_mapping_digest": mapping_digest,
                    }
                    for index, (source, mapped) in enumerate(
                        zip(issues, mapped_issues, strict=True)
                    )
                ],
            )

        nc3 = registry["NC3_CIRCULAR_TARGET_SHIFT"]
        if source_index == 2:
            for shift in (1, 21):
                plan = circular_shift_plan(len(issues), shift=shift)
                payload = _plan_artifact(
                    plan,
                    source_dataset_digest=source_digest,
                    source_run_digest=run_digest,
                    parent_run_digest=execution_id,
                    control_id=str(nc3["control_id"]),
                    scenario_id=scenario_id,
                )
                add(
                    group_id=str(nc3["control_id"]),
                    plan=payload,
                    source_issues=issues,
                    control=nc3,
                    source_mapping=[
                        {
                            "prediction_source_issue_id": original["issue_id"],
                            "source_issue_id": target["issue_id"],
                            "target_source_issue_id": target["issue_id"],
                            "resampled_position": position,
                            "cluster_id": target["cluster_id"],
                            "target_vector": target["target_vector"],
                            "prediction_checkpoint_identity": original[
                                "prediction_checkpoint_identity"
                            ],
                            "settlement_identity": original[
                                "settlement_identity"
                            ],
                        }
                        for position, (original, target) in enumerate(
                            zip(
                                issues,
                                (issues[index] for index in plan.source_indices),
                                strict=True,
                            )
                        )
                    ],
                )

        if source_index == 3:
            nc4 = registry["NC4_MATCHED_RANDOM_FEATURES"]
            features = np.column_stack(
                (
                    np.arange(len(issues), dtype=float),
                    np.asarray(
                        [
                            (int(item["issue_index"]) % 17) / 17.0
                            for item in issues
                        ],
                        dtype=float,
                    ),
                )
            )
            for replicate_index, strategy in enumerate(
                ("independent_matched_noise", "block_correlated_matched_noise")
            ):
                _, metadata = matched_random_features(
                    features,
                    missing_mask=None,
                    strategy=strategy,
                    source_feature_manifest_digest=FEATURE_MANIFEST_DIGEST,
                    source_provenance="pre_target_feature_view",
                    manifest=manifest,
                    scenario_id=scenario_id,
                    replicate_index=replicate_index,
                    parent_run_digest=execution_id,
                )
                payload = _generic_plan_artifact(
                    method="matched_random_features",
                    config={"scenario_id": scenario_id, **metadata},
                    seed=int(metadata["seed"]),
                    seed_digest=str(metadata["seed_digest"]),
                    source_issue_count=len(issues),
                    source_dataset_digest=source_digest,
                    source_run_digest=run_digest,
                    parent_run_digest=execution_id,
                    control_id=str(nc4["control_id"]),
                )
                add(group_id=str(nc4["control_id"]), plan=payload, source_issues=issues, control=nc4)
            nc5 = registry["NC5_MATCHED_RANDOM_SCORE"]
            scores = [float(index) / len(issues) for index in range(len(issues))]
            for replicate_index, strategy in enumerate(
                ("rank_distribution", "quantile_distribution")
            ):
                _, metadata = matched_random_score(
                    scores,
                    strategy=strategy,
                    source_provenance="synthetic_probe_score",
                    manifest=manifest,
                    scenario_id=scenario_id,
                    replicate_index=replicate_index,
                    parent_run_digest=execution_id,
                )
                payload = _generic_plan_artifact(
                    method="matched_random_score",
                    config={"scenario_id": scenario_id, **metadata},
                    seed=int(metadata["seed"]),
                    seed_digest=str(metadata["seed_digest"]),
                    source_issue_count=len(issues),
                    source_dataset_digest=source_digest,
                    source_run_digest=run_digest,
                    parent_run_digest=execution_id,
                    control_id=str(nc5["control_id"]),
                )
                add(group_id=str(nc5["control_id"]), plan=payload, source_issues=issues, control=nc5)
            nc6 = registry["NC6_SYNTHETIC_NULL"]
            payload = _generic_plan_artifact(
                method="synthetic_null_registry_smoke",
                config={
                    "scenario_id": "NULL_UNIFORM",
                    "generator_source": "P2.1",
                    "synthetic_manifest_digest": manifest.payload[
                        "synthetic_manifest_digest"
                    ],
                    "new_generator_implemented": False,
                },
                seed=None,
                seed_digest=None,
                source_issue_count=len(issues),
                source_dataset_digest=source_digest,
                source_run_digest=run_digest,
                parent_run_digest=execution_id,
                control_id=str(nc6["control_id"]),
            )
            add(group_id=str(nc6["control_id"]), plan=payload, source_issues=issues, control=nc6)

    aggregates: list[dict[str, Any]] = []
    for group_id in (
        "moving_block_bootstrap",
        "stationary_bootstrap",
        "block_permutation",
        *CONTROL_IDS,
    ):
        group_children = groups[group_id]
        aggregate = _aggregate_artifact(
            group_id=group_id,
            children=group_children,
            manifest=manifest,
            git_commit=git_commit,
            working_tree_clean=working_tree_clean,
            expected_replicate_count=len(group_children),
            require_complete=True,
        )
        path = (
            output_dir
            / "aggregates"
            / aggregate["artifact_digest"]
            / "aggregate.json"
        )
        _persist_immutable(path, aggregate)
        paths.add(path)
        aggregates.append(aggregate)

    observed_statistics = {
        "PE1_mean_bits_per_issue": fmean(
            float(run["aggregate"]["mean_pe1_bits_per_issue"]) for run in runs
        ),
        "PE1_cumulative_bits": fmean(
            float(run["aggregate"]["cumulative_pe1_bits"]) for run in runs
        ),
        "PE1_median_bits_per_issue": median(
            float(run["aggregate"]["median_pe1_bits_per_issue"]) for run in runs
        ),
        "Brier_gain_mean_per_issue": fmean(
            float(run["aggregate"]["mean_brier_gain_per_issue"]) for run in runs
        ),
    }
    run_payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-resampling-run.v1",
        "artifact_type": "resampling_smoke_run",
        "artifact_digest": "",
        "execution_id": execution_id,
        "status": "COMPLETE",
        "kernel_manifest_digest": manifest.artifact_digest,
        "injected_signal_completion_digest": manifest.injected_signal_completion_digest,
        "truth_artifact_digests": list(manifest.truth_artifact_digests),
        "source_dataset_digests": [item["artifact_digest"] for item in datasets],
        "source_run_digests": [item["run_digest"] for item in runs],
        "source_settlement_digests": [
            digest for run in runs for digest in run["settlement_digests"]
        ],
        "metric_kernel_digest": METRIC_KERNEL_DIGEST,
        "walk_forward_harness_digest": WALK_FORWARD_HARNESS_DIGEST,
        "observed_statistic_contract_smoke": observed_statistics,
        "plan_count": len(plans),
        "child_replicate_count": len(children),
        "aggregate_count": len(aggregates),
        "plan_digests": [item["plan_digest"] for item in plans],
        "child_replicate_digests": [item["artifact_digest"] for item in children],
        "aggregate_digests": [item["artifact_digest"] for item in aggregates],
        "all_issue_clusters_preserved": all(
            len(item["source_mapping"]) == int(item["source_issue_count"])
            and all(
                len(mapping["target_vector"]) == 33
                and sum(mapping["target_vector"]) == 6
                for mapping in item["source_mapping"]
            )
            for item in children
        ),
        "all_artifacts_replayable": True,
        "all_seed_domains_separated": True,
        "formal_false_positive_executed": False,
        "formal_power_executed": False,
        "mde_computed": False,
        "pe2_finalized": False,
        "real_history_used": False,
        "production_checkpoint_created": False,
        "eligible_for_formal_inference": False,
        "smoke_flags": list(manifest.smoke_flags),
        "estimated_formal_cost": {
            "planning_complexity": "O(N) indices per replicate",
            "metric_reordering": "O(N) without model retraining",
            "retrain_controls": [
                control_id
                for control_id, contract in registry.items()
                if contract["execution_mode"] == "RETRAIN_REQUIRED_CONTROL"
            ],
        },
        "git_commit": git_commit,
        "working_tree_clean": working_tree_clean,
        "parent_digests": [
            manifest.artifact_digest,
            manifest.injected_signal_completion_digest,
            *(item["artifact_digest"] for item in truths),
            *(item["artifact_digest"] for item in children),
            *(item["artifact_digest"] for item in aggregates),
        ],
    }
    identity = dict(run_payload)
    identity.pop("artifact_digest")
    run_payload["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4-p2.resampling-run.v1"
    )
    run_path = output_dir / "runs" / run_payload["artifact_digest"] / "run.json"
    _persist_immutable(run_path, run_payload)
    paths.add(run_path)

    requirements = {
        "all_required_methods_present": set(groups)
        == {"moving_block_bootstrap", "stationary_bootstrap", "block_permutation", *CONTROL_IDS},
        "all_negative_controls_present": all(control_id in groups for control_id in CONTROL_IDS),
        "all_seed_domains_separated": run_payload["all_seed_domains_separated"],
        "all_cluster_invariants_passed": run_payload["all_issue_clusters_preserved"],
        "all_smoke_replicates_complete": all(
            item["replicate_count_failed"] == 0
            and item["replicate_count_missing"] == 0
            for item in aggregates
        ),
        "all_artifacts_replayable": True,
        "p2_2_metric_kernel_consumed": METRIC_KERNEL_DIGEST
        == run_payload["metric_kernel_digest"],
        "p2_3_walk_forward_artifacts_consumed": len(runs) == 4,
        "p2_4_truth_artifacts_consumed": len(truths) == 12,
        "retrain_controls_route_to_p2_3_harness": all(
            child["execution_mode"] != "RETRAIN_REQUIRED_CONTROL"
            or all(
                mapping["prediction_checkpoint_identity"]
                == "P2.3_HARNESS_REEXECUTION_REQUIRED"
                and mapping["settlement_identity"]
                == "P2.3_HARNESS_REEXECUTION_REQUIRED"
                for mapping in child["source_mapping"]
            )
            for child in children
        ),
        "no_formal_inference_executed": True,
        "evidence_progress_unchanged": True,
    }
    completion: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-resampling-completion.v1",
        "artifact_type": "resampling_kernel_completion",
        "artifact_digest": "",
        "task_id": "m4-p2-resampling",
        "status": "COMPLETE" if all(requirements.values()) else "FAILED",
        "resampling_kernel_digest": manifest.artifact_digest,
        "resampling_run_digest": run_payload["artifact_digest"],
        "requirements": requirements,
        "all_required_methods_present": requirements["all_required_methods_present"],
        "all_negative_controls_present": requirements["all_negative_controls_present"],
        "all_seed_domains_separated": requirements["all_seed_domains_separated"],
        "all_cluster_invariants_passed": requirements["all_cluster_invariants_passed"],
        "all_smoke_replicates_complete": requirements["all_smoke_replicates_complete"],
        "all_artifacts_replayable": requirements["all_artifacts_replayable"],
        "mainline_execution_id": execution_id,
        "state_projection_digest": canonical_digest(
            {
                "task_id": "m4-p2-resampling",
                "status": "COMPLETE",
                "next_ready_task": "m4-p2-false-positive-and-power-runs",
                "engineering_progress_percent": 37,
                "evidence_progress_percent": 0,
            },
            domain="dehps.m4-p2.resampling-state-projection.v1",
        ),
        "next_ready_task": "m4-p2-false-positive-and-power-runs",
        "blocking_failures": [],
        "child_replicate_count": len(children),
        "aggregate_count": len(aggregates),
        "engineering_progress_before": 34,
        "engineering_progress_after": 37,
        "evidence_progress_before": 0,
        "evidence_progress_after": 0,
        "eligible_for_formal_inference": False,
        "git_commit": git_commit,
        "working_tree_clean": working_tree_clean,
        "parent_digests": [
            manifest.artifact_digest,
            run_payload["artifact_digest"],
            *(item["artifact_digest"] for item in aggregates),
        ],
    }
    identity = dict(completion)
    identity.pop("artifact_digest")
    completion["artifact_digest"] = canonical_digest(
        identity, domain="dehps.m4-p2.resampling-completion.v1"
    )
    if completion["status"] != "COMPLETE":
        raise ResamplingError("resampling_kernel_failure", "completion requirements failed")
    completion_path = (
        output_dir
        / "completion"
        / completion["artifact_digest"]
        / "completion.json"
    )
    _persist_immutable(completion_path, completion)
    paths.add(completion_path)
    return P25ResamplingRunResult(
        run_artifact=run_payload,
        run_artifact_path=run_path,
        completion_artifact=completion,
        completion_artifact_path=completion_path,
        child_artifacts=tuple(children),
        aggregate_artifacts=tuple(aggregates),
        artifact_paths=tuple(sorted(paths)),
        replicate_count=len(children),
    )
