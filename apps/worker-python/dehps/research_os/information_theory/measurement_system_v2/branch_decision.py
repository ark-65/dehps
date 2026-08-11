from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from dehps.research_os.models import (
    M4_V2_MEASUREMENT_CONTRACT_DIGEST,
    M4_V2_MEASUREMENT_CONTRACT_KEY,
    M4V2BranchDecisionArtifact,
    M4V2BranchDecisionReplayArtifact,
    ResearchOSValidationError,
)


class MarginalStaticBranchDecisionError(ResearchOSValidationError):
    """Raised when result-blind Marginal identity adoption is not exact."""


MARGINAL_STATIC_BRANCH_ID: Final = "MARGINAL_STATIC"
MARGINAL_STATIC_ESTIMAND_DIGEST: Final = (
    "821491eb28b19ebe4ce60d8f7baf7ff7233fec20dc6f25021581437ade56c631"
)
MARGINAL_STATIC_DECISION_PATH: Final = "IDENTITY_ADOPTION_COMPLETE"
MARGINAL_STATIC_DECISION_TASK_KEY: Final = (
    "m4-v2-marginal-static-historical-identity-adoption"
)
MARGINAL_STATIC_DECISION_CAPABILITY: Final = (
    "m4_v2_marginal_static_historical_identity_adoption"
)
MARGINAL_STATIC_REPLAY_TASK_KEY: Final = (
    "m4-v2-marginal-static-historical-branch-decision-replay"
)
MARGINAL_STATIC_REPLAY_CAPABILITY: Final = (
    "m4_v2_marginal_static_historical_branch_decision_replay"
)
MARGINAL_STATIC_TERMINAL_FACT: Final = (
    "m4-v2-historical-branch-decision:M4_MEASUREMENT_CONTRACT_V2:"
    "MARGINAL_STATIC:TERMINAL"
)
MARGINAL_STATIC_DECISION_COMPLETION_FACT: Final = (
    "m4-v2-marginal-static-historical-identity-adoption:COMPLETE"
)
MARGINAL_STATIC_REPLAY_VERIFIED_FACT: Final = (
    "m4-v2-historical-branch-decision-replay:M4_MEASUREMENT_CONTRACT_V2:"
    "MARGINAL_STATIC:VERIFIED"
)
MARGINAL_STATIC_REPLAY_COMPLETION_FACT: Final = (
    "m4-v2-marginal-static-historical-branch-decision-replay:COMPLETE"
)

MARGINAL_STATIC_GATE_ARTIFACT_DIGEST: Final = (
    "24e4c78cc12eab32aef2ee45cbeebb2b1078e6effea49442c2f45214890e7100"
)
MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST: Final = (
    "fb7eb603f7fc283ee645a38ae1d2555d47b43fb86dbb23439a91ef329f1167d6"
)
MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST: Final = (
    "efbb2a3d3b711c5c63b9f05b8133f9cc4ba77b1121b90ef9f951ab56fe263b3e"
)

_CATEGORICAL_IDENTITY_FIELDS: Final = frozenset(
    {
        "measurement_health",
        "historical_run_status",
        "historical_evidence",
        "identity_valid_scientific_execution_status",
        "accepted_for_downstream_baseline",
        "accepted_model_artifact_digest",
        "baseline_artifact_digest",
        "baseline_source_model_artifact_digest",
        "endpoint_digest",
    }
)
_RESULT_PAYLOAD_KEYS: Final = frozenset(
    {
        "raw_p_value",
        "raw_primary_p_value",
        "adjusted_p_value",
        "holm_adjusted_p_value",
        "effect_estimate",
        "effect_interval",
        "simultaneous_effect_interval_bits_per_issue",
        "equivalence_bound",
        "equivalence_upper_bound_bits_per_issue",
        "equivalence_power_at_zero",
        "power",
        "mde",
        "mde_bits_per_issue",
        "half_means",
        "half_means_bits_per_issue",
        "third_means",
        "fold_scores",
        "historical_fold_scores",
        "bootstrap_children",
        "seed",
        "seed_value",
        "prediction_metrics",
        "prediction_results",
        "outcomes",
        "winning_numbers",
        "prizes",
        "returns",
    }
)

_TERMINAL_FIELDS: Final = {
    "BRANCH_INFORMATION_ACCEPTED": {
        "scientific_decision": "BRANCH_INFORMATION_ACCEPTED",
        "evaluation_status": "COMPLETE",
        "measurement_health": "PASS",
        "historical_evidence": "POSITIVE",
        "accepted_for_downstream_baseline": True,
    },
    "NO_DETECTABLE_INFORMATION": {
        "scientific_decision": "NO_DETECTABLE_INFORMATION",
        "evaluation_status": "COMPLETE",
        "measurement_health": "PASS",
        "historical_evidence": "NEGATIVE",
        "accepted_for_downstream_baseline": False,
    },
    "INCONCLUSIVE_DUE_TO_POWER": {
        "scientific_decision": "INCONCLUSIVE_DUE_TO_POWER",
        "evaluation_status": "COMPLETE",
        "measurement_health": "PASS",
        "historical_evidence": "INCONCLUSIVE",
        "accepted_for_downstream_baseline": False,
    },
    "MEASUREMENT_REPAIR_REQUIRED": {
        "scientific_decision": "MEASUREMENT_REPAIR_REQUIRED",
        "evaluation_status": "REPAIR_REQUIRED",
        "measurement_health": "REPAIR",
        "historical_evidence": "INCONCLUSIVE",
        "accepted_for_downstream_baseline": False,
    },
    "INVALID_EXECUTION": {
        "scientific_decision": "INVALID_EXECUTION",
        "evaluation_status": "INVALID",
        "measurement_health": "INCONCLUSIVE",
        "historical_evidence": "INCONCLUSIVE",
        "accepted_for_downstream_baseline": False,
    },
}


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MarginalStaticBranchDecisionError(f"{name}_must_be_object")
    return value


def _reject_result_payload(value: Any, *, path: str = "categorical_identity") -> None:
    if isinstance(value, Mapping):
        forbidden = _RESULT_PAYLOAD_KEYS.intersection(value)
        if forbidden:
            raise MarginalStaticBranchDecisionError(
                "marginal_static_result_payload_access_attempted:"
                f"{path}:{','.join(sorted(forbidden))}"
            )
        for key, item in value.items():
            _reject_result_payload(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, item in enumerate(value):
            _reject_result_payload(item, path=f"{path}[{index}]")


def _require_digest_or_none(value: Any, *, name: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise MarginalStaticBranchDecisionError(f"{name}_must_be_sha256")
    return value


def _terminal_decision(categorical_identity: Mapping[str, Any]) -> str:
    execution_status = categorical_identity.get(
        "identity_valid_scientific_execution_status"
    )
    if execution_status is not None:
        if execution_status != "FAILED_OR_INCOMPLETE":
            raise MarginalStaticBranchDecisionError(
                "marginal_static_invalid_execution_status_outside_contract"
            )
        return "INVALID_EXECUTION"

    health = categorical_identity.get("measurement_health")
    if health == "REPAIR":
        return "MEASUREMENT_REPAIR_REQUIRED"
    if health != "PASS":
        raise MarginalStaticBranchDecisionError(
            "marginal_static_measurement_health_outside_contract"
        )
    if categorical_identity.get("historical_run_status") != "COMPLETE":
        raise MarginalStaticBranchDecisionError(
            "marginal_static_historical_run_status_outside_contract"
        )
    evidence = categorical_identity.get("historical_evidence")
    if not isinstance(evidence, str):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_historical_evidence_outside_contract"
        )
    mapping = {
        "POSITIVE": "BRANCH_INFORMATION_ACCEPTED",
        "NEGATIVE": "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE": "INCONCLUSIVE_DUE_TO_POWER",
    }
    try:
        return mapping[evidence]
    except KeyError as exc:
        raise MarginalStaticBranchDecisionError(
            "marginal_static_historical_evidence_outside_contract"
        ) from exc


def _validate_categorical_identity(
    value: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    categorical_identity = _mapping(value, name="categorical_identity")
    if any(not isinstance(key, str) for key in categorical_identity):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_categorical_identity_requires_string_keys"
        )
    _reject_result_payload(categorical_identity)
    unknown = set(categorical_identity).difference(_CATEGORICAL_IDENTITY_FIELDS)
    if unknown:
        raise MarginalStaticBranchDecisionError(
            "marginal_static_categorical_identity_unknown_fields:"
            + ",".join(sorted(unknown))
        )
    if "accepted_for_downstream_baseline" not in categorical_identity or not isinstance(
        categorical_identity["accepted_for_downstream_baseline"], bool
    ):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_registered_acceptance_boolean_missing"
        )
    terminal = _terminal_decision(categorical_identity)
    terminal_fields = dict(_TERMINAL_FIELDS[terminal])
    if (
        categorical_identity["accepted_for_downstream_baseline"]
        is not terminal_fields["accepted_for_downstream_baseline"]
    ):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_registered_acceptance_boolean_mismatch"
        )

    endpoint_digest = categorical_identity.get("endpoint_digest")
    _require_digest_or_none(endpoint_digest, name="endpoint_digest")

    evaluated = terminal in {
        "BRANCH_INFORMATION_ACCEPTED",
        "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE_DUE_TO_POWER",
    }
    expected_model = MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST if evaluated else None
    expected_baseline = (
        MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST if evaluated else None
    )
    observed_model = _require_digest_or_none(
        categorical_identity.get("accepted_model_artifact_digest"),
        name="accepted_model_artifact_digest",
    )
    observed_baseline = _require_digest_or_none(
        categorical_identity.get("baseline_artifact_digest"),
        name="baseline_artifact_digest",
    )
    observed_baseline_source = _require_digest_or_none(
        categorical_identity.get("baseline_source_model_artifact_digest"),
        name="baseline_source_model_artifact_digest",
    )
    if (
        observed_model != expected_model
        or observed_baseline != expected_baseline
        or observed_baseline_source is not None
    ):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_model_or_baseline_identity_mismatch"
        )
    terminal_fields.update(
        {
            "accepted_model_artifact_digest": expected_model,
            "baseline_artifact_digest": expected_baseline,
            "baseline_source_model_artifact_digest": None,
        }
    )
    return terminal, terminal_fields


def build_marginal_static_branch_decision(
    *,
    categorical_identity: Mapping[str, Any],
    producer_execution_id: str,
    parent_digests: Sequence[str],
) -> M4V2BranchDecisionArtifact:
    """Adopt only an already-registered categorical Marginal gate identity."""

    terminal, terminal_fields = _validate_categorical_identity(
        categorical_identity
    )
    producer_execution_id = _require_digest_or_none(
        producer_execution_id, name="producer_execution_id"
    )
    assert producer_execution_id is not None
    return M4V2BranchDecisionArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id=MARGINAL_STATIC_BRANCH_ID,
        estimand_digest=MARGINAL_STATIC_ESTIMAND_DIGEST,
        decision_path=MARGINAL_STATIC_DECISION_PATH,
        terminal_decision=terminal,
        producer_task_key=MARGINAL_STATIC_DECISION_TASK_KEY,
        producer_execution_id=producer_execution_id,
        parent_digests=tuple(parent_digests),
        **terminal_fields,
    )


def validate_marginal_static_branch_decision(
    value: Mapping[str, Any] | M4V2BranchDecisionArtifact,
) -> M4V2BranchDecisionArtifact:
    """Validate the shared envelope plus every Marginal-specific fixed field."""

    artifact = (
        value
        if isinstance(value, M4V2BranchDecisionArtifact)
        else M4V2BranchDecisionArtifact.from_dict(
            _mapping(value, name="marginal_static_branch_decision")
        )
    )
    body = artifact.to_body()
    fixed = {
        "measurement_contract_key": M4_V2_MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": MARGINAL_STATIC_BRANCH_ID,
        "estimand_digest": MARGINAL_STATIC_ESTIMAND_DIGEST,
        "decision_path": MARGINAL_STATIC_DECISION_PATH,
        "producer_task_key": MARGINAL_STATIC_DECISION_TASK_KEY,
    }
    if any(body.get(key) != item for key, item in fixed.items()):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_branch_decision_fixed_identity_mismatch"
        )
    terminal = body["terminal_decision"]
    expected = _TERMINAL_FIELDS.get(terminal)
    if expected is None or any(body.get(key) != item for key, item in expected.items()):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_branch_decision_terminal_mapping_mismatch"
        )
    evaluated = terminal in {
        "BRANCH_INFORMATION_ACCEPTED",
        "NO_DETECTABLE_INFORMATION",
        "INCONCLUSIVE_DUE_TO_POWER",
    }
    expected_model = MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST if evaluated else None
    expected_baseline = (
        MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST if evaluated else None
    )
    if (
        body.get("accepted_model_artifact_digest") != expected_model
        or body.get("baseline_artifact_digest") != expected_baseline
        or body.get("baseline_source_model_artifact_digest") is not None
    ):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_branch_decision_model_mapping_mismatch"
        )
    return artifact


def build_marginal_static_branch_decision_replay(
    *,
    decision: Mapping[str, Any] | M4V2BranchDecisionArtifact,
    source_contract_digest: str,
    decision_registration_digest: str,
    decision_producer_execution_artifact_digest: str,
    replay_execution_id: str,
) -> M4V2BranchDecisionReplayArtifact:
    """Construct the read-only four-parent replay of a registered Decision."""

    decision_artifact = validate_marginal_static_branch_decision(decision)
    source_contract_digest = _require_digest_or_none(
        source_contract_digest, name="source_contract_digest"
    )
    decision_registration_digest = _require_digest_or_none(
        decision_registration_digest, name="decision_registration_digest"
    )
    decision_producer_execution_artifact_digest = _require_digest_or_none(
        decision_producer_execution_artifact_digest,
        name="decision_producer_execution_artifact_digest",
    )
    replay_execution_id = _require_digest_or_none(
        replay_execution_id, name="replay_execution_id"
    )
    assert source_contract_digest is not None
    assert decision_registration_digest is not None
    assert decision_producer_execution_artifact_digest is not None
    assert replay_execution_id is not None
    return M4V2BranchDecisionReplayArtifact(
        measurement_contract_key=M4_V2_MEASUREMENT_CONTRACT_KEY,
        measurement_contract_digest=M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        branch_id=MARGINAL_STATIC_BRANCH_ID,
        decision_artifact_digest=decision_artifact.artifact_digest,
        decision_registration_digest=decision_registration_digest,
        decision_producer_task_key=MARGINAL_STATIC_DECISION_TASK_KEY,
        decision_producer_execution_id=decision_artifact.producer_execution_id,
        replay_task_key=MARGINAL_STATIC_REPLAY_TASK_KEY,
        replay_execution_id=replay_execution_id,
        replay_status="REGISTERED_REPLAY_VERIFIED",
        source_integrity_verified=True,
        registered_content_verified=True,
        workload_rerun=False,
        parent_digests=(
            source_contract_digest,
            decision_artifact.artifact_digest,
            decision_registration_digest,
            decision_producer_execution_artifact_digest,
        ),
    )


def validate_marginal_static_branch_decision_replay(
    value: Mapping[str, Any] | M4V2BranchDecisionReplayArtifact,
    *,
    decision: Mapping[str, Any] | M4V2BranchDecisionArtifact | None = None,
) -> M4V2BranchDecisionReplayArtifact:
    """Validate a registered replay and optionally bind it to its Decision."""

    artifact = (
        value
        if isinstance(value, M4V2BranchDecisionReplayArtifact)
        else M4V2BranchDecisionReplayArtifact.from_dict(
            _mapping(value, name="marginal_static_branch_decision_replay")
        )
    )
    body = artifact.to_body()
    fixed = {
        "measurement_contract_key": M4_V2_MEASUREMENT_CONTRACT_KEY,
        "measurement_contract_digest": M4_V2_MEASUREMENT_CONTRACT_DIGEST,
        "branch_id": MARGINAL_STATIC_BRANCH_ID,
        "decision_producer_task_key": MARGINAL_STATIC_DECISION_TASK_KEY,
        "replay_task_key": MARGINAL_STATIC_REPLAY_TASK_KEY,
        "replay_status": "REGISTERED_REPLAY_VERIFIED",
        "source_integrity_verified": True,
        "registered_content_verified": True,
        "workload_rerun": False,
    }
    if any(body.get(key) != item for key, item in fixed.items()):
        raise MarginalStaticBranchDecisionError(
            "marginal_static_branch_replay_fixed_identity_mismatch"
        )
    if decision is not None:
        decision_artifact = validate_marginal_static_branch_decision(decision)
        if (
            body["decision_artifact_digest"] != decision_artifact.artifact_digest
            or body["decision_producer_execution_id"]
            != decision_artifact.producer_execution_id
        ):
            raise MarginalStaticBranchDecisionError(
                "marginal_static_branch_replay_decision_identity_mismatch"
            )
    return artifact


__all__ = [
    "MARGINAL_STATIC_BASELINE_ARTIFACT_DIGEST",
    "MARGINAL_STATIC_BRANCH_ID",
    "MARGINAL_STATIC_DECISION_CAPABILITY",
    "MARGINAL_STATIC_DECISION_COMPLETION_FACT",
    "MARGINAL_STATIC_DECISION_PATH",
    "MARGINAL_STATIC_DECISION_TASK_KEY",
    "MARGINAL_STATIC_ESTIMAND_DIGEST",
    "MARGINAL_STATIC_GATE_ARTIFACT_DIGEST",
    "MARGINAL_STATIC_MODEL_ARTIFACT_DIGEST",
    "MARGINAL_STATIC_REPLAY_CAPABILITY",
    "MARGINAL_STATIC_REPLAY_COMPLETION_FACT",
    "MARGINAL_STATIC_REPLAY_TASK_KEY",
    "MARGINAL_STATIC_REPLAY_VERIFIED_FACT",
    "MARGINAL_STATIC_TERMINAL_FACT",
    "MarginalStaticBranchDecisionError",
    "build_marginal_static_branch_decision",
    "build_marginal_static_branch_decision_replay",
    "validate_marginal_static_branch_decision",
    "validate_marginal_static_branch_decision_replay",
]
