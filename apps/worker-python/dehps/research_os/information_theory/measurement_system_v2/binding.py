from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2.compatibility import (
    P263_EXECUTION_ID,
    P263_TASK_DIGEST,
)

P261_MARGINAL_BINDING_CONTRACT_PATH = Path(
    "configs/research-os/m4-p2-6-1-marginal-binding-contract-v1.json"
)
MARGINAL_BRANCH_ID = "MARGINAL_STATIC"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class P261MarginalBindingError(RuntimeError):
    pass


@dataclass(frozen=True)
class P261MarginalBindingContract:
    payload: Mapping[str, Any]
    artifact_digest: str


def load_p261_marginal_binding_contract(
    path: Path,
) -> P261MarginalBindingContract:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P261MarginalBindingError(
            f"p261_marginal_binding_contract_invalid: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise P261MarginalBindingError(
            "p261_marginal_binding_contract_invalid: root must be an object"
        )
    expected_identity = (
        "dehps-m4-p2-6-1-marginal-binding-contract.v1",
        "p261_marginal_binding_contract",
        "P261MarginalBindingContract.v1",
        "1.0.0",
        "FROZEN_RESULT_BLIND",
    )
    actual_identity = (
        payload.get("schema_version"),
        payload.get("artifact_type"),
        payload.get("contract_key"),
        payload.get("semantic_version"),
        payload.get("status"),
    )
    if actual_identity != expected_identity:
        raise P261MarginalBindingError(
            "p261_marginal_binding_contract_invalid: identity changed"
        )
    digest = str(payload.get("artifact_digest") or "")
    if not _DIGEST.fullmatch(digest) or config_digest(payload) != digest:
        raise P261MarginalBindingError(
            "p261_marginal_binding_contract_invalid: digest changed"
        )
    blind = payload.get("result_blind_freeze")
    if not isinstance(blind, dict) or any(blind.values()):
        raise P261MarginalBindingError(
            "p261_marginal_binding_contract_invalid: result-blind freeze changed"
        )
    if (
        payload.get("historical_evidence") != "NOT_RUN"
        or payload.get("failure_mapping") != "INCONCLUSIVE"
        or payload.get("promotion_gate_opened") is not False
        or payload.get("production_action") != "none"
        or payload.get("decision_mapping")
        != {
            "PASS_TO_P3": "PASS",
            "REPAIR_MEASUREMENT_SYSTEM": "REPAIR",
        }
    ):
        raise P261MarginalBindingError(
            "p261_marginal_binding_contract_invalid: decision boundary changed"
        )
    sources = payload.get("source_identities")
    allowlist = payload.get("input_allowlist")
    if not isinstance(sources, dict) or not isinstance(allowlist, dict):
        raise P261MarginalBindingError(
            "p261_marginal_binding_contract_invalid: source or allowlist missing"
        )
    for field in (
        "measurement_contract_v2_digest",
        "p2_6_1_task_digest",
        "p2_6_1_execution_id",
        "p2_6_1_measurement_validation_manifest_digest",
    ):
        if not _DIGEST.fullmatch(str(sources.get(field) or "")):
            raise P261MarginalBindingError(
                f"p261_marginal_binding_contract_invalid: {field} changed"
            )
    for key in ("p2_6_1_raw_replay", "p2_7_gate_replay"):
        fields = allowlist.get(key)
        if (
            not isinstance(fields, list)
            or not fields
            or len(fields) != len(set(fields))
            or not all(isinstance(item, str) and item for item in fields)
        ):
            raise P261MarginalBindingError(
                f"p261_marginal_binding_contract_invalid: {key} allowlist changed"
            )
    return P261MarginalBindingContract(payload=payload, artifact_digest=digest)


def bind_p261_marginal_acceptance(
    contract: P261MarginalBindingContract,
    *,
    raw_replay: Mapping[str, Any] | None,
    gate_replay: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Bind replayed synthetic acceptance to health, never historical evidence."""

    failures: list[str] = []
    sources = contract.payload["source_identities"]
    raw = _allowlisted_input(
        raw_replay,
        allowed=contract.payload["input_allowlist"]["p2_6_1_raw_replay"],
        missing_failure="missing_or_nonterminal_raw_execution",
        failures=failures,
    )
    gate = _allowlisted_input(
        gate_replay,
        allowed=contract.payload["input_allowlist"]["p2_7_gate_replay"],
        missing_failure="missing_partial_or_unverified_p2_7_replay",
        failures=failures,
    )

    if raw:
        if raw.get("status") != "REPLAY_VERIFIED":
            failures.append("raw_execution_replay_not_verified")
        expected_raw = {
            "task_key": sources["p2_6_1_task_key"],
            "task_digest": P263_TASK_DIGEST,
            "execution_id": P263_EXECUTION_ID,
            "measurement_validation_manifest_digest": sources[
                "p2_6_1_measurement_validation_manifest_digest"
            ],
        }
        if any(raw.get(key) != value for key, value in expected_raw.items()):
            failures.append("task_execution_or_manifest_identity_drift")
        if (
            raw.get("same_execution_identity") is not True
            or raw.get("same_artifact_identity") is not True
            or raw.get("manual_input_assembly") is not False
        ):
            failures.append("raw_execution_replay_not_verified")
        for field in (
            "execution_artifact_digest",
            "completion_artifact_digest",
            "completion_event_digest",
        ):
            if not _DIGEST.fullmatch(str(raw.get(field) or "")):
                failures.append("missing_or_nonterminal_raw_execution")
                break

    if gate:
        if gate.get("status") != "REPLAY_VERIFIED":
            failures.append("missing_partial_or_unverified_p2_7_replay")
        if gate.get("task_key") != sources["p2_7_task_key"]:
            failures.append("missing_partial_or_unverified_p2_7_replay")
        if raw and (
            gate.get("parent_p2_6_1_execution_id") != raw.get("execution_id")
            or gate.get("parent_p2_6_1_execution_artifact_digest")
            != raw.get("execution_artifact_digest")
        ):
            failures.append("wrong_p2_6_1_parent")
        if (
            gate.get("same_execution_identity") is not True
            or gate.get("same_artifact_identity") is not True
            or gate.get("manual_input_assembly") is not False
        ):
            failures.append("missing_partial_or_unverified_p2_7_replay")
        for field in (
            "execution_artifact_digest",
            "automatic_gate_digest",
        ):
            if not _DIGEST.fullmatch(str(gate.get(field) or "")):
                failures.append("missing_partial_or_unverified_p2_7_replay")
                break

    decision = None if not gate else gate.get("decision")
    mapping = contract.payload["decision_mapping"]
    if not failures and decision not in mapping:
        failures.append("unrecognized_gate_decision")
    measurement_health = (
        "INCONCLUSIVE" if failures else str(mapping[str(decision)])
    )
    eligibility = contract.payload["formal_branch_program_eligibility"]
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-marginal-measurement-acceptance-decision.v1",
        "artifact_type": "marginal_measurement_acceptance_decision",
        "artifact_digest": "",
        "binding_contract_digest": contract.artifact_digest,
        "measurement_contract_v2_digest": sources[
            "measurement_contract_v2_digest"
        ],
        "branch_id": MARGINAL_BRANCH_ID,
        "semantic_purpose": "MARGINAL_OUTPUT_MEASUREMENT_ACCEPTANCE_BASELINE",
        "measurement_health": measurement_health,
        "historical_evidence": "NOT_RUN",
        "historical_run_status": "NOT_RUN",
        "p2_6_1_execution_id": None if not raw else raw.get("execution_id"),
        "p2_6_1_execution_artifact_digest": (
            None if not raw else raw.get("execution_artifact_digest")
        ),
        "p2_7_execution_artifact_digest": (
            None if not gate else gate.get("execution_artifact_digest")
        ),
        "automatic_gate_digest": (
            None if not gate else gate.get("automatic_gate_digest")
        ),
        "source_gate_decision": decision,
        "source_gate_decision_fact": (
            None if not gate else gate.get("decision_fact")
        ),
        "failure_reasons": sorted(set(failures)),
        "eligible_for_formal_branch_program": bool(
            eligibility[measurement_health]
        ),
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "production_action": "none",
        "promotion_gate_opened": False,
        "parent_digests": [
            contract.artifact_digest,
            *(
                []
                if not raw
                else [str(raw.get("execution_artifact_digest") or "")]
            ),
            *(
                []
                if not gate
                else [str(gate.get("execution_artifact_digest") or "")]
            ),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p261-marginal-binding-decision.v1",
    )
    return payload


def build_branch_decision_replay_artifact(
    *,
    decision: Mapping[str, Any],
    reconstructed_decision: Mapping[str, Any],
) -> dict[str, Any]:
    if dict(decision) != dict(reconstructed_decision):
        raise P261MarginalBindingError(
            "p261_marginal_binding_replay_failed: decision content changed"
        )
    digest = str(decision.get("artifact_digest") or "")
    if not _DIGEST.fullmatch(digest):
        raise P261MarginalBindingError(
            "p261_marginal_binding_replay_failed: decision digest missing"
        )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-branch-decision-replay-artifact.v1",
        "artifact_type": "branch_decision_replay_attestation",
        "artifact_digest": "",
        "branch_id": decision.get("branch_id"),
        "decision_artifact_digest": digest,
        "status": "REPLAY_VERIFIED",
        "same_decision_content": True,
        "historical_evidence": decision.get("historical_evidence"),
        "promotion_gate_opened": False,
        "parent_digests": [digest],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.branch-decision-replay.v1",
    )
    return payload


def _allowlisted_input(
    value: Mapping[str, Any] | None,
    *,
    allowed: list[str],
    missing_failure: str,
    failures: list[str],
) -> dict[str, Any]:
    if value is None or not isinstance(value, Mapping):
        failures.append(missing_failure)
        return {}
    unexpected = set(value).difference(allowed)
    if unexpected:
        failures.append("input_contains_non_allowlisted_fields")
    return {key: value[key] for key in allowed if key in value}
