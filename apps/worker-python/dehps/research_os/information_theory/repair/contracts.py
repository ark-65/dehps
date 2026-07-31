from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.digest import config_digest

from .calibration import MeasurementRepairError, verify_frozen_scenario
from .development import development_contract_digest

MEASUREMENT_REPAIR_MANIFEST_DIGEST = (
    "5e41910553643e6559e78aa401fdcdd1e661b5709eaf55f0e73e694fb5a61355"
)


@dataclass(frozen=True)
class MeasurementRepairManifest:
    payload: Mapping[str, Any]
    artifact_digest: str
    scenarios: tuple[Mapping[str, Any], ...]


def load_measurement_repair_manifest(path: Path) -> MeasurementRepairManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementRepairError(
            "measurement_repair_manifest_invalid",
            str(exc),
        ) from exc
    if not isinstance(payload, Mapping):
        raise MeasurementRepairError(
            "measurement_repair_manifest_invalid",
            "manifest root must be an object",
        )
    return validate_measurement_repair_manifest(payload)


def validate_measurement_repair_manifest(
    payload: Mapping[str, Any],
) -> MeasurementRepairManifest:
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-measurement-contract-repair-manifest.v1"
        or payload.get("artifact_type") != "measurement_contract_repair_manifest"
        or payload.get("phase") != "M4-P2-REPAIR"
        or payload.get("status") != "FROZEN"
        or payload.get("approved_strategy")
        != "SCHEME_A_MARGINAL_TRUTH_TO_MARGINAL_METRIC"
        or payload.get("production_action") != "none"
    ):
        raise MeasurementRepairError(
            "measurement_repair_contract_invalid",
            "repair identity or approved strategy changed",
        )
    supplied = str(payload.get("artifact_digest") or "")
    calculated = config_digest(payload)
    if supplied != calculated or supplied != MEASUREMENT_REPAIR_MANIFEST_DIGEST:
        raise MeasurementRepairError(
            "measurement_repair_manifest_digest_mismatch",
            "frozen Scheme A manifest changed",
        )
    result_blind = payload.get("result_blind_freeze")
    if not isinstance(result_blind, Mapping) or set(result_blind.values()) != {False}:
        raise MeasurementRepairError(
            "measurement_repair_result_blind_invalid",
            "repair may not inspect old P2.6 statistical outcomes",
        )
    boundaries = payload.get("boundaries")
    if not isinstance(boundaries, Mapping) or dict(boundaries) != {
        "joint_probe_or_kernel_added": False,
        "real_history_prior_state_available": False,
        "synthetic_prior_state_instrument_only": True,
        "state_number_interactions_synthetic_only": True,
        "old_partial_statistical_results_inspected": False,
        "evidence_created_during_repair": False,
        "P3_opened_during_repair": False,
    }:
        raise MeasurementRepairError(
            "measurement_repair_boundary_invalid",
            "Scheme A scope or leakage boundary changed",
        )
    raw_scenarios = payload.get("scenario_contracts")
    if not isinstance(raw_scenarios, list) or len(raw_scenarios) != 12:
        raise MeasurementRepairError(
            "measurement_repair_scenario_invalid",
            "all twelve original signal scenarios require a typed disposition",
        )
    scenarios = tuple(dict(item) for item in raw_scenarios if isinstance(item, Mapping))
    if (
        len(scenarios) != 12
        or len({str(item.get("scenario_id")) for item in scenarios}) != 12
    ):
        raise MeasurementRepairError(
            "measurement_repair_scenario_invalid",
            "scenario identities must be complete and unique",
        )
    roles = [str(item.get("role")) for item in scenarios]
    if (
        roles.count("FORMAL_POWER_TARGET") != 8
        or roles.count("JOINT_ONLY_NEGATIVE_CONTROL") != 3
        or roles.count("MARGINAL_FEASIBILITY_SENTINEL") != 1
    ):
        raise MeasurementRepairError(
            "measurement_repair_scenario_invalid",
            "Scheme A requires 8 power targets, 3 joint-only controls, and 1 sentinel",
        )
    for scenario in scenarios:
        verify_frozen_scenario(scenario)
    feature_contract = payload.get("state_visible_feature_contract")
    if not isinstance(feature_contract, Mapping) or dict(feature_contract) != {
        "feature_manifest_digest": (
            "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981"
        ),
        "prior_state_available_strictly_before_target": True,
        "state_number_interaction_count": 33,
        "real_history_access": "forbidden",
        "scope": "P2.6.1 synthetic measurement validation only",
    }:
        raise MeasurementRepairError(
            "measurement_repair_feature_contract_invalid",
            "synthetic state instrument identity or boundary changed",
        )
    development = payload.get("development_selection")
    if (
        not isinstance(development, Mapping)
        or development.get("contract_digest")
        != development_contract_digest(development)
        or development.get("expected_selection_artifact_digest")
        != "90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2"
    ):
        raise MeasurementRepairError(
            "measurement_repair_development_contract_invalid",
            "frozen development selection contract changed",
        )
    frozen = payload.get("frozen_probe_configs")
    if not isinstance(frozen, Mapping) or dict(frozen) != {
        "development_selection_artifact_digest": (
            "90459ebf8b88afcc60ee1177043e436b90b71c00b557f15e9e4d7026f37586f2"
        ),
        "REGULARIZED_LOGISTIC_REGRESSION": {
            "selection_mode": "frozen_development",
            "selected_C": 0.1,
        },
        "NAIVE_BAYES": {
            "selection_mode": "frozen_development",
            "selected_alpha": 2.0,
        },
        "SHALLOW_CALIBRATED_TREE": {
            "selection_mode": "frozen_development",
            "selected_max_depth": 2,
            "selected_min_samples_leaf": 50,
        },
    }:
        raise MeasurementRepairError(
            "measurement_repair_frozen_probe_invalid",
            "selected development hyperparameters changed",
        )
    fit_contract = payload.get("outer_fold_fit_contract")
    if not isinstance(fit_contract, Mapping) or dict(fit_contract) != {
        "EMPIRICAL_BASELINE": 0,
        "REGULARIZED_LOGISTIC_REGRESSION": 1,
        "NAIVE_BAYES": 1,
        "SHALLOW_CALIBRATED_TREE": 2,
        "total_estimator_and_calibrator_fits": 4,
        "inner_model_selection_per_outer_fold": 0,
    }:
        raise MeasurementRepairError(
            "measurement_repair_fit_contract_invalid",
            "frozen outer-fold fit budget changed",
        )
    return MeasurementRepairManifest(
        payload=dict(payload),
        artifact_digest=supplied,
        scenarios=scenarios,
    )
