from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import (
    config_digest,
    preregistration_digest,
)

from .contracts import json_compatible_copy

MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-design"
)
MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY = (
    "m4_v2_marginal_static_historical_measurement_design"
)
MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-historical-measurement-design:FROZEN"
)
MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-preregistration"
)
MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-historical-design-source-v1.json"
)
FROZEN_PREREGISTRATION_PATH = Path(
    "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)

REPAIR_V2_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-health-decision"
)
REPAIR_V2_HEALTH_DECISION_EXECUTION_ID = (
    "3acce7cbc42b51a2d1db6fcc0b9c2185dc0767857b5ebc19f92b77dcf8a2d305"
)
REPAIR_V2_HEALTH_DECISION_EXECUTION_DIGEST = (
    "8d127c7b83cbed9974d51d23477900763a8cceae09f3db62a9e8fe3449e3a2a4"
)
REPAIR_V2_HEALTH_DECISION_DIGEST = (
    "8b1badb229e8517695bc41aed6d87e469a27fe010006e60e11244e3792573124"
)
MARGINAL_STATIC_CONTRACT_TASK_KEY = "m4-v2-marginal-static-measurement-contract-freeze"
MARGINAL_STATIC_CONTRACT_EXECUTION_ID = (
    "cb29070267701d0d53c8fd452874fcb5e4a2be3eb5b457eaeed73b64e3b46de9"
)
MARGINAL_STATIC_CONTRACT_EXECUTION_DIGEST = (
    "ab0e17013b5b4b1e30f6a45652f6a9e5269392d525ad41db718f357a8b4bffef"
)
MARGINAL_STATIC_MEASUREMENT_CONTRACT_DIGEST = (
    "26a12fa7ad46ebdeb8b08559e70bc7d6e15f4a1f3c7d3f8be5e16f4865071d5b"
)
MEASUREMENT_CONTRACT_DESIGN_TASK_KEY = "m4-v2-measurement-contract-design"
MEASUREMENT_CONTRACT_DESIGN_EXECUTION_ID = (
    "9d2195be1b9949b0d6b35f00dffea8b0cdedb17f001f62d759a1bcc042727691"
)
MEASUREMENT_CONTRACT_DESIGN_EXECUTION_DIGEST = (
    "8164610dcac5bfa385cbd6cf4e78fcba885a83866bf9bd781fef387d22d83dc9"
)
GATE_COMPILER_CONTRACT_DIGEST = (
    "9f9519be92fb5db4a4fb4939d1d5d3d32f7646a6e449f3dd20fd5c63b409f821"
)
MEASUREMENT_CONTRACT_V2_DIGEST = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
FROZEN_PREREGISTRATION_DIGEST = (
    "4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9"
)
HISTORY_DATASET_DIGEST = (
    "30224d09a8b2d9080d3bc848f50b534c6d6de50b2eac867882915e85acbf206b"
)
ORDERED_ISSUE_DATE_METADATA_SHA256 = (
    "437ffb9d03ca844e0564dd147050e6668bf600fc6e601c6e4dcc0753b65fe2fe"
)

NUMBER_COUNT = 33
DRAW_CARDINALITY = 6
LEGAL_SUBSET_COUNT = 1_107_568
HISTORICAL_ISSUE_COUNT = 3_481
INITIAL_TRAINING_ISSUES = 900
EVALUATION_FOLD_COUNT = 2_581
BOOTSTRAP_REPLICATES = 2_000
PRIMARY_BLOCK_LENGTH = 5
PRACTICAL_THRESHOLD_BITS_PER_ISSUE = 0.01

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-historical-measurement-design-round-52-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-historical-measurement-design-round-52-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_historical_design.py"
)


EXPECTED_LEGAL_SAMPLE_SPACE = {
    "object": "unordered red-ball subset",
    "number_labels": "1..33",
    "number_count": NUMBER_COUNT,
    "draw_cardinality": DRAW_CARDINALITY,
    "legal_subset_count": LEGAL_SUBSET_COUNT,
    "within_draw_duplicates": "forbidden",
    "blue_ball": "excluded",
    "observation_unit": "one issue",
    "number_event_rows_are_clusters": True,
    "independent_33_row_inference": "forbidden",
}

EXPECTED_HISTORICAL_BOUNDARY = {
    "dataset_schema": "ssq_history.reds_only.v1",
    "existing_dataset_digest_to_verify_next": HISTORY_DATASET_DIGEST,
    "start_issue": "2003001",
    "start_date": "2003-02-23",
    "end_issue": "2026084",
    "end_date": "2026-07-23",
    "issue_count": HISTORICAL_ISSUE_COUNT,
    "ordered_issue_date_metadata_sha256": ORDERED_ISSUE_DATE_METADATA_SHA256,
    "metadata_rows_observed_at_design": 3_487,
    "rows_through_cutoff": HISTORICAL_ISSUE_COUNT,
    "post_cutoff_rows_excluded_at_design": 6,
    "first_excluded_issue": "2026085",
    "last_excluded_issue_observed": "2026090",
    "post_cutoff_use": "forbidden",
    "revision_policy": (
        "new dataset digest and run; immutable prior artifacts are never overwritten"
    ),
    "design_database_columns_read": ["issue", "draw_date"],
    "design_red_numbers_read": False,
    "design_blue_number_read": False,
}

EXPECTED_ESTIMAND_AND_MODEL = {
    "branch_id": "MARGINAL_STATIC",
    "estimand": (
        "mean issue-level sum of 33 Bernoulli log2 score differences, "
        "candidate minus legal-uniform baseline"
    ),
    "unit": "bits_per_issue",
    "joint_information_claim": "forbidden",
    "candidate_estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
    "candidate_formula": "q_i(t)=(c_i(t-1)+2/11)/(n(t-1)+1)",
    "fit_window": "expanding strict-prior only",
    "minimum_training_issues": INITIAL_TRAINING_ISSUES,
    "prior_strength_issues_alpha": 1,
    "history_features": "forbidden",
    "hyperparameter_search": "none",
    "random_seed": "none",
    "clipping": "forbidden",
    "renormalization": "forbidden",
    "probability_sum_identity": "sum_i q_i(t)=6",
    "baseline_id": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
    "baseline_probability_each_number": "2/11",
    "baseline_artifact_must_differ_from_candidate_model": True,
    "primary_endpoint_threshold_bits_per_issue": (PRACTICAL_THRESHOLD_BITS_PER_ISSUE),
}

EXPECTED_WALK_FORWARD = {
    "retrospective": True,
    "initial_training_ordinals": [1, 900],
    "initial_training_issues": ["2003001", "2009075"],
    "evaluation_ordinals": [901, 3481],
    "evaluation_issues": ["2009076", "2026084"],
    "evaluation_fold_count": EVALUATION_FOLD_COUNT,
    "test_horizon_issues": 1,
    "fold_rule": (
        "fit ordinals 1..t-1, persist virtual checkpoint, then expose target t"
    ),
    "virtual_checkpoint_scope": (
        "retrospective ordering proof only; never forward Evidence"
    ),
    "current_target_in_fit": "forbidden",
    "future_target_in_fit": "forbidden",
    "post_cutoff_target_in_fit_or_score": "forbidden",
    "failed_or_missing_fold_policy": "fail closed",
}

EXPECTED_INFERENCE = {
    "canonical_sample": "2581 settled issue-level prequential score differences",
    "primary_null": "Delta_MARGINAL_STATIC <= 0.01 bits/issue",
    "primary_alternative": "Delta_MARGINAL_STATIC > 0.01 bits/issue",
    "primary_p_value_tail": "one-sided upper",
    "fixed_primary_family": [
        "MARGINAL_STATIC",
        "TEMPORAL_MARGINAL_INCREMENT",
        "JOINT_RESIDUAL_INCREMENT",
    ],
    "family_method": "Holm",
    "familywise_alpha": 0.05,
    "not_run_or_invalid_branch_p_value": 1,
    "partial_family_redefinition": "forbidden",
    "resampling_unit": "issue-level settled score difference",
    "primary_resampling": "non-circular moving-block bootstrap",
    "primary_block_length": PRIMARY_BLOCK_LENGTH,
    "block_length_sensitivities": [3, 8, 13],
    "stationary_bootstrap_sensitivity_expected_lengths": [3, 5, 8, 13],
    "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    "primary_interval": (
        "two-sided Bonferroni simultaneous percentile moving-block interval "
        "at per-branch total alpha 0.05/3"
    ),
    "positive_rule": (
        "health PASS, complete canonical run, distinct candidate/baseline, "
        "Holm p<=0.05, simultaneous lower bound>0.01"
    ),
    "negative_equivalence_null": "Delta_MARGINAL_STATIC >= 0.01 bits/issue",
    "negative_equivalence_alternative": ("Delta_MARGINAL_STATIC < 0.01 bits/issue"),
    "equivalence_upper_bound": (
        "separate one-sided Bonferroni upper bound at alpha 0.05/3"
    ),
    "minimum_equivalence_power_at_zero": 0.8,
    "mde_rule": (
        "nonnegative dependence-aware MDE at alpha 0.05/3 and power 0.8; "
        "NEGATIVE requires MDE<=0.01"
    ),
    "non_significance_without_equivalence_power": "INCONCLUSIVE",
    "conditioning_scope": (
        "conditional historical evidence for the frozen prequential trajectory"
    ),
}

EXPECTED_TIME_STABILITY = {
    "primary_halves": [
        {"start_issue": "2009076", "end_issue": "2017139", "issue_count": 1291},
        {"start_issue": "2017140", "end_issue": "2026084", "issue_count": 1290},
    ],
    "supported_signal_requires_both_half_means_positive": True,
    "thirds_sensitivity": [
        {"start_issue": "2009076", "end_issue": "2015016", "issue_count": 861},
        {"start_issue": "2015017", "end_issue": "2020111", "issue_count": 860},
        {"start_issue": "2020112", "end_issue": "2026084", "issue_count": 860},
    ],
    "partition_change_after_scores": "forbidden",
    "post_cutoff_forward_cohort": (
        "separate and eligible only with a real pre-draw checkpoint"
    ),
}

EXPECTED_CONTROLS_AND_INVARIANTS = {
    "legal_uniform_baseline": "primary adjacent baseline",
    "synthetic_repair_v2_health": "measurement-health prerequisite only",
    "global_number_relabeling": "equivariance test; no decision credit",
    "issue_block_permutation": "order-sensitivity diagnostic; no decision credit",
    "circular_target_shift": "alignment diagnostic; no decision credit",
    "matched_random_score": "diagnostic only; no decision credit",
    "formal_path_current_or_future_target_access": "hard failure",
    "best_control_or_seed_selection": "forbidden",
}


class MarginalStaticHistoricalDesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticHistoricalDesignRun:
    dataset_boundary: Mapping[str, Any]
    walk_forward_design: Mapping[str, Any]
    inference_design: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.dataset_boundary,
            self.walk_forward_design,
            self.inference_design,
            self.completion,
        )


def load_marginal_static_historical_design_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHistoricalDesignError(
            f"marginal_static_historical_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-historical-design-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_historical_design_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_HISTORICAL_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 362
        or payload.get("research_execution_id") != 283
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 363
        or payload.get("engineering_execution_id") != 284
        or payload.get("result_blind") is not True
        or payload.get("formal_historical_folds_executed") != 0
        or payload.get("database_queries_during_capability") != 0
        or payload.get("historical_red_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.marginal-static-historical-design-source-set.v1",
        )
    ):
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_historical_design_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHistoricalDesignError(
                f"marginal_static_historical_design_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHistoricalDesignError(
                f"marginal_static_historical_design_source_modified:{relative}"
            )


def validate_fold_boundary(*, training_end_ordinal: int, test_ordinal: int) -> None:
    if (
        isinstance(training_end_ordinal, bool)
        or isinstance(test_ordinal, bool)
        or not isinstance(training_end_ordinal, int)
        or not isinstance(test_ordinal, int)
        or training_end_ordinal < INITIAL_TRAINING_ISSUES
        or test_ordinal != training_end_ordinal + 1
        or test_ordinal < INITIAL_TRAINING_ISSUES + 1
        or test_ordinal > HISTORICAL_ISSUE_COUNT
    ):
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_fold_boundary_invalid"
        )


def build_marginal_static_historical_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    repair_v2_health_decision_execution: Mapping[str, Any],
    repair_v2_health_decision: Mapping[str, Any],
    marginal_static_contract_execution: Mapping[str, Any],
    marginal_static_measurement_contract: Mapping[str, Any],
    measurement_contract_design_execution: Mapping[str, Any],
    gate_compiler_contract: Mapping[str, Any],
    frozen_preregistration: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticHistoricalDesignRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_parents(
        repair_v2_health_decision_execution=repair_v2_health_decision_execution,
        repair_v2_health_decision=repair_v2_health_decision,
        marginal_static_contract_execution=marginal_static_contract_execution,
        marginal_static_measurement_contract=marginal_static_measurement_contract,
        measurement_contract_design_execution=measurement_contract_design_execution,
        gate_compiler_contract=gate_compiler_contract,
        frozen_preregistration=frozen_preregistration,
    )
    if not _is_digest(execution_id) or len(git_commit) != 40:
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_execution_identity_invalid"
        )
    validate_fold_boundary(training_end_ordinal=900, test_ordinal=901)
    validate_fold_boundary(training_end_ordinal=3480, test_ordinal=3481)

    source_digest = str(source_contract["artifact_digest"])
    base_parents = (
        source_digest,
        str(repair_v2_health_decision_execution["artifact_digest"]),
        str(repair_v2_health_decision["artifact_digest"]),
        str(marginal_static_contract_execution["artifact_digest"]),
        str(marginal_static_measurement_contract["artifact_digest"]),
        str(measurement_contract_design_execution["artifact_digest"]),
        str(gate_compiler_contract["artifact_digest"]),
        str(frozen_preregistration["artifact_digest"]),
    )
    dataset_boundary = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-dataset-boundary.v1"),
        artifact_type="m4_v2_marginal_static_historical_dataset_boundary",
        body={
            "status": "FROZEN_METADATA_ONLY",
            "source_contract_digest": source_digest,
            "legal_sample_space": json_compatible_copy(frozen["legal_sample_space"]),
            "historical_boundary": json_compatible_copy(frozen["historical_boundary"]),
            "dataset_materialized": False,
            "database_queries_during_capability": 0,
            "historical_red_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=base_parents,
        domain="dehps.m4.v2.marginal-static-historical-dataset-boundary.v1",
    )
    walk_forward_design = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-historical-walk-forward-design.v1"
        ),
        artifact_type="m4_v2_marginal_static_historical_walk_forward_design",
        body={
            "status": "FROZEN_RESULT_BLIND",
            "source_contract_digest": source_digest,
            "dataset_boundary_digest": dataset_boundary["artifact_digest"],
            "estimand_and_model": json_compatible_copy(frozen["estimand_and_model"]),
            "walk_forward": json_compatible_copy(frozen["walk_forward"]),
            "formal_historical_folds_executed": 0,
            "virtual_checkpoints_created": 0,
            "historical_red_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "production_action": "none",
        },
        parent_digests=(*base_parents, str(dataset_boundary["artifact_digest"])),
        domain=("dehps.m4.v2.marginal-static-historical-walk-forward-design.v1"),
    )
    inference_design = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-inference-design.v1"),
        artifact_type="m4_v2_marginal_static_historical_inference_design",
        body={
            "status": "FROZEN_RESULT_BLIND",
            "source_contract_digest": source_digest,
            "dataset_boundary_digest": dataset_boundary["artifact_digest"],
            "walk_forward_design_digest": walk_forward_design["artifact_digest"],
            "inference": json_compatible_copy(frozen["inference"]),
            "time_stability": json_compatible_copy(frozen["time_stability"]),
            "controls_and_invariants": json_compatible_copy(
                frozen["controls_and_invariants"]
            ),
            "bootstrap_replicates_executed": 0,
            "historical_red_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *base_parents,
            str(dataset_boundary["artifact_digest"]),
            str(walk_forward_design["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-inference-design.v1",
    )
    completion = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-historical-design-completion.v1"),
        artifact_type=(
            "m4_v2_marginal_static_historical_measurement_design_completion"
        ),
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "dataset_boundary_digest": dataset_boundary["artifact_digest"],
            "walk_forward_design_digest": walk_forward_design["artifact_digest"],
            "inference_design_digest": inference_design["artifact_digest"],
            "completion_fact": MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
            "next_consumer": MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
            "historical_issue_count": HISTORICAL_ISSUE_COUNT,
            "initial_training_issue_count": INITIAL_TRAINING_ISSUES,
            "evaluation_fold_count": EVALUATION_FOLD_COUNT,
            "formal_historical_folds_executed": 0,
            "bootstrap_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_red_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *base_parents,
            str(dataset_boundary["artifact_digest"]),
            str(walk_forward_design["artifact_digest"]),
            str(inference_design["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-design-completion.v1",
    )
    return MarginalStaticHistoricalDesignRun(
        dataset_boundary=dataset_boundary,
        walk_forward_design=walk_forward_design,
        inference_design=inference_design,
        completion=completion,
    )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    expected = {
        "task_key": MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY,
        "capability": MARGINAL_STATIC_HISTORICAL_DESIGN_CAPABILITY,
        "completion_fact": MARGINAL_STATIC_HISTORICAL_DESIGN_COMPLETION_FACT,
        "next_consumer": MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
        "repair_v2_health_decision_execution_digest": (
            REPAIR_V2_HEALTH_DECISION_EXECUTION_DIGEST
        ),
        "repair_v2_health_decision_digest": REPAIR_V2_HEALTH_DECISION_DIGEST,
        "marginal_static_contract_execution_digest": (
            MARGINAL_STATIC_CONTRACT_EXECUTION_DIGEST
        ),
        "marginal_static_measurement_contract_digest": (
            MARGINAL_STATIC_MEASUREMENT_CONTRACT_DIGEST
        ),
        "measurement_contract_design_execution_digest": (
            MEASUREMENT_CONTRACT_DESIGN_EXECUTION_DIGEST
        ),
        "gate_compiler_contract_digest": GATE_COMPILER_CONTRACT_DIGEST,
        "frozen_preregistration_digest": FROZEN_PREREGISTRATION_DIGEST,
        "legal_sample_space": EXPECTED_LEGAL_SAMPLE_SPACE,
        "historical_boundary": EXPECTED_HISTORICAL_BOUNDARY,
        "estimand_and_model": EXPECTED_ESTIMAND_AND_MODEL,
        "walk_forward": EXPECTED_WALK_FORWARD,
        "inference": EXPECTED_INFERENCE,
        "time_stability": EXPECTED_TIME_STABILITY,
        "controls_and_invariants": EXPECTED_CONTROLS_AND_INVARIANTS,
        "design_budget": {
            "formal_historical_folds": 0,
            "bootstrap_replicates_executed": 0,
            "database_queries_during_capability": 0,
            "historical_red_outcomes_read": 0,
            "statistical_results_read": 0,
            "evidence_records": 0,
            "accepted_models": 0,
            "production_actions": 0,
        },
        "historical_execution_authorized": False,
        "preregistration_authorized_next": True,
    }
    if dict(frozen) != expected:
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_frozen_contract_changed"
        )


def _validate_parents(
    *,
    repair_v2_health_decision_execution: Mapping[str, Any],
    repair_v2_health_decision: Mapping[str, Any],
    marginal_static_contract_execution: Mapping[str, Any],
    marginal_static_measurement_contract: Mapping[str, Any],
    measurement_contract_design_execution: Mapping[str, Any],
    gate_compiler_contract: Mapping[str, Any],
    frozen_preregistration: Mapping[str, Any],
) -> None:
    estimator = marginal_static_measurement_contract.get("estimator")
    score = marginal_static_measurement_contract.get("score")
    compiler = gate_compiler_contract.get("gate_compiler_contract")
    prereg_dataset = frozen_preregistration.get("dataset_identity")
    prereg_stability = frozen_preregistration.get("time_stability")
    if (
        repair_v2_health_decision_execution.get("task_key")
        != REPAIR_V2_HEALTH_DECISION_TASK_KEY
        or repair_v2_health_decision_execution.get("execution_id")
        != REPAIR_V2_HEALTH_DECISION_EXECUTION_ID
        or repair_v2_health_decision_execution.get("artifact_digest")
        != REPAIR_V2_HEALTH_DECISION_EXECUTION_DIGEST
        or repair_v2_health_decision_execution.get("status") != "COMPLETE"
        or repair_v2_health_decision_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or repair_v2_health_decision.get("artifact_digest")
        != REPAIR_V2_HEALTH_DECISION_DIGEST
        or repair_v2_health_decision.get("authoritative_decision")
        != "PASS_TO_HISTORICAL_MEASUREMENT"
        or repair_v2_health_decision.get("measurement_health") != "PASS"
        or repair_v2_health_decision.get("eligible_for_historical_measurement_design")
        is not True
        or repair_v2_health_decision.get("historical_outcomes_read") is not False
        or repair_v2_health_decision.get("evidence_created") is not False
        or marginal_static_contract_execution.get("task_key")
        != MARGINAL_STATIC_CONTRACT_TASK_KEY
        or marginal_static_contract_execution.get("execution_id")
        != MARGINAL_STATIC_CONTRACT_EXECUTION_ID
        or marginal_static_contract_execution.get("artifact_digest")
        != MARGINAL_STATIC_CONTRACT_EXECUTION_DIGEST
        or marginal_static_measurement_contract.get("artifact_digest")
        != MARGINAL_STATIC_MEASUREMENT_CONTRACT_DIGEST
        or not isinstance(estimator, Mapping)
        or estimator.get("estimator_id") != "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
        or estimator.get("minimum_training_issues") != INITIAL_TRAINING_ISSUES
        or estimator.get("formula") != "q_i=(c_i+2/11)/(n+1)"
        or estimator.get("exact_sum_identity") != "sum_i q_i=(6*n+6)/(n+1)=6"
        or not isinstance(score, Mapping)
        or score.get("baseline_q_i") != "2/11"
        or score.get("unit") != "bits_per_issue"
        or measurement_contract_design_execution.get("task_key")
        != MEASUREMENT_CONTRACT_DESIGN_TASK_KEY
        or measurement_contract_design_execution.get("execution_id")
        != MEASUREMENT_CONTRACT_DESIGN_EXECUTION_ID
        or measurement_contract_design_execution.get("artifact_digest")
        != MEASUREMENT_CONTRACT_DESIGN_EXECUTION_DIGEST
        or gate_compiler_contract.get("artifact_digest")
        != GATE_COMPILER_CONTRACT_DIGEST
        or not isinstance(compiler, Mapping)
        or compiler.get("practical_threshold_bits_per_issue")
        != PRACTICAL_THRESHOLD_BITS_PER_ISSUE
        or compiler.get("multiplicity", {}).get("family")
        != "fixed_three_primary_branch_endpoints"
        or compiler.get("multiplicity", {}).get("method") != "HOLM"
        or frozen_preregistration.get("artifact_digest")
        != FROZEN_PREREGISTRATION_DIGEST
        or preregistration_digest(frozen_preregistration)
        != FROZEN_PREREGISTRATION_DIGEST
        or not isinstance(prereg_dataset, Mapping)
        or prereg_dataset.get("history_dataset_digest") != HISTORY_DATASET_DIGEST
        or prereg_dataset.get("start_issue") != "2003001"
        or prereg_dataset.get("end_issue") != "2026084"
        or prereg_dataset.get("issue_count") != HISTORICAL_ISSUE_COUNT
        or not isinstance(prereg_stability, Mapping)
        or prereg_stability.get("primary_requirement", {}).get("segments")
        != EXPECTED_TIME_STABILITY["primary_halves"]
        or prereg_stability.get("sensitivity", {}).get("segments")
        != EXPECTED_TIME_STABILITY["thirds_sensitivity"]
    ):
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_parent_changed"
        )


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: tuple[str, ...],
    domain: str,
) -> dict[str, Any]:
    if not parent_digests or any(not _is_digest(item) for item in parent_digests):
        raise MarginalStaticHistoricalDesignError(
            "marginal_static_historical_design_parent_digest_invalid"
        )
    payload = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
