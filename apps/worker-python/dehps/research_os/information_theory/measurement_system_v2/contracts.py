from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from dehps.research_os.information_theory.digest import config_digest


MEASUREMENT_CONTRACT_V2_DIGEST = (
    "a0a367c99d7646cadc162bd9ceb0d5d73481cd7c26656bf02b40a99d9180095b"
)
MEASUREMENT_CONTRACT_V2_PATH = Path(
    "configs/research-os/m4-measurement-contract-v2.json"
)
BRANCH_IDS = (
    "MARGINAL_STATIC",
    "TEMPORAL_MARGINAL_INCREMENT",
    "JOINT_RESIDUAL_INCREMENT",
)
ROLE_VALUES = frozenset(
    {
        "POSITIVE_CONTROL",
        "NEGATIVE_CONTROL",
        "LEAKAGE_SENTINEL",
        "OUT_OF_SCOPE",
        "UNRESOLVED_PENDING_PREFLIGHT",
    }
)
EXPECTED_RESULT_BLIND_FREEZE = {
    "p2_6_1_partial_replicates_read": False,
    "p2_6_1_partial_aggregates_read": False,
    "p2_6_1_gate_outputs_read": False,
    "real_history_outcomes_read": False,
    "formal_v2_results_existed_before_freeze": False,
    "thresholds_selected_from_results": False,
    "frozen_source_contract_identities_used": True,
    "exact_synthetic_truth_definitions_used": True,
}
EXPECTED_SOURCE_IDENTITIES = {
    "information_theory_contract_digest": (
        "ae4e741cfc55547785ca9cf57b5b49f37a3d8c4f2bd53daeff9228982f797a69"
    ),
    "metric_kernel_digest": (
        "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
    ),
    "walk_forward_harness_digest": (
        "177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca"
    ),
    "measurement_repair_manifest_digest": (
        "5e41910553643e6559e78aa401fdcdd1e661b5709eaf55f0e73e694fb5a61355"
    ),
    "p2_6_1_measurement_validation_manifest_digest": (
        "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
    ),
    "p2_6_1_state_visible_feature_manifest_digest": (
        "1a76f46d7a47a134c1688657749bc040290f65a03dbc7c860e38144e02005981"
    ),
}
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class MeasurementContractV2Error(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class _FrozenMapping(Mapping[str, Any]):
    """A recursively frozen JSON object with a mutable-copy escape hatch.

    ``MappingProxyType`` protects the backing dictionary, while ``__deepcopy__``
    deliberately returns a detached JSON-compatible dictionary for callers
    that need to derive a candidate contract without mutating the accepted one.
    """

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        self._values = MappingProxyType(dict(values))

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "_values" or hasattr(self, "_values"):
            raise TypeError("frozen contract mappings cannot be reassigned")
        object.__setattr__(self, name, value)

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __deepcopy__(self, memo: dict[int, Any]) -> dict[str, Any]:
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        copied: dict[str, Any] = {}
        memo[id(self)] = copied
        copied.update(
            (deepcopy(key, memo), deepcopy(value, memo))
            for key, value in self._values.items()
        )
        return copied


@dataclass(frozen=True)
class MeasurementContractV2:
    payload: Mapping[str, Any]
    artifact_digest: str
    branches: tuple[Mapping[str, Any], ...]
    mechanism_rows: tuple[Mapping[str, Any], ...]

    def branch(self, branch_id: str) -> Mapping[str, Any]:
        try:
            return next(
                item
                for item in self.branches
                if item.get("branch_id") == branch_id
            )
        except StopIteration as exc:
            raise MeasurementContractV2Error(
                "measurement_v2_branch_unknown",
                branch_id,
            ) from exc

    def estimand_digest(self, branch_id: str) -> str:
        from dehps.contracts import canonical_digest

        return canonical_digest(
            self.branch(branch_id),
            domain="dehps.m4.measurement-v2.branch-estimand.v1",
        )

    def statistical_input_digest(self) -> str:
        from dehps.contracts import canonical_digest

        return canonical_digest(
            self.payload["gate_compiler_contract"][
                "statistical_input_contract"
            ],
            domain="dehps.m4.measurement-v2.statistical-input.v1",
        )


def json_compatible_copy(value: Any) -> Any:
    """Return a detached primitive JSON tree from a frozen contract value."""

    if isinstance(value, Mapping):
        return {
            str(key): json_compatible_copy(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_compatible_copy(item) for item in value]
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenMapping(
            {
                str(key): _freeze_json(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MeasurementContractV2Error(
            "measurement_v2_contract_invalid",
            f"{field} must be an object",
        )
    return value


def _array(value: Any, *, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise MeasurementContractV2Error(
            "measurement_v2_contract_invalid",
            f"{field} must be an array",
        )
    return value


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(
            item
            for nested in value.values()
            for item in _strings(nested)
        )
    if isinstance(value, list):
        return tuple(item for nested in value for item in _strings(nested))
    return (value,) if isinstance(value, str) else ()


def load_measurement_contract_v2(path: Path) -> MeasurementContractV2:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementContractV2Error(
            "measurement_v2_manifest_invalid",
            str(exc),
        ) from exc
    return validate_measurement_contract_v2(
        _mapping(payload, field="manifest root")
    )


def validate_measurement_contract_v2(
    payload: Mapping[str, Any],
) -> MeasurementContractV2:
    identity = (
        payload.get("schema_version"),
        payload.get("artifact_type"),
        payload.get("contract_key"),
        payload.get("semantic_version"),
        payload.get("status"),
        payload.get("purpose"),
        payload.get("production_action"),
    )
    if identity != (
        "dehps-m4-measurement-contract.v2",
        "hierarchical_information_measurement_contract",
        "M4_MEASUREMENT_CONTRACT_V2",
        "2.0.0",
        "FROZEN_SOURCE_INTEGRATION_PENDING",
        "hierarchical_incremental_information_measurement",
        "none",
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_identity_invalid",
            "frozen contract identity or production boundary changed",
        )

    supplied_digest = str(payload.get("artifact_digest") or "")
    if (
        not _DIGEST.fullmatch(supplied_digest)
        or supplied_digest != config_digest(payload)
        or supplied_digest != MEASUREMENT_CONTRACT_V2_DIGEST
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_digest_mismatch",
            "frozen v2 source contract changed",
        )

    legal = _mapping(payload.get("legal_domain"), field="legal_domain")
    if dict(legal) != {
        "domain": "SSQ_RED_BALL",
        "outcome_representation": "binary_vector_length_33_with_exactly_6_ones",
        "legal_combination_count": 1_107_568,
        "legal_combination_formula": "C(33,6)",
        "uniform_draw_probability": "1/C(33,6)",
        "uniform_number_marginal": "6/33",
        "sampling": "without_replacement",
        "illegal_draw_probability": 0,
    }:
        raise MeasurementContractV2Error(
            "measurement_v2_legal_domain_invalid",
            "legal six-of-33 domain changed",
        )

    result_blind = _mapping(
        payload.get("result_blind_freeze"),
        field="result_blind_freeze",
    )
    if dict(result_blind) != EXPECTED_RESULT_BLIND_FREEZE:
        raise MeasurementContractV2Error(
            "measurement_v2_result_blind_invalid",
            "result-blind freeze flags changed",
        )
    sources = _mapping(
        payload.get("upstream_source_identities"),
        field="upstream_source_identities",
    )
    if dict(sources) != EXPECTED_SOURCE_IDENTITIES:
        raise MeasurementContractV2Error(
            "measurement_v2_source_identity_invalid",
            "source-only upstream identity allowlist changed",
        )
    forbidden_source_markers = (
        "runtime/",
        "replicates/",
        "aggregates/",
        "gate-output",
        "partial-result",
    )
    if any(
        marker in value.lower()
        for value in _strings(sources)
        for marker in forbidden_source_markers
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_result_path_forbidden",
            "runtime statistical outcome identity entered the source allowlist",
        )

    lineage = _mapping(
        payload.get("p2_6_1_lineage_boundary"),
        field="p2_6_1_lineage_boundary",
    )
    if (
        lineage.get("task_key") != "m4-p2-false-positive-and-power-runs"
        or lineage.get("task_digest")
        != "80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa"
        or lineage.get("measurement_validation_manifest_digest")
        != EXPECTED_SOURCE_IDENTITIES[
            "p2_6_1_measurement_validation_manifest_digest"
        ]
        or lineage.get("immutable_task_identity_changed") is not False
        or lineage.get("immutable_manifest_identity_changed") is not False
        or lineage.get("runtime_operation_allowed") is not False
        or lineage.get("semantic_purpose")
        != "MARGINAL_OUTPUT_MEASUREMENT_ACCEPTANCE_BASELINE"
        or lineage.get("v2_historical_branch_evidence_credit") != "NONE"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_p2_6_1_lineage_invalid",
            "P2.6.1 immutable identity or evidence boundary changed",
        )

    axes = _mapping(payload.get("information_axes"), field="information_axes")
    if (
        axes.get("output_geometry")
        != ["NUMBER_EVENT_MARGINAL", "LEGAL_FIXED_CARDINALITY_JOINT"]
        or axes.get("formal_historical_conditioning_set")
        != "STRICT_PRIOR_HISTORY_H_LT"
        or axes.get("synthetic_instrument_historical_evidence")
        != "FORBIDDEN"
        or axes.get("axis_conflation") != "FAIL_CLOSED"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_information_axes_invalid",
            "output geometry and conditioning set must remain separate",
        )

    estimands = _mapping(
        payload.get("estimand_contract"),
        field="estimand_contract",
    )
    if (
        estimands.get("unit") != "bits_per_issue"
        or tuple(estimands.get("required_branch_order") or ()) != BRANCH_IDS
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_estimand_invalid",
            "branch order or unit changed",
        )
    raw_branches = _array(estimands.get("branches"), field="estimand branches")
    branches = tuple(
        _mapping(item, field="estimand branch") for item in raw_branches
    )
    if tuple(item.get("branch_id") for item in branches) != BRANCH_IDS:
        raise MeasurementContractV2Error(
            "measurement_v2_estimand_invalid",
            "exactly three ordered incremental branches are required",
        )
    marginal, temporal, joint = branches
    if (
        marginal.get("target_geometry") != "NUMBER_EVENT_MARGINAL"
        or marginal.get("conditioning_set") != "STATIONARY_NO_HISTORY"
        or temporal.get("target_geometry") != "NUMBER_EVENT_MARGINAL"
        or temporal.get("conditioning_set") != "STRICT_PRIOR_HISTORY_H_LT"
        or joint.get("target_geometry") != "LEGAL_FIXED_CARDINALITY_JOINT"
        or joint.get("conditioning_set") != "STRICT_PRIOR_HISTORY_H_LT"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_estimand_invalid",
            "branch geometry or conditioning boundary changed",
        )
    temporal_baseline = _mapping(
        temporal.get("baseline"),
        field="temporal baseline",
    )
    joint_baseline = _mapping(joint.get("baseline"), field="joint baseline")
    if (
        temporal_baseline.get("source_branch_id") != BRANCH_IDS[0]
        or temporal_baseline.get("artifact_identity")
        != "DIRECT_REUSE_OF_ACCEPTED_MARGINAL_MODEL_ARTIFACT"
        or temporal_baseline.get("fallback") != "FORBIDDEN"
        or joint_baseline.get("source_branch_id") != BRANCH_IDS[1]
        or joint_baseline.get("artifact_identity")
        != (
            "DISTINCT_DERIVED_BASELINE_ARTIFACT_WITH_"
            "PARENT_TEMPORAL_MODEL_DIGEST"
        )
        or joint_baseline.get("independent_bernoulli_product") != "FORBIDDEN"
        or joint_baseline.get("uniform_fallback") != "FORBIDDEN"
        or joint_baseline.get("solver_and_boundary_policy")
        != "UNRESOLVED_PENDING_PREFLIGHT"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_baseline_invalid",
            "incremental adjacent baseline contract changed",
        )
    invariants = _array(
        estimands.get("no_duplicate_credit_invariants"),
        field="no_duplicate_credit_invariants",
    )
    if len(invariants) != 7:
        raise MeasurementContractV2Error(
            "measurement_v2_duplicate_credit_invalid",
            "all seven no-duplicate-credit invariants are required",
        )

    roles = _mapping(
        payload.get("mechanism_role_contract"),
        field="mechanism_role_contract",
    )
    if (
        frozenset(roles.get("role_values") or ()) != ROLE_VALUES
        or tuple(roles.get("branch_ids") or ()) != BRANCH_IDS
        or roles.get("role_is_relative_to_estimand") is not True
        or roles.get("synthetic_roles_can_create_historical_evidence")
        is not False
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_role_contract_invalid",
            "role vocabulary or estimand-relative boundary changed",
        )
    raw_rows = _array(roles.get("matrix"), field="mechanism role matrix")
    mechanism_rows = tuple(
        _mapping(item, field="mechanism role row") for item in raw_rows
    )
    mechanism_ids = tuple(str(item.get("mechanism_id") or "") for item in mechanism_rows)
    if len(mechanism_ids) != 8 or len(set(mechanism_ids)) != len(mechanism_ids):
        raise MeasurementContractV2Error(
            "measurement_v2_role_matrix_invalid",
            "the eight mechanism rows must be complete and unique",
        )
    for row in mechanism_rows:
        cells = _mapping(row.get("roles"), field="mechanism role cells")
        if tuple(cells) != BRANCH_IDS:
            raise MeasurementContractV2Error(
                "measurement_v2_role_matrix_invalid",
                f"{row.get('mechanism_id')} does not cover every branch in order",
            )
        for branch_id, raw_cell in cells.items():
            cell = _mapping(raw_cell, field=f"{branch_id} role cell")
            if (
                cell.get("role") not in ROLE_VALUES
                or cell.get("historical_evidence_eligible") is not False
                or cell.get("decision_credit") is not False
                or not str(cell.get("truth_basis") or "").strip()
            ):
                raise MeasurementContractV2Error(
                    "measurement_v2_role_matrix_invalid",
                    f"{row.get('mechanism_id')}:{branch_id} role is unsafe",
                )
    _verify_required_control_roles(mechanism_rows)

    gate = _mapping(
        payload.get("gate_compiler_contract"),
        field="gate_compiler_contract",
    )
    if (
        tuple(gate.get("required_branch_ids") or ()) != BRANCH_IDS
        or gate.get("practical_threshold_bits_per_issue") != 0.01
        or gate.get("simultaneous_confidence_level") != 0.95
        or _mapping(gate.get("multiplicity"), field="multiplicity").get(
            "method"
        )
        != "HOLM"
        or _mapping(gate.get("multiplicity"), field="multiplicity").get(
            "familywise_alpha"
        )
        != 0.05
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_contract_invalid",
            "fixed three-branch compiler family or thresholds changed",
        )
    if (
        frozenset(gate.get("measurement_health_values") or ())
        != {"PASS", "REPAIR", "INCONCLUSIVE"}
        or frozenset(gate.get("historical_evidence_values") or ())
        != {"POSITIVE", "NEGATIVE", "INCONCLUSIVE", "NOT_RUN"}
        or frozenset(gate.get("global_coverage_values") or ())
        != {"FULL", "PARTIAL"}
        or frozenset(gate.get("global_evidence_values") or ())
        != {
            "CANDIDATE_INFORMATION_FOUND",
            "NO_DETECTABLE_INFORMATION",
            "INCONCLUSIVE",
        }
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_contract_invalid",
            "health, evidence, or coverage outputs changed",
        )
    provenance = _mapping(
        gate.get("branch_report_provenance_contract"),
        field="branch_report_provenance_contract",
    )
    if (
        tuple(
            provenance.get("identifiability_preflight_status_values") or ()
        )
        != ("PASS", "FAIL", "UNRESOLVED")
        or provenance.get("temporal_baseline_identity")
        != (
            "baseline_artifact_digest equals the accepted Marginal model "
            "artifact digest"
        )
        or provenance.get("joint_baseline_identity")
        != (
            "baseline_artifact_digest is distinct from the accepted "
            "Temporal model artifact and baseline_source_model_artifact_"
            "digest equals that Temporal model digest"
        )
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_provenance_invalid",
            "preflight or adjacent baseline provenance changed",
        )
    statistical = _mapping(
        gate.get("statistical_input_contract"),
        field="statistical_input_contract",
    )
    endpoint = _mapping(
        statistical.get("canonical_primary_endpoint"),
        field="canonical_primary_endpoint",
    )
    interval = _mapping(
        statistical.get("simultaneous_interval"),
        field="simultaneous_interval",
    )
    mde = _mapping(
        statistical.get("minimum_detectable_effect"),
        field="minimum_detectable_effect",
    )
    equivalence = _mapping(
        statistical.get("equivalence"),
        field="equivalence",
    )
    if (
        endpoint.get("unit") != "bits_per_issue"
        or endpoint.get("direction") != "higher_is_better"
        or endpoint.get("null") != "Delta_branch<=0.01"
        or endpoint.get("alternative") != "Delta_branch>0.01"
        or endpoint.get("p_value_tail") != "ONE_SIDED_UPPER"
        or endpoint.get("frozen_before_results") is not True
        or interval.get("family_coverage") != 0.95
        or interval.get("construction") != "BONFERRONI_TWO_SIDED"
        or interval.get("per_branch_total_two_sided_alpha") != "0.05/3"
        or interval.get("per_tail_alpha") != "0.05/6"
        or mde.get("minimum_power") != 0.8
        or mde.get("must_be_nonnegative") is not True
        or mde.get("computed_from_design_only") is not True
        or equivalence.get("null") != "Delta_branch>=0.01"
        or equivalence.get("alternative") != "Delta_branch<0.01"
        or equivalence.get("test") != "ONE_SIDED_UPPER_BOUND"
        or equivalence.get("per_branch_alpha") != "0.05/3"
        or equivalence.get("upper_bound_input")
        != "equivalence_upper_bound_bits_per_issue"
        or equivalence.get(
            "upper_bound_provenance_artifact_digest_required"
        )
        is not True
        or equivalence.get("minimum_power_at_zero") != 0.8
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_statistical_input_invalid",
            "endpoint, interval, MDE, or equivalence method changed",
        )

    integration = _mapping(
        payload.get("mainline_integration"),
        field="mainline_integration",
    )
    if (
        integration.get("goal") != "M4_INFORMATION_THEORY_EVIDENCE"
        or integration.get("task_key") != "m4-v2-measurement-contract-design"
        or integration.get("runner") != "research_evidence_supervisor"
        or integration.get("downstream_consumer")
        != "m4-v2-branch-identifiability-preflight-design"
        or integration.get("completion_fact")
        != "m4-measurement-contract-v2-design:FROZEN"
        or integration.get("live_import_while_p2_6_1_running") != "FORBIDDEN"
        or integration.get("current_completion_classification")
        != "INTEGRATION_PENDING"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_mainline_contract_invalid",
            "canonical integration or live-runtime boundary changed",
        )

    frozen_payload = _mapping(
        _freeze_json(payload),
        field="frozen manifest root",
    )
    frozen_estimands = _mapping(
        frozen_payload["estimand_contract"],
        field="frozen estimand contract",
    )
    frozen_branches = tuple(
        _mapping(item, field="frozen estimand branch")
        for item in frozen_estimands["branches"]
    )
    frozen_roles = _mapping(
        frozen_payload["mechanism_role_contract"],
        field="frozen mechanism role contract",
    )
    frozen_mechanism_rows = tuple(
        _mapping(item, field="frozen mechanism role row")
        for item in frozen_roles["matrix"]
    )
    return MeasurementContractV2(
        payload=frozen_payload,
        artifact_digest=supplied_digest,
        branches=frozen_branches,
        mechanism_rows=frozen_mechanism_rows,
    )


def _verify_required_control_roles(
    rows: tuple[Mapping[str, Any], ...],
) -> None:
    by_id = {str(item["mechanism_id"]): item for item in rows}
    expected = {
        "NULL_UNIFORM_LEGAL_SIX_OF_33": (
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
        ),
        "V2_M1_STATIONARY_MARGINAL_SHIFT": (
            "POSITIVE_CONTROL",
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
        ),
        "V2_T1_HISTORY_CONDITIONAL_MARGINAL_SHIFT": (
            "NEGATIVE_CONTROL",
            "POSITIVE_CONTROL",
            "NEGATIVE_CONTROL",
        ),
        "V2_J1_HISTORY_CONDITIONAL_JOINT_SHIFT": (
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
            "POSITIVE_CONTROL",
        ),
        "IS4_MARGINAL_PRESERVING_CONDITIONAL": (
            "NEGATIVE_CONTROL",
            "NEGATIVE_CONTROL",
            "POSITIVE_CONTROL",
        ),
    }
    if not set(expected).issubset(by_id):
        raise MeasurementContractV2Error(
            "measurement_v2_control_coverage_invalid",
            "required null and branch-isolating controls are missing",
        )
    for mechanism_id, expected_roles in expected.items():
        cells = _mapping(by_id[mechanism_id]["roles"], field="control roles")
        actual = tuple(cells[branch_id]["role"] for branch_id in BRANCH_IDS)
        if actual != expected_roles:
            raise MeasurementContractV2Error(
                "measurement_v2_control_coverage_invalid",
                f"{mechanism_id} control roles changed",
            )
