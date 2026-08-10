from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest

from .m4_p3_result_blind_design import M4_P3_STRUCTURAL_UTILITY_GOAL_KEY
from .m4_p3_result_blind_execution import (
    COORDINATE_ORDER,
    FOLD_COUNT,
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
    PARENT_PREREGISTRATION_DIGEST,
    Sha256CounterStream,
)

M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_CAPABILITY = (
    "m4_p3_result_blind_structural_utility_evidence_compiler"
)
M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT = (
    "m4-p3-result-blind-structural-utility-evidence-compiler:COMPLETE"
)
M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT = (
    "research-contract:m4-p3-result-blind-structural-utility-evidence-compiler:approved"
)
M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/"
    "m4-p3-result-blind-structural-utility-evidence-compiler-source-v1.json"
)

RESEARCH_REQUEST_KEY = (
    "research-m4-p3-result-blind-structural-utility-evidence-compiler-"
    "round-130-20260810"
)
RESEARCH_REQUEST_ID = 462
RESEARCH_EXECUTION_ID = 383
RESEARCH_PARENT_REQUEST_ID = 461
RESEARCH_CONTEXT_FINGERPRINT = (
    "12ce0a5ba65d2d9ff1d3bebe43792bb6671aba9f2c24f2a572aa51e987fc9bb3"
)
RESEARCH_CONTRACT_DOMAIN = (
    "dehps.m4-p3.result-blind.structural-evidence-compiler.research-contract.v1"
)
RESEARCH_EXECUTION_CONTRACT_DIGEST = (
    "888881ea69e660c3c6ff62b5f7d9849b3fa79fcc23db22582e2fa8a8df8a8a32"
)

PARENT_EXECUTION_ID = (
    "df9c1cca8252f6cec16ca9740ec051f5c6dbb5df19eb6d363f2b4070c79b1619"
)
PARENT_EXECUTION_DIGEST = (
    "df1dd942bf0469b5a3ba47f1121fc7924c955c15f87c07ab32d5c5ebff148a61"
)
PARENT_RESULT_INDEX_DIGEST = (
    "62ccb47c00240b6191994e8df3be057810f8ef61e342e64cfa9958fb3cfb1475"
)
PARENT_EXECUTION_COMPLETION_DIGEST = (
    "0159b4d6048a9bf815c9ba426e51b3bcf3c0beae075088776956465a6814df4d"
)

CONTROL_ORDER = (
    "uniform_random_without_replacement",
    "legacy_structural_top100",
)
HYPOTHESIS_ORDER = tuple(
    f"{coordinate}:{control}"
    for coordinate in COORDINATE_ORDER
    for control in CONTROL_ORDER
)
PRIMARY_COORDINATES = frozenset(
    {
        "triple_coverage_ratio",
        "high_overlap_ticket_pair_rate",
        "normalized_pair_usage_entropy",
    }
)
PROTECTED_THRESHOLDS = {
    "pair_coverage_ratio": -(1.0 / 528.0),
    "largest_similarity_cluster_fraction": -0.01,
    "family_concentration_hhi": -0.0002,
}
BOOTSTRAP_RESAMPLES = 20_000
BLOCK_LENGTH = 5
BLOCKS_PER_RESAMPLE = 18
FAMILYWISE_ALPHA = 0.05
BOOTSTRAP_SEED_ROOT = (
    "c54c1dcd5c51f74bbe51a118676dd0e6da82fc80978e183df89d6190af27ad90"
)
EXPECTED_CAPABILITY_ARTIFACTS = 4

_SOURCE_MODULE_PATH = (
    "apps/worker-python/dehps/research_os/structural_utility/"
    "m4_p3_evidence_compiler.py"
)
_RESULT_INDEX_DOMAIN = "dehps.m4-p3.result-blind-structural-utility.result-index.v1"
_BOOTSTRAP_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility.bootstrap-family.v1"
)
_EVIDENCE_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility.structural-evidence.v1"
)
_DECISION_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility.route-decision.v1"
)
_COMPLETION_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility.evidence-completion.v1"
)


class M4P3StructuralEvidenceCompilerError(RuntimeError):
    pass


@dataclass(frozen=True)
class M4P3StructuralEvidenceCompilerRun:
    bootstrap_family: Mapping[str, Any]
    evidence: Mapping[str, Any]
    route_decision: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.bootstrap_family,
            self.evidence,
            self.route_decision,
            self.completion,
        )


def load_m4_p3_structural_evidence_compiler_source_contract(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M4P3StructuralEvidenceCompilerError(
            f"m4_p3_structural_evidence_source_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-p3-result-blind-structural-utility-evidence-compiler-source.v1"
        or payload.get("artifact_type")
        != "m4_p3_result_blind_structural_utility_evidence_compiler_source"
        or payload.get("contract_key")
        != "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE"
        or payload.get("research_request_key") != RESEARCH_REQUEST_KEY
        or payload.get("research_request_id") != RESEARCH_REQUEST_ID
        or payload.get("research_execution_id") != RESEARCH_EXECUTION_ID
        or payload.get("research_context_fingerprint") != RESEARCH_CONTEXT_FINGERPRINT
        or payload.get("research_execution_contract_digest")
        != RESEARCH_EXECUTION_CONTRACT_DIGEST
        or payload.get("result_blind") is not True
        or payload.get("execution_authorized") is not False
        or not isinstance(entries, list)
        or len(entries) != 1
        or entries[0].get("path") != _SOURCE_MODULE_PATH
        or payload.get("source_set_digest")
        != canonical_digest(
            {"source_entries": entries},
            domain="dehps.m4-information-theory.config.v1",
        )
        or payload.get("artifact_digest")
        != canonical_digest(
            {key: value for key, value in payload.items() if key != "artifact_digest"},
            domain="dehps.m4-information-theory.config.v1",
        )
    ):
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_source_invalid"
        )
    return payload


def verify_m4_p3_structural_evidence_compiler_source_bytes(
    *, root_dir: Path, contract: Mapping[str, Any]
) -> None:
    root = root_dir.resolve()
    entry = contract["source_entries"][0]
    path = (root / str(entry["path"])).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_source_missing"
        )
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("content_sha256"):
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_source_modified"
        )


def validate_research_contract(
    request: Mapping[str, Any], execution: Mapping[str, Any]
) -> Mapping[str, Any]:
    payload = request.get("payload")
    contract = payload.get("execution_contract") if isinstance(payload, Mapping) else None
    result = execution.get("result")
    work = result.get("work") if isinstance(result, Mapping) else None
    if (
        request.get("id") != RESEARCH_REQUEST_ID
        or request.get("request_key") != RESEARCH_REQUEST_KEY
        or request.get("status") != "completed"
        or request.get("parent_request_id") != RESEARCH_PARENT_REQUEST_ID
        or not isinstance(contract, Mapping)
        or contract.get("status") != "FROZEN_BEFORE_EVIDENCE_COMPILATION"
        or canonical_digest(contract, domain=RESEARCH_CONTRACT_DOMAIN)
        != RESEARCH_EXECUTION_CONTRACT_DIGEST
        or execution.get("id") != RESEARCH_EXECUTION_ID
        or execution.get("request_id") != RESEARCH_REQUEST_ID
        or execution.get("status") != "completed"
        or not isinstance(result, Mapping)
        or result.get("execution_contract_digest")
        != RESEARCH_EXECUTION_CONTRACT_DIGEST
        or result.get("execution_contract") != dict(contract)
        or not isinstance(work, Mapping)
        or any(value != 0 for value in work.values())
    ):
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_research_contract_invalid"
        )
    return contract


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
        "parent_digests": list(parent_digests),
        **dict(body),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _verify_digest(payload: Mapping[str, Any], *, domain: str) -> None:
    identity = dict(payload)
    digest = identity.pop("artifact_digest", None)
    if digest != canonical_digest(identity, domain=domain):
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_artifact_digest_mismatch"
        )


def _validate_result_index(
    result_index: Mapping[str, Any],
    *,
    expected_digest: str,
) -> dict[str, np.ndarray]:
    _verify_digest(result_index, domain=_RESULT_INDEX_DOMAIN)
    raw_series = result_index.get("favorable_difference_series")
    if (
        result_index.get("artifact_digest") != expected_digest
        or result_index.get("status") != "COMPLETE"
        or result_index.get("fold_count") != FOLD_COUNT
        or tuple(result_index.get("coordinate_order") or ()) != COORDINATE_ORDER
        or tuple(result_index.get("control_order") or ()) != CONTROL_ORDER
        or result_index.get("bootstrap_resamples_executed") != 0
        or result_index.get("holm_executed") is not False
        or result_index.get("evidence_created") is not False
        or result_index.get("route_decision_created") is not False
        or result_index.get("target_draw_rows_read") != 0
        or not isinstance(raw_series, Mapping)
        or set(raw_series) != set(HYPOTHESIS_ORDER)
    ):
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_result_index_invalid"
        )
    normalized: dict[str, np.ndarray] = {}
    for key in HYPOTHESIS_ORDER:
        value = np.asarray(raw_series[key], dtype=np.float64)
        if value.shape != (FOLD_COUNT,) or not np.isfinite(value).all():
            raise M4P3StructuralEvidenceCompilerError(
                "m4_p3_structural_evidence_series_invalid"
            )
        normalized[key] = value
    return normalized


def _bootstrap_indices(result_index_digest: str) -> np.ndarray:
    indices = np.empty(
        (BOOTSTRAP_RESAMPLES, FOLD_COUNT),
        dtype=np.uint16,
    )
    for resample_index in range(BOOTSTRAP_RESAMPLES):
        material = (
            f"{BOOTSTRAP_SEED_ROOT}|{result_index_digest}|{resample_index:05d}"
        ).encode()
        stream = Sha256CounterStream(hashlib.sha256(material).digest())
        position = 0
        for _ in range(BLOCKS_PER_RESAMPLE):
            start = stream.bounded(FOLD_COUNT)
            for offset in range(BLOCK_LENGTH):
                indices[resample_index, position] = (start + offset) % FOLD_COUNT
                position += 1
    return indices


def _threshold(coordinate: str) -> float:
    return 0.0 if coordinate in PRIMARY_COORDINATES else PROTECTED_THRESHOLDS[coordinate]


def _order_statistic(values: np.ndarray, *, probability: float) -> float:
    ordered = np.sort(values)
    index = math.ceil((BOOTSTRAP_RESAMPLES + 1) * probability) - 1
    return float(ordered[min(max(index, 0), BOOTSTRAP_RESAMPLES - 1)])


def compile_structural_evidence(
    *,
    result_index: Mapping[str, Any],
    source_contract_digest: str,
    expected_result_index_digest: str = PARENT_RESULT_INDEX_DIGEST,
) -> M4P3StructuralEvidenceCompilerRun:
    series = _validate_result_index(
        result_index,
        expected_digest=expected_result_index_digest,
    )
    indices = _bootstrap_indices(expected_result_index_digest)
    index_digest = hashlib.sha256(indices.astype(">u2", copy=False).tobytes()).hexdigest()
    bootstrap_means: dict[str, list[float]] = {}
    preliminary: dict[str, dict[str, Any]] = {}
    for key in HYPOTHESIS_ORDER:
        coordinate, control = key.split(":", 1)
        values = series[key]
        observed = float(np.mean(values, dtype=np.float64))
        means_array = np.mean(values[indices], axis=1, dtype=np.float64)
        if not math.isfinite(observed) or not np.isfinite(means_array).all():
            raise M4P3StructuralEvidenceCompilerError(
                "m4_p3_structural_evidence_numerical_degeneracy"
            )
        means = [float(value) for value in means_array]
        bootstrap_means[key] = means
        null_threshold = _threshold(coordinate)
        exceedance_count = int(
            np.count_nonzero(
                (means_array - observed) >= (observed - null_threshold)
            )
        )
        p_value = (1.0 + exceedance_count) / (BOOTSTRAP_RESAMPLES + 1.0)
        stability_count = int(
            np.count_nonzero(
                values > 0.0
                if coordinate in PRIMARY_COORDINATES
                else values >= null_threshold
            )
        )
        preliminary[key] = {
            "hypothesis_key": key,
            "coordinate": coordinate,
            "control": control,
            "decision_role": (
                "primary_support"
                if coordinate in PRIMARY_COORDINATES
                else "protected_non_regression"
            ),
            "observed_mean": observed,
            "null_threshold": null_threshold,
            "bootstrap_exceedance_count": exceedance_count,
            "unadjusted_p_value": p_value,
            "stability_count": stability_count,
            "stability_required": 60,
        }

    coordinate_rank = {value: index for index, value in enumerate(COORDINATE_ORDER)}
    control_rank = {value: index for index, value in enumerate(CONTROL_ORDER)}
    ordered_keys = sorted(
        HYPOTHESIS_ORDER,
        key=lambda key: (
            preliminary[key]["unadjusted_p_value"],
            coordinate_rank[preliminary[key]["coordinate"]],
            control_rank[preliminary[key]["control"]],
        ),
    )
    adjusted_running = 0.0
    results: dict[str, dict[str, Any]] = {}
    for position, key in enumerate(ordered_keys, start=1):
        remaining = len(HYPOTHESIS_ORDER) - position + 1
        adjusted_running = max(
            adjusted_running,
            min(1.0, remaining * preliminary[key]["unadjusted_p_value"]),
        )
        critical_alpha = FAMILYWISE_ALPHA / remaining
        observed = float(preliminary[key]["observed_mean"])
        upper_quantile = _order_statistic(
            np.asarray(bootstrap_means[key], dtype=np.float64),
            probability=1.0 - critical_alpha,
        )
        lower_bound = 2.0 * observed - upper_quantile
        passed = (
            adjusted_running <= FAMILYWISE_ALPHA
            and lower_bound > preliminary[key]["null_threshold"]
            and preliminary[key]["stability_count"] >= 60
        )
        results[key] = {
            **preliminary[key],
            "holm_position": position,
            "holm_remaining_hypotheses": remaining,
            "holm_critical_alpha": critical_alpha,
            "holm_adjusted_p_value": adjusted_running,
            "basic_one_sided_lower_bound": lower_bound,
            "pass": passed,
        }

    parent_digests = (
        source_contract_digest,
        RESEARCH_EXECUTION_CONTRACT_DIGEST,
        PARENT_EXECUTION_DIGEST,
        expected_result_index_digest,
        PARENT_EXECUTION_COMPLETION_DIGEST,
        PARENT_PREREGISTRATION_DIGEST,
    )
    bootstrap_family = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-bootstrap-family.v1"
        ),
        artifact_type="m4_p3_result_blind_structural_utility_bootstrap_family",
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "task_key": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            "result_blind": True,
            "result_index_digest": expected_result_index_digest,
            "fold_count": FOLD_COUNT,
            "hypothesis_order": list(HYPOTHESIS_ORDER),
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "block_length": BLOCK_LENGTH,
            "blocks_per_resample": BLOCKS_PER_RESAMPLE,
            "shared_resample_indices": True,
            "bootstrap_index_digest": index_digest,
            "bootstrap_means": bootstrap_means,
            "target_draw_rows_read": 0,
            "winning_labels_read": 0,
            "payout_or_reward_values_read": 0,
            "outcome_rank_values_read": 0,
            "production_action": "none",
        },
        parent_digests=parent_digests,
        domain=_BOOTSTRAP_DOMAIN,
    )
    family_pass = all(results[key]["pass"] for key in HYPOTHESIS_ORDER)
    decision = (
        "STRUCTURAL_UTILITY_SUPPORTED_WITHIN_FROZEN_SCOPE"
        if family_pass
        else "NO_STABLE_STRUCTURAL_UTILITY"
    )
    evidence = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-structural-evidence.v1"
        ),
        artifact_type="m4_p3_result_blind_structural_utility_evidence",
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "task_key": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            "result_blind": True,
            "bootstrap_family_digest": bootstrap_family["artifact_digest"],
            "familywise_alpha": FAMILYWISE_ALPHA,
            "multiplicity_method": "Holm step-down",
            "hypothesis_results": results,
            "all_twelve_gates_pass": family_pass,
            "decision": decision,
            "historical_prediction_evidence": "INCONCLUSIVE",
            "predictive_probability_claim_allowed": False,
            "payout_or_return_claim_allowed": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, bootstrap_family["artifact_digest"]),
        domain=_EVIDENCE_DOMAIN,
    )
    route_decision = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-route-decision.v1"
        ),
        artifact_type="m4_p3_result_blind_structural_utility_route_decision",
        body={
            "status": "COMPLETE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "task_key": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            "decision": decision,
            "supported_route": (
                "candidate portfolio optimizer research only"
                if family_pass
                else None
            ),
            "unsupported_route": (
                None
                if family_pass
                else (
                    "stop the lottery structural-optimization route and retain "
                    "Research OS/measurement/replay infrastructure"
                )
            ),
            "evidence_digest": evidence["artifact_digest"],
            "prediction_v2_mode": "SHADOW_ONLY",
            "prediction_v2_route": "BASELINE_ONLY",
            "old_training_lines": "FROZEN",
            "promotion_gate_opened": False,
            "predictive_p3_authorized": False,
            "production_action": "none",
        },
        parent_digests=(*parent_digests, evidence["artifact_digest"]),
        domain=_DECISION_DOMAIN,
    )
    completion = _artifact(
        schema_version=(
            "dehps-m4-p3-result-blind-structural-utility-evidence-completion.v1"
        ),
        artifact_type="m4_p3_result_blind_structural_utility_evidence_completion",
        body={
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "goal_key": M4_P3_STRUCTURAL_UTILITY_GOAL_KEY,
            "task_key": M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
            "bootstrap_family_digest": bootstrap_family["artifact_digest"],
            "evidence_digest": evidence["artifact_digest"],
            "route_decision_digest": route_decision["artifact_digest"],
            "decision": decision,
            "registered_child_count": EXPECTED_CAPABILITY_ARTIFACTS,
            "bootstrap_resamples_executed": BOOTSTRAP_RESAMPLES,
            "holm_hypotheses_evaluated": len(HYPOTHESIS_ORDER),
            "target_draw_rows_read": 0,
            "winning_labels_read": 0,
            "payout_or_reward_values_read": 0,
            "outcome_rank_values_read": 0,
            "next_consumer": "terminal structural route record",
            "production_action": "none",
        },
        parent_digests=(
            *parent_digests,
            bootstrap_family["artifact_digest"],
            evidence["artifact_digest"],
            route_decision["artifact_digest"],
        ),
        domain=_COMPLETION_DOMAIN,
    )
    return M4P3StructuralEvidenceCompilerRun(
        bootstrap_family=bootstrap_family,
        evidence=evidence,
        route_decision=route_decision,
        completion=completion,
    )


def replay_structural_evidence(
    *,
    result_index: Mapping[str, Any],
    source_contract_digest: str,
    artifacts: Sequence[Mapping[str, Any]],
    expected_result_index_digest: str = PARENT_RESULT_INDEX_DIGEST,
) -> dict[str, Any]:
    if len(artifacts) != EXPECTED_CAPABILITY_ARTIFACTS:
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_replay_artifact_count_invalid"
        )
    rebuilt = compile_structural_evidence(
        result_index=result_index,
        source_contract_digest=source_contract_digest,
        expected_result_index_digest=expected_result_index_digest,
    )
    if tuple(dict(item) for item in artifacts) != tuple(
        dict(item) for item in rebuilt.artifacts
    ):
        raise M4P3StructuralEvidenceCompilerError(
            "m4_p3_structural_evidence_replay_identity_changed"
        )
    return {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-evidence-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "manual_input_assembly": False,
        "workload_rerun": True,
        "bootstrap_resamples_replayed": BOOTSTRAP_RESAMPLES,
        "registered_capability_artifact_count": EXPECTED_CAPABILITY_ARTIFACTS,
        "decision": rebuilt.route_decision["decision"],
        "target_draw_rows_read": 0,
        "next_consumer": "terminal structural route record",
    }


__all__ = (
    "BOOTSTRAP_RESAMPLES",
    "CONTROL_ORDER",
    "EXPECTED_CAPABILITY_ARTIFACTS",
    "HYPOTHESIS_ORDER",
    "M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_APPROVED_EVENT",
    "M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_CAPABILITY",
    "M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT",
    "M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH",
    "M4P3StructuralEvidenceCompilerError",
    "M4P3StructuralEvidenceCompilerRun",
    "compile_structural_evidence",
    "load_m4_p3_structural_evidence_compiler_source_contract",
    "replay_structural_evidence",
    "validate_research_contract",
    "verify_m4_p3_structural_evidence_compiler_source_bytes",
)
