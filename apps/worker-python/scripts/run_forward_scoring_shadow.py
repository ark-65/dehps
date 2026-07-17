from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

import numpy as np
from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.forward_runtime.shadow_adapter import (
    ForwardShadowViolation,
    compare_forward_evaluation,
    compare_official_candidate_artifact,
    forward_operational_evidence,
)
from dehps.models.frequency_ranker import FrequencyRankerConfig, train_frequency_stats
from dehps.optimization.prediction_evaluation import load_actual_draw
from dehps.optimization.ranking_audit import training_history_for_prediction_run
from dehps.optimization.walk_forward import (
    _config_weight_matrix,
    _target_scores,
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    is_excluded_red_combination,
)
from dehps.scoring_kernel import (
    KernelRequest,
    WeightMatrix,
    candidate_store_from_matrix,
    compare_kernel_results,
    execute_shadow_pair,
    numbers_mask,
    pack_window_state,
    target_lex_id,
    write_shadow_artifact,
)
from dehps.source_version import resolve_git_commit


DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/scoring-shadow"


def load_forward_runs(conn, *, target_issue: str) -> list[dict[str, Any]]:
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


def load_stored_candidates(conn, *, prediction_run_key: str) -> list[dict[str, Any]]:
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


def _target_date(run: dict[str, Any], actual: dict[str, Any] | None) -> date | None:
    if actual is not None and isinstance(actual.get("draw_date"), date):
        return actual["draw_date"]
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    value = metadata.get("next_draw_date")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None


def _source_code_commit(run: dict[str, Any]) -> str:
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    value = str(metadata.get("git_commit") or "")
    return value


def build_run_evidence(
    conn,
    *,
    run: dict[str, Any],
    store,
    worker_count: int,
    restart_recovery_result: str,
    watchdog_result: str,
) -> dict[str, Any]:
    prediction_run_key = str(run["prediction_run_key"])
    stored_candidates = load_stored_candidates(
        conn,
        prediction_run_key=prediction_run_key,
    )
    if len(stored_candidates) != int(run["candidate_count"]):
        raise ForwardShadowViolation(
            "forward_shadow_candidate_count_mismatch",
            "stored candidate count does not match the prediction run",
            prediction_run_key=prediction_run_key,
            run_count=int(run["candidate_count"]),
            stored_count=len(stored_candidates),
        )

    full_history = training_history_for_prediction_run(
        conn,
        run,
        apply_train_window=False,
    )
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    stored_history_fingerprint = str(metadata.get("history_fingerprint") or "")
    replay_history_fingerprint = fingerprint_history(full_history)
    if not stored_history_fingerprint or stored_history_fingerprint != replay_history_fingerprint:
        raise ForwardShadowViolation(
            "forward_shadow_history_fingerprint_mismatch",
            "the prediction history snapshot cannot be reproduced exactly",
            prediction_run_key=prediction_run_key,
            stored=stored_history_fingerprint,
            replay=replay_history_fingerprint,
        )
    history = training_history_for_prediction_run(conn, run)
    config_payload = run.get("config") if isinstance(run.get("config"), dict) else {}
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
    target_draw_date = _target_date(run, actual)
    stats = train_frequency_stats(history, target_draw_date=target_draw_date)
    state = pack_window_state(stats)
    weights = WeightMatrix(
        np.ascontiguousarray(_config_weight_matrix((config,)), dtype=np.float64)
    )
    if actual is None:
        target_numbers = None
        target_scores = np.zeros(1, dtype=np.float64)
        target_mask = np.uint64(0)
        lex_id = 0
        target_excluded = False
    else:
        target_numbers = tuple(int(value) for value in actual["red_numbers"])
        target_scores = np.ascontiguousarray(
            _target_scores(target_numbers, stats, (config,)),
            dtype=np.float64,
        )
        target_mask = numbers_mask(target_numbers)
        lex_id = target_lex_id(store, target_numbers)
        target_excluded = is_excluded_red_combination(target_numbers)
    request = KernelRequest(
        target_scores=target_scores,
        target_lex_id=lex_id,
        target_mask=target_mask,
        top_k=int(run["top_n"]),
        chunk_size=262_144,
        worker_count=worker_count,
        exact_rank=actual is not None,
        red5=actual is not None,
        target_excluded=target_excluded,
    )
    official, shadow = execute_shadow_pair(
        candidate_store=store,
        window_state=state,
        weights=weights,
        request=request,
    )
    artifact_check = compare_official_candidate_artifact(
        candidate_store=store,
        official_result=official,
        stored_candidates=stored_candidates,
    )
    evaluation_row = None
    if run.get("evaluation_status") is not None:
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
    operational = forward_operational_evidence(
        prediction_run=run,
        artifact_check=artifact_check,
        evaluation_check=evaluation_check,
        source_code_commit=_source_code_commit(run),
        replay_code_commit=resolve_git_commit(),
        capture_mode="posthoc_reconstruction",
        restart_recovery_result=restart_recovery_result,
        watchdog_result=watchdog_result,
    )
    return compare_kernel_results(
        target_issue=str(run["target_issue"]),
        line_key=str(run["line_key"]),
        config_fingerprint=str(run["config_hash"]),
        candidate_store_version=store.store_version,
        official=official,
        shadow=shadow,
        operational=operational,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct forward runs read-only and emit post-hoc NumPy/Numba shadow evidence. "
            "Post-hoc evidence is diagnostic and cannot satisfy the simultaneous promotion gate."
        ),
    )
    parser.add_argument("--target-issue", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--restart-recovery-result",
        choices=("pending", "passed", "failed"),
        default="pending",
    )
    parser.add_argument(
        "--watchdog-result",
        choices=("pending", "passed", "failed"),
        default="pending",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be positive")

    matrix = build_ranked_universe()
    store = candidate_store_from_matrix(matrix)
    output: list[dict[str, Any]] = []
    with get_connection() as conn:
        runs = load_forward_runs(conn, target_issue=args.target_issue)
        if not runs:
            raise SystemExit(f"forward_shadow_runs_missing:{args.target_issue}")
        line_keys = [str(run["line_key"]) for run in runs]
        duplicate_lines = sorted(
            line_key for line_key in set(line_keys) if line_keys.count(line_key) > 1
        )
        if duplicate_lines:
            raise ForwardShadowViolation(
                "forward_shadow_duplicate_active_lines",
                "one target issue cannot have multiple non-superseded runs for a line",
                target_issue=args.target_issue,
                line_keys=duplicate_lines,
            )
        for run in runs:
            evidence = build_run_evidence(
                conn,
                run=run,
                store=store,
                worker_count=args.workers,
                restart_recovery_result=args.restart_recovery_result,
                watchdog_result=args.watchdog_result,
            )
            path = write_shadow_artifact(args.output_dir, evidence)
            output.append(
                {
                    "prediction_run_key": run["prediction_run_key"],
                    "line_key": run["line_key"],
                    "comparison_status": evidence["comparison_status"],
                    "official_candidate_artifact_status": evidence[
                        "official_candidate_artifact_status"
                    ],
                    "evaluation_status": evidence["evaluation_status"],
                    "capture_mode": evidence["capture_mode"],
                    "artifact_path": str(path),
                    "comparison_digest": evidence["comparison_digest"],
                }
            )
    print(json.dumps({"target_issue": args.target_issue, "runs": output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
