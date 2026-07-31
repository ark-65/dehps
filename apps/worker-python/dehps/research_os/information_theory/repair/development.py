from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import fsum
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_validation.dataset import (
    generate_evaluation_dataset,
)
from dehps.research_os.information_theory.measurement_validation.feature_cache import (
    StrictPriorFeatureCache,
)
from dehps.research_os.information_theory.measurement_validation.schedule import (
    ROOT_SEED_SET_DIGEST,
    AnalysisCell,
    AnalysisReplicate,
)
from dehps.research_os.information_theory.metrics import (
    probe_log_loss_bits_per_issue_batch_exact_native,
)
from dehps.research_os.information_theory.probes import (
    prepare_logistic_probe,
    prepare_naive_bayes_probe,
    prepare_shallow_calibrated_tree,
)
from dehps.research_os.information_theory.seed_domains import derive_m4_p2_seed
from dehps.research_os.information_theory.synthetic.contracts import (
    SyntheticRunManifest,
)
from dehps.research_os.information_theory.walk_forward import (
    restrict_to_training_history,
)

from .calibration import MeasurementRepairError


def development_contract_digest(contract: Mapping[str, Any]) -> str:
    identity = dict(contract)
    identity.pop("contract_digest", None)
    identity.pop("expected_selection_artifact_digest", None)
    return canonical_digest(
        identity,
        domain="dehps.m4-p2.scheme-a-development-contract.v1",
    )


def _development_replicate(
    *,
    cell: AnalysisCell,
    contract_digest: str,
) -> AnalysisReplicate:
    orchestration = derive_m4_p2_seed(
        root_seed_set_digest=ROOT_SEED_SET_DIGEST,
        seed_domain="M4_P2_6_1_HYPERPARAMETER_DEVELOPMENT",
        scenario_id=cell.scenario_id,
        method_id="FORWARD_61:development_selection",
        replicate_index=0,
        parent_run_digest=contract_digest,
    )
    dataset = derive_m4_p2_seed(
        root_seed_set_digest=ROOT_SEED_SET_DIGEST,
        seed_domain="M4_P2_6_1_HYPERPARAMETER_DEVELOPMENT_DATASET",
        scenario_id=cell.scenario_id,
        method_id="FORWARD_61:development_dataset",
        replicate_index=0,
        parent_run_digest=str(orchestration["seed_digest"]),
    )
    identity = {
        "scale_id": cell.scale_id,
        "scenario_id": cell.scenario_id,
        "replicate_index": 0,
        "development_orchestration_seed_digest": orchestration["seed_digest"],
        "development_dataset_seed_digest": dataset["seed_digest"],
        "development_contract_digest": contract_digest,
    }
    return AnalysisReplicate(
        cell=cell,
        replicate_index=0,
        parent_execution_id=contract_digest,
        power_replicate_seed=int(orchestration["seed"]),
        power_replicate_seed_digest=str(orchestration["seed_digest"]),
        evaluation_dataset_seed=int(dataset["seed"]),
        evaluation_dataset_seed_digest=str(dataset["seed_digest"]),
        artifact_digest=canonical_digest(
            identity,
            domain="dehps.m4-p2.scheme-a-development-replicate.v1",
        ),
    )


def _cell(
    synthetic: SyntheticRunManifest,
    *,
    scenario_id: str,
) -> AnalysisCell:
    scenario = synthetic.scenario(scenario_id)
    scale = synthetic.scale("FORWARD_61")
    return AnalysisCell(
        scale_id=scale.scale_id,
        scenario_id=scenario.scenario_id,
        mechanism=scenario.mechanism,
        signal_strength=scenario.signal_strength,
        target_bits_per_issue=scenario.target_bits_per_issue,
        outer_issue_count=scale.outer_evaluation_length,
    )


def _truth_payload(scenario: Mapping[str, Any]) -> dict[str, Any]:
    identity = {
        "scenario_id": scenario["scenario_id"],
        "mechanism": scenario["mechanism"],
        "parameter_value": scenario["parameter_value"],
        "marginal_information_bits_per_issue": scenario[
            "marginal_information_bits_per_issue"
        ],
        "joint_information_bits_per_issue": scenario[
            "joint_information_bits_per_issue"
        ],
        "role": "development_only_truth",
    }
    return {
        **identity,
        "artifact_digest": canonical_digest(
            identity,
            domain="dehps.m4-p2.scheme-a-development-truth.v1",
        ),
    }


def run_development_selection(
    *,
    contract: Mapping[str, Any],
    synthetic: SyntheticRunManifest,
    scenario_contracts: Mapping[str, Mapping[str, Any]],
    probe_configs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    supplied_contract_digest = str(contract.get("contract_digest") or "")
    if (
        supplied_contract_digest != development_contract_digest(contract)
        or contract.get("dataset_role") != "P2_6_1_HYPERPARAMETER_DEVELOPMENT"
        or contract.get("train_issues") != [1, 900]
        or contract.get("validation_issues") != [901, 960]
        or contract.get("selection_metric")
        != "mean_issue_log_loss_across_all_development_scenarios"
        or contract.get("formal_evaluation_seed_reuse") != "forbidden"
        or contract.get("selection_policy") != "no_best_seed"
    ):
        raise MeasurementRepairError(
            "measurement_repair_development_contract_invalid",
            "development split, metric, or seed separation changed",
        )
    scenario_ids = tuple(str(value) for value in contract["scenario_ids"])
    if len(scenario_ids) != 9 or scenario_ids[0] != "NULL_UNIFORM":
        raise MeasurementRepairError(
            "measurement_repair_development_contract_invalid",
            "development selection requires null plus eight feasible targets",
        )
    candidates = contract["candidates"]
    if candidates != {
        "REGULARIZED_LOGISTIC_REGRESSION": {"C": [0.01, 0.1, 1.0]},
        "NAIVE_BAYES": {"alpha": [0.5, 1.0, 2.0]},
        "SHALLOW_CALIBRATED_TREE": {
            "max_depth": [2, 3],
            "min_samples_leaf": [50, 100],
        },
    }:
        raise MeasurementRepairError(
            "measurement_repair_development_contract_invalid",
            "development candidate grid changed",
        )

    score_lists: dict[str, dict[str, list[float]]] = {
        "REGULARIZED_LOGISTIC_REGRESSION": {
            f"C={value:g}": []
            for value in candidates["REGULARIZED_LOGISTIC_REGRESSION"]["C"]
        },
        "NAIVE_BAYES": {
            f"alpha={value:g}": [] for value in candidates["NAIVE_BAYES"]["alpha"]
        },
        "SHALLOW_CALIBRATED_TREE": {
            f"max_depth={depth},min_samples_leaf={leaf}": []
            for depth in candidates["SHALLOW_CALIBRATED_TREE"]["max_depth"]
            for leaf in candidates["SHALLOW_CALIBRATED_TREE"]["min_samples_leaf"]
        },
    }
    dataset_digests: list[str] = []
    seed_digests: list[str] = []
    scenario_score_rows: list[dict[str, Any]] = []
    for scenario_id in scenario_ids:
        cell = _cell(synthetic, scenario_id=scenario_id)
        replicate = _development_replicate(
            cell=cell,
            contract_digest=supplied_contract_digest,
        )
        truth = (
            None
            if scenario_id == "NULL_UNIFORM"
            else _truth_payload(scenario_contracts[scenario_id])
        )
        dataset = generate_evaluation_dataset(
            replicate,
            synthetic=synthetic,
            truth_artifact=truth,
            expose_prior_state=True,
            development_only=True,
        )
        training = restrict_to_training_history(
            dataset,
            available_through_issue=900,
        )
        cache = StrictPriorFeatureCache(
            dataset,
            include_prior_state=True,
        )
        cache.reveal_training_history(training, through_issue=900)
        train_view = cache.build_train_feature_view(
            training,
            tuple(range(1, 901)),
        )
        blind_views = []
        targets = []
        for issue in range(901, 961):
            blind_views.append(cache.build_blind_test_feature_view(target_issue=issue))
            targets.append(dataset.issue(issue).target_vector)
            if issue < 960:
                available = restrict_to_training_history(
                    dataset,
                    available_through_issue=issue,
                )
                cache.reveal_training_history(
                    available,
                    through_issue=issue,
                )

        def score(
            prepared: Any,
            *,
            views: tuple[Any, ...] = tuple(blind_views),
            target_vectors: tuple[tuple[int, ...], ...] = tuple(targets),
        ) -> float:
            probabilities = tuple(prepared.predict(view) for view in views)
            losses = probe_log_loss_bits_per_issue_batch_exact_native(
                target_vectors=target_vectors,
                probe_probability_vectors=probabilities,
            )
            return fsum(losses) / len(losses)

        row: dict[str, Any] = {"scenario_id": scenario_id, "scores": {}}
        for c_value in candidates["REGULARIZED_LOGISTIC_REGRESSION"]["C"]:
            config = deepcopy(dict(probe_configs["REGULARIZED_LOGISTIC_REGRESSION"]))
            config.update(
                {
                    "selection_mode": "frozen_development",
                    "selected_C": c_value,
                    "C": [c_value],
                    "development_selection_digest": (supplied_contract_digest),
                }
            )
            identifier = f"C={c_value:g}"
            value = score(
                prepare_logistic_probe(
                    training,
                    train_view,
                    config=config,
                    outer_test_issue=901,
                )
            )
            score_lists["REGULARIZED_LOGISTIC_REGRESSION"][identifier].append(value)
            row["scores"][f"REGULARIZED_LOGISTIC_REGRESSION:{identifier}"] = value
        for alpha in candidates["NAIVE_BAYES"]["alpha"]:
            config = deepcopy(dict(probe_configs["NAIVE_BAYES"]))
            config.update(
                {
                    "selection_mode": "frozen_development",
                    "selected_alpha": alpha,
                    "alpha": [alpha],
                    "development_selection_digest": (supplied_contract_digest),
                }
            )
            identifier = f"alpha={alpha:g}"
            value = score(
                prepare_naive_bayes_probe(
                    training,
                    train_view,
                    config=config,
                    outer_test_issue=901,
                )
            )
            score_lists["NAIVE_BAYES"][identifier].append(value)
            row["scores"][f"NAIVE_BAYES:{identifier}"] = value
        for depth in candidates["SHALLOW_CALIBRATED_TREE"]["max_depth"]:
            for leaf in candidates["SHALLOW_CALIBRATED_TREE"]["min_samples_leaf"]:
                config = deepcopy(dict(probe_configs["SHALLOW_CALIBRATED_TREE"]))
                config.update(
                    {
                        "selection_mode": "frozen_development",
                        "selected_max_depth": depth,
                        "selected_min_samples_leaf": leaf,
                        "max_depth": [depth],
                        "min_samples_leaf": [leaf],
                        "development_selection_digest": (supplied_contract_digest),
                    }
                )
                identifier = f"max_depth={depth},min_samples_leaf={leaf}"
                value = score(
                    prepare_shallow_calibrated_tree(
                        training,
                        train_view,
                        config=config,
                        outer_test_issue=901,
                        train_view_builder=cache.build_train_feature_view,
                    )
                )
                score_lists["SHALLOW_CALIBRATED_TREE"][identifier].append(value)
                row["scores"][f"SHALLOW_CALIBRATED_TREE:{identifier}"] = value
        dataset_digests.append(dataset.artifact_digest)
        seed_digests.extend(
            (
                replicate.power_replicate_seed_digest,
                replicate.evaluation_dataset_seed_digest,
            )
        )
        scenario_score_rows.append(row)

    complexity_order = {
        "REGULARIZED_LOGISTIC_REGRESSION": {
            "C=0.01": 0,
            "C=0.1": 1,
            "C=1": 2,
        },
        "NAIVE_BAYES": {
            "alpha=2": 0,
            "alpha=1": 1,
            "alpha=0.5": 2,
        },
        "SHALLOW_CALIBRATED_TREE": {
            "max_depth=2,min_samples_leaf=100": 0,
            "max_depth=2,min_samples_leaf=50": 1,
            "max_depth=3,min_samples_leaf=100": 2,
            "max_depth=3,min_samples_leaf=50": 3,
        },
    }
    summaries: dict[str, dict[str, float]] = {}
    selected: dict[str, str] = {}
    for family, family_scores in score_lists.items():
        summaries[family] = {
            identifier: fsum(values) / len(values)
            for identifier, values in sorted(family_scores.items())
        }
        selected[family] = min(
            summaries[family],
            key=lambda identifier: (
                summaries[family][identifier],
                complexity_order[family][identifier],
            ),
        )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-development-selection.v1",
        "artifact_type": "frozen_hyperparameter_development_selection",
        "artifact_digest": "",
        "status": "COMPLETE",
        "development_contract_digest": supplied_contract_digest,
        "dataset_role": contract["dataset_role"],
        "train_issues": contract["train_issues"],
        "validation_issues": contract["validation_issues"],
        "scenario_ids": list(scenario_ids),
        "candidate_mean_issue_log_loss": summaries,
        "selected_config_ids": selected,
        "scenario_scores": scenario_score_rows,
        "dataset_digest_root": canonical_digest(
            dataset_digests,
            domain="dehps.m4-p2.scheme-a-development-datasets.v1",
        ),
        "seed_set_digest": canonical_digest(
            sorted(seed_digests),
            domain="dehps.m4-p2.scheme-a-development-seeds.v1",
        ),
        "development_dataset_count": len(dataset_digests),
        "candidate_fit_count": 126,
        "formal_outer_metrics_used": False,
        "formal_evaluation_seed_reuse": False,
        "selection_policy": "minimum_mean_issue_log_loss_then_simpler_model",
        "eligible_for_evidence": False,
        "eligible_for_formal_inference": False,
        "production_action": "none",
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4-p2.scheme-a-development-selection.v1",
    )
    expected = str(contract.get("expected_selection_artifact_digest") or "")
    if expected and expected != payload["artifact_digest"]:
        raise MeasurementRepairError(
            "measurement_repair_development_replay_mismatch",
            "development selection changed from the frozen result",
        )
    return payload
