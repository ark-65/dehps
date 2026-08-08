from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY = (
    "m4-v2-marginal-static-historical-measurement-gate-compiler"
)
MARGINAL_STATIC_HISTORICAL_GATE_CAPABILITY = (
    "m4_v2_marginal_static_historical_measurement_gate_compiler"
)
MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT = (
    "m4-v2-marginal-static-historical-measurement-gate-compiler:COMPLETE"
)
MARGINAL_STATIC_HISTORICAL_GATE_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-historical-gate-source-v1.json"
)
PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY = "prediction-v2-promotion-planner"

MARGINAL_STATIC_HISTORICAL_EVIDENCE_FACTS = {
    value: f"m4-v2-marginal-static-historical-evidence:{value}"
    for value in ("POSITIVE", "NEGATIVE", "INCONCLUSIVE")
}

GATE_COMPILER_CONTRACT_DIGEST = (
    "9f9519be92fb5db4a4fb4939d1d5d3d32f7646a6e449f3dd20fd5c63b409f821"
)
HISTORICAL_EXECUTION_TASK_KEY = "m4-v2-marginal-static-historical-measurement-execution"
HISTORICAL_EXECUTION_COMPLETION_FACT = (
    "m4-v2-marginal-static-historical-measurement-execution:COMPLETE"
)
HISTORICAL_EXECUTION_ID = (
    "8cfbd33f314ebabdf3a334cfe96887c9802580bff91e8ab43304f1c6b67ef52a"
)
HISTORICAL_EXECUTION_ARTIFACT_DIGEST = (
    "046d08b7f2fba0514b64d228b5492b11f607753376d54947f7f6c3515300b462"
)
HISTORICAL_EXECUTION_SOURCE_CONTRACT_DIGEST = (
    "dd034e9a6358af0090ce77d9896da2df28616db57374c71f7c89058c69ed71d2"
)
HISTORICAL_COMPLETION_INDEX_DIGEST = (
    "cb6e184beb00bdb22af28a4ee6770240327f59f0fd171f443315841866b421a3"
)
HISTORICAL_INFERENCE_AGGREGATE_DIGEST = (
    "36056c0168bf71a995ec2a0bb9bf4663b0222b8fce621899a1e861282597e841"
)
HISTORICAL_BRANCH_CANDIDATE_DIGEST = (
    "5044252bd63afb00bd7719a4c20febf29a5ce41ab2f6679def643d450f9eb2d0"
)
HISTORICAL_EXECUTION_COMPLETION_DIGEST = (
    "f66218ac1261f3466c0d36d11f91f5c362899e08c2bd9e310384178161517464"
)

BRANCH_IDS = (
    "MARGINAL_STATIC",
    "TEMPORAL_MARGINAL_INCREMENT",
    "JOINT_RESIDUAL_INCREMENT",
)
FAMILYWISE_ALPHA = 0.05
PRACTICAL_THRESHOLD = 0.01
SIMULTANEOUS_CONFIDENCE = 0.95
PER_BRANCH_ALPHA = FAMILYWISE_ALPHA / len(BRANCH_IDS)
HISTORICAL_FOLD_COUNT = 2581
BOOTSTRAP_CHILD_COUNT = 16000
FOLD_SHARD_COUNT = 11
HALF_COUNTS = (1291, 1290)
THIRD_COUNTS = (861, 860, 860)

_EXPECTED_RESEARCH_REQUEST_KEY = (
    "research-m4-v2-marginal-static-historical-measurement-gate-round-55-20260808"
)
_EXPECTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-v2-marginal-static-historical-measurement-gate-round-55-20260808"
)
_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/information_theory/"
    "measurement_system_v2/marginal_static_historical_gate.py"
)
FROZEN_CONTRACT_DIGEST = (
    "5f09bf14d56eea92b9d0637dab2fbf8e1a5363849324aef7bad35509cc3272d7"
)


class MarginalStaticHistoricalGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticHistoricalGateRun:
    baseline_model: Mapping[str, Any]
    candidate_model: Mapping[str, Any]
    gate_output: Mapping[str, Any]
    evidence: Mapping[str, Any]
    eligibility: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.baseline_model,
            self.candidate_model,
            self.gate_output,
            self.evidence,
            self.eligibility,
            self.completion,
        )

    @property
    def historical_evidence(self) -> str:
        return str(self.evidence["historical_evidence"])

    @property
    def evidence_fact(self) -> str:
        return str(self.evidence["evidence_fact"])


def load_marginal_static_historical_gate_source_contract(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticHistoricalGateError(
            f"marginal_static_historical_gate_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-historical-gate-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_historical_gate_source"
        or payload.get("contract_key") != "M4_V2_MARGINAL_STATIC_HISTORICAL_GATE_SOURCE"
        or payload.get("research_request_key") != _EXPECTED_RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != 373
        or payload.get("research_execution_id") != 294
        or payload.get("engineering_request_key") != _EXPECTED_ENGINEERING_REQUEST_KEY
        or payload.get("engineering_request_id") != 374
        or payload.get("engineering_execution_id") != 295
        or payload.get("result_aware") is not True
        or payload.get("engineering_durable_result_read") is not False
        or payload.get("historical_rows_read") != 0
        or payload.get("folds_executed") != 0
        or payload.get("bootstrap_children_executed") != 0
        or payload.get("registered_children") != 6
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or len(entries) != 1
        or not isinstance(frozen, dict)
        or payload.get("frozen_contract_digest") != FROZEN_CONTRACT_DIGEST
        or canonical_digest(
            frozen,
            domain="dehps.m4.v2.marginal-static-historical-gate-frozen-contract.v1",
        )
        != FROZEN_CONTRACT_DIGEST
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.marginal-static-historical-gate-source-set.v1",
        )
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_source_invalid"
        )
    entry = entries[0]
    if (
        not isinstance(entry, dict)
        or entry.get("path") != _SOURCE_MODULE_PATH
        or not _is_digest(entry.get("content_sha256"))
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_source_entry_invalid"
        )
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_historical_gate_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticHistoricalGateError(
                f"marginal_static_historical_gate_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticHistoricalGateError(
                f"marginal_static_historical_gate_source_modified:{relative}"
            )


def build_marginal_static_historical_gate_artifacts(
    *,
    source_contract: Mapping[str, Any],
    gate_compiler_contract: Mapping[str, Any],
    historical_execution: Mapping[str, Any],
    completion_index: Mapping[str, Any],
    inference_aggregate: Mapping[str, Any],
    branch_candidate: Mapping[str, Any],
    historical_execution_completion: Mapping[str, Any],
    require_registered_identities: bool = True,
) -> MarginalStaticHistoricalGateRun:
    _validate_frozen_contract(source_contract["frozen_contract"])
    _validate_gate_contract(gate_compiler_contract)
    _validate_parent_artifacts(
        historical_execution=historical_execution,
        completion_index=completion_index,
        inference_aggregate=inference_aggregate,
        branch_candidate=branch_candidate,
        historical_execution_completion=historical_execution_completion,
        require_registered_identities=require_registered_identities,
    )
    source_digest = str(source_contract["artifact_digest"])
    endpoint_digest = str(branch_candidate["endpoint_digest"])
    last_shard = completion_index["shards"][-1]
    decision = _compile_decision(
        inference_aggregate=inference_aggregate,
        branch_candidate=branch_candidate,
    )
    evidence_value = decision["historical_evidence"]
    evidence_fact = MARGINAL_STATIC_HISTORICAL_EVIDENCE_FACTS[evidence_value]
    eligible = evidence_value == "POSITIVE"
    route = {
        "POSITIVE": "ELIGIBLE_FOR_PREDICTION_V2_PROMOTION_PLANNING",
        "NEGATIVE": "NOT_ELIGIBLE_FOR_PREDICTION_PROMOTION_AND_PIVOT_CANDIDATE",
        "INCONCLUSIVE": "NOT_ELIGIBLE_REQUIRES_EVIDENCE_REVIEW",
    }[evidence_value]

    baseline_model = _artifact(
        schema_version="dehps-m4-v2-legal-uniform-baseline-model-identity.v1",
        artifact_type="m4_v2_legal_uniform_baseline_model_identity",
        body={
            "status": "COMPLETE",
            "branch_id": "MARGINAL_STATIC",
            "model_id": "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE",
            "legal_sample_space": "choose_6_of_33_without_replacement",
            "number_event_probability": "2/11",
            "number_non_event_probability": "9/11",
            "score_unit": "bits_per_issue",
            "fit_required": False,
            "production_action": "none",
        },
        parent_digests=(source_digest, GATE_COMPILER_CONTRACT_DIGEST),
        domain="dehps.m4.v2.legal-uniform-baseline-model-identity.v1",
    )
    candidate_model = _artifact(
        schema_version="dehps-m4-v2-marginal-static-evaluated-model-identity.v1",
        artifact_type="m4_v2_marginal_static_evaluated_model_identity",
        body={
            "status": "COMPLETE",
            "branch_id": "MARGINAL_STATIC",
            "model_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "formula": "q_i(t)=(c_i(t-1)+2/11)/(n(t-1)+1)",
            "fit_window": "expanding_strict_prior_only",
            "fit_through_issue": "2026084",
            "historical_issue_count": 3481,
            "initial_training_issue_count": 900,
            "dataset_content_digest": inference_aggregate["dataset_content_digest"],
            "completion_index_digest": completion_index["artifact_digest"],
            "final_state_digest": last_shard["counts_after_digest"],
            "endpoint_digest": endpoint_digest,
            "baseline_model_artifact_digest": baseline_model["artifact_digest"],
            "candidate_baseline_distinct": True,
            "accepted_for_downstream_baseline": eligible,
            "eligible_for_production": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(completion_index["artifact_digest"]),
            str(inference_aggregate["artifact_digest"]),
            str(branch_candidate["artifact_digest"]),
            str(baseline_model["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-evaluated-model-identity.v1",
    )
    gate_output = _artifact(
        schema_version="dehps-m4-measurement-gate-compiler-output.v2",
        artifact_type="hierarchical_measurement_gate_output",
        body={
            "status": "COMPLETE",
            "contract_digest": GATE_COMPILER_CONTRACT_DIGEST,
            "required_branch_ids": list(BRANCH_IDS),
            "branch_outputs": [
                {
                    "branch_id": "MARGINAL_STATIC",
                    "measurement_health": branch_candidate["measurement_health"],
                    "historical_run_status": "COMPLETE",
                    "historical_evidence": evidence_value,
                    "primary_p_value": decision["raw_p_value"],
                    "holm_adjusted_p_value": decision["holm_adjusted_p_value"],
                    "endpoint_digest": endpoint_digest,
                    "baseline_artifact_digest": baseline_model["artifact_digest"],
                    "accepted_model_artifact_digest": (
                        candidate_model["artifact_digest"] if eligible else None
                    ),
                    "accepted_for_downstream_baseline": eligible,
                    "prediction_v2_planning_eligible": eligible,
                    "positive_stability_pass": decision["positive_stability_pass"],
                },
                *(
                    {
                        "branch_id": branch_id,
                        "measurement_health": "INCONCLUSIVE",
                        "historical_run_status": "NOT_RUN",
                        "historical_evidence": "NOT_RUN",
                        "primary_p_value": 1.0,
                        "holm_adjusted_p_value": 1.0,
                        "endpoint_digest": None,
                        "baseline_artifact_digest": None,
                        "accepted_model_artifact_digest": None,
                        "accepted_for_downstream_baseline": False,
                        "prediction_v2_planning_eligible": False,
                        "positive_stability_pass": False,
                    }
                    for branch_id in BRANCH_IDS[1:]
                ),
            ],
            "global_coverage": "PARTIAL",
            "global_evidence": (
                "CANDIDATE_INFORMATION_FOUND" if eligible else "INCONCLUSIVE"
            ),
            "candidate_branches": ["MARGINAL_STATIC"] if eligible else [],
            "inconclusive_branches": (
                list(BRANCH_IDS)
                if evidence_value == "INCONCLUSIVE"
                else list(BRANCH_IDS[1:])
            ),
            "multiplicity_method": "HOLM",
            "familywise_alpha": FAMILYWISE_ALPHA,
            "practical_threshold_bits_per_issue": PRACTICAL_THRESHOLD,
            "prediction_v2_planning_eligible": eligible,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            GATE_COMPILER_CONTRACT_DIGEST,
            str(historical_execution["artifact_digest"]),
            str(inference_aggregate["artifact_digest"]),
            str(branch_candidate["artifact_digest"]),
            str(baseline_model["artifact_digest"]),
            str(candidate_model["artifact_digest"]),
        ),
        domain="dehps.m4.measurement-v2.gate-output.v1",
    )
    evidence = _artifact(
        schema_version="dehps-m4-v2-marginal-static-historical-evidence.v1",
        artifact_type="m4_v2_marginal_static_historical_evidence",
        body={
            "status": "COMPLETE",
            "branch_id": "MARGINAL_STATIC",
            "historical_evidence": evidence_value,
            "evidence_fact": evidence_fact,
            "evidence_scope": (
                "conditional_historical_evidence_for_frozen_prequential_trajectory"
            ),
            "future_predictive_proof": False,
            "formal_historical_fold_count": HISTORICAL_FOLD_COUNT,
            "bootstrap_child_count": BOOTSTRAP_CHILD_COUNT,
            "raw_primary_p_value": decision["raw_p_value"],
            "holm_adjusted_p_value": decision["holm_adjusted_p_value"],
            "effect_interval_bits_per_issue": decision["effect_interval"],
            "equivalence_upper_bound_bits_per_issue": decision[
                "equivalence_upper_bound"
            ],
            "mde_bits_per_issue": decision["mde"],
            "equivalence_power_sufficient": decision["equivalence_power_sufficient"],
            "half_means_bits_per_issue": decision["half_means"],
            "positive_stability_pass": decision["positive_stability_pass"],
            "third_means_bits_per_issue": decision["third_means"],
            "thirds_have_decision_credit": False,
            "gate_output_digest": gate_output["artifact_digest"],
            "baseline_model_artifact_digest": baseline_model["artifact_digest"],
            "candidate_model_artifact_digest": candidate_model["artifact_digest"],
            "prediction_v2_planning_eligible": eligible,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(inference_aggregate["artifact_digest"]),
            str(branch_candidate["artifact_digest"]),
            str(gate_output["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-evidence.v1",
    )
    eligibility = _artifact(
        schema_version="dehps-prediction-v2-promotion-planning-eligibility.v1",
        artifact_type="prediction_v2_promotion_planning_eligibility",
        body={
            "status": "COMPLETE",
            "branch_id": "MARGINAL_STATIC",
            "historical_evidence": evidence_value,
            "decision": route,
            "eligible_for_prediction_v2_promotion_planning": eligible,
            "eligible_for_prediction_v2_production": False,
            "candidate_model_artifact_digest": candidate_model["artifact_digest"],
            "evidence_artifact_digest": evidence["artifact_digest"],
            "forward_evidence_required": True,
            "promotion_gate_opened": False,
            "next_consumer": PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(gate_output["artifact_digest"]),
            str(evidence["artifact_digest"]),
            str(candidate_model["artifact_digest"]),
        ),
        domain="dehps.prediction-v2.promotion-planning-eligibility.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-marginal-static-historical-gate-completion.v1",
        artifact_type="m4_v2_marginal_static_historical_gate_completion",
        body={
            "status": "COMPLETE",
            "source_contract_digest": source_digest,
            "historical_execution_id": historical_execution["execution_id"],
            "historical_execution_artifact_digest": historical_execution[
                "artifact_digest"
            ],
            "gate_output_digest": gate_output["artifact_digest"],
            "evidence_artifact_digest": evidence["artifact_digest"],
            "eligibility_artifact_digest": eligibility["artifact_digest"],
            "historical_evidence": evidence_value,
            "evidence_fact": evidence_fact,
            "evidence_created": True,
            "registered_child_count": 6,
            "database_queries_during_capability": 0,
            "historical_rows_read": 0,
            "folds_executed": 0,
            "bootstrap_children_executed": 0,
            "promotion_gate_opened": False,
            "completion_fact": MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT,
            "next_consumer": PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(gate_output["artifact_digest"]),
            str(evidence["artifact_digest"]),
            str(eligibility["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-historical-gate-completion.v1",
    )
    return MarginalStaticHistoricalGateRun(
        baseline_model=baseline_model,
        candidate_model=candidate_model,
        gate_output=gate_output,
        evidence=evidence,
        eligibility=eligibility,
        completion=completion,
    )


def _compile_decision(
    *,
    inference_aggregate: Mapping[str, Any],
    branch_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    raw_p = _probability(inference_aggregate.get("primary_raw_p_value"), "raw p")
    raw_family = inference_aggregate.get("fixed_family_raw_p_values")
    adjusted_family = inference_aggregate.get("fixed_family_holm_adjusted_p_values")
    if not isinstance(raw_family, Mapping) or not isinstance(adjusted_family, Mapping):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_family_missing"
        )
    expected_raw = {
        "MARGINAL_STATIC": raw_p,
        "TEMPORAL_MARGINAL_INCREMENT": 1.0,
        "JOINT_RESIDUAL_INCREMENT": 1.0,
    }
    expected_adjusted = _holm_adjusted(expected_raw)
    if (
        dict(raw_family) != expected_raw
        or set(adjusted_family) != set(BRANCH_IDS)
        or any(
            not _same_number(adjusted_family[key], expected_adjusted[key])
            for key in BRANCH_IDS
        )
        or not _same_number(
            inference_aggregate.get("holm_adjusted_p_value"),
            expected_adjusted["MARGINAL_STATIC"],
        )
        or not _same_number(branch_candidate.get("primary_p_value"), raw_p)
        or not _same_number(
            branch_candidate.get("holm_adjusted_p_value"),
            expected_adjusted["MARGINAL_STATIC"],
        )
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_holm_identity_changed"
        )
    interval = inference_aggregate.get("simultaneous_effect_interval_bits_per_issue")
    if not isinstance(interval, Mapping):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_interval_missing"
        )
    lower = _finite(interval.get("lower"), "interval lower")
    upper = _finite(interval.get("upper"), "interval upper")
    equivalence_upper = _finite(
        inference_aggregate.get("equivalence_upper_bound_bits_per_issue"),
        "equivalence upper",
    )
    if (
        lower > upper
        or not lower <= equivalence_upper <= upper
        or not _same_number(
            interval.get("simultaneous_confidence_level"),
            SIMULTANEOUS_CONFIDENCE,
        )
        or not _same_number(interval.get("per_branch_total_alpha"), PER_BRANCH_ALPHA)
        or interval.get("quantile_method") != "Hyndman-Fan type 7"
        or branch_candidate.get("effect_interval_bits_per_issue") != dict(interval)
        or not _same_number(
            branch_candidate.get("equivalence_upper_bound_bits_per_issue"),
            equivalence_upper,
        )
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_interval_identity_changed"
        )
    half_means = _finite_sequence(
        inference_aggregate.get("half_means_bits_per_issue"),
        expected_length=2,
        field="half means",
    )
    third_means = _finite_sequence(
        inference_aggregate.get("third_means_bits_per_issue"),
        expected_length=3,
        field="third means",
    )
    if (
        branch_candidate.get("half_means_bits_per_issue") != half_means
        or branch_candidate.get("third_means_bits_per_issue") != third_means
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_stability_identity_changed"
        )
    raw_mde = inference_aggregate.get("mde_bits_per_issue")
    mde = None if raw_mde is None else _finite(raw_mde, "MDE")
    if mde is not None and mde < 0:
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_mde_invalid"
        )
    power_sufficient = inference_aggregate.get("equivalence_power_sufficient")
    if not isinstance(power_sufficient, bool):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_power_invalid"
        )
    if (
        branch_candidate.get("mde_bits_per_issue") != raw_mde
        or branch_candidate.get("equivalence_power_sufficient") is not power_sufficient
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_equivalence_identity_changed"
        )
    adjusted = expected_adjusted["MARGINAL_STATIC"]
    stable = all(value > 0.0 for value in half_means)
    positive = adjusted <= FAMILYWISE_ALPHA and lower > PRACTICAL_THRESHOLD and stable
    negative = (
        adjusted > FAMILYWISE_ALPHA
        and power_sufficient
        and mde is not None
        and mde <= PRACTICAL_THRESHOLD
        and equivalence_upper <= PRACTICAL_THRESHOLD
    )
    evidence = "POSITIVE" if positive else "NEGATIVE" if negative else "INCONCLUSIVE"
    return {
        "historical_evidence": evidence,
        "raw_p_value": raw_p,
        "holm_adjusted_p_value": adjusted,
        "effect_interval": dict(interval),
        "equivalence_upper_bound": equivalence_upper,
        "mde": mde,
        "equivalence_power_sufficient": power_sufficient,
        "half_means": half_means,
        "third_means": third_means,
        "positive_stability_pass": stable,
    }


def _validate_parent_artifacts(
    *,
    historical_execution: Mapping[str, Any],
    completion_index: Mapping[str, Any],
    inference_aggregate: Mapping[str, Any],
    branch_candidate: Mapping[str, Any],
    historical_execution_completion: Mapping[str, Any],
    require_registered_identities: bool,
) -> None:
    _verify_artifact(
        historical_execution,
        domain="dehps.research-os.mainline-execution.v1",
    )
    _verify_artifact(
        completion_index,
        domain="dehps.m4.v2.marginal-static-historical-completion-index.v1",
    )
    _verify_artifact(
        inference_aggregate,
        domain="dehps.m4.v2.marginal-static-historical-inference-aggregate.v1",
    )
    _verify_artifact(
        branch_candidate,
        domain="dehps.m4.v2.marginal-static-historical-branch-candidate.v1",
    )
    _verify_artifact(
        historical_execution_completion,
        domain="dehps.m4.v2.marginal-static-historical-execution-completion.v1",
    )
    if require_registered_identities and (
        historical_execution.get("artifact_digest")
        != HISTORICAL_EXECUTION_ARTIFACT_DIGEST
        or completion_index.get("artifact_digest") != HISTORICAL_COMPLETION_INDEX_DIGEST
        or inference_aggregate.get("artifact_digest")
        != HISTORICAL_INFERENCE_AGGREGATE_DIGEST
        or branch_candidate.get("artifact_digest") != HISTORICAL_BRANCH_CANDIDATE_DIGEST
        or historical_execution_completion.get("artifact_digest")
        != HISTORICAL_EXECUTION_COMPLETION_DIGEST
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_registered_identity_changed"
        )
    endpoint = completion_index.get("canonical_score_sequence_digest")
    if (
        historical_execution.get("artifact_type") != "research_os_mainline_execution"
        or historical_execution.get("task_key") != HISTORICAL_EXECUTION_TASK_KEY
        or historical_execution.get("execution_id") != HISTORICAL_EXECUTION_ID
        or historical_execution.get("status") != "COMPLETE"
        or historical_execution.get("completion_classification")
        != "VALIDATED_IN_MAINLINE"
        or historical_execution.get("completion_fact")
        != HISTORICAL_EXECUTION_COMPLETION_FACT
        or historical_execution.get("historical_completion_index_digest")
        != completion_index.get("artifact_digest")
        or historical_execution.get("historical_inference_aggregate_digest")
        != inference_aggregate.get("artifact_digest")
        or historical_execution.get("historical_branch_candidate_digest")
        != branch_candidate.get("artifact_digest")
        or historical_execution.get("historical_execution_completion_digest")
        != historical_execution_completion.get("artifact_digest")
        or historical_execution.get("formal_historical_folds_executed")
        != HISTORICAL_FOLD_COUNT
        or historical_execution.get("bootstrap_children_executed")
        != BOOTSTRAP_CHILD_COUNT
        or historical_execution.get("duplicate_validation") is not False
        or historical_execution.get("evidence_created") is not False
        or historical_execution.get("production_action") != "none"
        or completion_index.get("status") != "COMPLETE"
        or completion_index.get("completed_shard_count") != FOLD_SHARD_COUNT
        or completion_index.get("completed_fold_count") != HISTORICAL_FOLD_COUNT
        or not _is_digest(endpoint)
        or not isinstance(completion_index.get("shards"), list)
        or len(completion_index["shards"]) != FOLD_SHARD_COUNT
        or completion_index.get("evidence_created") is not False
        or inference_aggregate.get("status") != "COMPLETE"
        or inference_aggregate.get("score_sequence_digest") != endpoint
        or inference_aggregate.get("formal_historical_folds_executed")
        != HISTORICAL_FOLD_COUNT
        or inference_aggregate.get("bootstrap_children_executed")
        != BOOTSTRAP_CHILD_COUNT
        or inference_aggregate.get("complete_run") is not True
        or inference_aggregate.get("partial_run_evidence") != "forbidden"
        or inference_aggregate.get("evidence_created") is not False
        or branch_candidate.get("status") != "READY_FOR_GATE_COMPILER_AFTER_REPLAY"
        or branch_candidate.get("branch_id") != "MARGINAL_STATIC"
        or branch_candidate.get("gate_compiler_contract_digest")
        != GATE_COMPILER_CONTRACT_DIGEST
        or branch_candidate.get("inference_aggregate_digest")
        != inference_aggregate.get("artifact_digest")
        or branch_candidate.get("endpoint_digest") != endpoint
        or branch_candidate.get("candidate_estimator_id")
        != "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
        or branch_candidate.get("baseline_id") != "LEGAL_UNIFORM_NUMBER_EVENT_BASELINE"
        or branch_candidate.get("candidate_baseline_distinct") is not True
        or branch_candidate.get("measurement_health") != "PASS"
        or branch_candidate.get("historical_run_status") != "COMPLETE"
        or branch_candidate.get("decision") is not None
        or branch_candidate.get("decision_compiled") is not False
        or branch_candidate.get("evidence_created") is not False
        or branch_candidate.get("accepted_model_artifact_digest") is not None
        or branch_candidate.get("promotion_gate_opened") is not False
        or historical_execution_completion.get("status") != "COMPLETE"
        or historical_execution_completion.get("execution_id")
        != historical_execution.get("execution_id")
        or historical_execution_completion.get("completion_index_digest")
        != completion_index.get("artifact_digest")
        or historical_execution_completion.get("inference_aggregate_digest")
        != inference_aggregate.get("artifact_digest")
        or historical_execution_completion.get("branch_candidate_digest")
        != branch_candidate.get("artifact_digest")
        or historical_execution_completion.get("completion_fact")
        != HISTORICAL_EXECUTION_COMPLETION_FACT
        or historical_execution_completion.get("evidence_created") is not False
        or any(
            item.get("shard_index") != index
            or not _is_digest(item.get("artifact_digest"))
            or not _is_digest(item.get("counts_after_digest"))
            for index, item in enumerate(completion_index["shards"])
        )
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_parent_lineage_invalid"
        )


def _validate_gate_contract(contract: Mapping[str, Any]) -> None:
    gate = contract.get("gate_compiler_contract")
    if (
        contract.get("artifact_type") != "measurement_v2_gate_compiler_contract"
        or contract.get("artifact_digest") != GATE_COMPILER_CONTRACT_DIGEST
        or not isinstance(gate, Mapping)
        or gate.get("required_branch_ids") != list(BRANCH_IDS)
        or gate.get("multiplicity", {}).get("family")
        != "fixed_three_primary_branch_endpoints"
        or gate.get("multiplicity", {}).get("method") != "HOLM"
        or gate.get("multiplicity", {}).get("familywise_alpha") != FAMILYWISE_ALPHA
        or gate.get("multiplicity", {}).get("not_run_or_invalid_branch_p_value") != 1
        or gate.get("practical_threshold_bits_per_issue") != PRACTICAL_THRESHOLD
        or gate.get("simultaneous_confidence_level") != SIMULTANEOUS_CONFIDENCE
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_compiler_contract_changed"
        )


def _validate_frozen_contract(frozen: Mapping[str, Any]) -> None:
    if (
        frozen.get("task_key") != MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
        or frozen.get("capability") != MARGINAL_STATIC_HISTORICAL_GATE_CAPABILITY
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_HISTORICAL_GATE_COMPLETION_FACT
        or frozen.get("next_consumer") != PREDICTION_V2_PROMOTION_PLANNER_TASK_KEY
        or frozen.get("gate_compiler_contract_digest") != GATE_COMPILER_CONTRACT_DIGEST
        or frozen.get("historical_execution_id") != HISTORICAL_EXECUTION_ID
        or frozen.get("historical_execution_artifact_digest")
        != HISTORICAL_EXECUTION_ARTIFACT_DIGEST
        or frozen.get("completion_index_digest") != HISTORICAL_COMPLETION_INDEX_DIGEST
        or frozen.get("inference_aggregate_digest")
        != HISTORICAL_INFERENCE_AGGREGATE_DIGEST
        or frozen.get("branch_candidate_digest") != HISTORICAL_BRANCH_CANDIDATE_DIGEST
        or frozen.get("historical_execution_completion_digest")
        != HISTORICAL_EXECUTION_COMPLETION_DIGEST
        or frozen.get("fixed_primary_family") != list(BRANCH_IDS)
        or frozen.get("familywise_alpha") != FAMILYWISE_ALPHA
        or frozen.get("not_run_branch_p_value") != 1.0
        or frozen.get("practical_threshold_bits_per_issue") != PRACTICAL_THRESHOLD
        or frozen.get("positive_rule")
        != "health_PASS_and_complete_and_distinct_models_and_Holm_p_lte_0.05_and_lower_gt_0.01_and_both_half_means_gt_0"
        or frozen.get("negative_rule")
        != "health_PASS_and_complete_and_distinct_models_and_Holm_p_gt_0.05_and_equivalence_power_sufficient_and_0_lte_MDE_lte_0.01_and_equivalence_upper_lte_0.01"
        or frozen.get("otherwise") != "INCONCLUSIVE"
        or frozen.get("half_counts") != list(HALF_COUNTS)
        or frozen.get("third_counts") != list(THIRD_COUNTS)
        or frozen.get("thirds_have_decision_credit") is not False
        or frozen.get("global_coverage") != "PARTIAL"
        or frozen.get("global_positive") != "CANDIDATE_INFORMATION_FOUND"
        or frozen.get("global_nonpositive") != "INCONCLUSIVE"
        or frozen.get("registered_child_count") != 6
        or frozen.get("registered_total_with_mainline_execution") != 7
        or frozen.get("evidence_scope")
        != "conditional_historical_evidence_for_frozen_prequential_trajectory_not_forward_proof"
        or frozen.get("promotion_gate_opened") is not False
        or frozen.get("production_action") != "none"
    ):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_frozen_contract_changed"
        )


def _holm_adjusted(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(
        p_values.items(),
        key=lambda item: (item[1], BRANCH_IDS.index(item[0])),
    )
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for index, (branch_id, p_value) in enumerate(ordered):
        running = max(running, (count - index) * p_value)
        adjusted[branch_id] = min(1.0, running)
    return adjusted


def _probability(value: Any, field: str) -> float:
    number = _finite(value, field)
    if not 0.0 <= number <= 1.0:
        raise MarginalStaticHistoricalGateError(
            f"marginal_static_historical_gate_{field.replace(' ', '_')}_invalid"
        )
    return number


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MarginalStaticHistoricalGateError(
            f"marginal_static_historical_gate_{field.replace(' ', '_')}_invalid"
        )
    number = float(value)
    if not math.isfinite(number):
        raise MarginalStaticHistoricalGateError(
            f"marginal_static_historical_gate_{field.replace(' ', '_')}_invalid"
        )
    return number


def _finite_sequence(value: Any, *, expected_length: int, field: str) -> list[float]:
    if not isinstance(value, list) or len(value) != expected_length:
        raise MarginalStaticHistoricalGateError(
            f"marginal_static_historical_gate_{field.replace(' ', '_')}_invalid"
        )
    return [_finite(item, field) for item in value]


def _same_number(left: Any, right: Any) -> bool:
    try:
        left_value = _finite(left, "numeric identity")
        right_value = _finite(right, "numeric identity")
    except MarginalStaticHistoricalGateError:
        return False
    return math.isclose(left_value, right_value, rel_tol=0.0, abs_tol=1e-15)


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
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


def _verify_artifact(artifact: Mapping[str, Any], *, domain: str) -> None:
    identity = dict(artifact)
    observed = identity.pop("artifact_digest", None)
    if observed != canonical_digest(identity, domain=domain):
        raise MarginalStaticHistoricalGateError(
            "marginal_static_historical_gate_parent_digest_invalid"
        )


def _is_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
