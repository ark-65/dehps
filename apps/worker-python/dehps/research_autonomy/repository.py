from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ContextManager

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection

if TYPE_CHECKING:
    from dehps.research_autonomy.context import ResearchContext


ConnectionFactory = Callable[[], ContextManager[Connection[Any]]]


class ResearchContextRepository:
    """Read-only normalized access to formal Registry records."""

    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self._connection_factory = connection_factory

    def read_registry(self, *, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            families = cursor.execute(
                """
                SELECT family_key, title, mechanism, status, rejection_scope,
                       rejection_reason, reopen_condition
                FROM research_hypothesis_families
                ORDER BY updated_at DESC, id DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
            hypotheses = cursor.execute(
                """
                SELECT h.hypothesis_key, f.family_key, h.title, h.mechanism, h.status,
                       h.baseline_definition_json, h.metric_definition_json,
                       h.metadata_json, h.rejection_scope, h.rejection_reason,
                       h.reopen_condition
                FROM research_hypotheses h
                JOIN research_hypothesis_families f ON f.id = h.family_id
                ORDER BY h.updated_at DESC, h.id DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
            experiments = cursor.execute(
                """
                SELECT e.experiment_key, h.hypothesis_key, e.experiment_type, e.status,
                       COALESCE(e.external_run_id, e.training_run_id) AS run_id,
                       e.report_path, e.config_snapshot_json
                FROM research_hypothesis_experiments e
                JOIN research_hypotheses h ON h.id = e.hypothesis_id
                ORDER BY e.created_at DESC, e.id DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
            evidence = cursor.execute(
                """
                SELECT ev.id AS evidence_id, h.hypothesis_key, e.experiment_key,
                       ev.evidence_type, ev.direction, ev.summary, ev.metrics_json
                FROM research_hypothesis_evidence ev
                JOIN research_hypotheses h ON h.id = ev.hypothesis_id
                LEFT JOIN research_hypothesis_experiments e ON e.id = ev.experiment_id
                ORDER BY ev.observed_at DESC, ev.id DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return {
            "families": [dict(row) for row in families],
            "hypotheses": [self._hypothesis(dict(row)) for row in hypotheses],
            "experiments": [self._experiment(dict(row)) for row in experiments],
            "evidence": [self._evidence(dict(row)) for row in evidence],
        }

    def read_training_rounds(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT run_id, round_index, as_of_issue, improved, objective_policy_version,
                       objective_policy_hash, top_100_hits, top_1000_hits, top_10000_hits,
                       median_rank, best_rank, worst_rank, objective_score, best_summary, prefilter
                FROM training_round_results
                ORDER BY created_at DESC, id DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _hypothesis(row: dict[str, Any]) -> dict[str, Any]:
        baseline = dict(row.pop("baseline_definition_json") or {})
        metrics = dict(row.pop("metric_definition_json") or {})
        metadata = dict(row.pop("metadata_json") or {})
        return {
            **row,
            "input_fields": tuple(metadata.get("input_fields") or ("issue", "draw_date", "red_numbers")),
            "feature_keys": tuple(metadata.get("feature_keys") or baseline.get("feature_keys") or ()),
            "model_keys": tuple(metadata.get("model_keys") or baseline.get("model_keys") or ()),
            "validation_protocol": str(
                metadata.get("validation_protocol") or metrics.get("validation_protocol") or "unspecified"
            ),
        }

    @staticmethod
    def _experiment(row: dict[str, Any]) -> dict[str, Any]:
        row["config_snapshot"] = dict(row.pop("config_snapshot_json") or {})
        return row

    @staticmethod
    def _evidence(row: dict[str, Any]) -> dict[str, Any]:
        row["evidence_id"] = int(row["evidence_id"])
        row["metrics"] = dict(row.pop("metrics_json") or {})
        return row


class ResearchAutonomyArtifactRepository:
    """Explicit JSON artifact I/O; generation remains dry-run unless a path is supplied."""

    def __init__(self, repository_root: Path | None = None) -> None:
        self.root = (repository_root or Path(__file__).resolve().parents[4]).resolve()
        self.default_context_path = self.root / "data/output/research-autonomy/context-latest.json"

    def write_context(self, context: ResearchContext, path: Path | None = None) -> Path:
        target = (path or self.default_context_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {"context_fingerprint": context.fingerprint, "context": asdict(context)},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        return target

    def read_context(self, path: Path | None = None) -> dict[str, Any]:
        target = (path or self.default_context_path).resolve()
        try:
            value = json.loads(target.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read ResearchContext artifact {target}: {exc}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("context"), dict):
            raise ValueError(f"invalid ResearchContext artifact: {target}")
        return value
