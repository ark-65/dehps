from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from dehps.contracts import canonical_digest

from .contracts import (
    BRANCH_IDS,
    MeasurementContractV2,
    MeasurementContractV2Error,
)


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CHECK_VALUES = {"PASS", "FAIL", "NOT_EVALUATED"}
_MEASUREMENT_RUN_VALUES = {"COMPLETE", "INCOMPLETE", "NOT_RUN"}
_HISTORICAL_RUN_VALUES = {"COMPLETE", "INCOMPLETE", "NOT_RUN"}
_PREFLIGHT_VALUES = {"PASS", "FAIL", "UNRESOLVED"}


def compile_hierarchical_gate(
    contract: MeasurementContractV2,
    *,
    branch_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compile branch-local health separately from historical evidence.

    The function is pure and consumes only explicit typed reports. It neither
    reads experiment paths nor performs model fitting.
    """

    reports = _validated_reports(contract, branch_reports)
    gate_contract = contract.payload["gate_compiler_contract"]
    validity_checks = tuple(gate_contract["validity_checks"])
    acceptance_checks = tuple(gate_contract["measurement_acceptance_checks"])
    health: dict[str, str] = {}
    baseline_ready: dict[str, bool] = {}
    baseline_reasons: dict[str, str | None] = {}
    accepted_for_downstream: dict[str, bool] = {}
    effective_historical_run: dict[str, str] = {}
    p_values: dict[str, float] = {}

    for branch_id in BRANCH_IDS:
        report = reports[branch_id]
        ready, reason = _baseline_dependency_status(
            branch_id,
            reports=reports,
            health=health,
            accepted_for_downstream=accepted_for_downstream,
        )
        baseline_ready[branch_id] = ready
        baseline_reasons[branch_id] = reason
        checks = report["measurement_checks"]
        measurement_run = report["measurement_run_status"]
        preflight_status = report["identifiability_preflight_status"]
        validity_failed = any(checks[key] == "FAIL" for key in validity_checks)
        acceptance_failed = any(
            checks[key] == "FAIL" for key in acceptance_checks
        )
        not_evaluated = any(
            checks[key] == "NOT_EVALUATED"
            for key in (*validity_checks, *acceptance_checks)
        )
        if preflight_status == "FAIL" or validity_failed or (
            measurement_run == "COMPLETE" and acceptance_failed
        ):
            health[branch_id] = "REPAIR"
        elif (
            preflight_status == "UNRESOLVED"
            or not ready
            or measurement_run != "COMPLETE"
            or not_evaluated
        ):
            health[branch_id] = "INCONCLUSIVE"
        elif acceptance_failed:
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} reports an acceptance FAIL before completion",
            )
        else:
            health[branch_id] = "PASS"

        accepted_for_downstream[branch_id] = (
            health[branch_id] == "PASS"
            and report["accepted_for_downstream_baseline"] is True
            and report.get("accepted_model_artifact_digest") is not None
        )
        reported_historical_run = report["historical_run_status"]
        effective_historical_run[branch_id] = (
            "NOT_RUN"
            if preflight_status != "PASS" or not ready
            else reported_historical_run
        )
        p_value = report.get("primary_p_value")
        if (
            effective_historical_run[branch_id] == "COMPLETE"
            and health[branch_id] == "PASS"
            and report.get("endpoint_digest") is not None
            and report.get("accepted_model_artifact_digest") is not None
            and report.get("accepted_model_artifact_digest")
            != report.get("baseline_artifact_digest")
            and p_value is not None
            and report.get("statistical_input_contract_digest")
            == contract.statistical_input_digest()
            and isinstance(
                report.get("effect_interval_bits_per_issue"),
                Mapping,
            )
            and report.get("interval_provenance_artifact_digest")
            is not None
            and report.get("interval_source_endpoint_digest")
            == report.get("endpoint_digest")
        ):
            if (
                isinstance(p_value, bool)
                or not isinstance(p_value, (int, float))
                or not 0 <= float(p_value) <= 1
            ):
                raise MeasurementContractV2Error(
                    "measurement_v2_gate_input_invalid",
                    f"{branch_id} requires one canonical primary p-value",
                )
            p_values[branch_id] = float(p_value)
        else:
            p_values[branch_id] = 1.0

    adjusted = _holm_adjusted(p_values)
    threshold = float(
        gate_contract["practical_threshold_bits_per_issue"]
    )
    alpha = float(gate_contract["multiplicity"]["familywise_alpha"])
    confidence = float(gate_contract["simultaneous_confidence_level"])
    evidence: dict[str, str] = {}
    branch_outputs: list[dict[str, Any]] = []

    for branch_id in BRANCH_IDS:
        report = reports[branch_id]
        historical_run = effective_historical_run[branch_id]
        if historical_run == "NOT_RUN":
            evidence_value = "NOT_RUN"
        elif historical_run != "COMPLETE" or health[branch_id] != "PASS":
            evidence_value = "INCONCLUSIVE"
        elif (
            report.get("endpoint_digest") is None
            or report.get("accepted_model_artifact_digest") is None
            or report.get("accepted_model_artifact_digest")
            == report.get("baseline_artifact_digest")
            or report.get("primary_p_value") is None
            or report.get("statistical_input_contract_digest")
            != contract.statistical_input_digest()
            or report.get("interval_provenance_artifact_digest") is None
            or report.get("interval_source_endpoint_digest")
            != report.get("endpoint_digest")
        ):
            evidence_value = "INCONCLUSIVE"
        else:
            interval = report.get("effect_interval_bits_per_issue")
            if interval is None:
                evidence_value = "INCONCLUSIVE"
            else:
                if not isinstance(interval, Mapping):
                    raise MeasurementContractV2Error(
                        "measurement_v2_gate_input_invalid",
                        f"{branch_id} effect interval must be an object",
                    )
                lower = _finite_number(
                    interval.get("lower"),
                    field="interval lower",
                )
                upper = _finite_number(
                    interval.get("upper"),
                    field="interval upper",
                )
                if (
                    lower > upper
                    or interval.get("simultaneous_confidence_level")
                    != confidence
                ):
                    raise MeasurementContractV2Error(
                        "measurement_v2_gate_input_invalid",
                        f"{branch_id} effect interval is invalid",
                    )
                raw_equivalence_upper = report.get(
                    "equivalence_upper_bound_bits_per_issue"
                )
                equivalence_upper = (
                    None
                    if raw_equivalence_upper is None
                    else _finite_number(
                        raw_equivalence_upper,
                        field=(
                            "equivalence_upper_bound_bits_per_issue"
                        ),
                    )
                )
                if (
                    equivalence_upper is not None
                    and not lower <= equivalence_upper <= upper
                ):
                    raise MeasurementContractV2Error(
                        "measurement_v2_gate_input_invalid",
                        f"{branch_id} equivalence upper bound contradicts "
                        "the two-sided interval",
                    )
                positive = (
                    adjusted[branch_id] <= alpha and lower > threshold
                )
                if positive:
                    evidence_value = "POSITIVE"
                else:
                    raw_mde = report.get("mde_bits_per_issue")
                    negative_inputs_ready = (
                        adjusted[branch_id] > alpha
                        and report.get("equivalence_power_sufficient") is True
                        and raw_mde is not None
                        and report.get("mde_provenance_artifact_digest")
                        is not None
                        and report.get(
                            "equivalence_power_artifact_digest"
                        )
                        is not None
                        and report.get(
                            "equivalence_upper_bound_bits_per_issue"
                        )
                        is not None
                        and report.get(
                            "equivalence_upper_bound_provenance_artifact_digest"
                        )
                        is not None
                        and report.get(
                            "equivalence_source_endpoint_digest"
                        )
                        == report.get("endpoint_digest")
                    )
                    if not negative_inputs_ready:
                        evidence_value = "INCONCLUSIVE"
                    else:
                        mde = _finite_number(
                            raw_mde,
                            field="mde_bits_per_issue",
                        )
                        if mde < 0:
                            raise MeasurementContractV2Error(
                                "measurement_v2_gate_input_invalid",
                                f"{branch_id} MDE must be nonnegative",
                            )
                        assert equivalence_upper is not None
                        evidence_value = (
                            "NEGATIVE"
                            if (
                                mde <= threshold
                                and equivalence_upper <= threshold
                            )
                            else "INCONCLUSIVE"
                        )
        evidence[branch_id] = evidence_value
        normalized_report = _normalized_branch_report(report)
        branch_report_digest = canonical_digest(
            normalized_report,
            domain="dehps.m4.measurement-v2.branch-report.v1",
        )
        branch_outputs.append(
            {
                "branch_id": branch_id,
                "branch_report_digest": branch_report_digest,
                "estimand_digest": contract.estimand_digest(branch_id),
                "measurement_run_status": report[
                    "measurement_run_status"
                ],
                "measurement_checks": dict(report["measurement_checks"]),
                "measurement_health": health[branch_id],
                "historical_evidence": evidence_value,
                "historical_run_status": historical_run,
                "reported_historical_run_status": report[
                    "historical_run_status"
                ],
                "identifiability_preflight_status": report[
                    "identifiability_preflight_status"
                ],
                "identifiability_preflight_artifact_digest": report.get(
                    "identifiability_preflight_artifact_digest"
                ),
                "primary_p_value": (
                    None
                    if report.get("primary_p_value") is None
                    else float(report["primary_p_value"])
                ),
                "holm_adjusted_p_value": adjusted[branch_id],
                "endpoint_digest": report.get("endpoint_digest"),
                "accepted_model_artifact_digest": report.get(
                    "accepted_model_artifact_digest"
                ),
                "accepted_for_downstream_baseline": (
                    accepted_for_downstream[branch_id]
                ),
                "baseline_artifact_digest": report.get(
                    "baseline_artifact_digest"
                ),
                "baseline_source_model_artifact_digest": report.get(
                    "baseline_source_model_artifact_digest"
                ),
                "baseline_dependency_ready": baseline_ready[branch_id],
                "baseline_dependency_reason": baseline_reasons[branch_id],
                "statistical_input_contract_digest": report.get(
                    "statistical_input_contract_digest"
                ),
                "effect_interval_bits_per_issue": normalized_report[
                    "effect_interval_bits_per_issue"
                ],
                "interval_provenance_artifact_digest": report.get(
                    "interval_provenance_artifact_digest"
                ),
                "interval_source_endpoint_digest": report.get(
                    "interval_source_endpoint_digest"
                ),
                "mde_bits_per_issue": report.get(
                    "mde_bits_per_issue"
                ),
                "mde_provenance_artifact_digest": report.get(
                    "mde_provenance_artifact_digest"
                ),
                "equivalence_power_sufficient": report.get(
                    "equivalence_power_sufficient"
                ),
                "equivalence_power_artifact_digest": report.get(
                    "equivalence_power_artifact_digest"
                ),
                "equivalence_upper_bound_bits_per_issue": report.get(
                    "equivalence_upper_bound_bits_per_issue"
                ),
                "equivalence_upper_bound_provenance_artifact_digest": (
                    report.get(
                        "equivalence_upper_bound_provenance_artifact_digest"
                    )
                ),
                "equivalence_source_endpoint_digest": report.get(
                    "equivalence_source_endpoint_digest"
                ),
            }
        )

    coverage = (
        "FULL"
        if all(health[item] == "PASS" for item in BRANCH_IDS)
        and all(
            effective_historical_run[item] == "COMPLETE"
            for item in BRANCH_IDS
        )
        else "PARTIAL"
    )
    if any(evidence[item] == "POSITIVE" for item in BRANCH_IDS):
        global_evidence = "CANDIDATE_INFORMATION_FOUND"
    elif coverage == "FULL" and all(
        evidence[item] == "NEGATIVE" for item in BRANCH_IDS
    ):
        global_evidence = "NO_DETECTABLE_INFORMATION"
    else:
        global_evidence = "INCONCLUSIVE"

    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-measurement-gate-compiler-output.v2",
        "artifact_type": "hierarchical_measurement_gate_output",
        "artifact_digest": "",
        "contract_digest": contract.artifact_digest,
        "required_branch_ids": list(BRANCH_IDS),
        "branch_outputs": branch_outputs,
        "global_coverage": coverage,
        "global_evidence": global_evidence,
        "repair_branches": [
            item for item in BRANCH_IDS if health[item] == "REPAIR"
        ],
        "inconclusive_branches": [
            item
            for item in BRANCH_IDS
            if health[item] == "INCONCLUSIVE"
            or evidence[item] == "INCONCLUSIVE"
        ],
        "candidate_branches": [
            item for item in BRANCH_IDS if evidence[item] == "POSITIVE"
        ],
        "multiplicity_method": "HOLM",
        "familywise_alpha": alpha,
        "practical_threshold_bits_per_issue": threshold,
        "production_action": "none",
        "promotion_gate_opened": False,
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.measurement-v2.gate-output.v1",
    )
    return payload


def _validated_reports(
    contract: MeasurementContractV2,
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if len(reports) != len(BRANCH_IDS):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_input_invalid",
            "the fixed primary family requires exactly three branch reports",
        )
    by_id: dict[str, Mapping[str, Any]] = {}
    endpoint_digests: list[str] = []
    gate_contract = contract.payload["gate_compiler_contract"]
    required_checks = (
        *gate_contract["validity_checks"],
        *gate_contract["measurement_acceptance_checks"],
    )
    for report in reports:
        if not isinstance(report, Mapping):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                "branch report must be an object",
            )
        branch_id = str(report.get("branch_id") or "")
        if branch_id not in BRANCH_IDS or branch_id in by_id:
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"unknown or duplicate branch report: {branch_id}",
            )
        if report.get("estimand_digest") != contract.estimand_digest(branch_id):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} estimand digest changed",
            )
        checks = report.get("measurement_checks")
        if (
            not isinstance(checks, Mapping)
            or set(checks) != set(required_checks)
            or any(value not in _CHECK_VALUES for value in checks.values())
        ):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} measurement checks are incomplete",
            )
        if report.get("measurement_run_status") not in _MEASUREMENT_RUN_VALUES:
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} measurement run status is invalid",
            )
        if report.get("historical_run_status") not in _HISTORICAL_RUN_VALUES:
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} historical run status is invalid",
            )
        preflight_status = report.get("identifiability_preflight_status")
        if preflight_status not in _PREFLIGHT_VALUES:
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} identifiability preflight status is invalid",
            )
        preflight_digest = _optional_digest(
            report.get("identifiability_preflight_artifact_digest"),
            branch_id=branch_id,
            field="identifiability_preflight_artifact_digest",
        )
        if (
            preflight_status in {"PASS", "FAIL"}
            and preflight_digest is None
        ) or (
            preflight_status == "UNRESOLVED"
            and preflight_digest is not None
        ):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} preflight provenance does not match its status",
            )
        if not isinstance(
            report.get("accepted_for_downstream_baseline"),
            bool,
        ):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} downstream baseline acceptance must be boolean",
            )
        for digest_field in (
            "accepted_model_artifact_digest",
            "baseline_artifact_digest",
            "baseline_source_model_artifact_digest",
            "statistical_input_contract_digest",
            "interval_provenance_artifact_digest",
            "interval_source_endpoint_digest",
            "mde_provenance_artifact_digest",
            "equivalence_power_artifact_digest",
            "equivalence_upper_bound_provenance_artifact_digest",
            "equivalence_source_endpoint_digest",
        ):
            _optional_digest(
                report.get(digest_field),
                branch_id=branch_id,
                field=digest_field,
            )
        endpoint = _optional_digest(
            report.get("endpoint_digest"),
            branch_id=branch_id,
            field="endpoint_digest",
        )
        if endpoint is not None:
            endpoint_digests.append(endpoint)
        p_value = report.get("primary_p_value")
        if p_value is not None and (
            isinstance(p_value, bool)
            or not isinstance(p_value, (int, float))
            or not 0 <= float(p_value) <= 1
        ):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} primary p-value is invalid",
            )
        effect_interval = report.get("effect_interval_bits_per_issue")
        if effect_interval is not None and not isinstance(
            effect_interval,
            Mapping,
        ):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} effect interval must be an object",
            )
        raw_mde = report.get("mde_bits_per_issue")
        if raw_mde is not None:
            mde = _finite_number(raw_mde, field="mde_bits_per_issue")
            if mde < 0:
                raise MeasurementContractV2Error(
                    "measurement_v2_gate_input_invalid",
                    f"{branch_id} MDE must be nonnegative",
                )
        equivalence_power = report.get("equivalence_power_sufficient")
        if equivalence_power is not None and not isinstance(
            equivalence_power,
            bool,
        ):
            raise MeasurementContractV2Error(
                "measurement_v2_gate_input_invalid",
                f"{branch_id} equivalence power flag must be boolean",
            )
        equivalence_upper = report.get(
            "equivalence_upper_bound_bits_per_issue"
        )
        if equivalence_upper is not None:
            _finite_number(
                equivalence_upper,
                field="equivalence_upper_bound_bits_per_issue",
            )
        by_id[branch_id] = report
    if set(by_id) != set(BRANCH_IDS):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_input_invalid",
            "every required branch must appear exactly once",
        )
    if len(endpoint_digests) != len(set(endpoint_digests)):
        raise MeasurementContractV2Error(
            "measurement_v2_duplicate_endpoint_credit",
            "one endpoint digest cannot receive primary credit in two branches",
        )
    return by_id


def _normalized_branch_report(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    fields = (
        "branch_id",
        "estimand_digest",
        "measurement_run_status",
        "historical_run_status",
        "identifiability_preflight_status",
        "identifiability_preflight_artifact_digest",
        "accepted_for_downstream_baseline",
        "accepted_model_artifact_digest",
        "baseline_artifact_digest",
        "baseline_source_model_artifact_digest",
        "endpoint_digest",
        "primary_p_value",
        "statistical_input_contract_digest",
        "effect_interval_bits_per_issue",
        "interval_provenance_artifact_digest",
        "interval_source_endpoint_digest",
        "mde_bits_per_issue",
        "mde_provenance_artifact_digest",
        "equivalence_power_sufficient",
        "equivalence_power_artifact_digest",
        "equivalence_upper_bound_bits_per_issue",
        "equivalence_upper_bound_provenance_artifact_digest",
        "equivalence_source_endpoint_digest",
    )
    normalized = {field: report.get(field) for field in fields}
    normalized["measurement_checks"] = dict(report["measurement_checks"])
    interval = report.get("effect_interval_bits_per_issue")
    normalized["effect_interval_bits_per_issue"] = (
        None if interval is None else dict(interval)
    )
    return normalized


def _baseline_dependency_status(
    branch_id: str,
    *,
    reports: Mapping[str, Mapping[str, Any]],
    health: Mapping[str, str],
    accepted_for_downstream: Mapping[str, bool],
) -> tuple[bool, str | None]:
    report = reports[branch_id]
    baseline_digest = report.get("baseline_artifact_digest")
    source_digest = report.get("baseline_source_model_artifact_digest")
    if baseline_digest is None:
        return False, "MISSING_BASELINE_ARTIFACT"
    if branch_id == BRANCH_IDS[0]:
        if source_digest is not None:
            return False, "LEVEL_ONE_BASELINE_MUST_NOT_HAVE_PARENT"
        return True, None

    index = BRANCH_IDS.index(branch_id)
    parent_id = BRANCH_IDS[index - 1]
    parent = reports[parent_id]
    parent_model_digest = parent.get("accepted_model_artifact_digest")
    if (
        health.get(parent_id) != "PASS"
        or accepted_for_downstream.get(parent_id) is not True
        or parent_model_digest is None
    ):
        return False, "UPSTREAM_BASELINE_NOT_ACCEPTED"
    if source_digest != parent_model_digest:
        return False, "BASELINE_SOURCE_MODEL_MISMATCH"
    if branch_id == BRANCH_IDS[1]:
        if baseline_digest != parent_model_digest:
            return False, "DIRECT_BASELINE_ARTIFACT_MISMATCH"
        return True, None
    if baseline_digest == parent_model_digest:
        return False, "DERIVED_JOINT_BASELINE_IDENTITY_REQUIRED"
    return True, None


def _optional_digest(
    value: Any,
    *,
    branch_id: str,
    field: str,
) -> str | None:
    if value is None:
        return None
    normalized = str(value)
    if not _DIGEST.fullmatch(normalized):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_input_invalid",
            f"{branch_id} {field} is invalid",
        )
    return normalized


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


def _finite_number(value: Any, *, field: str) -> float:
    from math import isfinite

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_input_invalid",
            f"{field} must be numeric",
        )
    number = float(value)
    if not isfinite(number):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_input_invalid",
            f"{field} must be finite",
        )
    return number
