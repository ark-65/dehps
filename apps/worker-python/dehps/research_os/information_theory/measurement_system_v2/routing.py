from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from dehps.research_os.models import (
    M4_V2_BRANCH_DECISION_ARTIFACT_TYPE,
    M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE,
    M4_V2_BRANCH_DECISION_REPLAY_SCHEMA,
    M4_V2_BRANCH_DECISION_SCHEMA,
    M4_V2_BRANCH_IDS,
    M4_V2_ESTIMAND_DIGESTS,
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
    MainlineArtifactRegistration,
    m4_v2_canonical_json,
    m4_v2_domain_digest,
    validate_m4_v2_artifact_envelope,
)

from .contracts import BRANCH_IDS, MeasurementContractV2Error

ADAPTIVE_RESEARCH_ELIGIBILITY_FACT = "m4-v2-routing:ADAPTIVE_RESEARCH_ELIGIBLE"
NO_DETECTABLE_INFORMATION = "NO_DETECTABLE_INFORMATION_UNDER_FROZEN_M4_V2_CONTRACT"
GLOBAL_ROUTE_SCHEMA = "dehps-m4-measurement-routing-decision.v1"
GLOBAL_ROUTE_ARTIFACT_TYPE = "m4_measurement_routing_decision"
GLOBAL_ROUTE_DIGEST_DOMAIN = "dehps.m4.v2.global-routing-decision.v1"
GLOBAL_ROUTE_TASK_KEY = "m4-v2-global-routing"
GLOBAL_ROUTE_CAPABILITY = "m4_v2_global_routing"
GLOBAL_ROUTE_COMPLETION_FACT = "m4-v2-global-routing:COMPLETE"
GLOBAL_ROUTE_ARTIFACT_SLUG = "global-routing-decision"
GLOBAL_ROUTE_ARTIFACT_FILENAME = "decision.json"
GLOBAL_ROUTE_REPLAY_FACTS = tuple(
    "m4-v2-historical-branch-decision-replay:"
    f"{M4_V2_MEASUREMENT_CONTRACT_KEY}:{branch_id}:VERIFIED"
    for branch_id in M4_V2_BRANCH_IDS
)
GLOBAL_ROUTES = (
    "ADAPTIVE_RESEARCH_ELIGIBLE",
    NO_DETECTABLE_INFORMATION,
    "DEEPER_VALIDATION_REQUIRED",
    "MEASUREMENT_REPAIR_REQUIRED",
)
_ALLOWED_TERMINAL_DECISIONS = frozenset(
    {
        "BRANCH_INFORMATION_ACCEPTED",
        "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE_DUE_TO_POWER",
        "MEASUREMENT_REPAIR_REQUIRED",
        "INVALID_EXECUTION",
        "NOT_EVALUABLE_PARENT_NOT_ACCEPTED",
    }
)
_ALLOWED_HEALTH = frozenset({"PASS", "REPAIR", "INCONCLUSIVE"})
_ALLOWED_EVIDENCE = frozenset({"POSITIVE", "NEGATIVE", "INCONCLUSIVE", "NOT_RUN"})
_EVALUATED_TERMINALS = frozenset(
    {
        "BRANCH_INFORMATION_ACCEPTED",
        "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE_DUE_TO_POWER",
    }
)
_TERMINAL_SHAPES = {
    "BRANCH_INFORMATION_ACCEPTED": (
        "BRANCH_INFORMATION_ACCEPTED",
        "COMPLETE",
        "PASS",
        frozenset({"POSITIVE"}),
    ),
    "NO_DETECTABLE_INFORMATION": (
        "NO_DETECTABLE_INFORMATION",
        "COMPLETE",
        "PASS",
        frozenset({"NEGATIVE"}),
    ),
    "INCONCLUSIVE_DUE_TO_POWER": (
        "INCONCLUSIVE_DUE_TO_POWER",
        "COMPLETE",
        "PASS",
        frozenset({"INCONCLUSIVE"}),
    ),
    "MEASUREMENT_REPAIR_REQUIRED": (
        "MEASUREMENT_REPAIR_REQUIRED",
        "REPAIR_REQUIRED",
        "REPAIR",
        frozenset({"INCONCLUSIVE", "NOT_RUN"}),
    ),
    "INVALID_EXECUTION": (
        "INVALID_EXECUTION",
        "INVALID",
        "INCONCLUSIVE",
        frozenset({"INCONCLUSIVE", "NOT_RUN"}),
    ),
    "NOT_EVALUABLE_PARENT_NOT_ACCEPTED": (
        None,
        "NOT_RUN_PARENT_NOT_ACCEPTED",
        "INCONCLUSIVE",
        frozenset({"NOT_RUN"}),
    ),
}
_MARGINAL_ACCEPTED_MODEL_DIGEST = (
    "fb7eb603f7fc283ee645a38ae1d2555d47b43fb86dbb23439a91ef329f1167d6"
)
_MARGINAL_BASELINE_DIGEST = (
    "efbb2a3d3b711c5c63b9f05b8133f9cc4ba77b1121b90ef9f951ab56fe263b3e"
)
_DECISION_PROJECTION_FIELDS = (
    "branch_id",
    "estimand_digest",
    "decision_path",
    "terminal_decision",
    "scientific_decision",
    "evaluation_status",
    "measurement_health",
    "historical_evidence",
    "accepted_for_downstream_baseline",
    "accepted_model_artifact_digest",
    "baseline_artifact_digest",
    "baseline_source_model_artifact_digest",
    "decision_artifact_digest",
    "decision_producer_execution_id",
    "replay_artifact_digest",
    "replay_registration_digest",
)
_ROUTE_BODY_FIELDS = (
    "measurement_contract_digest",
    "canonical_branch_order",
    "canonical_estimand_digests",
    "registered_branch_decision_digests",
    "registered_branch_replay_registration_digests",
    "decision_projection_rows",
    "decision_replay_coverage",
    "source_contract_digest",
    "task_digest",
    "measurement_global_coverage",
    "router_conclusive_coverage",
    "canonical_global_evidence",
    "positive_branches",
    "repair_branches",
    "route",
    "next_lane",
)


class M4V2GlobalRoutingError(ValueError):
    pass


def _mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        converted = converter()
        if isinstance(converted, Mapping):
            return deepcopy(dict(converted))
    if is_dataclass(value) and not isinstance(value, type):
        return deepcopy(asdict(value))
    raise M4V2GlobalRoutingError(f"{field_name}_must_be_mapping_or_typed_artifact")


def _body(value: Mapping[str, Any], *, field_name: str) -> dict[str, Any]:
    candidate = value.get("body", value)
    if not isinstance(candidate, Mapping):
        raise M4V2GlobalRoutingError(f"{field_name}_body_invalid")
    return deepcopy(dict(candidate))


def _digest(value: Any, *, field_name: str) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise M4V2GlobalRoutingError(f"{field_name}_invalid")
    return digest


def m4_v2_global_route_artifact_path(*, execution_id: str, artifact_digest: str) -> str:
    """Return the sole content-addressed path for a Global route artifact."""

    frozen_execution_id = _digest(execution_id, field_name="execution_id")
    frozen_artifact_digest = _digest(artifact_digest, field_name="artifact_digest")
    return (
        f"runtime/research-os/mainline/tasks/{GLOBAL_ROUTE_TASK_KEY}/"
        f"{frozen_execution_id}/artifacts/{GLOBAL_ROUTE_ARTIFACT_SLUG}/"
        f"{frozen_artifact_digest}/{GLOBAL_ROUTE_ARTIFACT_FILENAME}"
    )


@dataclass(frozen=True)
class M4V2GlobalRouteDecisionArtifact:
    measurement_contract_digest: str
    canonical_branch_order: tuple[str, ...]
    canonical_estimand_digests: Mapping[str, str]
    registered_branch_decision_digests: tuple[str, ...]
    registered_branch_replay_registration_digests: tuple[str, ...]
    decision_projection_rows: tuple[Mapping[str, Any], ...]
    decision_replay_coverage: str
    source_contract_digest: str
    task_digest: str
    measurement_global_coverage: str
    router_conclusive_coverage: str
    canonical_global_evidence: str
    positive_branches: tuple[str, ...]
    repair_branches: tuple[str, ...]
    route: str
    next_lane: str

    def __post_init__(self) -> None:
        if (
            self.measurement_contract_digest != M4_V2_MEASUREMENT_CONTRACT_DIGEST
            or self.canonical_branch_order != tuple(M4_V2_BRANCH_IDS)
            or dict(self.canonical_estimand_digests) != M4_V2_ESTIMAND_DIGESTS
            or len(self.registered_branch_decision_digests) != 3
            or len(self.registered_branch_replay_registration_digests) != 3
            or len(self.decision_projection_rows) != 3
            or self.decision_replay_coverage != "COMPLETE"
            or self.measurement_global_coverage not in {"FULL", "PARTIAL"}
            or self.router_conclusive_coverage not in {"FULL", "PARTIAL"}
            or self.canonical_global_evidence
            not in {
                "CANDIDATE_INFORMATION_FOUND",
                "NO_DETECTABLE_INFORMATION",
                "INCONCLUSIVE",
            }
            or self.route not in GLOBAL_ROUTES
            or not self.next_lane
        ):
            raise M4V2GlobalRoutingError("global_route_artifact_body_invalid")
        _digest(self.source_contract_digest, field_name="source_contract_digest")
        _digest(self.task_digest, field_name="task_digest")
        for field_name, values in (
            (
                "registered_branch_decision_digests",
                self.registered_branch_decision_digests,
            ),
            (
                "registered_branch_replay_registration_digests",
                self.registered_branch_replay_registration_digests,
            ),
        ):
            if len(set(values)) != 3:
                raise M4V2GlobalRoutingError(
                    f"global_route_artifact_{field_name}_not_unique"
                )
            for value in values:
                _digest(value, field_name=field_name)
        for expected_branch_id, row in zip(
            M4_V2_BRANCH_IDS, self.decision_projection_rows, strict=True
        ):
            if (
                tuple(row) != _DECISION_PROJECTION_FIELDS
                or row.get("branch_id") != expected_branch_id
                or row.get("estimand_digest")
                != M4_V2_ESTIMAND_DIGESTS[expected_branch_id]
            ):
                raise M4V2GlobalRoutingError("global_route_artifact_projection_invalid")
            _validate_decision_semantics(row, branch_id=expected_branch_id)
            for field_name in (
                "decision_artifact_digest",
                "decision_producer_execution_id",
                "replay_artifact_digest",
                "replay_registration_digest",
            ):
                _digest(row[field_name], field_name=field_name)
        if (
            tuple(
                row["decision_artifact_digest"] for row in self.decision_projection_rows
            )
            != self.registered_branch_decision_digests
            or tuple(
                row["replay_registration_digest"]
                for row in self.decision_projection_rows
            )
            != self.registered_branch_replay_registration_digests
        ):
            raise M4V2GlobalRoutingError(
                "global_route_artifact_registered_projection_mismatch"
            )
        if (
            len(
                {row["replay_artifact_digest"] for row in self.decision_projection_rows}
            )
            != 3
        ):
            raise M4V2GlobalRoutingError(
                "global_route_artifact_replay_digests_not_unique"
            )
        _validate_hierarchical_reachability(self.decision_projection_rows)
        derived = _derive_global_route(self.decision_projection_rows)
        declared = {
            "measurement_global_coverage": self.measurement_global_coverage,
            "router_conclusive_coverage": self.router_conclusive_coverage,
            "canonical_global_evidence": self.canonical_global_evidence,
            "positive_branches": list(self.positive_branches),
            "repair_branches": list(self.repair_branches),
            "route": self.route,
            "next_lane": self.next_lane,
        }
        if m4_v2_canonical_json(declared) != m4_v2_canonical_json(derived):
            raise M4V2GlobalRoutingError("global_route_artifact_derivation_mismatch")

    def to_body(self) -> dict[str, Any]:
        body = {
            "measurement_contract_digest": self.measurement_contract_digest,
            "canonical_branch_order": list(self.canonical_branch_order),
            "canonical_estimand_digests": dict(self.canonical_estimand_digests),
            "registered_branch_decision_digests": list(
                self.registered_branch_decision_digests
            ),
            "registered_branch_replay_registration_digests": list(
                self.registered_branch_replay_registration_digests
            ),
            "decision_projection_rows": [
                deepcopy(dict(row)) for row in self.decision_projection_rows
            ],
            "decision_replay_coverage": self.decision_replay_coverage,
            "source_contract_digest": self.source_contract_digest,
            "task_digest": self.task_digest,
            "measurement_global_coverage": self.measurement_global_coverage,
            "router_conclusive_coverage": self.router_conclusive_coverage,
            "canonical_global_evidence": self.canonical_global_evidence,
            "positive_branches": list(self.positive_branches),
            "repair_branches": list(self.repair_branches),
            "route": self.route,
            "next_lane": self.next_lane,
        }
        if tuple(body) != _ROUTE_BODY_FIELDS:
            raise AssertionError("global route body order changed")
        return body

    @property
    def artifact_digest(self) -> str:
        return m4_v2_domain_digest(self.to_body(), domain=GLOBAL_ROUTE_DIGEST_DOMAIN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": GLOBAL_ROUTE_SCHEMA,
            "artifact_type": GLOBAL_ROUTE_ARTIFACT_TYPE,
            "artifact_digest": self.artifact_digest,
            **self.to_body(),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> M4V2GlobalRouteDecisionArtifact:
        payload = _mapping(value, field_name="global_route_artifact")
        expected_fields = {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            *_ROUTE_BODY_FIELDS,
        }
        if set(payload) != expected_fields:
            raise M4V2GlobalRoutingError("global_route_artifact_fields_invalid")
        if (
            payload["schema_version"] != GLOBAL_ROUTE_SCHEMA
            or payload["artifact_type"] != GLOBAL_ROUTE_ARTIFACT_TYPE
        ):
            raise M4V2GlobalRoutingError("global_route_artifact_envelope_invalid")
        artifact = cls(
            measurement_contract_digest=payload["measurement_contract_digest"],
            canonical_branch_order=tuple(payload["canonical_branch_order"]),
            canonical_estimand_digests=dict(payload["canonical_estimand_digests"]),
            registered_branch_decision_digests=tuple(
                payload["registered_branch_decision_digests"]
            ),
            registered_branch_replay_registration_digests=tuple(
                payload["registered_branch_replay_registration_digests"]
            ),
            decision_projection_rows=tuple(
                deepcopy(dict(row)) for row in payload["decision_projection_rows"]
            ),
            decision_replay_coverage=payload["decision_replay_coverage"],
            source_contract_digest=payload["source_contract_digest"],
            task_digest=payload["task_digest"],
            measurement_global_coverage=payload["measurement_global_coverage"],
            router_conclusive_coverage=payload["router_conclusive_coverage"],
            canonical_global_evidence=payload["canonical_global_evidence"],
            positive_branches=tuple(payload["positive_branches"]),
            repair_branches=tuple(payload["repair_branches"]),
            route=payload["route"],
            next_lane=payload["next_lane"],
        )
        if (
            _digest(payload["artifact_digest"], field_name="artifact_digest")
            != artifact.artifact_digest
        ):
            raise M4V2GlobalRoutingError("global_route_artifact_digest_mismatch")
        return artifact


def _validate_decision_semantics(
    decision: Mapping[str, Any], *, branch_id: str
) -> None:
    terminal = decision.get("terminal_decision")
    shape = _TERMINAL_SHAPES.get(terminal)
    if shape is None:
        raise M4V2GlobalRoutingError(
            f"branch_record_terminal_decision_invalid:{branch_id}"
        )
    scientific, evaluation, health, allowed_evidence = shape
    if (
        decision.get("scientific_decision") != scientific
        or decision.get("evaluation_status") != evaluation
        or decision.get("measurement_health") != health
        or decision.get("historical_evidence") not in allowed_evidence
    ):
        raise M4V2GlobalRoutingError(
            f"branch_record_terminal_shape_invalid:{branch_id}"
        )

    if branch_id == "MARGINAL_STATIC":
        expected_path = "IDENTITY_ADOPTION_COMPLETE"
        if terminal == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED":
            raise M4V2GlobalRoutingError(
                "branch_record_marginal_parent_not_accepted_unreachable"
            )
    elif terminal in _EVALUATED_TERMINALS:
        expected_path = "EVALUATED_COMPLETE"
    elif terminal == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED":
        expected_path = "PARENT_NOT_ACCEPTED"
    elif terminal == "MEASUREMENT_REPAIR_REQUIRED":
        expected_path = (
            "IDENTITY_VALID_HEALTH_REPAIR"
            if decision.get("historical_evidence") == "NOT_RUN"
            else "IDENTITY_VALID_HISTORICAL_REPAIR"
        )
    else:
        expected_path = (
            "IDENTITY_VALID_HEALTH_INVALID"
            if decision.get("historical_evidence") == "NOT_RUN"
            else "IDENTITY_VALID_HISTORICAL_INVALID"
        )
    if decision.get("decision_path") != expected_path:
        raise M4V2GlobalRoutingError(f"branch_record_decision_path_invalid:{branch_id}")

    accepted_model = decision.get("accepted_model_artifact_digest")
    baseline = decision.get("baseline_artifact_digest")
    baseline_source = decision.get("baseline_source_model_artifact_digest")
    evaluated = terminal in _EVALUATED_TERMINALS
    if evaluated:
        accepted_model = _digest(
            accepted_model,
            field_name=f"{branch_id}.accepted_model_artifact_digest",
        )
        baseline = _digest(
            baseline,
            field_name=f"{branch_id}.baseline_artifact_digest",
        )
        if branch_id == "MARGINAL_STATIC":
            if (
                accepted_model != _MARGINAL_ACCEPTED_MODEL_DIGEST
                or baseline != _MARGINAL_BASELINE_DIGEST
                or baseline_source is not None
            ):
                raise M4V2GlobalRoutingError(
                    "branch_record_marginal_model_identity_invalid"
                )
        else:
            baseline_source = _digest(
                baseline_source,
                field_name=f"{branch_id}.baseline_source_model_artifact_digest",
            )
            if branch_id == "TEMPORAL_MARGINAL_INCREMENT":
                if baseline != baseline_source:
                    raise M4V2GlobalRoutingError(
                        "branch_record_temporal_baseline_identity_invalid"
                    )
            elif accepted_model == baseline or baseline == baseline_source:
                raise M4V2GlobalRoutingError(
                    "branch_record_joint_baseline_identity_invalid"
                )
    elif any(item is not None for item in (accepted_model, baseline, baseline_source)):
        raise M4V2GlobalRoutingError(
            f"branch_record_non_evaluated_model_identity_invalid:{branch_id}"
        )

    expected_accepted = bool(
        terminal == "BRANCH_INFORMATION_ACCEPTED"
        and evaluated
        and accepted_model != baseline
    )
    if decision.get("accepted_for_downstream_baseline") is not expected_accepted:
        raise M4V2GlobalRoutingError(
            f"branch_record_accepted_baseline_invalid:{branch_id}"
        )


def _validate_hierarchical_reachability(
    projections: Sequence[Mapping[str, Any]],
) -> None:
    marginal, temporal, joint = projections
    marginal_accepted = bool(marginal["accepted_for_downstream_baseline"])
    temporal_accepted = bool(temporal["accepted_for_downstream_baseline"])
    temporal_parent_stop = (
        temporal["terminal_decision"] == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
    )
    joint_parent_stop = (
        joint["terminal_decision"] == "NOT_EVALUABLE_PARENT_NOT_ACCEPTED"
    )
    if not marginal_accepted:
        if not temporal_parent_stop or not joint_parent_stop:
            raise M4V2GlobalRoutingError(
                "global_route_hierarchical_reachability_invalid:marginal"
            )
    else:
        if temporal_parent_stop:
            raise M4V2GlobalRoutingError(
                "global_route_hierarchical_reachability_invalid:temporal"
            )
        if temporal_accepted == joint_parent_stop:
            raise M4V2GlobalRoutingError(
                "global_route_hierarchical_reachability_invalid:joint"
            )

    if temporal["terminal_decision"] in _EVALUATED_TERMINALS and (
        temporal["baseline_source_model_artifact_digest"]
        != marginal["accepted_model_artifact_digest"]
        or temporal["baseline_artifact_digest"]
        != marginal["accepted_model_artifact_digest"]
    ):
        raise M4V2GlobalRoutingError(
            "global_route_temporal_parent_model_lineage_invalid"
        )
    if joint["terminal_decision"] in _EVALUATED_TERMINALS and (
        joint["baseline_source_model_artifact_digest"]
        != temporal["accepted_model_artifact_digest"]
        or joint["baseline_artifact_digest"]
        == temporal["accepted_model_artifact_digest"]
    ):
        raise M4V2GlobalRoutingError("global_route_joint_parent_model_lineage_invalid")


def _derive_global_route(
    projections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    measurement_coverage = (
        "FULL"
        if all(
            row["measurement_health"] == "PASS"
            and row["evaluation_status"] == "COMPLETE"
            for row in projections
        )
        else "PARTIAL"
    )
    router_coverage = (
        "FULL"
        if measurement_coverage == "FULL"
        and all(
            row["historical_evidence"] in {"POSITIVE", "NEGATIVE"}
            for row in projections
        )
        else "PARTIAL"
    )
    positive = [
        row["branch_id"]
        for row in projections
        if row["measurement_health"] == "PASS"
        and row["historical_evidence"] == "POSITIVE"
    ]
    repair = [
        row["branch_id"]
        for row in projections
        if row["terminal_decision"]
        in {"MEASUREMENT_REPAIR_REQUIRED", "INVALID_EXECUTION"}
        or row["measurement_health"] == "REPAIR"
    ]
    if positive:
        global_evidence = "CANDIDATE_INFORMATION_FOUND"
    elif measurement_coverage == "FULL" and all(
        row["historical_evidence"] == "NEGATIVE" for row in projections
    ):
        global_evidence = "NO_DETECTABLE_INFORMATION"
    else:
        global_evidence = "INCONCLUSIVE"

    if router_coverage == "FULL" and positive:
        route, next_lane = (
            "ADAPTIVE_RESEARCH_ELIGIBLE",
            "P3_PREDICTIVE_PREREGISTRATION_FREEZE",
        )
    elif router_coverage == "FULL" and all(
        row["historical_evidence"] == "NEGATIVE" for row in projections
    ):
        route, next_lane = NO_DETECTABLE_INFORMATION, "KERNEL_SEARCH_EFFICIENCY"
    elif repair and not positive:
        route, next_lane = "MEASUREMENT_REPAIR_REQUIRED", "MEASUREMENT_REPAIR"
    else:
        route, next_lane = "DEEPER_VALIDATION_REQUIRED", "M4_DEEPER_VALIDATION"
    if route not in GLOBAL_ROUTES:
        raise AssertionError("global route escaped the frozen finite set")
    return {
        "measurement_global_coverage": measurement_coverage,
        "router_conclusive_coverage": router_coverage,
        "canonical_global_evidence": global_evidence,
        "positive_branches": positive,
        "repair_branches": repair,
        "route": route,
        "next_lane": next_lane,
    }


def _registration(
    value: Any,
    *,
    field_name: str,
    expected_artifact_digest: str,
    expected_artifact_type: str,
    expected_schema_version: str,
    expected_parent_digests: Sequence[str],
) -> dict[str, Any]:
    registration = _mapping(value, field_name=field_name)
    if "registration_digest" not in registration and hasattr(
        value, "registration_digest"
    ):
        registration["registration_digest"] = value.registration_digest
    canonical_path_alias = registration.pop("canonical_artifact_path", None)
    if canonical_path_alias is not None:
        if (
            registration.get("artifact_path") is not None
            and registration["artifact_path"] != canonical_path_alias
        ):
            raise M4V2GlobalRoutingError(f"{field_name}_canonical_path_mismatch")
        registration["artifact_path"] = canonical_path_alias
    required = {
        "registration_digest",
        "execution_id",
        "control_plane_key",
        "task_key",
        "task_digest",
        "artifact_digest",
        "artifact_type",
        "schema_version",
        "artifact_path",
        "parent_digests",
        "git_commit",
    }
    if set(registration) != required:
        raise M4V2GlobalRoutingError(f"{field_name}_fields_missing")
    if (
        _digest(
            registration["artifact_digest"],
            field_name=f"{field_name}.artifact_digest",
        )
        != expected_artifact_digest
    ):
        raise M4V2GlobalRoutingError(f"{field_name}_artifact_digest_mismatch")
    supplied_registration_digest = _digest(
        registration["registration_digest"],
        field_name=f"{field_name}.registration_digest",
    )
    execution_id = _digest(
        registration["execution_id"], field_name=f"{field_name}.execution_id"
    )
    task_digest = _digest(
        registration["task_digest"], field_name=f"{field_name}.task_digest"
    )
    task_key = str(registration.get("task_key") or "")
    control_plane_key = str(registration.get("control_plane_key") or "")
    if not task_key or not control_plane_key:
        raise M4V2GlobalRoutingError(f"{field_name}_owner_identity_invalid")
    if registration["artifact_type"] != expected_artifact_type:
        raise M4V2GlobalRoutingError(f"{field_name}_artifact_type_mismatch")
    if registration["schema_version"] != expected_schema_version:
        raise M4V2GlobalRoutingError(f"{field_name}_schema_version_mismatch")
    raw_parents = registration["parent_digests"]
    if not isinstance(raw_parents, Sequence) or isinstance(
        raw_parents, (str, bytes, bytearray)
    ):
        raise M4V2GlobalRoutingError(f"{field_name}_parent_digests_invalid")
    parents = tuple(
        _digest(item, field_name=f"{field_name}.parent_digests") for item in raw_parents
    )
    if parents != tuple(expected_parent_digests):
        raise M4V2GlobalRoutingError(f"{field_name}_parent_digests_mismatch")
    path = str(registration.get("artifact_path") or "")
    slug, filename = {
        M4_V2_BRANCH_DECISION_ARTIFACT_TYPE: ("branch-decision", "decision.json"),
        M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE: (
            "branch-decision-replay",
            "replay.json",
        ),
    }[expected_artifact_type]
    expected_path = (
        f"runtime/research-os/mainline/tasks/{task_key}/{execution_id}/"
        f"artifacts/{slug}/{expected_artifact_digest}/{filename}"
    )
    if path != expected_path:
        raise M4V2GlobalRoutingError(f"{field_name}_canonical_path_invalid")
    git_commit = str(registration.get("git_commit") or "")
    if len(git_commit) != 40 or any(
        character not in "0123456789abcdef" for character in git_commit
    ):
        raise M4V2GlobalRoutingError(f"{field_name}_git_commit_invalid")
    canonical = MainlineArtifactRegistration(
        execution_id=execution_id,
        control_plane_key=control_plane_key,
        task_key=task_key,
        task_digest=task_digest,
        artifact_digest=expected_artifact_digest,
        artifact_type=expected_artifact_type,
        schema_version=expected_schema_version,
        artifact_path=path,
        parent_digests=parents,
        git_commit=git_commit,
    )
    if canonical.registration_digest != supplied_registration_digest:
        raise M4V2GlobalRoutingError(f"{field_name}_registration_digest_mismatch")
    return {
        "registration_digest": supplied_registration_digest,
        **asdict(canonical),
        "parent_digests": list(parents),
    }


def _validated_record(
    value: Any, *, expected_branch_id: str
) -> tuple[dict[str, Any], str, str, dict[str, str]]:
    record = _mapping(value, field_name="branch_record")
    try:
        validated_decision = validate_m4_v2_artifact_envelope(
            _mapping(record.get("decision"), field_name="decision"),
            expected_artifact_type=M4_V2_BRANCH_DECISION_ARTIFACT_TYPE,
        )
        validated_replay = validate_m4_v2_artifact_envelope(
            _mapping(record.get("replay"), field_name="replay"),
            expected_artifact_type=M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE,
        )
    except (TypeError, ValueError) as exc:
        raise M4V2GlobalRoutingError(
            f"branch_record_artifact_invalid:{expected_branch_id}"
        ) from exc
    decision_envelope = _mapping(validated_decision, field_name="decision")
    replay_envelope = _mapping(validated_replay, field_name="replay")
    decision = _body(decision_envelope, field_name="decision")
    replay = _body(replay_envelope, field_name="replay")
    if (
        decision.get("measurement_contract_key") != M4_V2_MEASUREMENT_CONTRACT_KEY
        or decision.get("measurement_contract_digest")
        != M4_V2_MEASUREMENT_CONTRACT_DIGEST
        or decision.get("branch_id") != expected_branch_id
        or decision.get("estimand_digest") != M4_V2_ESTIMAND_DIGESTS[expected_branch_id]
        or decision.get("terminal_decision") not in _ALLOWED_TERMINAL_DECISIONS
        or decision.get("measurement_health") not in _ALLOWED_HEALTH
        or decision.get("historical_evidence") not in _ALLOWED_EVIDENCE
        or not isinstance(decision.get("accepted_for_downstream_baseline"), bool)
    ):
        raise M4V2GlobalRoutingError(
            f"branch_record_decision_semantics_invalid:{expected_branch_id}"
        )
    _validate_decision_semantics(decision, branch_id=expected_branch_id)
    if decision["accepted_for_downstream_baseline"] and not (
        decision["terminal_decision"] == "BRANCH_INFORMATION_ACCEPTED"
        and decision["measurement_health"] == "PASS"
        and decision["historical_evidence"] == "POSITIVE"
    ):
        raise M4V2GlobalRoutingError(
            f"branch_record_accepted_baseline_invalid:{expected_branch_id}"
        )
    decision_digest = _digest(
        decision_envelope.get("artifact_digest"),
        field_name="decision.artifact_digest",
    )
    replay_digest = _digest(
        replay_envelope.get("artifact_digest"),
        field_name="replay.artifact_digest",
    )
    decision_registration = _registration(
        record.get("decision_registration"),
        field_name="decision_registration",
        expected_artifact_digest=decision_digest,
        expected_artifact_type=M4_V2_BRANCH_DECISION_ARTIFACT_TYPE,
        expected_schema_version=M4_V2_BRANCH_DECISION_SCHEMA,
        expected_parent_digests=tuple(decision_envelope["parent_digests"]),
    )
    replay_registration = _registration(
        record.get("replay_registration"),
        field_name="replay_registration",
        expected_artifact_digest=replay_digest,
        expected_artifact_type=M4_V2_BRANCH_DECISION_REPLAY_ARTIFACT_TYPE,
        expected_schema_version=M4_V2_BRANCH_DECISION_REPLAY_SCHEMA,
        expected_parent_digests=tuple(replay_envelope["parent_digests"]),
    )
    if (
        decision_registration["task_key"] != decision.get("producer_task_key")
        or decision_registration["execution_id"]
        != decision.get("producer_execution_id")
        or replay.get("measurement_contract_key") != M4_V2_MEASUREMENT_CONTRACT_KEY
        or replay.get("measurement_contract_digest")
        != M4_V2_MEASUREMENT_CONTRACT_DIGEST
        or replay.get("branch_id") != expected_branch_id
        or replay.get("decision_artifact_digest") != decision_digest
        or replay.get("decision_registration_digest")
        != decision_registration["registration_digest"]
        or replay.get("decision_producer_task_key") != decision.get("producer_task_key")
        or replay.get("decision_producer_execution_id")
        != decision.get("producer_execution_id")
        or replay.get("replay_task_key") != replay_registration["task_key"]
        or replay.get("replay_execution_id") != replay_registration["execution_id"]
        or replay.get("replay_execution_id")
        == replay.get("decision_producer_execution_id")
        or replay.get("replay_status") != "REGISTERED_REPLAY_VERIFIED"
        or replay.get("source_integrity_verified") is not True
        or replay.get("registered_content_verified") is not True
        or replay.get("workload_rerun") is not False
    ):
        raise M4V2GlobalRoutingError(
            f"branch_record_replay_lineage_invalid:{expected_branch_id}"
        )
    projection = {
        "branch_id": expected_branch_id,
        "estimand_digest": decision["estimand_digest"],
        "decision_path": decision["decision_path"],
        "terminal_decision": decision["terminal_decision"],
        "scientific_decision": decision["scientific_decision"],
        "evaluation_status": decision["evaluation_status"],
        "measurement_health": decision["measurement_health"],
        "historical_evidence": decision["historical_evidence"],
        "accepted_for_downstream_baseline": decision[
            "accepted_for_downstream_baseline"
        ],
        "accepted_model_artifact_digest": decision["accepted_model_artifact_digest"],
        "baseline_artifact_digest": decision["baseline_artifact_digest"],
        "baseline_source_model_artifact_digest": decision[
            "baseline_source_model_artifact_digest"
        ],
        "decision_artifact_digest": decision_digest,
        "decision_producer_execution_id": decision["producer_execution_id"],
        "replay_artifact_digest": replay_digest,
        "replay_registration_digest": replay_registration["registration_digest"],
    }
    if tuple(projection) != _DECISION_PROJECTION_FIELDS:
        raise AssertionError("global route Decision projection order changed")
    return (
        projection,
        decision_digest,
        str(replay_registration["registration_digest"]),
        {
            "control_plane_key": decision_registration["control_plane_key"],
            "decision_registration_digest": decision_registration[
                "registration_digest"
            ],
            "decision_execution_id": decision_registration["execution_id"],
            "decision_task_digest": decision_registration["task_digest"],
            "decision_task_key": decision_registration["task_key"],
            "replay_artifact_digest": replay_digest,
            "replay_execution_id": replay_registration["execution_id"],
            "replay_task_digest": replay_registration["task_digest"],
            "replay_task_key": replay_registration["task_key"],
            "replay_control_plane_key": replay_registration["control_plane_key"],
        },
    )


def compile_m4_v2_global_route_decision(
    branch_records: Sequence[Any],
    *,
    source_contract_digest: str,
    task_digest: str,
) -> dict[str, Any]:
    """Compile the frozen finite global route from three registered records."""

    if (
        not isinstance(branch_records, Sequence)
        or isinstance(branch_records, (str, bytes, bytearray))
        or len(branch_records) != 3
    ):
        raise M4V2GlobalRoutingError("global_route_requires_three_branch_records")
    source_digest = _digest(source_contract_digest, field_name="source_contract_digest")
    frozen_task_digest = _digest(task_digest, field_name="task_digest")
    projections: list[dict[str, Any]] = []
    decision_digests: list[str] = []
    replay_registration_digests: list[str] = []
    record_identities: list[dict[str, str]] = []
    for expected_branch_id, record in zip(
        M4_V2_BRANCH_IDS, branch_records, strict=True
    ):
        (
            projection,
            decision_digest,
            replay_registration_digest,
            record_identity,
        ) = _validated_record(record, expected_branch_id=expected_branch_id)
        projections.append(projection)
        decision_digests.append(decision_digest)
        replay_registration_digests.append(replay_registration_digest)
        record_identities.append(record_identity)

    _validate_hierarchical_reachability(projections)
    unique_triplet_fields = (
        "decision_registration_digest",
        "decision_execution_id",
        "decision_task_digest",
        "decision_task_key",
        "replay_artifact_digest",
        "replay_execution_id",
        "replay_task_digest",
        "replay_task_key",
    )
    if (
        len(set(decision_digests)) != 3
        or len(set(replay_registration_digests)) != 3
        or any(
            len({identity[field] for identity in record_identities}) != 3
            for field in unique_triplet_fields
        )
        or len(
            {
                identity[field]
                for identity in record_identities
                for field in ("decision_execution_id", "replay_execution_id")
            }
        )
        != 6
        or len(
            {
                identity[field]
                for identity in record_identities
                for field in ("decision_task_digest", "replay_task_digest")
            }
        )
        != 6
        or len(
            {
                identity[field]
                for identity in record_identities
                for field in ("decision_task_key", "replay_task_key")
            }
        )
        != 6
        or len(
            {
                identity[field]
                for identity in record_identities
                for field in ("control_plane_key", "replay_control_plane_key")
            }
        )
        != 1
    ):
        raise M4V2GlobalRoutingError("global_route_registered_input_not_unique")

    derived = _derive_global_route(projections)

    body: dict[str, Any] = {
        "measurement_contract_digest": M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        "canonical_branch_order": list(M4_V2_BRANCH_IDS),
        "canonical_estimand_digests": dict(M4_V2_ESTIMAND_DIGESTS),
        "registered_branch_decision_digests": decision_digests,
        "registered_branch_replay_registration_digests": replay_registration_digests,
        "decision_projection_rows": projections,
        "decision_replay_coverage": "COMPLETE",
        "source_contract_digest": source_digest,
        "task_digest": frozen_task_digest,
        **derived,
    }
    if tuple(body) != _ROUTE_BODY_FIELDS:
        raise AssertionError("global route body order changed")
    return M4V2GlobalRouteDecisionArtifact(
        measurement_contract_digest=body["measurement_contract_digest"],
        canonical_branch_order=tuple(body["canonical_branch_order"]),
        canonical_estimand_digests=body["canonical_estimand_digests"],
        registered_branch_decision_digests=tuple(
            body["registered_branch_decision_digests"]
        ),
        registered_branch_replay_registration_digests=tuple(
            body["registered_branch_replay_registration_digests"]
        ),
        decision_projection_rows=tuple(body["decision_projection_rows"]),
        decision_replay_coverage=body["decision_replay_coverage"],
        source_contract_digest=body["source_contract_digest"],
        task_digest=body["task_digest"],
        measurement_global_coverage=body["measurement_global_coverage"],
        router_conclusive_coverage=body["router_conclusive_coverage"],
        canonical_global_evidence=body["canonical_global_evidence"],
        positive_branches=tuple(body["positive_branches"]),
        repair_branches=tuple(body["repair_branches"]),
        route=body["route"],
        next_lane=body["next_lane"],
    ).to_dict()


def replay_m4_v2_global_route_decision(
    branch_records: Sequence[Any],
    registered_route_artifact: Any,
    *,
    source_contract_digest: str,
    task_digest: str,
) -> dict[str, Any]:
    """Pure zero-write replay; it never creates a durable replay artifact."""

    rebuilt = compile_m4_v2_global_route_decision(
        branch_records,
        source_contract_digest=source_contract_digest,
        task_digest=task_digest,
    )
    registered = M4V2GlobalRouteDecisionArtifact.from_dict(
        _mapping(registered_route_artifact, field_name="registered_route_artifact")
    ).to_dict()
    if m4_v2_canonical_json(registered) != m4_v2_canonical_json(rebuilt):
        raise M4V2GlobalRoutingError("global_route_registered_replay_mismatch")
    return {
        "status": "REPLAY_VERIFIED",
        "outer_status": "REPLAY_VERIFIED",
        "capability_status": "REGISTERED_REPLAY_VERIFIED",
        "same_route_decision_identity": True,
        "same_registered_content": True,
        "route_artifact_digest": rebuilt["artifact_digest"],
        "source_integrity_verified": True,
        "workload_rerun": False,
        "raw_history_read": False,
        "numerical_result_payload_read": False,
        "durable_write_count": 0,
        "new_fact_count": 0,
        "durable_state_changed": False,
    }


compile_m4_v2_global_routing_decision = compile_m4_v2_global_route_decision
replay_m4_v2_global_routing_decision = replay_m4_v2_global_route_decision


def compile_m4_v2_routing_decision(
    gate_output: Mapping[str, Any],
) -> dict[str, Any]:
    """Route only replay-eligible, full-coverage hierarchical evidence."""

    if (
        gate_output.get("schema_version")
        != "dehps-m4-measurement-gate-compiler-output.v2"
        or gate_output.get("artifact_type") != "hierarchical_measurement_gate_output"
        or gate_output.get("promotion_gate_opened") is not False
        or gate_output.get("production_action") != "none"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing requires a non-production v2 Gate Compiler output",
        )
    gate_digest = str(gate_output.get("artifact_digest") or "")
    if len(gate_digest) != 64:
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "Gate Compiler output digest is missing",
        )
    branch_outputs = gate_output.get("branch_outputs")
    if not isinstance(branch_outputs, list) or len(branch_outputs) != 3:
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing requires all three branch outputs",
        )
    by_id = {
        str(item.get("branch_id")): item
        for item in branch_outputs
        if isinstance(item, Mapping)
    }
    if set(by_id) != set(BRANCH_IDS):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing branch coverage changed",
        )
    coverage = gate_output.get("global_coverage")
    if coverage not in {"FULL", "PARTIAL"}:
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "routing coverage is invalid",
        )
    health = {
        branch_id: by_id[branch_id].get("measurement_health")
        for branch_id in BRANCH_IDS
    }
    evidence = {
        branch_id: by_id[branch_id].get("historical_evidence")
        for branch_id in BRANCH_IDS
    }
    if any(
        value not in {"PASS", "REPAIR", "INCONCLUSIVE"} for value in health.values()
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "branch Measurement Health is invalid",
        )
    if any(
        value not in {"POSITIVE", "NEGATIVE", "INCONCLUSIVE", "NOT_RUN"}
        for value in evidence.values()
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_routing_input_invalid",
            "branch Historical Evidence is invalid",
        )

    positive = [
        branch_id
        for branch_id in BRANCH_IDS
        if health[branch_id] == "PASS" and evidence[branch_id] == "POSITIVE"
    ]
    repair = [branch_id for branch_id in BRANCH_IDS if health[branch_id] == "REPAIR"]
    if coverage == "FULL" and positive:
        route = "ADAPTIVE_RESEARCH_ELIGIBLE"
        next_lane = "P3_ADAPTIVE_RESEARCH"
    elif coverage == "FULL" and all(
        evidence[branch_id] == "NEGATIVE" for branch_id in BRANCH_IDS
    ):
        route = NO_DETECTABLE_INFORMATION
        next_lane = "KERNEL_SEARCH_EFFICIENCY"
    elif repair and not positive:
        route = "MEASUREMENT_REPAIR_REQUIRED"
        next_lane = "MEASUREMENT_REPAIR"
    else:
        route = "DEEPER_VALIDATION_REQUIRED"
        next_lane = "M4_DEEPER_VALIDATION"

    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-measurement-routing-decision.v1",
        "artifact_type": "m4_measurement_routing_decision",
        "artifact_digest": "",
        "gate_output_digest": gate_digest,
        "measurement_contract_v2_digest": gate_output.get("contract_digest"),
        "global_coverage": coverage,
        "gate_global_evidence": gate_output.get("global_evidence"),
        "route": route,
        "next_lane": next_lane,
        "positive_branches": positive,
        "repair_branches": repair,
        "expert_router_research_enabled": (route == "ADAPTIVE_RESEARCH_ELIGIBLE"),
        "adaptive_research_eligibility_fact": (
            ADAPTIVE_RESEARCH_ELIGIBILITY_FACT
            if route == "ADAPTIVE_RESEARCH_ELIGIBLE"
            else None
        ),
        "full_coverage_required": True,
        "partial_candidate_does_not_route": True,
        "production_candidate_created": False,
        "promotion_gate_opened": False,
        "production_action": "none",
        "parent_digests": [gate_digest],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = m4_v2_domain_digest(
        identity,
        domain="dehps.m4.measurement-v2.routing-decision.v1",
    )
    return payload
