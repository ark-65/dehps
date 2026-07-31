from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.measurement_validation import (
    locate_truth_artifacts,
)
from dehps.research_os.information_theory.walk_forward.feature_view import (
    FEATURE_MANIFEST_DIGEST,
    FEATURE_NAMES,
)

from .contracts import IdentifiabilityPreflightManifest

IDENTIFIABLE_FACT = (
    "m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_IDENTIFIABLE"
)
REPAIR_REQUIRED_FACT = (
    "m4-p2-identifiability-decision:MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
)
REPORT_SCHEMA = "dehps-m4-p2-identifiability-preflight-report.v1"
REPORT_DIGEST_DOMAIN = "dehps.m4-p2.identifiability-preflight-report.v1"


@dataclass(frozen=True)
class IdentifiabilityPreflightRun:
    report: Mapping[str, Any]
    decision_fact: str


def _scenario_row(
    truth: Mapping[str, Any],
    *,
    comparison_tolerance_bits: float,
    epsilon_bits: float,
    state_representable: bool,
) -> dict[str, Any]:
    joint = float(truth["joint_draw_information_bits_per_issue"])
    marginal = float(
        truth["composite_number_event_information_bits_per_issue"]
    )
    gap = joint - marginal
    failures: list[str] = []
    if joint > epsilon_bits and abs(marginal) <= epsilon_bits:
        failures.append("NOT_IDENTIFIABLE_BY_CURRENT_METRIC")
    if abs(gap) > comparison_tolerance_bits:
        failures.append("TRUTH_METRIC_ESTIMAND_MISMATCH")
    if not state_representable:
        failures.append("STATE_NOT_EXPOSED_TO_PROBE")
    return {
        "scenario_id": str(truth["scenario_id"]),
        "mechanism": str(truth["mechanism"]),
        "truth_artifact_digest": str(truth["artifact_digest"]),
        "joint_information_bits_per_issue": joint,
        "composite_marginal_information_bits_per_issue": marginal,
        "joint_minus_marginal_bits_per_issue": gap,
        "joint_signal": "PASS" if joint > epsilon_bits else "NO_SIGNAL",
        "current_metric_oracle_signal": (
            "PASS" if marginal > epsilon_bits else "FAIL"
        ),
        "conditioning_state_representable": state_representable,
        "classifications": failures or ["IDENTIFIABLE_BY_CURRENT_CONTRACT"],
        "decision": "FAIL" if failures else "PASS",
    }


def run_identifiability_preflight(
    *,
    manifest: IdentifiabilityPreflightManifest,
    root_dir: Path,
    execution_id: str,
    git_commit: str,
) -> IdentifiabilityPreflightRun:
    truths = locate_truth_artifacts(
        root_dir,
        required_digests=manifest.truth_artifact_digests,
    )
    state_feature_names = {
        "state",
        "state_id",
        "prior_state",
        "mechanism_state",
        "latent_state",
    }
    state_representable = bool(set(FEATURE_NAMES) & state_feature_names)
    rows = tuple(
        _scenario_row(
            truths[scenario_id],
            comparison_tolerance_bits=(
                manifest.comparison_tolerance_bits
            ),
            epsilon_bits=manifest.joint_signal_epsilon_bits,
            state_representable=state_representable,
        )
        for scenario_id in sorted(truths)
    )
    failures = sorted({
        classification
        for row in rows
        for classification in row["classifications"]
        if classification != "IDENTIFIABLE_BY_CURRENT_CONTRACT"
    })
    decision = (
        "MEASUREMENT_CONTRACT_REPAIR_REQUIRED"
        if failures
        else "MEASUREMENT_CONTRACT_IDENTIFIABLE"
    )
    decision_fact = (
        REPAIR_REQUIRED_FACT
        if failures
        else IDENTIFIABLE_FACT
    )
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA,
        "artifact_type": "measurement_identifiability_preflight_report",
        "artifact_digest": "",
        "phase": "M4-P2.6-PREFLIGHT",
        "status": "COMPLETE",
        "execution_id": execution_id,
        "manifest_digest": manifest.artifact_digest,
        "truth_estimand": "I(Y_vector; state)",
        "current_metric_estimand": "sum_n I(Y_n; state)",
        "feature_manifest_digest": FEATURE_MANIFEST_DIGEST,
        "feature_names": list(FEATURE_NAMES),
        "conditioning_state_representable": state_representable,
        "comparison_tolerance_bits": (
            manifest.comparison_tolerance_bits
        ),
        "scenario_count": len(rows),
        "scenarios": list(rows),
        "failed_classifications": failures,
        "decision": decision,
        "decision_fact": decision_fact,
        "approved_repair_strategy": (
            manifest.approved_repair_strategy
        ),
        "p2_6_partial_statistical_results_inspected": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "eligible_for_p2_gate": False,
        "production_impact": "none",
        "git_commit": git_commit,
        "parent_digests": [
            manifest.artifact_digest,
            *manifest.truth_artifact_digests,
            FEATURE_MANIFEST_DIGEST,
        ],
    }
    identity = dict(report)
    identity.pop("artifact_digest")
    report["artifact_digest"] = canonical_digest(
        identity,
        domain=REPORT_DIGEST_DOMAIN,
    )
    return IdentifiabilityPreflightRun(
        report=report,
        decision_fact=decision_fact,
    )
