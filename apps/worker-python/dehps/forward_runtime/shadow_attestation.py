from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from psycopg import Connection
from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.forward_runtime.shadow_adapter import (
    ForwardShadowViolation,
    compare_forward_evaluation,
    compare_official_candidate_artifact,
    forward_operational_evidence,
)
from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    HistoryDraw,
    train_frequency_stats,
)
from dehps.optimization.prediction_evaluation import load_actual_draw
from dehps.optimization.ranking_audit import resolve_training_history_for_prediction_run
from dehps.optimization.walk_forward import (
    _config_weight_matrix,
    _target_scores,
    build_ranked_universe,
    config_hash,
    is_excluded_red_combination,
)
from dehps.scoring_kernel import (
    CandidateStore,
    KernelRequest,
    KernelResult,
    ShadowEvidenceViolation,
    WeightMatrix,
    build_shadow_operational_receipt,
    candidate_store_from_matrix,
    compare_kernel_results,
    execute_feature_abi_shadow_pair,
    link_post_draw_attestation,
    numbers_mask,
    target_lex_id,
    verify_shadow_evidence,
    verify_shadow_watch_cycle,
    write_shadow_artifact,
)
from dehps.scoring_kernel.runtime_input import (
    RuntimeInputCompiler,
    default_runtime_input_compiler,
)
from dehps.source_version import resolve_git_commit


FORWARD_SHADOW_ATTESTATION_ENV = "DEHPS_FORWARD_SHADOW_ATTESTATION"
DEFAULT_SHADOW_OUTPUT_DIR = ROOT_DIR / "data/output/scoring-shadow"
ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]
EvidenceBuilder = Callable[..., dict[str, Any]]


def forward_shadow_attestation_enabled() -> bool:
    value = str(os.getenv(FORWARD_SHADOW_ATTESTATION_ENV) or "").strip().lower()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise ValueError(f"{FORWARD_SHADOW_ATTESTATION_ENV} must be a boolean flag")


def execute_verified_replay_pair(
    *,
    history: Sequence[HistoryDraw],
    store: CandidateStore,
    target_draw_date: date | None,
    target_issue: str,
    weights: WeightMatrix,
    request: KernelRequest,
    code_commit: str,
    runtime_compiler: RuntimeInputCompiler | None = None,
) -> tuple[KernelResult, KernelResult, dict[str, Any]]:
    compiler = runtime_compiler or default_runtime_input_compiler()
    runtime_inputs = compiler.compile_effective_history(
        history=history,
        candidate_store=store,
        tile_size=request.chunk_size,
        target_draw_date=target_draw_date,
        target_issue=target_issue,
        source="forward_shadow_replay_effective_history",
    )
    official, shadow = execute_feature_abi_shadow_pair(
        verified_runtime=runtime_inputs.verified_runtime,
        code_commit=code_commit,
        weights=weights,
        request=request,
    )
    return official, shadow, runtime_inputs.abi_cache_compilation.as_dict()


def load_forward_runs(conn: Connection[Any], *, target_issue: str) -> list[dict[str, Any]]:
    tables = conn.execute(
        """
        SELECT to_regclass('public.forward_prediction_runs'),
               to_regclass('public.forward_prediction_candidates')
        """
    ).fetchone()
    if not tables or not all(tables):
        raise ForwardShadowViolation(
            "forward_shadow_schema_missing",
            "forward prediction evidence tables do not exist",
        )
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT r.prediction_run_key, r.line_key, r.line_label, r.line_kind,
                   r.snapshot_key, r.source_run_id, r.source_round_index,
                   r.as_of_issue, r.target_issue, r.train_mode, r.train_window,
                   r.top_n, r.candidate_count, r.config_hash, r.config,
                   r.metadata, r.prediction_fingerprint, r.ranking_contract,
                   r.status AS prediction_status, r.generated_at,
                   er.status AS forward_evaluation_status,
                   pe.status AS evaluation_status,
                   pe.candidate_count AS evaluation_candidate_count,
                   pe.summary AS evaluation_summary
            FROM forward_prediction_runs r
            LEFT JOIN forward_evaluation_runs er
              ON er.prediction_run_key = r.prediction_run_key
             AND er.target_issue = r.target_issue
            LEFT JOIN training_prediction_evaluations pe
              ON pe.prediction_run_key = r.prediction_run_key
             AND pe.predicted_issue = r.target_issue
            WHERE r.target_issue = %s
              AND r.status <> 'superseded'
            ORDER BY r.line_key ASC, r.generated_at ASC
            """,
            (target_issue,),
        ).fetchall()
    return [dict(row) for row in rows]


def load_stored_candidates(
    conn: Connection[Any],
    *,
    prediction_run_key: str,
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT rank, red_numbers, score
            FROM forward_prediction_candidates
            WHERE prediction_run_key = %s
            ORDER BY rank ASC
            """,
            (prediction_run_key,),
        ).fetchall()
    return [dict(row) for row in rows]


def _target_date(run: Mapping[str, Any], actual: Mapping[str, Any] | None) -> date | None:
    if actual is not None and isinstance(actual.get("draw_date"), date):
        return actual["draw_date"]
    metadata = run.get("metadata") if isinstance(run.get("metadata"), Mapping) else {}
    value = metadata.get("next_draw_date")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None


def build_run_attestation(
    conn: Connection[Any],
    *,
    run: dict[str, Any],
    store: CandidateStore,
    worker_count: int,
    watch_cycle: Mapping[str, Any],
    runtime_compiler: RuntimeInputCompiler | None = None,
) -> dict[str, Any]:
    """Rebuild one persisted run and bind it to a sealed watchdog cycle."""

    verify_shadow_watch_cycle(watch_cycle)
    prediction_run_key = str(run["prediction_run_key"])
    stored_candidates = load_stored_candidates(conn, prediction_run_key=prediction_run_key)
    if len(stored_candidates) != int(run["candidate_count"]):
        raise ForwardShadowViolation(
            "forward_shadow_candidate_count_mismatch",
            "stored candidate count does not match the prediction run",
            prediction_run_key=prediction_run_key,
            run_count=int(run["candidate_count"]),
            stored_count=len(stored_candidates),
        )

    history_replay = resolve_training_history_for_prediction_run(conn, run)
    if not history_replay.stored_fingerprint:
        raise ForwardShadowViolation(
            "forward_shadow_history_fingerprint_missing",
            "the prediction run has no sealed history fingerprint",
            prediction_run_key=prediction_run_key,
        )
    history = history_replay.history
    config_payload = run.get("config") if isinstance(run.get("config"), Mapping) else {}
    config = FrequencyRankerConfig(
        **{
            key: float(value)
            for key, value in config_payload.items()
            if isinstance(value, int | float)
        }
    )
    if config_hash(config) != str(run["config_hash"]):
        raise ForwardShadowViolation(
            "forward_shadow_config_fingerprint_mismatch",
            "the stored forward configuration cannot be reproduced exactly",
            prediction_run_key=prediction_run_key,
        )

    actual = load_actual_draw(conn, issue=str(run["target_issue"]))
    if actual is None:
        raise ForwardShadowViolation(
            "forward_shadow_actual_draw_missing",
            "post-draw attestation requires the synchronized actual draw",
            target_issue=str(run["target_issue"]),
        )
    target_draw_date = _target_date(run, actual)
    stats = train_frequency_stats(history, target_draw_date=target_draw_date)
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix((config,)), dtype=np.float64)
    )
    target_numbers = tuple(int(value) for value in actual["red_numbers"])
    request = KernelRequest(
        target_scores=np.ascontiguousarray(
            _target_scores(target_numbers, stats, (config,)),
            dtype=np.float64,
        ),
        target_lex_id=target_lex_id(store, target_numbers),
        target_mask=numbers_mask(target_numbers),
        top_k=int(run["top_n"]),
        chunk_size=262_144,
        worker_count=worker_count,
        exact_rank=True,
        red5=True,
        target_excluded=is_excluded_red_combination(target_numbers),
    )
    replay_commit = resolve_git_commit()
    official, shadow, runtime_abi_cache = execute_verified_replay_pair(
        history=history,
        store=store,
        target_draw_date=target_draw_date,
        target_issue=str(run["target_issue"]),
        weights=weights,
        request=request,
        code_commit=replay_commit,
        runtime_compiler=runtime_compiler,
    )
    artifact_check = compare_official_candidate_artifact(
        candidate_store=store,
        official_result=official,
        stored_candidates=stored_candidates,
    )
    evaluation_row = {
        "forward_evaluation_status": run.get("forward_evaluation_status"),
        "status": run.get("evaluation_status"),
        "candidate_count": run.get("evaluation_candidate_count"),
        "top_n": run.get("top_n"),
        "summary": run.get("evaluation_summary"),
    }
    evaluation_check = compare_forward_evaluation(
        official_result=official,
        evaluation_row=evaluation_row,
    )
    metadata = run.get("metadata") if isinstance(run.get("metadata"), Mapping) else {}
    source_capture = metadata.get("shadow_scoring_evidence")
    if not isinstance(source_capture, Mapping):
        raise ForwardShadowViolation(
            "forward_shadow_source_capture_missing",
            "automatic attestation requires a sealed simultaneous pre-draw capture",
            prediction_run_key=prediction_run_key,
        )
    verify_shadow_evidence(source_capture)

    preliminary_operational = forward_operational_evidence(
        prediction_run=run,
        artifact_check=artifact_check,
        evaluation_check=evaluation_check,
        source_code_commit=str(source_capture.get("source_code_commit") or ""),
        replay_code_commit=replay_commit,
        capture_mode="simultaneous",
        restart_recovery_result="pending",
        watchdog_result="pending",
    )
    reconstruction = compare_kernel_results(
        target_issue=str(run["target_issue"]),
        line_key=str(run["line_key"]),
        config_fingerprint=str(run["config_hash"]),
        candidate_store_version=store.store_version,
        official=official,
        shadow=shadow,
        operational=preliminary_operational,
        runtime_abi_cache=runtime_abi_cache,
    )
    receipt = build_shadow_operational_receipt(
        scoring_capture=source_capture,
        reconstruction=reconstruction,
        watch_cycle=watch_cycle,
    )
    final_operational = forward_operational_evidence(
        prediction_run=run,
        artifact_check=artifact_check,
        evaluation_check=evaluation_check,
        source_code_commit=str(source_capture.get("source_code_commit") or ""),
        replay_code_commit=replay_commit,
        capture_mode="simultaneous",
        restart_recovery_result=str(receipt["restart_recovery_result"]),
        watchdog_result=str(receipt["watchdog_result"]),
        operational_receipt=receipt,
    )
    comparison = compare_kernel_results(
        target_issue=str(run["target_issue"]),
        line_key=str(run["line_key"]),
        config_fingerprint=str(run["config_hash"]),
        candidate_store_version=store.store_version,
        official=official,
        shadow=shadow,
        operational=final_operational,
        runtime_abi_cache=runtime_abi_cache,
    )
    return link_post_draw_attestation(
        scoring_capture=source_capture,
        post_draw_comparison=comparison,
    )


class ForwardShadowAttestationService:
    """Idempotently close eligible pre-draw shadow captures after evaluation."""

    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory = get_connection,
        output_dir: Path = DEFAULT_SHADOW_OUTPUT_DIR,
        worker_count: int = 8,
        evidence_builder: EvidenceBuilder = build_run_attestation,
        candidate_store_factory: Callable[[], CandidateStore] | None = None,
        run_loader: Callable[..., list[dict[str, Any]]] = load_forward_runs,
    ) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be positive")
        self.connection_factory = connection_factory
        self.output_dir = output_dir
        self.worker_count = worker_count
        self.evidence_builder = evidence_builder
        self.run_loader = run_loader
        self.candidate_store_factory = candidate_store_factory or (
            lambda: candidate_store_from_matrix(build_ranked_universe())
        )

    def close_cycle(self, watch_cycle: Mapping[str, Any]) -> dict[str, Any]:
        verify_shadow_watch_cycle(watch_cycle)
        target_issue = str(watch_cycle.get("current_latest_issue") or "")
        if not target_issue:
            return self._summary(target_issue=None, outcomes=[], status="pending_no_current_issue")
        with self.connection_factory() as conn:
            runs = self.run_loader(conn, target_issue=target_issue)
            duplicate_lines = self._duplicate_lines(runs)
            if duplicate_lines:
                return self._summary(
                    target_issue=target_issue,
                    outcomes=[
                        {
                            "status": "failed_duplicate_active_line",
                            "line_key": line,
                            "error": {"code": "forward_shadow_duplicate_active_lines"},
                        }
                        for line in duplicate_lines
                    ],
                    status="failed",
                )
            outcomes: list[dict[str, Any]] = []
            store: CandidateStore | None = None
            for run in runs:
                outcome = self._preflight(run)
                if outcome is not None:
                    outcomes.append(outcome)
                    continue
                existing = self._existing_attestation(run)
                if existing is not None:
                    outcomes.append(existing)
                    continue
                try:
                    if store is None:
                        store = self.candidate_store_factory()
                    evidence = self.evidence_builder(
                        conn,
                        run=run,
                        store=store,
                        worker_count=self.worker_count,
                        watch_cycle=watch_cycle,
                    )
                    if evidence.get("restart_recovery_result") != "passed" or evidence.get(
                        "watchdog_result"
                    ) != "passed":
                        outcomes.append(
                            {
                                "prediction_run_key": run["prediction_run_key"],
                                "line_key": run["line_key"],
                                "status": "failed_operational_evidence",
                                "restart_recovery_result": evidence.get(
                                    "restart_recovery_result"
                                ),
                                "watchdog_result": evidence.get("watchdog_result"),
                            }
                        )
                        continue
                    path = write_shadow_artifact(self.output_dir, evidence)
                    outcomes.append(
                        {
                            "prediction_run_key": run["prediction_run_key"],
                            "line_key": run["line_key"],
                            "status": "attested",
                            "artifact_path": str(path),
                            "comparison_digest": evidence["comparison_digest"],
                        }
                    )
                except Exception as exc:
                    details = getattr(exc, "as_dict", None)
                    outcomes.append(
                        {
                            "prediction_run_key": run.get("prediction_run_key"),
                            "line_key": run.get("line_key"),
                            "status": "failed",
                            "error": (
                                details()
                                if callable(details)
                                else {"type": type(exc).__name__, "message": str(exc)}
                            ),
                        }
                    )
        status = (
            "failed"
            if any(str(row["status"]).startswith("failed") for row in outcomes)
            else "ok"
        )
        return self._summary(target_issue=target_issue, outcomes=outcomes, status=status)

    @staticmethod
    def _preflight(run: Mapping[str, Any]) -> dict[str, Any] | None:
        base = {
            "prediction_run_key": run.get("prediction_run_key"),
            "line_key": run.get("line_key"),
        }
        metadata = run.get("metadata") if isinstance(run.get("metadata"), Mapping) else {}
        capture = metadata.get("shadow_scoring_evidence")
        if not isinstance(capture, Mapping) or capture.get("capture_mode") != "simultaneous":
            return {**base, "status": "ineligible_no_simultaneous_capture"}
        if run.get("prediction_status") != "evaluated" or run.get(
            "forward_evaluation_status"
        ) != "completed":
            return {**base, "status": "pending_evaluation"}
        return None

    def _existing_attestation(self, run: Mapping[str, Any]) -> dict[str, Any] | None:
        if not self.output_dir.exists():
            return None
        metadata = run.get("metadata") if isinstance(run.get("metadata"), Mapping) else {}
        source = metadata.get("shadow_scoring_evidence")
        source_digest = source.get("comparison_digest") if isinstance(source, Mapping) else None
        issue = str(run.get("target_issue") or "")
        line = str(run.get("line_key") or "")
        for path in sorted(self.output_dir.glob(f"shadow-{issue}-{line}-*.json")):
            try:
                evidence = json.loads(path.read_text(encoding="utf-8"))
                verify_shadow_evidence(evidence)
            except (OSError, ValueError, TypeError, ShadowEvidenceViolation):
                continue
            if (
                evidence.get("evidence_phase") == "post_draw_attested"
                and evidence.get("prediction_run_key") == run.get("prediction_run_key")
                and evidence.get("source_comparison_digest") == source_digest
                and evidence.get("restart_recovery_result") == "passed"
                and evidence.get("watchdog_result") == "passed"
            ):
                return {
                    "prediction_run_key": run.get("prediction_run_key"),
                    "line_key": line,
                    "status": "already_attested",
                    "artifact_path": str(path),
                    "comparison_digest": evidence.get("comparison_digest"),
                }
        return None

    @staticmethod
    def _duplicate_lines(runs: Sequence[Mapping[str, Any]]) -> list[str]:
        lines = [str(run.get("line_key") or "") for run in runs]
        return sorted(line for line in set(lines) if line and lines.count(line) > 1)

    @staticmethod
    def _summary(
        *,
        target_issue: str | None,
        outcomes: list[dict[str, Any]],
        status: str,
    ) -> dict[str, Any]:
        return {
            "protocol": "forward-shadow-attestation-closure.v1",
            "status": status,
            "target_issue": target_issue,
            "run_count": len(outcomes),
            "attested_count": sum(row["status"] == "attested" for row in outcomes),
            "already_attested_count": sum(
                row["status"] == "already_attested" for row in outcomes
            ),
            "pending_count": sum(str(row["status"]).startswith("pending") for row in outcomes),
            "ineligible_count": sum(
                str(row["status"]).startswith("ineligible") for row in outcomes
            ),
            "failed_count": sum(str(row["status"]).startswith("failed") for row in outcomes),
            "runs": outcomes,
            "automatic_promotion_allowed": False,
        }
