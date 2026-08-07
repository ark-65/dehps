from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import exp, log
from pathlib import Path
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest

from .contracts import json_compatible_copy
from .fixture_freeze import (
    FIXTURE_FREEZE_COMPLETION_FACT,
    LEGAL_NUMBER_COUNT,
    NUMBER_MARGINAL,
    FixtureFreezeError,
    _composite_binary_gain,
    _group_fixture,
    _is2_joint_residual_truth,
    _is3_joint_residual_truth,
    _is4_joint_gain,
    _solve_maxent,
)

PREFLIGHT_EXECUTION_TASK_KEY = (
    "m4-v2-branch-identifiability-preflight-execution"
)
PREFLIGHT_EXECUTION_CAPABILITY = (
    "m4_v2_branch_identifiability_preflight_execution"
)
PREFLIGHT_EXECUTION_COMPLETION_FACT = (
    "m4-v2-branch-identifiability-preflight-execution:EXECUTED"
)
PREFLIGHT_EXECUTION_PASS_FACT = (
    "m4-v2-branch-identifiability-preflight-execution:ALL_BRANCHES_PASS"
)
MARGINAL_CONTRACT_FREEZE_TASK_KEY = (
    "m4-v2-marginal-static-measurement-contract-freeze"
)
PREFLIGHT_EXECUTION_SOURCE_CONTRACT_PATH = Path(
    "configs/research-os/m4-v2-branch-preflight-execution-source-contract-v1.json"
)

BRANCH_ORDER = (
    "MARGINAL_STATIC",
    "TEMPORAL_MARGINAL_INCREMENT",
    "JOINT_RESIDUAL_INCREMENT",
)
CONTROL_ORDER = (
    "V2_M1_GROUP_ODDS_2_STATIONARY",
    "V2_T1_OVERLAP_ODDS_2_MARKOV",
    "V2_J1_HISTORY_IS4_LAMBDA_HALF",
    "NULL_UNIFORM_LEGAL_SIX_OF_33",
)
EXPECTED_POSITIVE = {
    "MARGINAL_STATIC": "V2_M1_GROUP_ODDS_2_STATIONARY",
    "TEMPORAL_MARGINAL_INCREMENT": "V2_T1_OVERLAP_ODDS_2_MARKOV",
    "JOINT_RESIDUAL_INCREMENT": "V2_J1_HISTORY_IS4_LAMBDA_HALF",
}


class PreflightExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreflightExecutionRun:
    solver_result: Mapping[str, Any]
    orthogonal_result: Mapping[str, Any]
    legacy_result: Mapping[str, Any]
    branch_results: tuple[Mapping[str, Any], ...]
    completion: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (
            self.solver_result,
            self.orthogonal_result,
            self.legacy_result,
            *self.branch_results,
            self.completion,
        )

    @property
    def all_branches_pass(self) -> bool:
        return all(item.get("status") == "PASS" for item in self.branch_results)


def load_preflight_execution_source_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightExecutionError(
            f"preflight_execution_source_contract_unreadable:{path}"
        ) from exc
    entries = payload.get("source_entries") if isinstance(payload, dict) else None
    dependencies = (
        payload.get("source_dependencies") if isinstance(payload, dict) else None
    )
    frozen = payload.get("frozen_contract") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version")
        != "dehps-m4-v2-branch-preflight-execution-source-contract.v1"
        or payload.get("artifact_type")
        != "m4_v2_branch_preflight_execution_source_contract"
        or payload.get("contract_key")
        != "M4_V2_BRANCH_PREFLIGHT_EXECUTION_SOURCE"
        or payload.get("research_request_key")
        != "research-m4-v2-branch-preflight-execution-round-38-20260807"
        or payload.get("research_request_id") != 309
        or payload.get("research_execution_id") != 230
        or payload.get("result_blind") is not True
        or payload.get("formal_branch_execution_allowed") is not False
        or payload.get("historical_outcomes_read") is not False
        or payload.get("statistical_results_read") is not False
        or payload.get("monte_carlo_replicates") != 0
        or payload.get("evidence_created") is not False
        or payload.get("production_action") != "none"
        or not isinstance(entries, list)
        or not entries
        or dependencies
        != {
            "fixture_freeze_source_contract_digest": (
                "391acc6a04518389f841e94a640a14dcaf98bd2c36614d31a0e713446980b06d"
            )
        }
        or not isinstance(frozen, dict)
        or payload.get("artifact_digest") != config_digest(payload)
        or payload.get("source_set_digest")
        != canonical_digest(
            entries,
            domain="dehps.m4.v2.branch-preflight-execution-source-set.v1",
        )
    ):
        raise PreflightExecutionError(
            "preflight_execution_source_contract_invalid"
        )
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise PreflightExecutionError(
                "preflight_execution_source_entry_invalid"
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
            raise PreflightExecutionError(
                "preflight_execution_source_entry_invalid"
            )
        paths.add(relative)
    _validate_frozen_contract(frozen)
    return payload


def verify_preflight_execution_source_bytes(
    *,
    root_dir: Path,
    contract: Mapping[str, Any],
) -> None:
    root = root_dir.resolve()
    for entry in contract["source_entries"]:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise PreflightExecutionError(
                f"preflight_execution_source_missing:{relative}"
            )
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["content_sha256"]:
            raise PreflightExecutionError(
                f"preflight_execution_source_modified:{relative}"
            )


def build_preflight_execution_artifacts(
    *,
    source_contract: Mapping[str, Any],
    fixture_execution_artifact_digest: str,
    solver_fixture: Mapping[str, Any],
    orthogonal_fixture: Mapping[str, Any],
    legacy_fixture: Mapping[str, Any],
    fixture_completion: Mapping[str, Any],
    branch_designs: Sequence[Mapping[str, Any]],
    cross_branch_design: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> PreflightExecutionRun:
    _validate_inputs(
        source_contract=source_contract,
        fixture_execution_artifact_digest=fixture_execution_artifact_digest,
        solver_fixture=solver_fixture,
        orthogonal_fixture=orthogonal_fixture,
        legacy_fixture=legacy_fixture,
        fixture_completion=fixture_completion,
        branch_designs=branch_designs,
        cross_branch_design=cross_branch_design,
    )
    frozen = source_contract["frozen_contract"]
    source_digest = str(source_contract["artifact_digest"])
    fixture_digest = str(fixture_completion["artifact_digest"])
    solver = _artifact(
        schema_version="dehps-m4-v2-joint-solver-preflight-result.v1",
        artifact_type="m4_v2_joint_solver_preflight_result",
        body=_run_solver_preflight(
            solver_fixture=solver_fixture,
            frozen=frozen,
        ),
        parent_digests=(
            source_digest,
            fixture_execution_artifact_digest,
            str(solver_fixture["artifact_digest"]),
            fixture_digest,
        ),
        domain="dehps.m4.v2.joint-solver-preflight-result.v1",
    )
    orthogonal = _artifact(
        schema_version="dehps-m4-v2-orthogonal-endpoint-preflight-result.v1",
        artifact_type="m4_v2_orthogonal_endpoint_preflight_result",
        body=_run_orthogonal_preflight(
            orthogonal_fixture=orthogonal_fixture,
            frozen=frozen,
        ),
        parent_digests=(
            source_digest,
            fixture_execution_artifact_digest,
            str(orthogonal_fixture["artifact_digest"]),
            str(solver["artifact_digest"]),
            fixture_digest,
        ),
        domain="dehps.m4.v2.orthogonal-endpoint-preflight-result.v1",
    )
    legacy = _artifact(
        schema_version="dehps-m4-v2-legacy-role-preflight-result.v1",
        artifact_type="m4_v2_legacy_role_preflight_result",
        body=_run_legacy_preflight(
            legacy_fixture=legacy_fixture,
            frozen=frozen,
        ),
        parent_digests=(
            source_digest,
            fixture_execution_artifact_digest,
            str(legacy_fixture["artifact_digest"]),
            str(solver["artifact_digest"]),
            fixture_digest,
        ),
        domain="dehps.m4.v2.legacy-role-preflight-result.v1",
    )
    design_by_branch = {
        str(item["branch_id"]): item for item in branch_designs
    }
    branch_results = tuple(
        _branch_result(
            branch_id=branch_id,
            source_digest=source_digest,
            branch_design=design_by_branch[branch_id],
            cross_branch_design=cross_branch_design,
            solver_result=solver,
            orthogonal_result=orthogonal,
            legacy_result=legacy,
        )
        for branch_id in BRANCH_ORDER
    )
    all_pass = all(item["status"] == "PASS" for item in branch_results)
    overall_status = _overall_status(branch_results)
    completion = _artifact(
        schema_version="dehps-m4-v2-branch-preflight-execution-completion.v1",
        artifact_type="m4_v2_branch_preflight_execution_completion",
        body={
            "status": "COMPLETE",
            "preflight_status": overall_status,
            "all_branches_pass": all_pass,
            "execution_id": execution_id,
            "git_commit": git_commit,
            "source_contract_digest": source_digest,
            "fixture_execution_artifact_digest": (
                fixture_execution_artifact_digest
            ),
            "solver_result_digest": solver["artifact_digest"],
            "orthogonal_result_digest": orthogonal["artifact_digest"],
            "legacy_result_digest": legacy["artifact_digest"],
            "branch_result_digests": [
                item["artifact_digest"] for item in branch_results
            ],
            "branch_statuses": {
                str(item["branch_id"]): str(item["status"])
                for item in branch_results
            },
            "preflight_branch_result_count": 3,
            "solver_fixture_group_count": 4,
            "orthogonal_endpoint_count": 12,
            "legacy_state_result_count": 4,
            "completion_fact": PREFLIGHT_EXECUTION_COMPLETION_FACT,
            "all_branches_pass_fact": (
                PREFLIGHT_EXECUTION_PASS_FACT if all_pass else None
            ),
            "formal_branch_runs_executed": 0,
            "actual_fold_count": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "p2_6_3_statistical_results_read": False,
            "monte_carlo_replicates": 0,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "next_consumer": (
                MARGINAL_CONTRACT_FREEZE_TASK_KEY if all_pass else None
            ),
            "production_action": "none",
        },
        parent_digests=(
            source_digest,
            fixture_execution_artifact_digest,
            fixture_digest,
            str(cross_branch_design["artifact_digest"]),
            str(solver["artifact_digest"]),
            str(orthogonal["artifact_digest"]),
            str(legacy["artifact_digest"]),
            *(str(item["artifact_digest"]) for item in branch_results),
        ),
        domain="dehps.m4.v2.branch-preflight-execution-completion.v1",
    )
    return PreflightExecutionRun(
        solver_result=solver,
        orthogonal_result=orthogonal,
        legacy_result=legacy,
        branch_results=branch_results,
        completion=completion,
    )


def _run_solver_preflight(
    *,
    solver_fixture: Mapping[str, Any],
    frozen: Mapping[str, Any],
) -> dict[str, Any]:
    acceptance = frozen["solver_acceptance"]
    fixture_by_id = {
        str(item["fixture_id"]): item
        for item in solver_fixture["exact_solver_fixtures"]
    }
    valid_specs = (
        (
            "JME_UNIFORM",
            tuple(NUMBER_MARGINAL for _ in range(LEGAL_NUMBER_COUNT)),
            np.zeros(LEGAL_NUMBER_COUNT, dtype=np.float64),
        ),
        (
            "JME_GROUP_16_17_ODDS_2",
            tuple(
                Fraction(fixture_by_id["JME_GROUP_16_17_ODDS_2"][key])
                for key in (
                    *("expected_q_group_a" for _ in range(16)),
                    *("expected_q_group_b" for _ in range(17)),
                )
            ),
            np.asarray(
                [log(2.0)] * 16 + [0.0] * 17,
                dtype=np.float64,
            ),
        ),
        (
            "JME_OVERLAP_6_27_ODDS_2",
            tuple(
                Fraction(fixture_by_id["JME_OVERLAP_6_27_ODDS_2"][key])
                for key in (
                    *("expected_q_in_prior" for _ in range(6)),
                    *("expected_q_outside_prior" for _ in range(27)),
                )
            ),
            np.asarray(
                [log(2.0)] * 6 + [0.0] * 27,
                dtype=np.float64,
            ),
        ),
    )
    valid_results: list[dict[str, Any]] = []
    solved: dict[str, tuple[np.ndarray, float, tuple[Fraction, ...]]] = {}
    unresolved_reason: str | None = None
    for fixture_id, target, expected_theta in valid_specs:
        expected_partition = float(fixture_by_id[fixture_id]["expected_partition"])
        try:
            theta, log_partition, residual = _solve_maxent(target)
        except FixtureFreezeError as exc:
            unresolved_reason = f"{fixture_id}:{exc}"
            valid_results.append(
                {
                    "fixture_id": fixture_id,
                    "status": "UNRESOLVED",
                    "error": str(exc),
                }
            )
            continue
        parameter_error = float(np.max(np.abs(theta - expected_theta)))
        partition = exp(log_partition)
        partition_error = abs(partition - expected_partition) / expected_partition
        passed = (
            residual <= acceptance["maximum_marginal_residual"]
            and parameter_error
            <= acceptance["maximum_gauge_parameter_absolute_error"]
            and partition_error
            <= acceptance["maximum_partition_relative_error"]
            and theta[-1] == 0.0
        )
        valid_results.append(
            {
                "fixture_id": fixture_id,
                "status": "PASS" if passed else "FAIL",
                "maximum_marginal_residual": residual,
                "maximum_gauge_parameter_absolute_error": parameter_error,
                "partition_relative_error": partition_error,
                "gauge_lambda_33": float(theta[-1]),
                "fallback_used": False,
            }
        )
        solved[fixture_id] = (theta, log_partition, target)

    invalid_results = _invalid_solver_results()
    permutation = _permutation_result(
        solved.get("JME_GROUP_16_17_ODDS_2"),
        acceptance=acceptance,
    )
    if unresolved_reason is not None or permutation["status"] == "UNRESOLVED":
        status = "UNRESOLVED"
    elif all(item["status"] == "PASS" for item in valid_results) and all(
        item["status"] == "PASS" for item in invalid_results
    ) and permutation["status"] == "PASS":
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "status": status,
        "measurement_health": (
            "PASS"
            if status == "PASS"
            else "FAIL"
            if status == "FAIL"
            else "INCONCLUSIVE"
        ),
        "valid_fixture_results": valid_results,
        "invalid_boundary_results": invalid_results,
        "permutation_equivariance_result": permutation,
        "valid_fixture_count": 3,
        "invalid_boundary_case_count": 5,
        "fallback_used": False,
        "historical_outcomes_read": False,
        "statistical_results_read": False,
        "evidence_created": False,
        "production_action": "none",
    }


def _invalid_solver_results() -> list[dict[str, Any]]:
    p = float(NUMBER_MARGINAL)
    cases: list[tuple[str, np.ndarray]] = []
    sum_mismatch = np.full(LEGAL_NUMBER_COUNT, p, dtype=np.float64)
    sum_mismatch[0] += 1e-8
    cases.append(("SUM_MISMATCH_PLUS_1E_8", sum_mismatch))
    lower = np.full(LEGAL_NUMBER_COUNT, p, dtype=np.float64)
    lower[0] = 0.0
    lower[1] += p
    cases.append(("SUM_PRESERVING_Q_1_ZERO", lower))
    upper = np.full(LEGAL_NUMBER_COUNT, p, dtype=np.float64)
    upper[0] = 1.0
    upper[1:] -= (1.0 - p) / (LEGAL_NUMBER_COUNT - 1)
    cases.append(("SUM_PRESERVING_Q_1_ONE", upper))
    nan_case = np.full(LEGAL_NUMBER_COUNT, p, dtype=np.float64)
    nan_case[0] = np.nan
    cases.append(("Q_1_NAN", nan_case))
    infinity = np.full(LEGAL_NUMBER_COUNT, p, dtype=np.float64)
    infinity[0] = np.inf
    cases.append(("Q_1_POSITIVE_INFINITY", infinity))
    results: list[dict[str, Any]] = []
    for case_id, target in cases:
        error: str | None = None
        try:
            _solve_maxent(target)
        except FixtureFreezeError as exc:
            error = str(exc)
        passed = error == "fixture_freeze_solver_input_invalid"
        results.append(
            {
                "case_id": case_id,
                "status": "PASS" if passed else "FAIL",
                "typed_error": error,
                "substituted_distribution": False,
            }
        )
    return results


def _permutation_result(
    original: tuple[np.ndarray, float, tuple[Fraction, ...]] | None,
    *,
    acceptance: Mapping[str, Any],
) -> dict[str, Any]:
    if original is None:
        return {
            "status": "UNRESOLVED",
            "permutation": "swap_1_17_keep_33",
            "error": "source_fixture_not_solved",
        }
    theta, log_partition, target = original
    permutation = np.arange(LEGAL_NUMBER_COUNT)
    permutation[0], permutation[16] = permutation[16], permutation[0]
    permuted_target = tuple(target[index] for index in permutation)
    try:
        permuted_theta, permuted_log_partition, residual = _solve_maxent(
            permuted_target
        )
    except FixtureFreezeError as exc:
        return {
            "status": "UNRESOLVED",
            "permutation": "swap_1_17_keep_33",
            "error": str(exc),
        }
    expected_theta = theta[permutation]
    parameter_error = float(np.max(np.abs(permuted_theta - expected_theta)))
    partition_error = abs(permuted_log_partition - log_partition)
    original_score = float(
        np.dot(np.asarray(target, dtype=np.float64), theta) - log_partition
    )
    permuted_score = float(
        np.dot(
            np.asarray(permuted_target, dtype=np.float64),
            permuted_theta,
        )
        - permuted_log_partition
    )
    score_error = abs(permuted_score - original_score)
    passed = (
        residual <= acceptance["permutation_maximum_marginal_error"]
        and parameter_error
        <= acceptance["permutation_maximum_gauge_parameter_error"]
        and partition_error <= acceptance["permutation_maximum_log_partition_error"]
        and score_error <= acceptance["permutation_maximum_log_partition_error"]
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "permutation": "swap_1_17_keep_33",
        "maximum_marginal_residual": residual,
        "maximum_gauge_parameter_error": parameter_error,
        "log_partition_error": partition_error,
        "score_error": score_error,
    }


def _run_orthogonal_preflight(
    *,
    orthogonal_fixture: Mapping[str, Any],
    frozen: Mapping[str, Any],
) -> dict[str, Any]:
    acceptance = frozen["endpoint_acceptance"]
    observed = _computed_orthogonal_matrix()
    fixture_by_id = {
        str(item["fixture_id"]): item for item in orthogonal_fixture["fixtures"]
    }
    endpoint_results: list[dict[str, Any]] = []
    for fixture_id in CONTROL_ORDER:
        fixture = fixture_by_id[fixture_id]
        for branch_id in BRANCH_ORDER:
            truth_key = {
                "MARGINAL_STATIC": "marginal_static",
                "TEMPORAL_MARGINAL_INCREMENT": "temporal_increment",
                "JOINT_RESIDUAL_INCREMENT": "joint_residual",
            }[branch_id]
            observed_gain = float(observed[fixture_id][branch_id])
            truth_anchor = float(fixture["truth_anchor_bits"][truth_key])
            role = str(fixture["expected_roles"][branch_id])
            anchor_error = abs(observed_gain - truth_anchor)
            if role == "POSITIVE_CONTROL":
                passed = (
                    observed_gain >= acceptance["positive_floor_bits"]
                    and anchor_error
                    <= acceptance["maximum_truth_anchor_absolute_error"]
                )
            elif role == "NEGATIVE_CONTROL":
                passed = (
                    abs(observed_gain)
                    <= acceptance["negative_absolute_tolerance_bits"]
                    and anchor_error
                    <= acceptance["maximum_truth_anchor_absolute_error"]
                )
            else:
                raise PreflightExecutionError(
                    f"preflight_execution_unknown_control_role:{role}"
                )
            endpoint_results.append(
                {
                    "endpoint_key": f"{fixture_id}:{branch_id}",
                    "fixture_id": fixture_id,
                    "branch_id": branch_id,
                    "expected_role": role,
                    "observed_gain_bits_per_issue": observed_gain,
                    "truth_anchor_bits_per_issue": truth_anchor,
                    "truth_anchor_absolute_error": anchor_error,
                    "status": "PASS" if passed else "FAIL",
                    "decision_credit": False,
                }
            )
    unique_keys = {str(item["endpoint_key"]) for item in endpoint_results}
    status = (
        "PASS"
        if len(endpoint_results) == len(unique_keys) == 12
        and all(item["status"] == "PASS" for item in endpoint_results)
        else "FAIL"
    )
    return {
        "status": status,
        "measurement_health": "PASS" if status == "PASS" else "FAIL",
        "endpoint_results": endpoint_results,
        "endpoint_count": 12,
        "unique_endpoint_count": len(unique_keys),
        "copied_truth_anchor_as_observed": False,
        "duplicate_credit_detected": False,
        "historical_outcomes_read": False,
        "statistical_results_read": False,
        "evidence_created": False,
        "production_action": "none",
    }


def _computed_orthogonal_matrix() -> dict[str, dict[str, float]]:
    _, group_q_a, group_q_b = _group_fixture(
        group_a_size=16,
        group_b_size=17,
        group_a_weight=Fraction(2),
        group_b_weight=Fraction(1),
    )
    _, overlap_q_in, overlap_q_out = _group_fixture(
        group_a_size=6,
        group_b_size=27,
        group_a_weight=Fraction(2),
        group_b_weight=Fraction(1),
    )
    marginal_gain = _composite_binary_gain(
        ((16, group_q_a), (17, group_q_b)),
        baseline=NUMBER_MARGINAL,
    )
    temporal_gain = _composite_binary_gain(
        ((6, overlap_q_in), (27, overlap_q_out)),
        baseline=NUMBER_MARGINAL,
    )
    joint_gain = _is4_joint_gain(Fraction(1, 2))
    return {
        "V2_M1_GROUP_ODDS_2_STATIONARY": {
            "MARGINAL_STATIC": marginal_gain,
            "TEMPORAL_MARGINAL_INCREMENT": 0.0,
            "JOINT_RESIDUAL_INCREMENT": 0.0,
        },
        "V2_T1_OVERLAP_ODDS_2_MARKOV": {
            "MARGINAL_STATIC": 0.0,
            "TEMPORAL_MARGINAL_INCREMENT": temporal_gain,
            "JOINT_RESIDUAL_INCREMENT": 0.0,
        },
        "V2_J1_HISTORY_IS4_LAMBDA_HALF": {
            "MARGINAL_STATIC": 0.0,
            "TEMPORAL_MARGINAL_INCREMENT": 0.0,
            "JOINT_RESIDUAL_INCREMENT": joint_gain,
        },
        "NULL_UNIFORM_LEGAL_SIX_OF_33": {
            "MARGINAL_STATIC": 0.0,
            "TEMPORAL_MARGINAL_INCREMENT": 0.0,
            "JOINT_RESIDUAL_INCREMENT": 0.0,
        },
    }


def _run_legacy_preflight(
    *,
    legacy_fixture: Mapping[str, Any],
    frozen: Mapping[str, Any],
) -> dict[str, Any]:
    acceptance = frozen["legacy_acceptance"]
    fixture_by_id = {
        str(item["fixture_id"]): item for item in legacy_fixture["fixtures"]
    }
    observed_by_id: dict[str, tuple[float, float]] = {}
    unresolved_reason: str | None = None
    try:
        observed_by_id["IS2_LOCAL_TEMPORAL_DELTA_QUARTER"] = (
            _is2_joint_residual_truth()
        )
        observed_by_id["IS3_PAIR_CONDITIONAL_QUARTER_BASE_RATE"] = (
            _is3_joint_residual_truth()
        )
    except FixtureFreezeError as exc:
        unresolved_reason = str(exc)
    fixture_results: list[dict[str, Any]] = []
    for fixture_id in (
        "IS2_LOCAL_TEMPORAL_DELTA_QUARTER",
        "IS3_PAIR_CONDITIONAL_QUARTER_BASE_RATE",
    ):
        fixture = fixture_by_id[fixture_id]
        observed_values = observed_by_id.get(fixture_id)
        if observed_values is None:
            fixture_results.append(
                {
                    "fixture_id": fixture_id,
                    "status": "UNRESOLVED",
                    "error": unresolved_reason,
                    "decision_credit": False,
                }
            )
            continue
        truth_values = tuple(
            float(value) for value in fixture["joint_residual_truth_by_state_bits"]
        )
        state_results = [
            {
                "state_index": index,
                "observed_joint_residual_bits": observed,
                "truth_anchor_bits": truth,
                "truth_anchor_absolute_error": abs(observed - truth),
                "status": (
                    "PASS"
                    if observed >= acceptance["minimum_positive_residual_bits"]
                    and abs(observed - truth)
                    <= acceptance["maximum_truth_anchor_absolute_error"]
                    else "FAIL"
                ),
            }
            for index, (observed, truth) in enumerate(
                zip(observed_values, truth_values, strict=True)
            )
        ]
        expected_role = str(fixture["role_after_successful_preflight"])
        role = expected_role if all(
            item["status"] == "PASS" for item in state_results
        ) else "UNRESOLVED"
        fixture_results.append(
            {
                "fixture_id": fixture_id,
                "status": (
                    "PASS"
                    if all(item["status"] == "PASS" for item in state_results)
                    else "FAIL"
                ),
                "state_results": state_results,
                "resolved_role": role,
                "expected_role": expected_role,
                "decision_credit": False,
            }
        )
    if any(item["status"] == "UNRESOLVED" for item in fixture_results):
        status = "UNRESOLVED"
    elif all(item["status"] == "PASS" for item in fixture_results):
        status = "PASS"
    else:
        status = "FAIL"
    return {
        "status": status,
        "measurement_health": (
            "PASS"
            if status == "PASS"
            else "FAIL"
            if status == "FAIL"
            else "INCONCLUSIVE"
        ),
        "fixture_results": fixture_results,
        "fixture_count": 2,
        "state_result_count": 4 if unresolved_reason is None else 0,
        "is3_decision_credit": False,
        "copied_truth_anchor_as_observed": False,
        "historical_outcomes_read": False,
        "statistical_results_read": False,
        "evidence_created": False,
        "production_action": "none",
    }


def _branch_result(
    *,
    branch_id: str,
    source_digest: str,
    branch_design: Mapping[str, Any],
    cross_branch_design: Mapping[str, Any],
    solver_result: Mapping[str, Any],
    orthogonal_result: Mapping[str, Any],
    legacy_result: Mapping[str, Any],
) -> dict[str, Any]:
    endpoints = [
        item
        for item in orthogonal_result["endpoint_results"]
        if item["branch_id"] == branch_id
    ]
    positive_id = EXPECTED_POSITIVE[branch_id]
    positive = next(item for item in endpoints if item["fixture_id"] == positive_id)
    negatives = [item for item in endpoints if item["fixture_id"] != positive_id]
    supporting = [str(solver_result["status"]), str(orthogonal_result["status"])]
    if branch_id == "JOINT_RESIDUAL_INCREMENT":
        supporting.append(str(legacy_result["status"]))
    if "UNRESOLVED" in supporting:
        status = "UNRESOLVED"
    elif (
        all(item == "PASS" for item in supporting)
        and positive["status"] == "PASS"
        and len(negatives) == 3
        and all(item["status"] == "PASS" for item in negatives)
    ):
        status = "PASS"
    else:
        status = "FAIL"
    parents = [
        source_digest,
        str(branch_design["artifact_digest"]),
        str(cross_branch_design["artifact_digest"]),
        str(solver_result["artifact_digest"]),
        str(orthogonal_result["artifact_digest"]),
    ]
    if branch_id == "JOINT_RESIDUAL_INCREMENT":
        parents.append(str(legacy_result["artifact_digest"]))
    return _artifact(
        schema_version="dehps-m4-v2-branch-health-preflight-result.v1",
        artifact_type="m4_v2_branch_health_preflight_result",
        body={
            "status": status,
            "identifiability_preflight_status": status,
            "measurement_health": (
                "PASS"
                if status == "PASS"
                else "FAIL"
                if status == "FAIL"
                else "INCONCLUSIVE"
            ),
            "branch_id": branch_id,
            "branch_order_index": BRANCH_ORDER.index(branch_id),
            "branch_design_digest": branch_design["artifact_digest"],
            "primary_endpoint_key": positive["endpoint_key"],
            "primary_positive_fixture_id": positive_id,
            "positive_endpoint_status": positive["status"],
            "negative_endpoint_keys": [item["endpoint_key"] for item in negatives],
            "negative_endpoint_count": len(negatives),
            "negative_endpoints_pass": all(
                item["status"] == "PASS" for item in negatives
            ),
            "solver_preflight_status": solver_result["status"],
            "orthogonal_endpoint_status": orthogonal_result["status"],
            "legacy_role_resolution_status": (
                legacy_result["status"]
                if branch_id == "JOINT_RESIDUAL_INCREMENT"
                else "NOT_APPLICABLE"
            ),
            "accepted_for_downstream_baseline": False,
            "accepted_model_artifact_digest": None,
            "decision_credit": False,
            "historical_evidence_eligible": False,
            "historical_outcomes_read": False,
            "statistical_results_read": False,
            "evidence_created": False,
            "production_action": "none",
        },
        parent_digests=tuple(parents),
        domain=f"dehps.m4.v2.branch-health-preflight-result.{branch_id}.v1",
    )


def _overall_status(branch_results: Sequence[Mapping[str, Any]]) -> str:
    statuses = [str(item["status"]) for item in branch_results]
    if statuses == ["PASS", "PASS", "PASS"]:
        return "ALL_BRANCHES_PASS"
    if "UNRESOLVED" in statuses:
        return "UNRESOLVED"
    return "FAIL"


def _validate_inputs(
    *,
    source_contract: Mapping[str, Any],
    fixture_execution_artifact_digest: str,
    solver_fixture: Mapping[str, Any],
    orthogonal_fixture: Mapping[str, Any],
    legacy_fixture: Mapping[str, Any],
    fixture_completion: Mapping[str, Any],
    branch_designs: Sequence[Mapping[str, Any]],
    cross_branch_design: Mapping[str, Any],
) -> None:
    _validate_frozen_contract(source_contract.get("frozen_contract"))
    if (
        len(fixture_execution_artifact_digest) != 64
        or solver_fixture.get("artifact_type")
        != "m4_v2_joint_maxent_fixture_contract"
        or solver_fixture.get("status") != "FROZEN_FIXTURES"
        or orthogonal_fixture.get("artifact_type")
        != "m4_v2_orthogonal_control_fixture_contract"
        or orthogonal_fixture.get("status") != "FROZEN_FIXTURES"
        or legacy_fixture.get("artifact_type")
        != "m4_v2_legacy_role_resolution_fixture_contract"
        or legacy_fixture.get("status") != "FROZEN_FIXTURES"
        or fixture_completion.get("artifact_type")
        != "m4_v2_branch_fixture_freeze_completion"
        or fixture_completion.get("status") != "COMPLETE"
        or fixture_completion.get("completion_fact")
        != FIXTURE_FREEZE_COMPLETION_FACT
        or fixture_completion.get("solver_fixture_contract_digest")
        != solver_fixture.get("artifact_digest")
        or fixture_completion.get("orthogonal_control_fixture_contract_digest")
        != orthogonal_fixture.get("artifact_digest")
        or fixture_completion.get(
            "legacy_role_resolution_fixture_contract_digest"
        )
        != legacy_fixture.get("artifact_digest")
        or len(branch_designs) != 3
        or tuple(item.get("branch_id") for item in branch_designs) != BRANCH_ORDER
        or tuple(item.get("branch_order_index") for item in branch_designs)
        != (0, 1, 2)
        or cross_branch_design.get("artifact_type")
        != "m4_v2_cross_branch_preflight_design"
        or cross_branch_design.get("required_branch_order") != list(BRANCH_ORDER)
        or cross_branch_design.get("branch_preflight_design_digests")
        != [item.get("artifact_digest") for item in branch_designs]
        or solver_fixture.get("historical_outcomes_read") is not False
        or orthogonal_fixture.get("historical_outcomes_read") is not False
        or legacy_fixture.get("historical_outcomes_read") is not False
        or fixture_completion.get("historical_outcomes_read") is not False
    ):
        raise PreflightExecutionError("preflight_execution_input_identity_changed")


def _validate_frozen_contract(frozen: Any) -> None:
    if not isinstance(frozen, Mapping):
        raise PreflightExecutionError("preflight_execution_contract_missing")
    solver = frozen.get("solver_acceptance")
    endpoint = frozen.get("endpoint_acceptance")
    legacy = frozen.get("legacy_acceptance")
    counts = frozen.get("artifact_counts")
    if (
        frozen.get("execution_kind")
        != "deterministic_analytic_fixture_execution"
        or frozen.get("branch_order") != list(BRANCH_ORDER)
        or frozen.get("control_order") != list(CONTROL_ORDER)
        or frozen.get("expected_positive_map") != EXPECTED_POSITIVE
        or not isinstance(solver, Mapping)
        or solver.get("maximum_marginal_residual") != 1e-12
        or solver.get("maximum_gauge_parameter_absolute_error") != 1e-9
        or solver.get("maximum_partition_relative_error") != 1e-10
        or solver.get("permutation_maximum_marginal_error") != 1e-12
        or solver.get("permutation_maximum_gauge_parameter_error") != 1e-9
        or solver.get("permutation_maximum_log_partition_error") != 1e-10
        or solver.get("invalid_boundary_case_count") != 5
        or solver.get("fallback_allowed") is not False
        or not isinstance(endpoint, Mapping)
        or endpoint.get("positive_floor_bits") != 0.001
        or endpoint.get("negative_absolute_tolerance_bits") != 1e-10
        or endpoint.get("maximum_truth_anchor_absolute_error") != 5e-13
        or endpoint.get("endpoint_count") != 12
        or not isinstance(legacy, Mapping)
        or legacy.get("minimum_positive_residual_bits") != 0.001
        or legacy.get("maximum_truth_anchor_absolute_error") != 5e-13
        or legacy.get("fixture_count") != 2
        or legacy.get("state_result_count") != 4
        or legacy.get("is3_decision_credit") is not False
        or counts
        != {
            "solver_result_artifacts": 1,
            "orthogonal_matrix_artifacts": 1,
            "legacy_role_result_artifacts": 1,
            "branch_health_result_artifacts": 3,
            "completion_artifacts": 1,
            "mainline_execution_artifacts": 1,
            "preflight_branch_result_count": 3,
        }
        or frozen.get("formal_branch_runs") != 0
        or frozen.get("monte_carlo_replicates") != 0
        or frozen.get("historical_outcomes_read") is not False
        or frozen.get("statistical_results_read") is not False
        or frozen.get("evidence_created") is not False
        or frozen.get("execution_completion_fact")
        != PREFLIGHT_EXECUTION_COMPLETION_FACT
        or frozen.get("overall_pass_fact") != PREFLIGHT_EXECUTION_PASS_FACT
        or frozen.get("next_consumer") != MARGINAL_CONTRACT_FREEZE_TASK_KEY
    ):
        raise PreflightExecutionError("preflight_execution_frozen_contract_drift")


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    json_body = json_compatible_copy(body)
    if not isinstance(json_body, dict):
        raise PreflightExecutionError("preflight_execution_artifact_body_invalid")
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **json_body,
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload
