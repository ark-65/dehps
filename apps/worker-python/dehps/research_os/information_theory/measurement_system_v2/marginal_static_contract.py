from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy
from .preflight_execution import (
    MARGINAL_CONTRACT_FREEZE_TASK_KEY,
    PREFLIGHT_EXECUTION_PASS_FACT,
)

MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY = MARGINAL_CONTRACT_FREEZE_TASK_KEY
MARGINAL_STATIC_CONTRACT_FREEZE_CAPABILITY = (
    "m4_v2_marginal_static_measurement_contract_freeze"
)
MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT = (
    "m4-v2-marginal-static-measurement-contract-freeze:FROZEN"
)
MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY = (
    "m4-v2-marginal-static-measurement-fixture-freeze"
)
MARGINAL_STATIC_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-marginal-static-contract-freeze-source-v1.json"
)
MARGINAL_BRANCH_ID = "MARGINAL_STATIC"
ESTIMATOR_ID = "EXPANDING_LEGAL_MARGINAL_ALPHA_1"
NUMBER_COUNT = 33
DRAW_CARDINALITY = 6
UNIFORM_MARGINAL = Fraction(2, 11)
PRIOR_STRENGTH_ISSUES = 1
MINIMUM_TRAINING_ISSUES = 900


class MarginalStaticContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarginalStaticContractFreezeRun:
    measurement_contract: Mapping[str, Any]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.measurement_contract, self.completion)


def estimate_legal_marginals(
    number_event_counts: Sequence[int],
    *,
    training_issue_count: int,
) -> tuple[Fraction, ...]:
    if (
        isinstance(training_issue_count, bool)
        or not isinstance(training_issue_count, int)
        or training_issue_count < MINIMUM_TRAINING_ISSUES
        or len(number_event_counts) != NUMBER_COUNT
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > training_issue_count
            for value in number_event_counts
        )
        or sum(number_event_counts) != DRAW_CARDINALITY * training_issue_count
    ):
        raise MarginalStaticContractError(
            "marginal_static_estimator_input_invalid"
        )
    denominator = training_issue_count + PRIOR_STRENGTH_ISSUES
    probabilities = tuple(
        (Fraction(value) + UNIFORM_MARGINAL) / denominator
        for value in number_event_counts
    )
    if (
        sum(probabilities) != DRAW_CARDINALITY
        or any(value <= 0 or value >= 1 for value in probabilities)
    ):
        raise MarginalStaticContractError(
            "marginal_static_estimator_geometry_invalid"
        )
    return probabilities


def load_marginal_static_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarginalStaticContractError(
            f"marginal_static_source_contract_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-marginal-static-contract-freeze-source.v1"
        or payload.get("artifact_type")
        != "m4_v2_marginal_static_contract_freeze_source"
        or payload.get("contract_key")
        != "M4_V2_MARGINAL_STATIC_CONTRACT_FREEZE_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-marginal-static-contract-freeze-round-39-20260808"
        or payload.get("research_request_id") != 312
        or payload.get("research_execution_id") != 233
        or payload.get("result_blind") is not True
        or payload.get("formal_branch_execution_allowed") is not False
        or payload.get("synthetic_replicates") != 0
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or not entries
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.marginal-static-contract-freeze-source-set.v1",
        )
    ):
        raise MarginalStaticContractError(
            "marginal_static_source_contract_invalid"
        )
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise MarginalStaticContractError(
                "marginal_static_source_entry_invalid"
            )
        relative = str(entry.get("path") or "")
        digest = str(entry.get("content_sha256") or "")
        parsed = Path(relative)
        if (
            not relative
            or parsed.is_absolute()
            or ".." in parsed.parts
            or parsed.as_posix() != relative
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or relative in paths
        ):
            raise MarginalStaticContractError(
                "marginal_static_source_entry_invalid"
            )
        paths.add(relative)
    _validate_frozen_contract(frozen)
    return payload


def verify_marginal_static_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise MarginalStaticContractError(
                f"marginal_static_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise MarginalStaticContractError(
                f"marginal_static_source_modified:{relative}"
            )


def build_marginal_static_contract_artifacts(
    *,
    source_contract: Mapping[str, Any],
    measurement_contract_v2_digest: str,
    marginal_branch_design: Mapping[str, Any],
    preflight_execution_artifact_digest: str,
    marginal_branch_health: Mapping[str, Any],
    preflight_completion: Mapping[str, Any],
    legacy_marginal_decision: Mapping[str, Any],
    legacy_decision_replay: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> MarginalStaticContractFreezeRun:
    _validate_inputs(
        source_contract=source_contract,
        measurement_contract_v2_digest=measurement_contract_v2_digest,
        marginal_branch_design=marginal_branch_design,
        preflight_execution_artifact_digest=preflight_execution_artifact_digest,
        marginal_branch_health=marginal_branch_health,
        preflight_completion=preflight_completion,
        legacy_marginal_decision=legacy_marginal_decision,
        legacy_decision_replay=legacy_decision_replay,
    )
    frozen = source_contract["frozen_contract"]
    source_digest = str(source_contract["artifact_digest"])
    contract = _artifact(
        schema_version="dehps-m4-v2-marginal-static-measurement-contract.v1",
        artifact_type="m4_v2_marginal_static_measurement_contract",
        body={
            "status": "FROZEN_SYNTHETIC_HEALTH_PENDING",
            "branch_id": MARGINAL_BRANCH_ID,
            "measurement_contract_v2_digest": measurement_contract_v2_digest,
            "branch_design_digest": marginal_branch_design["artifact_digest"],
            "branch_estimand_digest": marginal_branch_design["estimand_digest"],
            "preflight_execution_artifact_digest": (
                preflight_execution_artifact_digest
            ),
            "identifiability_preflight_artifact_digest": (
                marginal_branch_health["artifact_digest"]
            ),
            "identifiability_preflight_status": "PASS",
            "estimator": json_compatible_copy(frozen["estimator"]),
            "score": json_compatible_copy(frozen["score"]),
            "model_artifact_contract": json_compatible_copy(
                frozen["model_artifact_contract"]
            ),
            "legacy_boundary": json_compatible_copy(frozen["legacy_boundary"]),
            "next_fixture_obligations": json_compatible_copy(
                frozen["next_fixture_obligations"]
            ),
            "legacy_marginal_decision_digest": legacy_marginal_decision[
                "artifact_digest"
            ],
            "legacy_decision_replay_digest": legacy_decision_replay[
                "artifact_digest"
            ],
            "legacy_measurement_health": "REPAIR",
            "legacy_repair_overridden": False,
            "accepted_for_downstream_baseline": False,
            "accepted_model_artifact_digest": None,
            "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
            "historical_execution_status": "NOT_AUTHORIZED",
            "synthetic_replicates": 0,
            "formal_branch_runs_executed": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            measurement_contract_v2_digest,
            str(marginal_branch_design["artifact_digest"]),
            preflight_execution_artifact_digest,
            str(marginal_branch_health["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
            str(legacy_marginal_decision["artifact_digest"]),
            str(legacy_decision_replay["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-measurement-contract.v1",
    )
    completion = _artifact(
        schema_version="dehps-m4-v2-marginal-static-contract-freeze-completion.v1",
        artifact_type="m4_v2_marginal_static_contract_freeze_completion",
        body={
            "status": "COMPLETE",
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "marginal_static_measurement_contract_digest": contract[
                "artifact_digest"
            ],
            "completion_fact": MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
            "branch_id": MARGINAL_BRANCH_ID,
            "estimator_id": ESTIMATOR_ID,
            "identifiability_preflight_status": "PASS",
            "legacy_measurement_health": "REPAIR",
            "legacy_repair_overridden": False,
            "accepted_model_artifact_digest": None,
            "sampled_synthetic_execution_status": "NOT_AUTHORIZED",
            "historical_execution_status": "NOT_AUTHORIZED",
            "synthetic_replicates": 0,
            "formal_branch_runs_executed": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            str(contract["artifact_digest"]),
            str(preflight_completion["artifact_digest"]),
            str(legacy_decision_replay["artifact_digest"]),
        ),
        domain="dehps.m4.v2.marginal-static-contract-freeze-completion.v1",
    )
    return MarginalStaticContractFreezeRun(
        measurement_contract=contract,
        completion=completion,
    )


def _validate_inputs(
    *,
    source_contract: Mapping[str, Any],
    measurement_contract_v2_digest: str,
    marginal_branch_design: Mapping[str, Any],
    preflight_execution_artifact_digest: str,
    marginal_branch_health: Mapping[str, Any],
    preflight_completion: Mapping[str, Any],
    legacy_marginal_decision: Mapping[str, Any],
    legacy_decision_replay: Mapping[str, Any],
) -> None:
    _validate_frozen_contract(source_contract.get("frozen_contract"))
    if (
        len(measurement_contract_v2_digest) != 64
        or len(preflight_execution_artifact_digest) != 64
        or marginal_branch_design.get("artifact_type")
        != "m4_v2_branch_identifiability_preflight_design"
        or marginal_branch_design.get("branch_id") != MARGINAL_BRANCH_ID
        or marginal_branch_design.get("status") != "FROZEN_DESIGN"
        or marginal_branch_design.get("historical_outcomes_read") is not False
        or marginal_branch_design.get("evidence_created") is not False
        or marginal_branch_health.get("artifact_type")
        != "m4_v2_branch_health_preflight_result"
        or marginal_branch_health.get("branch_id") != MARGINAL_BRANCH_ID
        or marginal_branch_health.get("status") != "PASS"
        or marginal_branch_health.get("measurement_health") != "PASS"
        or marginal_branch_health.get("decision_credit") is not False
        or marginal_branch_health.get("historical_evidence_eligible") is not False
        or marginal_branch_health.get("branch_design_digest")
        != marginal_branch_design.get("artifact_digest")
        or preflight_completion.get("artifact_type")
        != "m4_v2_branch_preflight_execution_completion"
        or preflight_completion.get("status") != "COMPLETE"
        or preflight_completion.get("all_branches_pass") is not True
        or preflight_completion.get("all_branches_pass_fact")
        != PREFLIGHT_EXECUTION_PASS_FACT
        or marginal_branch_health.get("artifact_digest")
        not in preflight_completion.get("branch_result_digests", [])
        or legacy_marginal_decision.get("artifact_type")
        != "marginal_measurement_acceptance_decision"
        or legacy_marginal_decision.get("branch_id") != MARGINAL_BRANCH_ID
        or legacy_marginal_decision.get("measurement_health") != "REPAIR"
        or legacy_marginal_decision.get("eligible_for_formal_branch_program")
        is not False
        or legacy_marginal_decision.get("historical_evidence") != "NOT_RUN"
        or legacy_marginal_decision.get("historical_run_status") != "NOT_RUN"
        or legacy_decision_replay.get("artifact_type")
        != "branch_decision_replay_attestation"
        or legacy_decision_replay.get("branch_id") != MARGINAL_BRANCH_ID
        or legacy_decision_replay.get("status") != "REPLAY_VERIFIED"
        or legacy_decision_replay.get("same_decision_content") is not True
        or legacy_decision_replay.get("decision_artifact_digest")
        != legacy_marginal_decision.get("artifact_digest")
    ):
        raise MarginalStaticContractError(
            "marginal_static_contract_input_identity_changed"
        )


def _validate_frozen_contract(frozen: Any) -> None:
    if not isinstance(frozen, Mapping):
        raise MarginalStaticContractError("marginal_static_contract_missing")
    estimator = frozen.get("estimator")
    score = frozen.get("score")
    model = frozen.get("model_artifact_contract")
    legacy = frozen.get("legacy_boundary")
    fixtures = frozen.get("next_fixture_obligations")
    if (
        not isinstance(estimator, Mapping)
        or estimator.get("branch_id") != MARGINAL_BRANCH_ID
        or estimator.get("estimator_id") != ESTIMATOR_ID
        or estimator.get("number_count") != NUMBER_COUNT
        or estimator.get("draw_cardinality") != DRAW_CARDINALITY
        or estimator.get("uniform_marginal") != "2/11"
        or estimator.get("prior_strength_issues_alpha")
        != PRIOR_STRENGTH_ISSUES
        or estimator.get("per_number_prior_event_count") != "2/11"
        or estimator.get("formula") != "q_i=(c_i+2/11)/(n+1)"
        or estimator.get("exact_sum_identity")
        != "sum_i q_i=(6*n+6)/(n+1)=6"
        or estimator.get("fit_window") != "expanding outer-train-only"
        or estimator.get("minimum_training_issues")
        != MINIMUM_TRAINING_ISSUES
        or estimator.get("history_features") != "forbidden"
        or estimator.get("target_issue_or_future_read") != "forbidden"
        or estimator.get("hyperparameter_search") != "none"
        or estimator.get("clipping") != "forbidden"
        or not isinstance(score, Mapping)
        or score.get("baseline_q_i") != "2/11"
        or score.get("unit") != "bits_per_issue"
        or score.get("geometry") != "SUM_33_BINARY_LOG_SCORES"
        or score.get("joint_information_claim") != "forbidden"
        or not isinstance(model, Mapping)
        or model.get("accepted_for_downstream_baseline_default") is not False
        or model.get("overwrite") != "forbidden"
        or model.get("same_inputs_require_same_digest") is not True
        or not isinstance(model.get("required_fields"), list)
        or len(model["required_fields"]) != 11
        or not isinstance(legacy, Mapping)
        or legacy.get("p2_6_1_measurement_health") != "REPAIR"
        or legacy.get("p2_6_1_formal_branch_program_eligible") is not False
        or legacy.get("p2_6_1_decision_is_overridden") is not False
        or legacy.get("historical_execution_allowed_after_contract_freeze")
        is not False
        or not isinstance(fixtures, Mapping)
        or fixtures.get("positive_control")
        != "V2_M1_GROUP_ODDS_2_STATIONARY"
        or len(fixtures.get("negative_controls", [])) != 3
        or fixtures.get("sampled_workload_is_frozen_in_this_round") is not False
        or fixtures.get("historical_data_is_allowed") is not False
        or frozen.get("completion_fact")
        != MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT
        or frozen.get("next_consumer") != MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    ):
        raise MarginalStaticContractError("marginal_static_contract_invalid")


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
        **json_compatible_copy(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload
