from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-design"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY = (
    "m4_v2_marginal_static_measurement_repair_v2_design"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-repair-v2-design:FROZEN"
)
MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-v2-preregistration"
)
MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-repair-v2-design-source-v1.json"
)

REPAIR_HEALTH_DECISION_TASK_KEY = (
    "m4-v2-marginal-static-measurement-repair-health-decision"
)
REPAIR_HEALTH_DECISION_TASK_DIGEST = (
    "3b0c6fbf31b37a7974990522ce7c1e593cb989a3bc853e2fd6fdcea8aed193a7"
)
REPAIR_HEALTH_DECISION_EXECUTION_ID = (
    "cae0235e700f5f6fbb61019888bafeedad2a596c904802f654bb6cee78471a87"
)
REPAIR_HEALTH_DECISION_EXECUTION_DIGEST = (
    "b124ab0119279ec498dc5f94e0cba53395aaced8da81be30f55e28892ddd6233"
)
REPAIR_HEALTH_DECISION_DIGEST = (
    "0ffafc6b5d89e4e17e71c981b985bd228d4ed20686fd85bd79e84461c642fcb5"
)
REPAIR_HEALTH_RESULT_DIGEST = (
    "f7bc1d3a2d64945eb8a93d1f9afec499f11e4f7c90a1b91a8e1825e26d1dce3f"
)

NULL_FIXTURE_ID = "NULL_UNIFORM_LEGAL_SIX_OF_33"
T1_FIXTURE_ID = "V2_T1_OVERLAP_ODDS_2_MARKOV"
J1_FIXTURE_ID = "V2_J1_HISTORY_IS4_LAMBDA_HALF"
M1_FIXTURE_ID = "V2_M1_GROUP_ODDS_2_STATIONARY"
IID_NULL_FAMILY = "IID_UNIFORM"
T1_NULL_FAMILY = "T1_MARKOV_STATIONARY"
J1_NULL_FAMILY = "J1_WITHIN_DRAW_IS4"
EXPECTED_NULL_FAMILY_BY_FIXTURE = {
    NULL_FIXTURE_ID: IID_NULL_FAMILY,
    M1_FIXTURE_ID: IID_NULL_FAMILY,
    T1_FIXTURE_ID: T1_NULL_FAMILY,
    J1_FIXTURE_ID: J1_NULL_FAMILY,
}
EXPECTED_SCALES = ("FORWARD_61", "HISTORICAL_2581")
EXPECTED_FAILED_CONTROL_CELL_IDS = (
    "BASE:V2_J1_HISTORY_IS4_LAMBDA_HALF:HISTORICAL_2581",
    "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:FORWARD_61",
    "BASE:V2_T1_OVERLAP_ODDS_2_MARKOV:HISTORICAL_2581",
)

CONFORMAL_ALPHA = 0.05
REFERENCE_SCORES_PER_BLOCK = 19
CONFORMAL_BLOCK_SIZE = 20
EVALUATION_REPLICATES_PER_CELL = 1024
EVALUATION_CELL_COUNT = 14
NEGATIVE_CONTROL_COUNT = 6
NULL_FAMILY_COUNT = 3
SCALE_COUNT = 2
CALIBRATION_REFERENCE_REPLICATES = 116_736
EVALUATION_REPLICATES = 14_336
TOTAL_REPLICATES = 131_072
EXECUTION_SHARD_SIZE = 64
EXECUTION_SHARDS = 2048
PLANNED_GENERATED_ISSUES = 291_110_912
PLANNED_OUTER_EVALUATION_ISSUES = 173_146_112
WILSON_Z = 1.959963984540054
NEGATIVE_CONTROL_WILSON_UPPER_MAX = 0.09
POSITIVE_CONTROL_WILSON_LOWER_MIN = 0.80
OLD_EVALUATION_REPLICATES_PER_CELL = 256
OLD_LARGEST_PASSING_DETECTION_COUNT = 14
NEW_LARGEST_PASSING_DETECTION_COUNT = 74
OLD_SINGLE_CONTROL_PASS_PROBABILITY = 0.6985308250304538
OLD_SIX_CONTROL_ALL_PASS_PROBABILITY = 0.11617520660518783
NEW_PER_CONTROL_FALSE_REPAIR_UPPER = 0.0007945187376967374
NEW_SIX_CONTROL_UNION_BOUND = 0.004767112426180425
NEW_SIX_CONTROL_EXACT_FALSE_REPAIR = 0.00475765355079516
FAMILYWISE_FALSE_REPAIR_MAX = 0.005
IDENTITY_ABSOLUTE_ERROR_MAX = 1e-12

ROOT_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_HEALTH_V1"
CALIBRATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_CALIBRATION_BLOCK_V1"
EVALUATION_SEED_DOMAIN = "M4_V2_MARGINAL_STATIC_REPAIR_V2_EVALUATION_V1"

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-repair-v2-design-round-48-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-repair-v2-design-round-48-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_repair_v2_design.py"
)


class MarginalStaticRepairV2DesignError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticRepairV2DesignRun:
    presample_feasibility: Mapping[str, Any]
    repair_v2_design: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.presample_feasibility, self.repair_v2_design, self.completion)


def load_marginal_static_repair_v2_design_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticRepairV2DesignError(
            f"marginal_static_repair_v2_design_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-repair-v2-design-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_repair_v2_design_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_REPAIR_V2_DESIGN_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 349
        or payload.get("research_execution_id") != 270
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 350
        or payload.get("engineering_execution_id") != 271
        or payload.get("result_aware") is not True
        or payload.get("formal_replicates_executed") != 0
        or payload.get("generated_issues") != 0
        or payload.get("compact_index_reads") != 0
        or payload.get("raw_replicates_regenerated") != 0
        or payload.get("sentinel_replicates_recomputed") != 0
        or payload.get("duplicate_validation") is not False
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not True
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.marginal-static-repair-v2-design-source-set.v1",
        )
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_repair_v2_design_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticRepairV2DesignError(
                f"marginal_static_repair_v2_design_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticRepairV2DesignError(
                f"marginal_static_repair_v2_design_source_modified:{relative}"
            )


def calibration_null_family(fixture_id: str) -> str:
    try:
        return EXPECTED_NULL_FAMILY_BY_FIXTURE[fixture_id]
    except KeyError as exc:
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_null_family_unrecognized"
        ) from exc


def independent_block_conformal_p_value(
    reference_scores: Sequence[float],
    evaluation_score: float,
) -> float:
    if len(reference_scores) != REFERENCE_SCORES_PER_BLOCK:
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_reference_count_invalid"
        )
    references = tuple(float(value) for value in reference_scores)
    evaluation = float(evaluation_score)
    if not math.isfinite(evaluation) or any(
        not math.isfinite(value) for value in references
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_score_nonfinite"
        )
    exceedances = sum(value >= evaluation for value in references)
    return (1 + exceedances) / CONFORMAL_BLOCK_SIZE


def independent_block_conformal_reject(
    reference_scores: Sequence[float],
    evaluation_score: float,
) -> bool:
    return (
        independent_block_conformal_p_value(reference_scores, evaluation_score)
        <= CONFORMAL_ALPHA
    )


def wilson_upper(successes: int, total: int) -> float:
    if (
        isinstance(successes, bool)
        or isinstance(total, bool)
        or not isinstance(successes, int)
        or not isinstance(total, int)
        or total <= 0
        or successes < 0
        or successes > total
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_wilson_input_invalid"
        )
    probability = successes / total
    denominator = 1.0 + WILSON_Z * WILSON_Z / total
    center = (probability + WILSON_Z * WILSON_Z / (2.0 * total)) / denominator
    radius = (
        WILSON_Z
        * math.sqrt(
            probability * (1.0 - probability) / total
            + WILSON_Z * WILSON_Z / (4.0 * total * total)
        )
        / denominator
    )
    return center + radius


def largest_passing_wilson_count(total: int) -> int:
    passing = [
        successes
        for successes in range(total + 1)
        if wilson_upper(successes, total) <= NEGATIVE_CONTROL_WILSON_UPPER_MAX
    ]
    if not passing:
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_wilson_boundary_missing"
        )
    return passing[-1]


def binomial_cdf(successes: int, total: int, probability: float) -> float:
    if (
        isinstance(successes, bool)
        or isinstance(total, bool)
        or not isinstance(successes, int)
        or not isinstance(total, int)
        or successes < 0
        or successes > total
        or not math.isfinite(probability)
        or not 0.0 <= probability <= 1.0
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_binomial_input_invalid"
        )
    with localcontext() as context:
        context.prec = 80
        decimal_probability = Decimal(str(probability))
        complement = Decimal(1) - decimal_probability
        result = sum(
            Decimal(math.comb(total, index))
            * decimal_probability**index
            * complement ** (total - index)
            for index in range(successes + 1)
        )
    return float(result)


def presample_operating_characteristics() -> dict[str, Any]:
    old_boundary = largest_passing_wilson_count(OLD_EVALUATION_REPLICATES_PER_CELL)
    new_boundary = largest_passing_wilson_count(EVALUATION_REPLICATES_PER_CELL)
    old_pass = binomial_cdf(
        old_boundary,
        OLD_EVALUATION_REPLICATES_PER_CELL,
        CONFORMAL_ALPHA,
    )
    new_pass = binomial_cdf(
        new_boundary,
        EVALUATION_REPLICATES_PER_CELL,
        CONFORMAL_ALPHA,
    )
    new_false = 1.0 - new_pass
    union_bound = NEGATIVE_CONTROL_COUNT * new_false
    exact_familywise = 1.0 - new_pass**NEGATIVE_CONTROL_COUNT
    payload = {
        "old": {
            "evaluation_replicates_per_cell": OLD_EVALUATION_REPLICATES_PER_CELL,
            "largest_passing_detection_count": old_boundary,
            "single_control_pass_probability_at_p_0_05": old_pass,
            "six_independent_controls_all_pass_probability_at_p_0_05": (
                old_pass**NEGATIVE_CONTROL_COUNT
            ),
        },
        "repair_v2": {
            "evaluation_replicates_per_cell": EVALUATION_REPLICATES_PER_CELL,
            "largest_passing_detection_count": new_boundary,
            "per_control_false_repair_probability_upper_bound": new_false,
            "six_control_union_bound": union_bound,
            "six_independent_control_exact_false_repair_probability": (
                exact_familywise
            ),
            "required_familywise_false_repair_probability_max": (
                FAMILYWISE_FALSE_REPAIR_MAX
            ),
        },
    }
    if (
        old_boundary != OLD_LARGEST_PASSING_DETECTION_COUNT
        or new_boundary != NEW_LARGEST_PASSING_DETECTION_COUNT
        or not math.isclose(
            old_pass,
            OLD_SINGLE_CONTROL_PASS_PROBABILITY,
            rel_tol=0.0,
            abs_tol=2e-15,
        )
        or not math.isclose(
            old_pass**NEGATIVE_CONTROL_COUNT,
            OLD_SIX_CONTROL_ALL_PASS_PROBABILITY,
            rel_tol=0.0,
            abs_tol=2e-15,
        )
        or not math.isclose(
            new_false,
            NEW_PER_CONTROL_FALSE_REPAIR_UPPER,
            rel_tol=0.0,
            abs_tol=2e-15,
        )
        or not math.isclose(
            union_bound,
            NEW_SIX_CONTROL_UNION_BOUND,
            rel_tol=0.0,
            abs_tol=2e-14,
        )
        or not math.isclose(
            exact_familywise,
            NEW_SIX_CONTROL_EXACT_FALSE_REPAIR,
            rel_tol=0.0,
            abs_tol=2e-15,
        )
        or union_bound > FAMILYWISE_FALSE_REPAIR_MAX
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_presample_proof_changed"
        )
    return payload


def build_marginal_static_repair_v2_design_artifacts(
    *,
    source_contract: Mapping[str, Any],
    repair_health_decision_execution: Mapping[str, Any],
    repair_health_decision: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticRepairV2DesignRun:
    frozen = source_contract.get("frozen_contract")
    if not isinstance(frozen, Mapping):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_contract_missing"
        )
    _validate_frozen_contract(frozen)
    _validate_parent_decision(
        execution=repair_health_decision_execution,
        decision=repair_health_decision,
    )
    if not _is_digest(execution_id) or len(git_commit) != 40:
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_execution_identity_invalid"
        )
    source_digest = str(source_contract["artifact_digest"])
    parent_digests = (
        source_digest,
        str(repair_health_decision_execution["artifact_digest"]),
        str(repair_health_decision["artifact_digest"]),
    )
    operating = presample_operating_characteristics()
    feasibility = _artifact(
        schema_version=(
            "dehps-m4-v2-marginal-static-repair-v2-presample-feasibility.v1"
        ),
        artifact_type=("m4_v2_marginal_static_repair_v2_presample_feasibility"),
        body={
            "status": "FROZEN_PRESAMPLE_FEASIBILITY",
            "source_contract_digest": source_digest,
            "repair_health_decision_digest": REPAIR_HEALTH_DECISION_DIGEST,
            "legal_sample_space": frozen["legal_sample_space"],
            "old_gate_operating_characteristic": operating["old"],
            "repair_v2_gate_operating_characteristic": operating["repair_v2"],
            "future_workload": frozen["future_workload"],
            "sample_size_selected_before_new_results": True,
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "compact_index_reads": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=("dehps.m4.v2.marginal-static-repair-v2-presample-feasibility.v1"),
    )
    design = _artifact(
        schema_version="dehps-m4-v2-marginal-static-repair-v2-design.v1",
        artifact_type="m4_v2_marginal_static_measurement_repair_v2_design",
        body={
            "status": "FROZEN_DESIGN",
            "branch_id": "MARGINAL_STATIC",
            "source_contract_digest": source_digest,
            "repair_health_result_digest": REPAIR_HEALTH_RESULT_DIGEST,
            "repair_health_decision_digest": REPAIR_HEALTH_DECISION_DIGEST,
            "old_measurement_health": "REPAIR",
            "old_decision_preserved": "REPAIR_MEASUREMENT_SYSTEM",
            "failed_control_cell_ids": list(EXPECTED_FAILED_CONTROL_CELL_IDS),
            "presample_feasibility_digest": feasibility["artifact_digest"],
            "diagnosis": frozen["diagnosis"],
            "frozen_estimator_and_gates": frozen["frozen_estimator_and_gates"],
            "calibration_strata": frozen["calibration_strata"],
            "independent_block_conformal": frozen["independent_block_conformal"],
            "presample_sample_size_proof": frozen["presample_sample_size_proof"],
            "future_workload": frozen["future_workload"],
            "seed_contract": frozen["seed_contract"],
            "decision_boundary": frozen["decision_boundary"],
            "automatic_pass_from_reanalysis": False,
            "same_seed_tuning": "forbidden",
            "posthoc_threshold_change": "forbidden",
            "next_consumer": MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "compact_index_reads": 0,
            "raw_replicates_regenerated": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "statistical_results_read": True,
            "evidence_created": False,
            "accepted_model_artifact_digest": None,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, str(feasibility["artifact_digest"])),
        domain="dehps.m4.v2.marginal-static-repair-v2-design.v1",
    )
    completion = _artifact(
        schema_version=("dehps-m4-v2-marginal-static-repair-v2-design-completion.v1"),
        artifact_type="m4_v2_marginal_static_repair_v2_design_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "repair_health_decision_digest": REPAIR_HEALTH_DECISION_DIGEST,
            "presample_feasibility_digest": feasibility["artifact_digest"],
            "repair_v2_design_digest": design["artifact_digest"],
            "completion_fact": MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT,
            "next_consumer": MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY,
            "formal_replicates_executed": 0,
            "generated_issues": 0,
            "compact_index_reads": 0,
            "raw_replicates_regenerated": 0,
            "sentinel_replicates_recomputed": 0,
            "duplicate_validation": False,
            "historical_outcomes_read": False,
            "evidence_created": False,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            str(feasibility["artifact_digest"]),
            str(design["artifact_digest"]),
        ),
        domain=("dehps.m4.v2.marginal-static-repair-v2-design-completion.v1"),
    )
    return MarginalStaticRepairV2DesignRun(
        presample_feasibility=feasibility,
        repair_v2_design=design,
        completion=completion,
    )


def _validate_parent_decision(
    *,
    execution: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> None:
    _verify_artifact(execution, domain="dehps.research-os.mainline-execution.v1")
    _verify_artifact(
        decision,
        domain="dehps.m4.v2.marginal-static-repair-health-decision.v1",
    )
    if (
        execution.get("artifact_type") != "research_os_mainline_execution"
        or execution.get("artifact_digest") != REPAIR_HEALTH_DECISION_EXECUTION_DIGEST
        or execution.get("execution_id") != REPAIR_HEALTH_DECISION_EXECUTION_ID
        or execution.get("task_key") != REPAIR_HEALTH_DECISION_TASK_KEY
        or execution.get("task_digest") != REPAIR_HEALTH_DECISION_TASK_DIGEST
        or execution.get("completion_classification") != "VALIDATED_IN_MAINLINE"
        or execution.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or execution.get("measurement_health") != "REPAIR"
        or execution.get("failed_control_cell_ids")
        != list(EXPECTED_FAILED_CONTROL_CELL_IDS)
        or execution.get("failed_control_cell_count") != 3
        or execution.get("registered_artifact_count") != 2
        or execution.get("generated_issues") != 0
        or execution.get("compact_index_reads") != 0
        or execution.get("raw_replicates_regenerated") != 0
        or execution.get("sentinel_replicates_recomputed") != 0
        or execution.get("duplicate_validation") is not False
        or execution.get("historical_outcomes_read") is not False
        or execution.get("evidence_created") is not False
        or execution.get("promotion_gate_opened") is not False
        or execution.get("production_action") != "none"
        or decision.get("artifact_type")
        != "m4_v2_marginal_static_measurement_repair_health_decision"
        or decision.get("artifact_digest") != REPAIR_HEALTH_DECISION_DIGEST
        or decision.get("health_result_digest") != REPAIR_HEALTH_RESULT_DIGEST
        or decision.get("measurement_health") != "REPAIR"
        or decision.get("decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or decision.get("failed_control_cell_ids")
        != list(EXPECTED_FAILED_CONTROL_CELL_IDS)
        or decision.get("failed_control_cell_count") != 3
        or decision.get("instrument_limit_cell_count") != 0
        or decision.get("eligible_for_historical_measurement") is not False
        or decision.get("manual_override") is not False
        or decision.get("threshold_changed") is not False
        or decision.get("duplicate_validation") is not False
        or decision.get("historical_outcomes_read") is not False
        or decision.get("evidence_created") is not False
        or decision.get("promotion_gate_opened") is not False
        or decision.get("production_action") != "none"
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_parent_decision_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    workload = frozen.get("future_workload")
    proof = frozen.get("presample_sample_size_proof")
    block = frozen.get("independent_block_conformal")
    strata = frozen.get("calibration_strata")
    estimator = frozen.get("frozen_estimator_and_gates")
    seeds = frozen.get("seed_contract")
    if (
        frozen.get("task_key") != MARGINAL_STATIC_REPAIR_V2_DESIGN_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_REPAIR_V2_DESIGN_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_REPAIR_V2_DESIGN_COMPLETION_FACT
        or frozen.get("next_consumer")
        != MARGINAL_STATIC_REPAIR_V2_PREREGISTRATION_TASK_KEY
        or frozen.get("repair_health_decision_digest") != REPAIR_HEALTH_DECISION_DIGEST
        or frozen.get("old_decision") != "REPAIR_MEASUREMENT_SYSTEM"
        or frozen.get("failed_control_cell_ids")
        != list(EXPECTED_FAILED_CONTROL_CELL_IDS)
        or not isinstance(strata, Mapping)
        or strata.get("null_family_by_fixture") != EXPECTED_NULL_FAMILY_BY_FIXTURE
        or strata.get("scales") != list(EXPECTED_SCALES)
        or strata.get("cross_family_pooling") != "forbidden"
        or strata.get("cross_scale_pooling") != "forbidden"
        or not isinstance(block, Mapping)
        or block.get("reference_scores_per_block") != REFERENCE_SCORES_PER_BLOCK
        or block.get("block_size") != CONFORMAL_BLOCK_SIZE
        or block.get("conformal_alpha") != CONFORMAL_ALPHA
        or block.get("tie_rule") != "reference_greater_or_equal_counts"
        or block.get("block_reuse_across_evaluation_indices") != "forbidden"
        or block.get("cross_index_independence_required") is not True
        or not isinstance(proof, Mapping)
        or proof.get("evaluation_replicates_per_cell") != EVALUATION_REPLICATES_PER_CELL
        or proof.get("negative_control_count") != NEGATIVE_CONTROL_COUNT
        or proof.get("wilson_largest_passing_detection_count")
        != NEW_LARGEST_PASSING_DETECTION_COUNT
        or proof.get("per_control_false_repair_probability_upper_bound")
        != NEW_PER_CONTROL_FALSE_REPAIR_UPPER
        or proof.get("six_control_union_bound") != NEW_SIX_CONTROL_UNION_BOUND
        or proof.get("required_familywise_false_repair_probability_max")
        != FAMILYWISE_FALSE_REPAIR_MAX
        or proof.get("sample_size_selected_before_new_results") is not True
        or not isinstance(workload, Mapping)
        or workload.get("calibration_reference_replicates")
        != CALIBRATION_REFERENCE_REPLICATES
        or workload.get("evaluation_replicates") != EVALUATION_REPLICATES
        or workload.get("total_replicates") != TOTAL_REPLICATES
        or workload.get("execution_shard_size") != EXECUTION_SHARD_SIZE
        or workload.get("execution_shards") != EXECUTION_SHARDS
        or workload.get("planned_generated_issues") != PLANNED_GENERATED_ISSUES
        or workload.get("planned_outer_evaluation_issues")
        != PLANNED_OUTER_EVALUATION_ISSUES
        or workload.get("nested_bootstrap_replicates") != 0
        or workload.get("database_reads_per_replicate") != 0
        or workload.get("database_writes_per_replicate") != 0
        or workload.get("duplicate_validation") is not False
        or not isinstance(estimator, Mapping)
        or estimator.get("conditional_identity_absolute_error_max")
        != IDENTITY_ABSOLUTE_ERROR_MAX
        or estimator.get("conformal_alpha") != CONFORMAL_ALPHA
        or estimator.get("negative_control_wilson_upper_95_max")
        != NEGATIVE_CONTROL_WILSON_UPPER_MAX
        or estimator.get("positive_control_wilson_lower_95_min")
        != POSITIVE_CONTROL_WILSON_LOWER_MIN
        or estimator.get("threshold_changed") is not False
        or estimator.get("estimator_changed") is not False
        or estimator.get("fixture_changed") is not False
        or not isinstance(seeds, Mapping)
        or seeds.get("root_seed_domain") != ROOT_SEED_DOMAIN
        or seeds.get("calibration_seed_domain") != CALIBRATION_SEED_DOMAIN
        or seeds.get("evaluation_seed_domain") != EVALUATION_SEED_DOMAIN
        or seeds.get("round_42_or_round_46_seed_reuse") is not False
        or seeds.get("calibration_evaluation_overlap") is not False
        or seeds.get("worker_or_shard_identity_in_seed") is not False
        or seeds.get("best_seed_selection") != "forbidden"
        or frozen.get("automatic_pass_from_reanalysis") is not False
        or frozen.get("same_seed_tuning") != "forbidden"
        or frozen.get("posthoc_threshold_change") != "forbidden"
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_contract_invalid"
        )
    for field in ("diagnosis", "legal_sample_space", "decision_boundary"):
        if not isinstance(frozen.get(field), Mapping):
            raise MarginalStaticRepairV2DesignError(
                "marginal_static_repair_v2_design_contract_invalid"
            )
    if (
        NULL_FAMILY_COUNT
        * SCALE_COUNT
        * EVALUATION_REPLICATES_PER_CELL
        * REFERENCE_SCORES_PER_BLOCK
        != CALIBRATION_REFERENCE_REPLICATES
        or EVALUATION_CELL_COUNT * EVALUATION_REPLICATES_PER_CELL
        != EVALUATION_REPLICATES
        or CALIBRATION_REFERENCE_REPLICATES + EVALUATION_REPLICATES != TOTAL_REPLICATES
        or TOTAL_REPLICATES // EXECUTION_SHARD_SIZE != EXECUTION_SHARDS
    ):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_workload_arithmetic_changed"
        )
    presample_operating_characteristics()


def _verify_artifact(payload: Mapping[str, Any], *, domain: str) -> None:
    digest = payload.get("artifact_digest")
    if not _is_digest(digest):
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_parent_digest_invalid"
        )
    identity = dict(payload)
    identity.pop("artifact_digest")
    if canonical_digest(identity, domain=domain) != digest:
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_parent_digest_invalid"
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
        raise MarginalStaticRepairV2DesignError(
            "marginal_static_repair_v2_design_parent_digest_invalid"
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
