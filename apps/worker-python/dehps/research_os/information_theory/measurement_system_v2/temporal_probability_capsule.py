from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
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
NUMERIC_RUNTIME_CONTRACT_DIGEST: Final = (
    "66df0140487ef61aaa438a9c6027945a891d67e7e9c06f01f48c7831bac30ed0"
)
WORKER_IMAGE_DIGEST: Final = (
    "e8b8eb142ed94afb6f91274b896856ba335789eac987f0fbdf15528d63b08690"
)
BLAS_LAPACK_BINARY_CLOSURE_DIGEST: Final = (
    "d68656f8750016103d07cb5ae19add5d1a3e5aad5af34e100ebe1b3545bf4435"
)
NUMERIC_RUNTIME_FIELDS: Final = (
    "runtime_contract_id",
    "worker_image_digest",
    "python_implementation",
    "python_version",
    "python_executable_digest",
    "platform_machine",
    "byte_order",
    "binary64_mantissa_bits",
    "binary64_rounding_mode",
    "fused_multiply_add_allowed",
    "extended_precision_allowed",
    "libm_binary_digest",
    "numpy_version",
    "numpy_core_binary_digest",
    "numpy_linalg_binary_digest",
    "blas_lapack_binary_closure_digest",
    "solver_source_contract_digest",
    "evaluator_contract_digest",
)
NUMERIC_RUNTIME_CONTRACT: Final = {
    "runtime_contract_id": "TEMPORAL_PROBABILITY_CAPSULE_BINARY64_RUNTIME_V1",
    "worker_image_digest": WORKER_IMAGE_DIGEST,
    "python_implementation": "cpython",
    "python_version": "3.14.4",
    "python_executable_digest": (
        "b8d8288faefdd300201f43fcf00f6f539a27218eeed3a3dff5ab10b9c4c99700"
    ),
    "platform_machine": "x86_64",
    "byte_order": "little",
    "binary64_mantissa_bits": 53,
    "binary64_rounding_mode": "ROUND_TO_NEAREST_TIES_TO_EVEN",
    "fused_multiply_add_allowed": False,
    "extended_precision_allowed": False,
    "libm_binary_digest": (
        "beea4eeacfcfa2cd96011b959a826c97cf4a774017e214f6a34d7eea3d49cd88"
    ),
    "numpy_version": "2.4.6",
    "numpy_core_binary_digest": (
        "75eb7a6fdffcad459e89100b5102342ec49b33717cb0f593f1b7146b90ad18d6"
    ),
    "numpy_linalg_binary_digest": (
        "9044fb4c88488c93acdcb13ed4b7c4d639fada857456bb0254a190deb2e12aa7"
    ),
    "blas_lapack_binary_closure_digest": BLAS_LAPACK_BINARY_CLOSURE_DIGEST,
    "solver_source_contract_digest": Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
    "evaluator_contract_digest": EVALUATOR_CONTRACT_DIGEST,
}
BLAS_LAPACK_BINARY_CLOSURE_PREIMAGE: Final = {
    "schema_version": "dehps-m4-v2-blas-lapack-binary-closure.v1",
    "ordered_binaries": [
        {
            "logical_name": "libgfortran-040039e1-0352e75f.so.5.0.0",
            "content_sha256": (
                "c6090048eccc763522c12ef016f81da6b627cb3a044f55cf0479a839c41c0980"
            ),
        },
        {
            "logical_name": "libquadmath-96973f99-934c22de.so.0.0.0",
            "content_sha256": (
                "6ed5137f412781ad7863439fb543613f620b43c32b63292a0029246162f5bbc6"
            ),
        },
        {
            "logical_name": "libscipy_openblas64_-32a4b2a6.so",
            "content_sha256": (
                "05c9f9eb89ee68a4b9d673184fa91c99587e736392c0c2d49180a8aa5303d080"
            ),
        },
    ],
}


def _binary(logical_name: str, content_sha256: str) -> dict[str, str]:
    return {"logical_name": logical_name, "content_sha256": content_sha256}


WORKER_IMAGE_CLOSURE_PREIMAGE: Final = {
    "schema_version": "dehps-m4-v2-worker-execution-image-closure.v1",
    "platform_machine": "x86_64",
    "numpy_core_sha256": NUMERIC_RUNTIME_CONTRACT["numpy_core_binary_digest"],
    "os_release_sha256": (
        "de1a366db70de1ae4b6612a1696f9c1f37948028fab733508a3d5cf49836faac"
    ),
    "worker_lock_sha256": (
        "5feceb82a5977fbd367dbe5836111c19a3005b56844681b534c2db901066ce48"
    ),
    "numpy_linalg_sha256": NUMERIC_RUNTIME_CONTRACT[
        "numpy_linalg_binary_digest"
    ],
    "python_executable_sha256": NUMERIC_RUNTIME_CONTRACT[
        "python_executable_digest"
    ],
    "python_dynamic_dependencies": [
        _binary("libm.so.6", NUMERIC_RUNTIME_CONTRACT["libm_binary_digest"]),
        _binary(
            "libz.so.1",
            "fbf56b0e59287033b6579bbbeae2f9de2fe86ad5bf2bd44d44aad67a15109318",
        ),
        _binary(
            "libexpat.so.1",
            "093e973baf0b0c786d32fd89d1f6904b794af28e489d20198b9fe0729fd39765",
        ),
        _binary(
            "libc.so.6",
            "a3947513a02831ec692ebf13053c07614882ab54a2101fb91a1b15724062ed0c",
        ),
        _binary(
            "ld-linux-x86-64.so.2",
            "c5e80a563850d6ab5c2f2482e4202d9c1b71fbf44854b8c399e63527202c64e1",
        ),
    ],
    "numpy_core_dynamic_dependencies": [
        _binary(
            "libscipy_openblas64_-32a4b2a6.so",
            "05c9f9eb89ee68a4b9d673184fa91c99587e736392c0c2d49180a8aa5303d080",
        ),
        _binary(
            "libstdc++.so.6",
            "5bb0d21308f123b6ad46c6f35b42cedfcb8d6d439a53aa3dae04d880aaffdde3",
        ),
        _binary("libm.so.6", NUMERIC_RUNTIME_CONTRACT["libm_binary_digest"]),
        _binary(
            "libgcc_s.so.1",
            "9d339ecb409578d6a5d587e6c537a8f9589b8a13fefba30d167433a4b5758bee",
        ),
        _binary(
            "libc.so.6",
            "a3947513a02831ec692ebf13053c07614882ab54a2101fb91a1b15724062ed0c",
        ),
        _binary(
            "ld-linux-x86-64.so.2",
            "c5e80a563850d6ab5c2f2482e4202d9c1b71fbf44854b8c399e63527202c64e1",
        ),
        _binary(
            "libpthread.so.0",
            "f93acb6e78dcf0213c8a85f922d21916249148e24de426079c40b6304c42085d",
        ),
        _binary(
            "libgfortran-040039e1-0352e75f.so.5.0.0",
            "c6090048eccc763522c12ef016f81da6b627cb3a044f55cf0479a839c41c0980",
        ),
        _binary(
            "libquadmath-96973f99-934c22de.so.0.0.0",
            "6ed5137f412781ad7863439fb543613f620b43c32b63292a0029246162f5bbc6",
        ),
        _binary(
            "libz.so.1",
            "fbf56b0e59287033b6579bbbeae2f9de2fe86ad5bf2bd44d44aad67a15109318",
        ),
    ],
    "blas_lapack_binary_closure_digest": BLAS_LAPACK_BINARY_CLOSURE_DIGEST,
    "numpy_linalg_dynamic_dependencies": [
        _binary(
            "libscipy_openblas64_-32a4b2a6.so",
            "05c9f9eb89ee68a4b9d673184fa91c99587e736392c0c2d49180a8aa5303d080",
        ),
        _binary("libm.so.6", NUMERIC_RUNTIME_CONTRACT["libm_binary_digest"]),
        _binary(
            "libc.so.6",
            "a3947513a02831ec692ebf13053c07614882ab54a2101fb91a1b15724062ed0c",
        ),
        _binary(
            "libpthread.so.0",
            "f93acb6e78dcf0213c8a85f922d21916249148e24de426079c40b6304c42085d",
        ),
        _binary(
            "libgfortran-040039e1-0352e75f.so.5.0.0",
            "c6090048eccc763522c12ef016f81da6b627cb3a044f55cf0479a839c41c0980",
        ),
        _binary(
            "ld-linux-x86-64.so.2",
            "c5e80a563850d6ab5c2f2482e4202d9c1b71fbf44854b8c399e63527202c64e1",
        ),
        _binary(
            "libquadmath-96973f99-934c22de.so.0.0.0",
            "6ed5137f412781ad7863439fb543613f620b43c32b63292a0029246162f5bbc6",
        ),
        _binary(
            "libz.so.1",
            "fbf56b0e59287033b6579bbbeae2f9de2fe86ad5bf2bd44d44aad67a15109318",
        ),
        _binary(
            "libgcc_s.so.1",
            "9d339ecb409578d6a5d587e6c537a8f9589b8a13fefba30d167433a4b5758bee",
        ),
    ],
}
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
STRICT_PRIOR_OWNER_FIELDS: Final = (
    "dataset_content_digest",
    "checkpoint_order_manifest_digest",
    "transition_ordinal",
    "issue",
    "prefix_last_ordinal",
    "prefix_last_issue",
    "prefix_outcome_chain_digest",
    "parent_estimator_id",
    "q_m_marginal_content_digest",
    "q_m_full_distribution_content_digest",
    "checkpoint_digest",
)
Q_M_SOLVER_OWNER_FIELDS: Final = (
    "schema_version",
    "support_kind",
    "dataset_content_digest",
    "fold_manifest_digest",
    "checkpoint_order_manifest_digest",
    "transition_ordinal",
    "issue",
    "training_prefix_last_ordinal",
    "training_prefix_outcome_chain_digest",
    "parent_estimator_id",
    "q_m_carrier_contract_digest",
    "q_m_solver_source_contract_digest",
    "numeric_runtime_contract_digest",
    "q_m_output_evaluator_contract_digest",
    "q_m_target_marginal_float_hex_in_ball_order_1_through_33",
    "q_m_target_marginal_content_digest",
    "q_m_natural_parameter_float_hex_in_ball_order_1_through_33",
    "q_m_solver_iteration_count",
    "q_m_solver_termination_reason",
    "q_m_maximum_marginal_residual_float_hex",
    "q_m_full_distribution_content_digest",
    "pretarget_checkpoint_digest",
    "q_m_solver_output_checkpoint_digest",
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
    if set(result) != set(fields):
        raise TemporalProbabilityCapsuleError(f"{name}_fields_invalid")
    return {field: result[field] for field in fields}


def validate_registered_build_closures() -> None:
    """Recompute the two exact Request518 content-addressed build owners."""

    if (
        m4_v2_domain_digest(
            BLAS_LAPACK_BINARY_CLOSURE_PREIMAGE,
            domain="dehps.m4.v2.blas-lapack-binary-closure.v1",
        )
        != BLAS_LAPACK_BINARY_CLOSURE_DIGEST
        or m4_v2_domain_digest(
            WORKER_IMAGE_CLOSURE_PREIMAGE,
            domain="dehps.m4.v2.worker-execution-image-closure.v1",
        )
        != WORKER_IMAGE_DIGEST
    ):
        raise TemporalProbabilityCapsuleError(
            "numeric_runtime_build_closure_digest_mismatch"
        )


def validate_numeric_runtime_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    """Require Request518's exact 18-field runtime owner, never ambient host facts."""

    validate_registered_build_closures()
    runtime = _closed(value, NUMERIC_RUNTIME_FIELDS, "numeric_runtime_contract")
    if runtime != {
        field: NUMERIC_RUNTIME_CONTRACT[field] for field in NUMERIC_RUNTIME_FIELDS
    }:
        raise TemporalProbabilityCapsuleError(
            "numeric_runtime_contract_identity_mismatch"
        )
    if (
        m4_v2_domain_digest(
            runtime,
            domain="dehps.m4.v2.temporal.probability-numeric-runtime.v1",
        )
        != NUMERIC_RUNTIME_CONTRACT_DIGEST
    ):
        raise TemporalProbabilityCapsuleError(
            "numeric_runtime_contract_digest_mismatch"
        )
    return runtime


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


def evaluate_registered_weights(weights_float_hex: Sequence[str]) -> dict[str, Any]:
    weights_key = tuple(weights_float_hex)
    if len(weights_key) != 33:
        raise TemporalProbabilityCapsuleError("capsule_weight_count_invalid")
    evaluated = _evaluate_registered_weights_cached(weights_key)
    return {
        "partition_float_hex": evaluated[0],
        "q_t_marginal_float_hex_in_ball_order_1_through_33": list(evaluated[1]),
        "q_t_marginal_content_digest": evaluated[2],
        "q_t_full_distribution_content_digest": evaluated[3],
    }


@lru_cache(maxsize=64)
def _evaluate_registered_weights_cached(
    weights_float_hex: tuple[str, ...],
) -> tuple[str, tuple[str, ...], str, str]:
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
    return partition.hex(), tuple(marginal_hex), marginal_digest, digest.hexdigest()


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
    if expected_kind == "WARMUP_NULL_ALIAS":
        owner = _closed(owner, STRICT_PRIOR_OWNER_FIELDS, "q_m_strict_prior_owner")
        expected_owner_digest = m4_v2_domain_digest(
            {field: owner[field] for field in STRICT_PRIOR_OWNER_FIELDS[:-1]},
            domain="dehps.m4.v2.strict-prior-marginal-checkpoint.v1",
        )
        if (
            owner["checkpoint_digest"] != expected_owner_digest
            or owner["transition_ordinal"] != certificate["transition_ordinal"]
            or owner["issue"] != certificate["issue"]
            or owner["prefix_outcome_chain_digest"]
            != certificate["prefix_outcome_chain_digest"]
            or owner["q_m_marginal_content_digest"]
            != certificate["q_m_target_marginal_content_digest"]
            or owner["q_m_full_distribution_content_digest"]
            != certificate["q_m_full_distribution_content_digest"]
        ):
            raise TemporalProbabilityCapsuleError(
                "certificate_q_m_warmup_owner_mismatch"
            )
    else:
        owner = _closed(owner, Q_M_SOLVER_OWNER_FIELDS, "q_m_solver_owner")
        expected_owner = {
            "schema_version": (
                "dehps-m4-v2-candidate-v3-q-m-solver-output-checkpoint.v1"
            ),
            "support_kind": "ACCEPTED_TEMPORAL_EVALUATION",
            "q_m_carrier_contract_digest": Q_M_CARRIER_CONTRACT_DIGEST,
            "q_m_solver_source_contract_digest": Q_M_SOLVER_SOURCE_CONTRACT_DIGEST,
            "q_m_output_evaluator_contract_digest": EVALUATOR_CONTRACT_DIGEST,
            "transition_ordinal": certificate["transition_ordinal"],
            "issue": certificate["issue"],
            "training_prefix_last_ordinal": certificate["transition_ordinal"] - 1,
            "training_prefix_outcome_chain_digest": certificate[
                "prefix_outcome_chain_digest"
            ],
            "parent_estimator_id": PARENT_ESTIMATOR_ID,
            "numeric_runtime_contract_digest": certificate[
                "numeric_runtime_contract_digest"
            ],
            "q_m_target_marginal_float_hex_in_ball_order_1_through_33": certificate[
                "q_m_target_marginal_float_hex_in_ball_order_1_through_33"
            ],
            "q_m_target_marginal_content_digest": certificate[
                "q_m_target_marginal_content_digest"
            ],
            "q_m_natural_parameter_float_hex_in_ball_order_1_through_33": certificate[
                "q_m_natural_parameter_float_hex_in_ball_order_1_through_33"
            ],
            "q_m_solver_iteration_count": certificate["q_m_solver_iteration_count"],
            "q_m_solver_termination_reason": certificate[
                "q_m_solver_termination_reason"
            ],
            "q_m_maximum_marginal_residual_float_hex": certificate[
                "q_m_maximum_marginal_residual_float_hex"
            ],
            "q_m_full_distribution_content_digest": certificate[
                "q_m_full_distribution_content_digest"
            ],
        }
        expected_owner_digest = m4_v2_domain_digest(
            {field: owner[field] for field in Q_M_SOLVER_OWNER_FIELDS[:-1]},
            domain="dehps.m4.v2.candidate-v3.q-m-solver-output-checkpoint.v1",
        )
        if (
            any(owner.get(field) != expected for field, expected in expected_owner.items())
            or owner["q_m_solver_output_checkpoint_digest"] != expected_owner_digest
        ):
            raise TemporalProbabilityCapsuleError(
                "certificate_q_m_solver_owner_mismatch"
            )
    marginal_digest = m4_v2_domain_digest(
        {
            "probabilities_float_hex_in_ball_order_1_through_33": certificate[
                "q_m_target_marginal_float_hex_in_ball_order_1_through_33"
            ]
        },
        domain="dehps.m4.v2.marginal-vector.v1",
    )
    natural_parameters = [
        _float_hex(value)
        for value in certificate[
            "q_m_natural_parameter_float_hex_in_ball_order_1_through_33"
        ]
    ]
    if len(natural_parameters) != 33 or natural_parameters[-1] != 0.0:
        raise TemporalProbabilityCapsuleError("certificate_q_m_lambda_invalid")
    maximum = max(natural_parameters)
    q_m_weights = [math.exp(value - maximum).hex() for value in natural_parameters]
    q_m_evaluated = evaluate_registered_weights(q_m_weights)
    if (
        marginal_digest != certificate["q_m_target_marginal_content_digest"]
        or q_m_evaluated["q_t_marginal_content_digest"] != marginal_digest
        or q_m_evaluated["q_t_full_distribution_content_digest"]
        != certificate["q_m_full_distribution_content_digest"]
    ):
        raise TemporalProbabilityCapsuleError("certificate_q_m_evaluator_mismatch")
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
    if row["numeric_runtime_contract_digest"] != NUMERIC_RUNTIME_CONTRACT_DIGEST:
        raise TemporalProbabilityCapsuleError("capsule_numeric_runtime_mismatch")
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
    # The registered evaluator is the sole owner of the probability bytes.  A
    # self-consistent capsule cannot attest arbitrary partition/marginal/full
    # digests: re-evaluate the exact normalized weight vector and require every
    # derived identity to agree with both the row and its derivation certificate.
    evaluated = evaluate_registered_weights(weights)
    evaluator_equalities = {
        "partition_float_hex": evaluated["partition_float_hex"],
        "q_t_marginal_content_digest": evaluated["q_t_marginal_content_digest"],
        "q_t_full_distribution_content_digest": evaluated[
            "q_t_full_distribution_content_digest"
        ],
    }
    if any(row.get(field) != expected for field, expected in evaluator_equalities.items()):
        raise TemporalProbabilityCapsuleError("capsule_evaluator_output_mismatch")
    if any(
        certificate.get(field) != expected
        for field, expected in evaluator_equalities.items()
        if field != "partition_float_hex"
    ):
        raise TemporalProbabilityCapsuleError("certificate_evaluator_output_mismatch")
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
    validate_numeric_runtime_contract(NUMERIC_RUNTIME_CONTRACT)
    if numeric_runtime_contract_digest != NUMERIC_RUNTIME_CONTRACT_DIGEST:
        raise TemporalProbabilityCapsuleError("capsule_index_runtime_mismatch")
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


def validate_sealed_probability_capsule_index(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate registered capsule bytes without re-running its numeric evaluator.

    Joint consumes the Temporal Candidate's content-addressed capsule.  It must
    verify the complete sealed row/certificate/index lineage, but Request518
    forbids probing the ambient host or numerically regenerating Temporal bytes.
    """

    index = _closed(value, CAPSULE_INDEX_FIELDS, "probability_capsule_index")
    if (
        index["numeric_runtime_contract_digest"] != NUMERIC_RUNTIME_CONTRACT_DIGEST
        or index["evaluator_contract_digest"] != EVALUATOR_CONTRACT_DIGEST
        or index["row_count"] != 3480
        or index["first_transition_ordinal"] != 2
        or index["last_transition_ordinal"] != 3481
        or not isinstance(index["rows"], list)
        or not isinstance(index["ordered_capsule_digests"], list)
        or len(index["rows"]) != 3480
    ):
        raise TemporalProbabilityCapsuleError("sealed_capsule_index_identity_mismatch")
    sealed_rows: list[dict[str, Any]] = []
    for expected_ordinal, raw in enumerate(index["rows"], start=2):
        row = _closed(raw, CAPSULE_ROW_FIELDS, "probability_capsule_row")
        certificate = _closed(
            row["weight_derivation_certificate"],
            CERTIFICATE_FIELDS,
            "weight_derivation_certificate",
        )
        expected_kind = (
            "WARMUP_NULL_ALIAS"
            if expected_ordinal <= 900
            else "ACCEPTED_TEMPORAL_EVALUATION"
        )
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
        owner = certificate.get("q_m_owner_checkpoint")
        owner_digest_field = (
            "checkpoint_digest"
            if expected_kind == "WARMUP_NULL_ALIAS"
            else "q_m_solver_output_checkpoint_digest"
        )
        owner_fields = (
            STRICT_PRIOR_OWNER_FIELDS
            if expected_kind == "WARMUP_NULL_ALIAS"
            else Q_M_SOLVER_OWNER_FIELDS
        )
        owner_domain = (
            "dehps.m4.v2.strict-prior-marginal-checkpoint.v1"
            if expected_kind == "WARMUP_NULL_ALIAS"
            else "dehps.m4.v2.candidate-v3.q-m-solver-output-checkpoint.v1"
        )
        if not isinstance(owner, Mapping):
            raise TemporalProbabilityCapsuleError("sealed_capsule_owner_missing")
        closed_owner = _closed(owner, owner_fields, "sealed_capsule_owner")
        weights = row["candidate_weight_float_hex_in_ball_order_1_through_33"]
        if (
            row["transition_ordinal"] != expected_ordinal
            or row["support_kind"] != expected_kind
            or any(row[field] != certificate[field] for field in equal_fields)
            or row["weight_derivation_certificate_digest"]
            != certificate["certificate_digest"]
            or row["numeric_runtime_contract_digest"]
            != NUMERIC_RUNTIME_CONTRACT_DIGEST
            or row["evaluator_contract_digest"] != EVALUATOR_CONTRACT_DIGEST
            or certificate["q_m_solver_source_contract_digest"]
            != Q_M_SOLVER_SOURCE_CONTRACT_DIGEST
            or certificate["q_m_owner_checkpoint_digest"]
            != closed_owner[owner_digest_field]
            or closed_owner[owner_digest_field]
            != m4_v2_domain_digest(
                {field: closed_owner[field] for field in owner_fields[:-1]},
                domain=owner_domain,
            )
            or not isinstance(weights, list)
            or len(weights) != 33
            or any(not math.isfinite(_float_hex(item, positive=True)) for item in weights)
            or m4_v2_domain_digest(
                {"candidate_weight_float_hex_in_ball_order_1_through_33": weights},
                domain="dehps.m4.v2.temporal.candidate-weight-content.v1",
            )
            != row["candidate_weight_content_digest"]
            or m4_v2_domain_digest(
                {field: certificate[field] for field in CERTIFICATE_FIELDS[:-1]},
                domain=(
                    "dehps.m4.v2.temporal."
                    "probability-weight-derivation-certificate.v1"
                ),
            )
            != certificate["certificate_digest"]
            or m4_v2_domain_digest(
                {field: row[field] for field in CAPSULE_ROW_FIELDS[:-1]},
                domain="dehps.m4.v2.temporal.probability-capsule-row.v2",
            )
            != row["capsule_digest"]
        ):
            raise TemporalProbabilityCapsuleError("sealed_capsule_row_identity_mismatch")
        sealed_rows.append(row)
    ordered = [row["capsule_digest"] for row in sealed_rows]
    expected_index = m4_v2_domain_digest(
        {field: index[field] for field in CAPSULE_INDEX_FIELDS[:-3]}
        | {"ordered_capsule_digests": ordered},
        domain="dehps.m4.v2.temporal.probability-capsule-index.v1",
    )
    if (
        index["ordered_capsule_digests"] != ordered
        or index["index_digest"] != expected_index
    ):
        raise TemporalProbabilityCapsuleError("sealed_capsule_index_digest_mismatch")
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
    "BLAS_LAPACK_BINARY_CLOSURE_DIGEST",
    "BLAS_LAPACK_BINARY_CLOSURE_PREIMAGE",
    "CAPSULE_INDEX_FIELDS",
    "CAPSULE_ROW_FIELDS",
    "CORRECTED_AMENDMENT_CONTRACT_DIGEST",
    "CORRECTED_REBASED_ADDENDUM_DIGEST",
    "CORRECTED_RESOLVED_CONTRACT_DIGEST",
    "EVALUATOR_CONTRACT_DIGEST",
    "INVALID_LEGACY_SUCCESSOR_DIGESTS",
    "NUMERIC_RUNTIME_CONTRACT",
    "NUMERIC_RUNTIME_CONTRACT_DIGEST",
    "NUMERIC_RUNTIME_FIELDS",
    "Q_M_CARRIER_CONTRACT_DIGEST",
    "Q_M_SOLVER_SOURCE_CONTRACT_DIGEST",
    "WORKER_IMAGE_CLOSURE_PREIMAGE",
    "WORKER_IMAGE_DIGEST",
    "TemporalProbabilityCapsuleError",
    "build_probability_capsule_index",
    "evaluate_registered_weights",
    "require_corrected_probability_authority",
    "validate_numeric_runtime_contract",
    "validate_probability_capsule_index",
    "validate_probability_capsule_row",
    "validate_registered_build_closures",
    "validate_sealed_probability_capsule_index",
    "validate_weight_derivation_certificate",
]
