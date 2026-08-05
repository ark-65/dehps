from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.digest import config_digest

from .contracts import MeasurementValidationContractError
from .repaired_contracts import REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST

PERIODIC_REFIT_CONTRACT_DIGEST = (
    "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
)
LEARNED_PROBES = (
    "REGULARIZED_LOGISTIC_REGRESSION",
    "NAIVE_BAYES",
    "SHALLOW_CALIBRATED_TREE",
)


@dataclass(frozen=True)
class PeriodicRefitContract:
    payload: Mapping[str, Any]
    artifact_digest: str
    learned_probe_refit_interval_folds: int

    def is_refit_boundary(self, fold_index: int) -> bool:
        return fold_index % self.learned_probe_refit_interval_folds == 0

    def boundary_fold_index(self, fold_index: int) -> int:
        return fold_index - fold_index % self.learned_probe_refit_interval_folds


def load_periodic_refit_contract(path: Path) -> PeriodicRefitContract:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementValidationContractError(
            "periodic_refit_contract_invalid",
            str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise MeasurementValidationContractError(
            "periodic_refit_contract_invalid",
            "contract root must be an object",
        )
    supplied = str(payload.get("artifact_digest") or "")
    if (
        payload.get("schema_version") != "dehps-m4-p2-periodic-refit-contract.v1"
        or payload.get("artifact_type") != "measurement_validation_update_policy"
        or payload.get("phase") != "M4-P2.6.3"
        or payload.get("status") != "FROZEN"
        or payload.get("production_action") != "none"
        or supplied != config_digest(payload)
        or supplied != PERIODIC_REFIT_CONTRACT_DIGEST
        or payload.get("base_measurement_validation_manifest_digest")
        != REPAIRED_MEASUREMENT_VALIDATION_MANIFEST_DIGEST
    ):
        raise MeasurementValidationContractError(
            "periodic_refit_contract_digest_mismatch",
            "the frozen P2.6.3 update policy changed",
        )
    policy = payload.get("update_policy")
    if not isinstance(policy, dict) or policy != {
        "policy_id": "FIXED_STRICT_PRIOR_LEARNED_REFIT_64",
        "outer_prediction_schedule": "EVERY_FOLD",
        "learned_probe_ids": list(LEARNED_PROBES),
        "learned_probe_refit_interval_folds": 64,
        "learned_probe_refit_rule": "fold_index_mod_interval_equals_zero",
        "empirical_baseline_update_schedule": "EVERY_FOLD",
        "first_fold_refit_required": True,
        "adaptive_cadence": False,
        "result_dependent_refit": False,
        "future_target_access": False,
        "restart_reconstructs_latest_boundary_only": True,
    }:
        raise MeasurementValidationContractError(
            "periodic_refit_policy_invalid",
            "the fixed strict-prior update policy changed",
        )
    result_blind = payload.get("result_blind_freeze")
    identity = payload.get("execution_identity")
    capacity = payload.get("capacity_gate")
    preserved = payload.get("preserved_contract")
    if (
        not isinstance(result_blind, dict)
        or set(result_blind.values()) != {False}
        or not isinstance(identity, dict)
        or identity
        != {
            "new_task_digest_required": True,
            "new_execution_id_required": True,
            "p2_6_1_results_reused": False,
            "p2_6_1_checkpoints_reused": False,
            "p2_6_1_results_mixed": False,
            "p2_6_1_execution_deleted": False,
        }
        or capacity
        != {
            "weighted_speedup_min": 8.0,
            "single_host_worker_count": 22,
            "single_host_forecast_days_max": 12.0,
        }
        or preserved
        != {
            "scenario_replicates": 31000,
            "outer_issue_predictions": 64656000,
            "workload_models_features_seeds_resampling_thresholds_and_gate": (
                "UNCHANGED_FROM_P2_6_1"
            ),
            "partial_scale_or_scenario_aggregation": "forbidden",
        }
    ):
        raise MeasurementValidationContractError(
            "periodic_refit_contract_invalid",
            "result-blind, execution-separation, capacity, or workload rules changed",
        )
    return PeriodicRefitContract(
        payload=payload,
        artifact_digest=supplied,
        learned_probe_refit_interval_folds=64,
    )
