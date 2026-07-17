from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.ranking_contract import STRICT_RANKING_CONTRACT, ShadowComparisonReport
from dehps.runtime_envelope import RuntimeEnvelopeV1
from dehps.scoring_kernel.contracts import (
    CandidateStore,
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    PackedWindowState,
    WeightMatrix,
)
from dehps.scoring_kernel.feature_abi_backend import kernel_result_payload_digest
from dehps.scoring_kernel.planner import KernelPlanner


SHADOW_PROTOCOL_VERSION = "scoring-kernel-shadow-evidence.v1"
SHADOW_GATE_VERSION = "scoring-kernel-shadow-promotion-gate.v1"
DEFAULT_PRODUCTION_LINES = ("static_100", "dynamic_kdj", "dynamic_kdj_near")
_CANDIDATE_IDENTITY_FIELDS = (
    "candidate_contract",
    "candidate_abi",
    "candidate_digest",
    "candidate_layout_digest",
    "candidate_package_digest",
    "candidate_abi_verification_id",
)


class ShadowEvidenceViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


@dataclass(frozen=True)
class ShadowOperationalEvidence:
    evaluation_status: str = "pending"
    evaluation_mismatch_count: int = 0
    restart_recovery_result: str = "pending"
    watchdog_result: str = "pending"

    def __post_init__(self) -> None:
        if self.evaluation_status not in {"pending", "passed", "failed"}:
            raise ValueError("evaluation_status must be pending, passed, or failed")
        if self.restart_recovery_result not in {"pending", "passed", "failed"}:
            raise ValueError("restart_recovery_result must be pending, passed, or failed")
        if self.watchdog_result not in {"pending", "passed", "failed"}:
            raise ValueError("watchdog_result must be pending, passed, or failed")
        if self.evaluation_mismatch_count < 0:
            raise ValueError("evaluation_mismatch_count must be non-negative")


def _mismatch_count(left: np.ndarray, right: np.ndarray) -> int:
    if left.shape != right.shape:
        raise ShadowEvidenceViolation(
            "shadow_result_shape_mismatch",
            "official and shadow result arrays must have identical shapes",
            official_shape=list(left.shape),
            shadow_shape=list(right.shape),
        )
    return int(np.count_nonzero(left != right))


def _maximum_absolute_difference(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise ShadowEvidenceViolation(
            "shadow_result_shape_mismatch",
            "official and shadow result arrays must have identical shapes",
            official_shape=list(left.shape),
            shadow_shape=list(right.shape),
        )
    if left.size == 0:
        return 0.0
    return float(np.max(np.abs(left.astype(np.float64) - right.astype(np.float64))))


def _result_digest(result: KernelResult) -> str:
    return kernel_result_payload_digest(
        target_scores=result.target_scores,
        exact_ranks=result.exact_ranks,
        top_candidate_ids=result.top_candidate_ids,
        top_scores=result.top_scores,
        red5_candidate_ids=result.red5_candidate_ids,
        red5_scores=result.red5_scores,
        red5_ranks=result.red5_ranks,
    )


def _candidate_identity(result: KernelResult) -> dict[str, str]:
    identity: dict[str, str] = {}
    for field in _CANDIDATE_IDENTITY_FIELDS:
        value = result.telemetry.get(field)
        if value is None or not str(value).strip():
            raise ShadowEvidenceViolation(
                "shadow_candidate_identity_missing",
                "both backends must emit complete Candidate ABI identity",
                backend=result.backend,
                field=field,
            )
        identity[field] = str(value)
    return identity


def _runtime_invariant(envelope: Mapping[str, Any]) -> dict[str, Any] | None:
    if not envelope:
        return None
    parsed = RuntimeEnvelopeV1.from_dict(envelope)
    return {
        "envelope_version": parsed.envelope_version,
        "artifact_type": parsed.artifact_type,
        "domain": parsed.domain,
        "state": parsed.state.value,
        "state_path": [state.value for state in parsed.state_path],
        "history_contract": parsed.history_contract.as_dict(),
        "history_snapshot_digest": parsed.history_snapshot_digest,
        "window_contract": parsed.window_contract.as_dict(),
        "window_artifact_digest": parsed.window_artifact_digest,
        "window_spec_digest": parsed.window_spec_digest,
        "candidate_contract": parsed.candidate_contract.as_dict(),
        "candidate_abi": parsed.candidate_abi,
        "candidate_digest": parsed.candidate_digest,
        "candidate_layout_digest": parsed.candidate_layout_digest,
        "candidate_package_digest": parsed.candidate_package_digest,
        "feature_contract": parsed.feature_contract.as_dict(),
        "feature_abi": parsed.feature_abi,
        "feature_component_manifest_digest": parsed.feature_component_manifest_digest,
        "feature_layout_digest": parsed.feature_layout_digest,
        "feature_runtime_digest": parsed.feature_runtime_digest,
        "scoring_contract": parsed.scoring_contract,
        "ranking_contract": parsed.ranking_contract,
        "evaluation_contract": parsed.evaluation_contract,
        "code_commit": parsed.code_commit,
        "abi_package_digest": parsed.abi_package_digest,
        "artifact_payload_digest": parsed.artifact_payload_digest,
    }


def compare_kernel_results(
    *,
    target_issue: str,
    line_key: str,
    config_fingerprint: str,
    candidate_store_version: str,
    official: KernelResult,
    shadow: KernelResult,
    operational: ShadowOperationalEvidence | None = None,
) -> dict[str, Any]:
    """Create immutable, exact shadow evidence; no tolerance or best-run selection exists."""

    if not str(target_issue).strip() or not str(line_key).strip():
        raise ShadowEvidenceViolation(
            "shadow_scope_missing",
            "target_issue and line_key are required",
        )
    if not str(config_fingerprint).strip():
        raise ShadowEvidenceViolation(
            "shadow_config_fingerprint_missing",
            "config_fingerprint is required",
        )
    if official.backend == shadow.backend:
        raise ShadowEvidenceViolation(
            "shadow_backend_not_distinct",
            "official and shadow backends must be distinct",
            backend=official.backend,
        )
    if official.contract_version != shadow.contract_version:
        raise ShadowEvidenceViolation(
            "shadow_scoring_contract_mismatch",
            "official and shadow scoring contracts differ",
            official=official.contract_version,
            shadow=shadow.contract_version,
        )
    official_ranking = str(official.telemetry.get("ranking_contract") or "")
    shadow_ranking = str(shadow.telemetry.get("ranking_contract") or "")
    if not official_ranking or not shadow_ranking:
        raise ShadowEvidenceViolation(
            "shadow_ranking_contract_missing",
            "both backends must emit ranking contracts",
        )
    ranking_contract_mismatch_count = int(official_ranking != shadow_ranking)

    official_candidate = _candidate_identity(official)
    shadow_candidate = _candidate_identity(shadow)
    candidate_identity_mismatch_count = sum(
        official_candidate[field] != shadow_candidate[field]
        for field in _CANDIDATE_IDENTITY_FIELDS
    )
    official_digest = _result_digest(official)
    shadow_digest = _result_digest(shadow)
    target_score_mismatch_count = _mismatch_count(
        official.target_scores,
        shadow.target_scores,
    )
    rank_mismatch_count = _mismatch_count(official.exact_ranks, shadow.exact_ranks)
    topk_id_mismatch_count = _mismatch_count(
        official.top_candidate_ids,
        shadow.top_candidate_ids,
    )
    topk_score_mismatch_count = _mismatch_count(official.top_scores, shadow.top_scores)
    red5_mismatch_count = sum(
        _mismatch_count(left, right)
        for left, right in (
            (official.red5_candidate_ids, shadow.red5_candidate_ids),
            (official.red5_scores, shadow.red5_scores),
            (official.red5_ranks, shadow.red5_ranks),
        )
    )
    runtime_envelope_mismatch_count = int(
        _runtime_invariant(official.runtime_envelope)
        != _runtime_invariant(shadow.runtime_envelope)
    )
    operational = operational or ShadowOperationalEvidence()

    base = ShadowComparisonReport(
        target_issue=str(target_issue),
        official_backend=official.backend,
        shadow_backend=shadow.backend,
        official_ranking_contract=official_ranking,
        shadow_ranking_contract=shadow_ranking,
        candidate_store_version=candidate_store_version,
        config_fingerprint=config_fingerprint,
        target_score_diff=_maximum_absolute_difference(
            official.target_scores,
            shadow.target_scores,
        ),
        rank_diff=int(_maximum_absolute_difference(official.exact_ranks, shadow.exact_ranks)),
        topk_id_mismatch_count=topk_id_mismatch_count,
        topk_score_mismatch_count=topk_score_mismatch_count,
        red5_mismatch_count=red5_mismatch_count,
        evaluation_mismatch_count=operational.evaluation_mismatch_count,
        restart_recovery_result=operational.restart_recovery_result,
        watchdog_result=operational.watchdog_result,
        candidate_abi=official_candidate["candidate_abi"],
        candidate_digest=official_candidate["candidate_digest"],
        candidate_layout_digest=official_candidate["candidate_layout_digest"],
        candidate_package_digest=official_candidate["candidate_package_digest"],
        official_runtime_envelope=official.runtime_envelope or None,
        shadow_runtime_envelope=shadow.runtime_envelope or None,
    ).as_dict()
    mismatch_total = (
        target_score_mismatch_count
        + rank_mismatch_count
        + topk_id_mismatch_count
        + topk_score_mismatch_count
        + red5_mismatch_count
        + candidate_identity_mismatch_count
        + runtime_envelope_mismatch_count
        + ranking_contract_mismatch_count
    )
    comparison_status = "exact" if mismatch_total == 0 and official_digest == shadow_digest else "mismatch"
    payload: dict[str, Any] = {
        **base,
        "protocol": SHADOW_PROTOCOL_VERSION,
        "line_key": str(line_key),
        "scoring_contract": official.contract_version,
        "official_result_digest": official_digest,
        "shadow_result_digest": shadow_digest,
        "target_score_mismatch_count": target_score_mismatch_count,
        "rank_mismatch_count": rank_mismatch_count,
        "candidate_identity_mismatch_count": candidate_identity_mismatch_count,
        "runtime_envelope_mismatch_count": runtime_envelope_mismatch_count,
        "ranking_contract_mismatch_count": ranking_contract_mismatch_count,
        "evaluation_status": operational.evaluation_status,
        "comparison_status": comparison_status,
        "comparison_passed": comparison_status == "exact",
        "automatic_promotion_allowed": False,
        "official_candidate_identity": official_candidate,
        "shadow_candidate_identity": shadow_candidate,
    }
    payload["comparison_digest"] = canonical_digest(
        payload,
        domain="dehps.scoring-kernel-shadow-evidence.v1",
    )
    return payload


def run_shadow_comparison(
    *,
    target_issue: str,
    line_key: str,
    config_fingerprint: str,
    candidate_store: CandidateStore,
    window_state: PackedWindowState,
    weights: WeightMatrix,
    request: KernelRequest,
    official_backend: str = "numpy_reference",
    shadow_backend: str = "numba_cpu",
    operational: ShadowOperationalEvidence | None = None,
) -> dict[str, Any]:
    official_engine = KernelPlanner(official_backend).backend()
    shadow_engine = KernelPlanner(shadow_backend).backend()
    official_result = official_engine.score_rank(
        official_engine.prepare(candidate_store),
        window_state,
        weights,
        request,
        KernelWorkspace(),
    )
    shadow_result = shadow_engine.score_rank(
        shadow_engine.prepare(candidate_store),
        window_state,
        weights,
        request,
        KernelWorkspace(),
    )
    return compare_kernel_results(
        target_issue=target_issue,
        line_key=line_key,
        config_fingerprint=config_fingerprint,
        candidate_store_version=candidate_store.store_version,
        official=official_result,
        shadow=shadow_result,
        operational=operational,
    )


def write_shadow_artifact(output_dir: Path, evidence: Mapping[str, Any]) -> Path:
    """Atomically persist an append-only evidence artifact outside production tables."""

    verify_shadow_evidence(evidence)
    expected_digest = canonical_digest(
        {key: value for key, value in evidence.items() if key != "comparison_digest"},
        domain="dehps.scoring-kernel-shadow-evidence.v1",
    )
    if evidence.get("comparison_digest") != expected_digest:
        raise ShadowEvidenceViolation(
            "shadow_comparison_digest_mismatch",
            "shadow evidence cannot be persisted with an invalid seal",
        )
    issue = str(evidence.get("target_issue") or "").strip()
    line_key = str(evidence.get("line_key") or "").strip()
    if not issue or not line_key:
        raise ShadowEvidenceViolation("shadow_scope_missing", "artifact scope is incomplete")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"shadow-{issue}-{line_key}-{expected_digest[:16]}.json"
    encoded = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != encoded:
            raise ShadowEvidenceViolation(
                "shadow_artifact_identity_collision",
                "an existing content-addressed artifact has different bytes",
                path=str(destination),
            )
        return destination
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_dir,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return destination


def verify_shadow_evidence(evidence: Mapping[str, Any]) -> None:
    if evidence.get("protocol") != SHADOW_PROTOCOL_VERSION:
        raise ShadowEvidenceViolation(
            "shadow_protocol_mismatch",
            "unsupported shadow evidence protocol",
        )
    stored_digest = evidence.get("comparison_digest")
    expected_digest = canonical_digest(
        {key: value for key, value in evidence.items() if key != "comparison_digest"},
        domain="dehps.scoring-kernel-shadow-evidence.v1",
    )
    if stored_digest != expected_digest:
        raise ShadowEvidenceViolation(
            "shadow_comparison_digest_mismatch",
            "shadow evidence seal does not match its payload",
        )
    if evidence.get("comparison_status") == "exact":
        mismatch_fields = (
            "target_score_mismatch_count",
            "rank_mismatch_count",
            "topk_id_mismatch_count",
            "topk_score_mismatch_count",
            "red5_mismatch_count",
            "candidate_identity_mismatch_count",
            "runtime_envelope_mismatch_count",
            "ranking_contract_mismatch_count",
        )
        if any(int(evidence.get(field) or 0) != 0 for field in mismatch_fields):
            raise ShadowEvidenceViolation(
                "shadow_exact_status_inconsistent",
                "exact shadow evidence contains mismatches",
            )
        if float(evidence.get("target_score_diff") or 0.0) != 0.0 or int(
            evidence.get("rank_diff") or 0
        ) != 0:
            raise ShadowEvidenceViolation(
                "shadow_exact_status_inconsistent",
                "exact shadow evidence contains non-zero differences",
            )
        if evidence.get("official_result_digest") != evidence.get("shadow_result_digest"):
            raise ShadowEvidenceViolation(
                "shadow_exact_status_inconsistent",
                "exact shadow evidence has different result digests",
            )
        if evidence.get("official_candidate_identity") != evidence.get(
            "shadow_candidate_identity"
        ):
            raise ShadowEvidenceViolation(
                "shadow_exact_status_inconsistent",
                "exact shadow evidence has different Candidate ABI identities",
            )


def shadow_promotion_readiness(
    evidence_rows: Iterable[Mapping[str, Any]],
    *,
    required_issue_count: int = 3,
    required_line_keys: Sequence[str] = DEFAULT_PRODUCTION_LINES,
) -> dict[str, Any]:
    """Evaluate evidence sufficiency only; this gate never authorizes promotion."""

    if required_issue_count < 1:
        raise ValueError("required_issue_count must be positive")
    required_lines = tuple(dict.fromkeys(str(value) for value in required_line_keys))
    if not required_lines or any(not value for value in required_lines):
        raise ValueError("required_line_keys must be non-empty")
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    duplicate_keys: list[str] = []
    ignored_keys: list[str] = []
    for row in evidence_rows:
        issue = str(row.get("target_issue") or "")
        line_key = str(row.get("line_key") or "")
        key = f"{issue}:{line_key}"
        if not issue or not line_key:
            duplicate_keys.append(f"invalid:{key}")
            continue
        if line_key not in required_lines:
            ignored_keys.append(key)
            continue
        if line_key in grouped[issue]:
            duplicate_keys.append(key)
            continue
        grouped[issue][line_key] = row

    issue_rows: list[dict[str, Any]] = []
    for issue in sorted(grouped, key=_issue_sort_key):
        lines = grouped[issue]
        missing = [line for line in required_lines if line not in lines]
        failures: list[str] = []
        for line in required_lines:
            row = lines.get(line)
            if row is None:
                continue
            try:
                verify_shadow_evidence(row)
            except (ShadowEvidenceViolation, TypeError, ValueError):
                failures.append(f"{line}:invalid_evidence")
            if row.get("comparison_status") != "exact":
                failures.append(f"{line}:comparison")
            if row.get("official_backend") != "numpy_reference":
                failures.append(f"{line}:official_backend")
            if row.get("shadow_backend") != "numba_cpu":
                failures.append(f"{line}:shadow_backend")
            if row.get("official_ranking_contract") != STRICT_RANKING_CONTRACT:
                failures.append(f"{line}:official_ranking_contract")
            if row.get("shadow_ranking_contract") != STRICT_RANKING_CONTRACT:
                failures.append(f"{line}:shadow_ranking_contract")
            if row.get("evaluation_status") != "passed" or int(
                row.get("evaluation_mismatch_count") or 0
            ) != 0:
                failures.append(f"{line}:evaluation")
            if row.get("restart_recovery_result") != "passed":
                failures.append(f"{line}:restart_recovery")
            if row.get("watchdog_result") != "passed":
                failures.append(f"{line}:watchdog")
            if row.get("automatic_promotion_allowed") is not False:
                failures.append(f"{line}:promotion_authority")
        passed = not missing and not failures
        issue_rows.append(
            {
                "target_issue": issue,
                "required_lines": list(required_lines),
                "missing_lines": missing,
                "failures": failures,
                "passed": passed,
            }
        )

    passing_issues = [row["target_issue"] for row in issue_rows if row["passed"]]
    selected_rows = issue_rows[-required_issue_count:]
    selected = [row["target_issue"] for row in selected_rows]
    consecutive = len(selected) == required_issue_count and _issues_are_consecutive(selected)
    evidence_sufficient = (
        not duplicate_keys
        and len(selected) == required_issue_count
        and all(row["passed"] for row in selected_rows)
        and consecutive
    )
    payload = {
        "protocol": SHADOW_GATE_VERSION,
        "required_issue_count": required_issue_count,
        "required_line_keys": list(required_lines),
        "issue_results": issue_rows,
        "passing_issues": passing_issues,
        "selected_issues": selected,
        "issues_are_consecutive": consecutive,
        "duplicate_evidence_keys": duplicate_keys,
        "ignored_evidence_keys": ignored_keys,
        "evidence_sufficient": evidence_sufficient,
        "status": "ready_for_independent_approval" if evidence_sufficient else "insufficient_evidence",
        "automatic_promotion_allowed": False,
    }
    payload["gate_digest"] = canonical_digest(
        payload,
        domain="dehps.scoring-kernel-shadow-promotion-gate.v1",
    )
    return payload


def _issue_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except ValueError:
        return (1, value)


def _issues_are_consecutive(issues: Sequence[str]) -> bool:
    if len(issues) < 2:
        return bool(issues)
    try:
        numeric = [int(issue) for issue in issues]
    except ValueError:
        return False
    return all(right == left + 1 for left, right in zip(numeric, numeric[1:]))
