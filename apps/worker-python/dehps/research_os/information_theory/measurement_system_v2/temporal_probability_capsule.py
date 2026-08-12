from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from dehps.research_os.models import m4_v2_domain_digest

from .m4_v2_legal_fixed_cardinality import LEGAL_STATE_COUNT, legal_states


class TemporalProbabilityCapsuleError(ValueError):
    pass


EVALUATOR_CONTRACT_DIGEST: Final = (
    "d3759bd8b3114e4bb75fe62298ecc1dcc127d6b85491e7f692ab14603bb0e0e9"
)
Q_M_CARRIER_CONTRACT_DIGEST: Final = (
    "34efd1f11789c5c55feecc88a4aff149e3a7accc563430fec7b0c985ee0d37ed"
)
Q_M_SOLVER_SOURCE_CONTRACT_DIGEST: Final = (
    "391acc6a04518389f841e94a640a14dcaf98bd2c36614d31a0e713446980b06d"
)
CORRECTED_AMENDMENT_CONTRACT_DIGEST: Final = (
    "a6c59a1f0e0ae81b8eedbee9dfac515a50b26d57bd33c9e0e4ae122d811fd37c"
)
CORRECTED_RESOLVED_CONTRACT_DIGEST: Final = (
    "51f8f56af4fde4e06e610a791876fd17bf49edfb0c221dec4d53c67dafd5b97d"
)
CORRECTED_REBASED_ADDENDUM_DIGEST: Final = (
    "deac42696723726613e780dfeeacbace7f054edb3a486caa33c884a20d64ef03"
)
INVALID_LEGACY_SUCCESSOR_DIGESTS: Final = frozenset(
    {
        "dfcca48ef27a7c7ff5fd4fe1ce76f26f395b20fcb0a87c99ca1946aff723e851",
        "36145e048db97858aa3fde4b77d25895232f825dcdcb38150f718b406dcc8b12",
        "ce0142948bd40d002a404c2687dbc7c2146a07e0646fe2f409d3188ba527c205",
    }
)
PARENT_ESTIMATOR_ID: Final = "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
CAPSULE_ROW_FIELDS: Final = (
    "transition_ordinal",
    "issue",
    "support_kind",
    "temporal_support_row_digest",
    "temporal_support_checkpoint_digest",
    "theta_float_hex",
    "weight_derivation_certificate",
    "weight_derivation_certificate_digest",
    "candidate_weight_float_hex_in_ball_order_1_through_33",
    "candidate_weight_content_digest",
    "partition_float_hex",
    "q_t_marginal_content_digest",
    "q_t_full_distribution_content_digest",
    "numeric_runtime_contract_digest",
    "evaluator_contract_digest",
    "capsule_digest",
)
CAPSULE_INDEX_FIELDS: Final = (
    "producer_source_contract_digest",
    "numeric_runtime_contract_digest",
    "evaluator_contract_digest",
    "row_count",
    "first_transition_ordinal",
    "last_transition_ordinal",
    "rows",
    "ordered_capsule_digests",
    "index_digest",
)
CERTIFICATE_FIELDS: Final = (
    "transition_ordinal",
    "issue",
    "support_kind",
    "temporal_support_row_digest",
    "temporal_support_checkpoint_digest",
    "prefix_outcome_chain_digest",
    "q_m_target_marginal_float_hex_in_ball_order_1_through_33",
    "q_m_target_marginal_content_digest",
    "q_m_full_distribution_content_digest",
    "q_m_solver_source_contract_digest",
    "q_m_solver_iteration_count",
    "q_m_solver_termination_reason",
    "q_m_natural_parameter_float_hex_in_ball_order_1_through_33",
    "q_m_maximum_marginal_residual_float_hex",
    "theta_float_hex",
    "previous_draw_issue",
    "previous_draw_labels_in_ascending_order",
    "previous_draw_content_digest",
    "combined_log_weight_float_hex_in_ball_order_1_through_33",
    "maximum_combined_log_weight_float_hex",
    "centered_log_weight_float_hex_in_ball_order_1_through_33",
    "candidate_weight_float_hex_in_ball_order_1_through_33",
    "candidate_weight_content_digest",
    "numeric_runtime_contract_digest",
    "evaluator_contract_digest",
    "q_t_marginal_content_digest",
    "q_t_full_distribution_content_digest",
    "q_m_owner_checkpoint",
    "q_m_owner_checkpoint_digest",
    "certificate_digest",
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class _Neumaier:
    def __init__(self) -> None:
        self.running_sum = 0.0
        self.compensation = 0.0

    def add(self, value: float) -> None:
        temporary = self.running_sum + value
        if abs(self.running_sum) >= abs(value):
            self.compensation += (self.running_sum - temporary) + value
        else:
            self.compensation += (value - temporary) + self.running_sum
        self.running_sum = temporary

    def value(self) -> float:
        return self.running_sum + self.compensation


def _closed(value: Mapping[str, Any], fields: Sequence[str], name: str) -> dict[str, Any]:
    result = dict(value)
    if tuple(result) != tuple(fields) or set(result) != set(fields):
        raise TemporalProbabilityCapsuleError(f"{name}_fields_invalid")
    return result


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _float_hex(value: str, *, positive: bool = False) -> float:
    try:
        decoded = float.fromhex(value)
    except (TypeError, ValueError) as exc:
        raise TemporalProbabilityCapsuleError("capsule_float_hex_invalid") from exc
    if not math.isfinite(decoded) or decoded.hex() != value or (positive and decoded <= 0.0):
        raise TemporalProbabilityCapsuleError("capsule_float_hex_invalid")
    return decoded


def _numerator(weights: Sequence[float], state: Sequence[int]) -> float:
    value = 1.0
    for index in state:
        value *= weights[index]
    if not math.isfinite(value) or value <= 0.0:
        raise TemporalProbabilityCapsuleError("capsule_numerator_invalid")
    return value


def evaluate_registered_weights(
    weights_float_hex: Sequence[str],
) -> dict[str, Any]:
    if len(weights_float_hex) != 33:
        raise TemporalProbabilityCapsuleError("capsule_weight_count_invalid")
    weights = [_float_hex(value, positive=True) for value in weights_float_hex]
    if max(weights) != 1.0 or any(value > 1.0 for value in weights):
        raise TemporalProbabilityCapsuleError("capsule_weight_scale_invalid")
    partition_accumulator = _Neumaier()
    for state in legal_states():
        partition_accumulator.add(_numerator(weights, state))
    partition = partition_accumulator.value()
    if not math.isfinite(partition) or partition <= 0.0:
        raise TemporalProbabilityCapsuleError("capsule_partition_invalid")

    marginal_accumulators = [_Neumaier() for _ in range(33)]
    domain = "dehps.m4.v2.legal-joint-probability-content.v1"
    digest = hashlib.sha256()
    digest.update(domain.encode())
    digest.update(b"\0")
    digest.update(
        b'{"legal_space_id":"LEGAL_SIX_OF_33_COMBINATIONS",'
        b'"legal_state_order_id":"INCREASING_LEXICOGRAPHIC_SIX_LABEL_TUPLE",'
        b'"probabilities_float_hex_in_canonical_1107568_state_order":['
    )
    count = 0
    for state in legal_states():
        probability = _numerator(weights, state) / partition
        if not math.isfinite(probability) or probability <= 0.0:
            raise TemporalProbabilityCapsuleError("capsule_probability_invalid")
        probability_hex = probability.hex()
        if count:
            digest.update(b",")
        digest.update(json.dumps(probability_hex).encode())
        for index in state:
            marginal_accumulators[index].add(probability)
        count += 1
    digest.update(b"]}")
    if count != LEGAL_STATE_COUNT:
        raise TemporalProbabilityCapsuleError("capsule_legal_state_count_invalid")
    marginal_hex = [accumulator.value().hex() for accumulator in marginal_accumulators]
    marginal_digest = m4_v2_domain_digest(
        {"probabilities_float_hex_in_ball_order_1_through_33": marginal_hex},
        domain="dehps.m4.v2.marginal-vector.v1",
    )
    return {
        "partition_float_hex": partition.hex(),
        "q_t_marginal_float_hex_in_ball_order_1_through_33": marginal_hex,
        "q_t_marginal_content_digest": marginal_digest,
        "q_t_full_distribution_content_digest": digest.hexdigest(),
    }


def validate_weight_derivation_certificate(value: Mapping[str, Any]) -> dict[str, Any]:
    certificate = _closed(value, CERTIFICATE_FIELDS, "weight_derivation_certificate")
    ordinal = certificate["transition_ordinal"]
    expected_kind = (
        "WARMUP_NULL_ALIAS" if isinstance(ordinal, int) and 2 <= ordinal <= 900
        else "ACCEPTED_TEMPORAL_EVALUATION"
    )
    if not isinstance(ordinal, int) or not 2 <= ordinal <= 3481 or certificate["support_kind"] != expected_kind:
        raise TemporalProbabilityCapsuleError("certificate_support_partition_invalid")
    if certificate["q_m_solver_source_contract_digest"] != Q_M_SOLVER_SOURCE_CONTRACT_DIGEST:
        raise TemporalProbabilityCapsuleError("certificate_q_m_solver_source_mismatch")
    if certificate["evaluator_contract_digest"] != EVALUATOR_CONTRACT_DIGEST:
        raise TemporalProbabilityCapsuleError("certificate_evaluator_mismatch")
    owner = certificate["q_m_owner_checkpoint"]
    if not isinstance(owner, Mapping):
        raise TemporalProbabilityCapsuleError("certificate_q_m_owner_missing")
    owner_digest_field = (
        "checkpoint_digest"
        if expected_kind == "WARMUP_NULL_ALIAS"
        else "q_m_solver_output_checkpoint_digest"
    )
    if (
        owner.get(owner_digest_field) != certificate["q_m_owner_checkpoint_digest"]
        or owner.get("parent_estimator_id") != PARENT_ESTIMATOR_ID
    ):
        raise TemporalProbabilityCapsuleError("certificate_q_m_owner_identity_mismatch")
    if expected_kind == "ACCEPTED_TEMPORAL_EVALUATION" and (
        owner.get("q_m_solver_source_contract_digest")
        != Q_M_SOLVER_SOURCE_CONTRACT_DIGEST
    ):
        raise TemporalProbabilityCapsuleError("certificate_q_m_owner_source_mismatch")
    expected = m4_v2_domain_digest(
        {field: certificate[field] for field in CERTIFICATE_FIELDS[:-1]},
        domain="dehps.m4.v2.temporal.probability-weight-derivation-certificate.v1",
    )
    if certificate["certificate_digest"] != expected:
        raise TemporalProbabilityCapsuleError("certificate_digest_mismatch")
    return certificate


def validate_probability_capsule_row(value: Mapping[str, Any]) -> dict[str, Any]:
    row = _closed(value, CAPSULE_ROW_FIELDS, "probability_capsule_row")
    certificate = validate_weight_derivation_certificate(row["weight_derivation_certificate"])
    equal_fields = (
        "transition_ordinal",
        "issue",
        "support_kind",
        "temporal_support_row_digest",
        "temporal_support_checkpoint_digest",
        "theta_float_hex",
        "candidate_weight_float_hex_in_ball_order_1_through_33",
        "candidate_weight_content_digest",
        "numeric_runtime_contract_digest",
        "evaluator_contract_digest",
        "q_t_marginal_content_digest",
        "q_t_full_distribution_content_digest",
    )
    if any(row[field] != certificate[field] for field in equal_fields):
        raise TemporalProbabilityCapsuleError("capsule_certificate_equality_mismatch")
    if row["weight_derivation_certificate_digest"] != certificate["certificate_digest"]:
        raise TemporalProbabilityCapsuleError("capsule_certificate_digest_mismatch")
    if row["evaluator_contract_digest"] != EVALUATOR_CONTRACT_DIGEST:
        raise TemporalProbabilityCapsuleError("capsule_evaluator_mismatch")
    if row["support_kind"] == "WARMUP_NULL_ALIAS" and row["theta_float_hex"] != "0x0.0p+0":
        raise TemporalProbabilityCapsuleError("capsule_warmup_theta_invalid")
    for field in (
        "temporal_support_row_digest",
        "temporal_support_checkpoint_digest",
        "candidate_weight_content_digest",
        "numeric_runtime_contract_digest",
        "q_t_marginal_content_digest",
        "q_t_full_distribution_content_digest",
    ):
        if not _valid_digest(row[field]):
            raise TemporalProbabilityCapsuleError(f"capsule_{field}_invalid")
    weights = row["candidate_weight_float_hex_in_ball_order_1_through_33"]
    if (
        m4_v2_domain_digest(
            {"candidate_weight_float_hex_in_ball_order_1_through_33": weights},
            domain="dehps.m4.v2.temporal.candidate-weight-content.v1",
        )
        != row["candidate_weight_content_digest"]
    ):
        raise TemporalProbabilityCapsuleError("capsule_weight_digest_mismatch")
    expected = m4_v2_domain_digest(
        {field: row[field] for field in CAPSULE_ROW_FIELDS[:-1]},
        domain="dehps.m4.v2.temporal.probability-capsule-row.v2",
    )
    if row["capsule_digest"] != expected:
        raise TemporalProbabilityCapsuleError("capsule_digest_mismatch")
    return row


def build_probability_capsule_index(
    *,
    producer_source_contract_digest: str,
    numeric_runtime_contract_digest: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validated = [validate_probability_capsule_row(row) for row in rows]
    if [row["transition_ordinal"] for row in validated] != list(range(2, 3482)):
        raise TemporalProbabilityCapsuleError("capsule_index_coverage_invalid")
    result = {
        "producer_source_contract_digest": producer_source_contract_digest,
        "numeric_runtime_contract_digest": numeric_runtime_contract_digest,
        "evaluator_contract_digest": EVALUATOR_CONTRACT_DIGEST,
        "row_count": 3480,
        "first_transition_ordinal": 2,
        "last_transition_ordinal": 3481,
        "rows": validated,
        "ordered_capsule_digests": [row["capsule_digest"] for row in validated],
    }
    result["index_digest"] = m4_v2_domain_digest(
        {field: result[field] for field in CAPSULE_INDEX_FIELDS[:-3]}
        | {"ordered_capsule_digests": result["ordered_capsule_digests"]},
        domain="dehps.m4.v2.temporal.probability-capsule-index.v1",
    )
    return result


def validate_probability_capsule_index(value: Mapping[str, Any]) -> dict[str, Any]:
    index = _closed(value, CAPSULE_INDEX_FIELDS, "probability_capsule_index")
    rebuilt = build_probability_capsule_index(
        producer_source_contract_digest=index["producer_source_contract_digest"],
        numeric_runtime_contract_digest=index["numeric_runtime_contract_digest"],
        rows=index["rows"],
    )
    if index != rebuilt:
        raise TemporalProbabilityCapsuleError("capsule_index_digest_mismatch")
    return index


def require_corrected_probability_authority(digests: Sequence[str]) -> None:
    if any(digest in INVALID_LEGACY_SUCCESSOR_DIGESTS for digest in digests):
        raise TemporalProbabilityCapsuleError("legacy_probability_authority_digest_rejected")
    required = {
        CORRECTED_AMENDMENT_CONTRACT_DIGEST,
        CORRECTED_RESOLVED_CONTRACT_DIGEST,
        CORRECTED_REBASED_ADDENDUM_DIGEST,
    }
    if not required <= set(digests):
        raise TemporalProbabilityCapsuleError("corrected_probability_authority_missing")


__all__ = [
    "CAPSULE_INDEX_FIELDS",
    "CAPSULE_ROW_FIELDS",
    "CORRECTED_AMENDMENT_CONTRACT_DIGEST",
    "CORRECTED_REBASED_ADDENDUM_DIGEST",
    "CORRECTED_RESOLVED_CONTRACT_DIGEST",
    "EVALUATOR_CONTRACT_DIGEST",
    "INVALID_LEGACY_SUCCESSOR_DIGESTS",
    "Q_M_CARRIER_CONTRACT_DIGEST",
    "Q_M_SOLVER_SOURCE_CONTRACT_DIGEST",
    "TemporalProbabilityCapsuleError",
    "build_probability_capsule_index",
    "evaluate_registered_weights",
    "require_corrected_probability_authority",
    "validate_probability_capsule_index",
    "validate_probability_capsule_row",
    "validate_weight_derivation_certificate",
]
