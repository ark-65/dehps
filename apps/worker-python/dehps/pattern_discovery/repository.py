from __future__ import annotations

import json
import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.pattern_discovery.models import (
    PatternCandidate,
    PatternDecision,
    PatternLifecycleStatus,
    PatternSearchCycle,
    PatternValidation,
    PatternValidationWindow,
    SynthesizedFeature,
    SynthesizedStrategy,
    jsonable,
    stable_hash,
)
from dehps.storage.postgres_store import ensure_pattern_discovery_schema, load_history


ConnectionFactory = Callable[[], AbstractContextManager[Connection[Any]]]


def _json(value: object) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _row_json(row: dict[str, Any], key: str) -> dict[str, Any]:
    value = row.get(key)
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return {}


def _pattern_from_json(value: dict[str, Any]) -> PatternCandidate:
    payload = dict(value)
    if "lifecycle_status" in payload and not isinstance(payload["lifecycle_status"], PatternLifecycleStatus):
        payload["lifecycle_status"] = PatternLifecycleStatus(payload["lifecycle_status"])
    if "leakage_risks" in payload:
        payload["leakage_risks"] = tuple(payload["leakage_risks"])
    if "source_artifacts" in payload:
        payload["source_artifacts"] = tuple(payload["source_artifacts"])
    return PatternCandidate(**payload)


class PatternDiscoveryRepository:
    def __init__(self, connection_factory: ConnectionFactory = get_connection) -> None:
        self.connection_factory = connection_factory

    def ensure_schema(self) -> None:
        with self.connection_factory() as conn:
            ensure_pattern_discovery_schema(conn)

    def load_history(self, *, limit: int | None = None) -> tuple[tuple[str, tuple[int, ...]], ...]:
        with self.connection_factory() as conn:
            history = load_history(conn)
        if limit is not None:
            history = history[-limit:]
        return tuple((str(issue), tuple(numbers)) for issue, numbers in history)

    def list_patterns(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        status: PatternLifecycleStatus | None = None,
        family: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status is not None:
            clauses.append("lifecycle_status = %s")
            params.append(status.value)
        if family is not None:
            clauses.append("pattern_family = %s")
            params.append(family)
        where = "" if not clauses else "WHERE " + " AND ".join(clauses)
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                f"""
                SELECT *
                FROM discovered_patterns
                {where}
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_pattern(self, pattern_key: str) -> PatternCandidate:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "SELECT pattern_json FROM discovered_patterns WHERE pattern_key = %s",
                (pattern_key,),
            ).fetchone()
        if row is None:
            raise KeyError(f"pattern not found: {pattern_key}")
        return _pattern_from_json(dict(row["pattern_json"]))

    def existing_pattern_summaries(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            rows = cursor.execute(
                """
                SELECT pattern_key, pattern_family, formula_hash, parameters_json AS parameters,
                       lifecycle_status
                FROM discovered_patterns
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_pattern(self, pattern: PatternCandidate, *, code_commit: str | None = None) -> PatternCandidate:
        commit = code_commit or os.environ.get("GIT_COMMIT") or "unknown"
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                """
                INSERT INTO discovered_patterns (
                  pattern_key, pattern_family, pattern_type, formula_hash, lifecycle_status,
                  history_fingerprint, legal_universe_fingerprint, search_issue_range_json,
                  formula_json, parameters_json, pattern_json, parent_pattern_key,
                  multiplicity_family, generator_version, code_commit, metadata_json
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                  %s::jsonb, %s, %s, %s, %s, %s::jsonb
                )
                ON CONFLICT (formula_hash) DO NOTHING
                RETURNING pattern_json
                """,
                (
                    pattern.pattern_key,
                    pattern.pattern_family,
                    pattern.pattern_type or pattern.pattern_family,
                    pattern.formula_hash,
                    pattern.lifecycle_status.value,
                    pattern.history_fingerprint,
                    pattern.legal_universe_fingerprint,
                    _json(pattern.search_issue_range),
                    _json(pattern.formula),
                    _json(pattern.parameters),
                    _json(pattern),
                    pattern.parent_pattern_key,
                    pattern.multiplicity_family,
                    pattern.generator_version,
                    commit,
                    _json(pattern.metadata),
                ),
            ).fetchone()
            if row is None:
                row = cursor.execute(
                    "SELECT pattern_json FROM discovered_patterns WHERE formula_hash = %s",
                    (pattern.formula_hash,),
                ).fetchone()
        assert row is not None
        return _pattern_from_json(dict(row["pattern_json"]))

    def append_observations(self, pattern: PatternCandidate) -> int:
        inserted = 0
        with self.connection_factory() as conn:
            for issue in pattern.source_artifacts:
                key = f"observation-{stable_hash((pattern.pattern_key, issue, pattern.observed_support))[:16]}"
                conn.execute(
                    """
                    INSERT INTO pattern_observations (
                      observation_key, pattern_key, issue, observed_support, expected_support, observation_json
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (observation_key) DO NOTHING
                    """,
                    (
                        key,
                        pattern.pattern_key,
                        issue,
                        pattern.observed_support,
                        pattern.expected_support,
                        _json({"source": "pattern_candidate", "formula_hash": pattern.formula_hash}),
                    ),
                )
                inserted += 1
        return inserted

    def append_validation(self, validation: PatternValidation) -> PatternValidation:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            existing = cursor.execute(
                "SELECT frozen_threshold_json, significance_json FROM pattern_validations WHERE validation_key = %s",
                (validation.validation_key,),
            ).fetchone()
            if existing is not None:
                if dict(existing["frozen_threshold_json"]) != jsonable(validation.frozen_threshold):
                    raise ValueError("frozen validation threshold is immutable")
                return validation
            cursor.execute(
                """
                INSERT INTO pattern_validations (
                  validation_key, pattern_key, window_type, decision, issue_range_json,
                  frozen_threshold_json, significance_json, immutable
                ) VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    validation.validation_key,
                    validation.pattern_key,
                    validation.window.value,
                    validation.decision.value,
                    _json(validation.issue_range),
                    _json(validation.frozen_threshold),
                    _json(validation.significance),
                    validation.immutable,
                ),
            )
        return validation

    def append_feature(self, feature: SynthesizedFeature) -> SynthesizedFeature:
        pattern_key = feature.source_pattern_keys[0]
        with self.connection_factory() as conn:
            conn.execute(
                """
                INSERT INTO synthesized_features (
                  feature_key, pattern_key, formula_hash, feature_json
                ) VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (feature_key) DO NOTHING
                """,
                (feature.feature_key, pattern_key, stable_hash(feature.formula), _json(feature)),
            )
        return feature

    def append_strategy(self, strategy: SynthesizedStrategy) -> SynthesizedStrategy:
        feature_key = strategy.source_feature_keys[0]
        with self.connection_factory() as conn:
            conn.execute(
                """
                INSERT INTO synthesized_strategies (
                  strategy_key, feature_key, strategy_type, strategy_json
                ) VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (strategy_key) DO NOTHING
                """,
                (strategy.strategy_key, feature_key, strategy.strategy_type.value, _json(strategy)),
            )
        return strategy

    def append_cycle(self, cycle: PatternSearchCycle) -> PatternSearchCycle:
        with self.connection_factory() as conn:
            conn.execute(
                """
                INSERT INTO pattern_search_cycles (
                  cycle_key, status, search_issue_range_json, budget_json,
                  discovered_count, accepted_count, result_json
                ) VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb)
                ON CONFLICT (cycle_key) DO NOTHING
                """,
                (
                    cycle.cycle_key,
                    cycle.status,
                    _json(cycle.search_issue_range),
                    _json(cycle.budget),
                    len(cycle.patterns),
                    len(cycle.strategies),
                    _json(cycle),
                ),
            )
        return cycle

    def summary(self) -> dict[str, Any]:
        with self.connection_factory() as conn, conn.cursor(row_factory=dict_row) as cursor:
            exists = cursor.execute("SELECT to_regclass('public.discovered_patterns') AS table_name").fetchone()
            if not exists or not exists["table_name"]:
                return {"enabled": False}
            counts = cursor.execute(
                """
                SELECT
                  count(*)::int AS pattern_count,
                  count(*) FILTER (WHERE lifecycle_status = 'discovered')::int AS discovered_count,
                  count(*) FILTER (WHERE lifecycle_status = 'screened')::int AS screened_count,
                  count(*) FILTER (WHERE lifecycle_status = 'frozen_supported')::int AS frozen_supported_count,
                  count(*) FILTER (WHERE lifecycle_status IN ('frozen_rejected', 'forward_rejected'))::int AS rejected_count
                FROM discovered_patterns
                """
            ).fetchone()
            features = cursor.execute("SELECT count(*)::int AS count FROM synthesized_features").fetchone()
            strategies = cursor.execute("SELECT count(*)::int AS count FROM synthesized_strategies").fetchone()
        return {
            "enabled": True,
            **dict(counts or {}),
            "feature_count": int(features["count"] if features else 0),
            "strategy_count": int(strategies["count"] if strategies else 0),
        }
