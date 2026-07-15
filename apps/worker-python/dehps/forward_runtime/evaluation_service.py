from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.optimization.prediction_evaluation import (
    evaluate_prediction_snapshot,
    load_actual_draw,
    load_prediction_rows,
)
from dehps.optimization.ranking_audit import build_actual_ranking_audit
from dehps.storage.postgres_store import (
    archive_current_forward_prediction_snapshots,
    ensure_forward_prediction_evaluation_schema,
)


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]
SnapshotEvaluator = Callable[..., dict[str, Any]]
RankingAuditor = Callable[..., dict[str, Any]]
ActualLoader = Callable[..., dict[str, Any] | None]
PredictionLoader = Callable[..., tuple[list[dict[str, Any]], str | None]]


class ForwardEvaluationService:
    def __init__(
        self,
        *,
        connection_factory: ConnectionFactory = get_connection,
        snapshot_evaluator: SnapshotEvaluator = evaluate_prediction_snapshot,
        ranking_auditor: RankingAuditor = build_actual_ranking_audit,
        actual_loader: ActualLoader = load_actual_draw,
        prediction_loader: PredictionLoader = load_prediction_rows,
    ) -> None:
        self.connection_factory = connection_factory
        self.snapshot_evaluator = snapshot_evaluator
        self.ranking_auditor = ranking_auditor
        self.actual_loader = actual_loader
        self.prediction_loader = prediction_loader

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_forward_prediction_evaluation_schema(conn)
            archive_current_forward_prediction_snapshots(conn)

    def pending_runs(self) -> list[dict[str, Any]]:
        self.ensure_schema()
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """
                SELECT prediction_run_key, line_key, line_label, line_kind,
                       snapshot_key, source_run_id, source_round_index,
                       as_of_issue, target_issue, train_mode, train_window,
                       top_n, candidate_count, config_hash, config, metadata,
                       status, generated_at
                FROM forward_prediction_runs
                WHERE status IN ('pending', 'evaluation_failed')
                   OR (status = 'evaluating' AND updated_at < now() - interval '30 minutes')
                ORDER BY target_issue ASC, line_key ASC, generated_at ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def evaluate_pending(self, *, write_report: bool = True) -> dict[str, Any]:
        pending = self.pending_runs()
        results: list[dict[str, Any]] = []
        missing_draw_count = 0
        failed_count = 0
        evaluated_count = 0
        skipped_count = 0
        for run in pending:
            target_issue = str(run["target_issue"])
            with self.connection_factory() as conn:
                actual = self.actual_loader(conn, issue=target_issue)
            if actual is None:
                missing_draw_count += 1
                results.append(
                    {
                        "prediction_run_key": run["prediction_run_key"],
                        "target_issue": target_issue,
                        "status": "pending_missing_actual_draw",
                    }
                )
                continue
            result = self._evaluate_one(run, actual, write_report=write_report)
            results.append(result)
            if result["status"] == "evaluated":
                evaluated_count += 1
            elif result["status"] == "evaluation_failed":
                failed_count += 1
            else:
                skipped_count += 1
        return {
            "status": "failed" if failed_count else "ok",
            "pending_count": len(pending),
            "evaluated_count": evaluated_count,
            "missing_draw_count": missing_draw_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "results": results,
        }

    def _evaluate_one(
        self,
        run: dict[str, Any],
        actual: dict[str, Any],
        *,
        write_report: bool,
    ) -> dict[str, Any]:
        prediction_run_key = str(run["prediction_run_key"])
        target_issue = str(run["target_issue"])
        evaluation_run_key = f"forward-eval:{prediction_run_key}:{target_issue}"
        if not self._claim(prediction_run_key, target_issue, evaluation_run_key):
            return {
                "prediction_run_key": prediction_run_key,
                "target_issue": target_issue,
                "status": "skipped_not_pending",
            }
        try:
            with self.connection_factory() as conn:
                candidates, _ = self.prediction_loader(
                    conn,
                    line_key=str(run["line_key"]),
                    predicted_issue=target_issue,
                    snapshot_key=str(run["snapshot_key"]),
                    prediction_run_key=prediction_run_key,
                )
                ranking_audit = self.ranking_auditor(
                    conn,
                    prediction_run=run,
                    actual_draw=actual,
                    candidates=candidates,
                )
                payload = self.snapshot_evaluator(
                    conn,
                    line_key=str(run["line_key"]),
                    predicted_issue=target_issue,
                    snapshot_key=str(run["snapshot_key"]),
                    prediction_run_key=prediction_run_key,
                    evaluation_run_key=evaluation_run_key,
                    ranking_audit=ranking_audit,
                    write_report=write_report,
                    persist=True,
                )
                summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
                accepted = (
                    payload.get("status") == "evaluated"
                    and summary.get("leakage_passed") is True
                    and int(payload.get("candidate_count") or 0) == int(run.get("top_n") or 0)
                    and int(run.get("top_n") or 0) > 0
                )
                if not accepted:
                    raise RuntimeError(
                        "forward_evaluation_not_accepted:"
                        f"status={payload.get('status')}:"
                        f"candidate_count={payload.get('candidate_count')}:"
                        f"top_n={run.get('top_n')}:"
                        f"leakage_passed={summary.get('leakage_passed')}"
                    )
                conn.execute(
                    """
                    UPDATE forward_evaluation_runs
                    SET status = 'completed', error = '{}'::jsonb,
                        completed_at = now(), updated_at = now()
                    WHERE evaluation_run_key = %s
                    """,
                    (evaluation_run_key,),
                )
                conn.execute(
                    """
                    UPDATE forward_prediction_runs
                    SET status = 'evaluated', failure = '{}'::jsonb,
                        evaluated_at = now(), updated_at = now()
                    WHERE prediction_run_key = %s
                    """,
                    (prediction_run_key,),
                )
            return {
                "prediction_run_key": prediction_run_key,
                "evaluation_run_key": evaluation_run_key,
                "target_issue": target_issue,
                "line_key": run["line_key"],
                "status": "evaluated",
                "ranking_audit": ranking_audit,
            }
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
            self._record_failure(prediction_run_key, evaluation_run_key, error)
            return {
                "prediction_run_key": prediction_run_key,
                "evaluation_run_key": evaluation_run_key,
                "target_issue": target_issue,
                "line_key": run["line_key"],
                "status": "evaluation_failed",
                "error": error,
            }

    def _claim(self, prediction_run_key: str, target_issue: str, evaluation_run_key: str) -> bool:
        with self.connection_factory() as conn:
            claimed = conn.execute(
                """
                UPDATE forward_prediction_runs
                SET status = 'evaluating', updated_at = now()
                WHERE prediction_run_key = %s
                  AND (
                    status IN ('pending', 'evaluation_failed')
                    OR (status = 'evaluating' AND updated_at < now() - interval '30 minutes')
                  )
                RETURNING prediction_run_key
                """,
                (prediction_run_key,),
            ).fetchone()
            if not claimed:
                return False
            conn.execute(
                """
                INSERT INTO forward_evaluation_runs (
                  evaluation_run_key, prediction_run_key, target_issue,
                  status, attempt_count, started_at
                ) VALUES (%s, %s, %s, 'running', 1, now())
                ON CONFLICT (prediction_run_key, target_issue) DO UPDATE
                SET evaluation_run_key = EXCLUDED.evaluation_run_key,
                    status = 'running',
                    attempt_count = forward_evaluation_runs.attempt_count + 1,
                    error = '{}'::jsonb,
                    started_at = now(), completed_at = NULL, updated_at = now()
                """,
                (evaluation_run_key, prediction_run_key, target_issue),
            )
        return True

    def _record_failure(
        self,
        prediction_run_key: str,
        evaluation_run_key: str,
        error: dict[str, str],
    ) -> None:
        encoded = json.dumps(error, ensure_ascii=False)
        with self.connection_factory() as conn:
            conn.execute(
                """
                UPDATE forward_evaluation_runs
                SET status = 'failed', error = %s::jsonb,
                    completed_at = now(), updated_at = now()
                WHERE evaluation_run_key = %s
                """,
                (encoded, evaluation_run_key),
            )
            conn.execute(
                """
                UPDATE forward_prediction_runs
                SET status = 'evaluation_failed', failure = %s::jsonb,
                    updated_at = now()
                WHERE prediction_run_key = %s
                """,
                (encoded, prediction_run_key),
            )
