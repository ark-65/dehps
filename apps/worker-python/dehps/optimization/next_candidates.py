from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.models.frequency_ranker import (
    FrequencyRankerConfig,
    HistoryDraw,
    history_draw_date,
    history_issue,
    history_numbers,
    infer_next_ssq_draw_date,
)
from dehps.optimization.regime import select_history
from dehps.optimization.weight_kdj import weight_kdj_advice_from_signals
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    build_ranked_universe,
    config_hash,
    fingerprint_history,
    rank_target_grid_with_red5,
    top_candidates_for_next,
)
from dehps.storage.postgres_store import (
    CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
    TOTAL_SSQ_RED_COMBINATIONS,
    ensure_training_supervisor_best_schema,
    load_history_with_dates,
    load_recent_training_weight_signals,
    replace_training_next_candidates_current,
)

STATIC_100_LINE_KEY = "static_100"
DYNAMIC_KDJ_LINE_KEY = "dynamic_kdj"
STATIC_100_LINE_LABEL = "100-period static training"
DYNAMIC_KDJ_LINE_LABEL = "Dynamic KDJ adjustment"
PRIMARY_CONFIG_FIELDS = frozenset({"structural_weight", "frequency_weight", "omission_weight"})
CONTEXT_CONFIG_FIELDS = tuple(field for field in CONFIG_WEIGHT_FIELDS if field not in PRIMARY_CONFIG_FIELDS)
REGRESSION_PROTOCOL_VERSION = "dual-line-regression-100-v1"


def next_issue_hint(issue: str | None) -> str:
    if not issue or not issue.isdigit():
        return ""
    return str(int(issue) + 1)


def issue_less_than(left: object, right: object) -> bool:
    left_text = str(left)
    right_text = str(right)
    try:
        return int(left_text) < int(right_text)
    except ValueError:
        return left_text < right_text


def issue_sort_key(value: object) -> tuple[int, int | str]:
    text = str(value)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def config_values(config: FrequencyRankerConfig) -> dict[str, float]:
    return {field: float(getattr(config, field)) for field in CONFIG_WEIGHT_FIELDS}


def clamp_frequency_config(config: FrequencyRankerConfig) -> FrequencyRankerConfig:
    values = config_values(config)
    for field in PRIMARY_CONFIG_FIELDS:
        values[field] = min(1.25, max(0.0, values[field]))
    for field in CONTEXT_CONFIG_FIELDS:
        values[field] = min(0.30, max(-0.30, values[field]))
    return FrequencyRankerConfig(**values)


def training_freshness_metadata(
    *,
    training_as_of_issue: str | None,
    latest_issue: str | None,
    training_history_fingerprint: str | None,
    current_history_fingerprint: str | None,
) -> dict[str, Any]:
    training_issue = str(training_as_of_issue or "")
    current_issue = str(latest_issue or "")
    issue_lag: int | None = None
    if training_issue.isdigit() and current_issue.isdigit():
        issue_lag = int(current_issue) - int(training_issue)
    issue_matches = bool(training_issue and current_issue and training_issue == current_issue)
    history_matches = bool(
        training_history_fingerprint
        and current_history_fingerprint
        and training_history_fingerprint == current_history_fingerprint
    )
    return {
        "status": "current" if issue_matches and history_matches else "stale",
        "training_issue_matches_current": issue_matches,
        "training_history_matches_current": history_matches,
        "training_issue_lag": issue_lag,
    }


def training_summary_sort_key(summary: dict[str, Any]) -> tuple:
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    reward = summary.get("reward") if isinstance(summary.get("reward"), dict) else {}
    rank_quality = summary.get("rank_quality") if isinstance(summary.get("rank_quality"), dict) else {}
    baseline_overlap = summary.get("baseline_overlap") if isinstance(summary.get("baseline_overlap"), dict) else {}
    baseline_bands = baseline_overlap.get("bands") if isinstance(baseline_overlap.get("bands"), dict) else {}
    top_10000_overlap = baseline_bands.get("top_10000") if isinstance(baseline_bands.get("top_10000"), dict) else {}
    top_1000_overlap = baseline_bands.get("top_1000") if isinstance(baseline_bands.get("top_1000"), dict) else {}
    return (
        int(summary.get("top_100_hits") or 0),
        int(summary.get("top_1000_hits") or 0),
        int(top_1000_overlap.get("unique_hit_count") or 0),
        float(reward.get("objectiveScore") or 0),
        -int(rank_quality.get("tail_over_1000000_count") or 0),
        -int(rank_quality.get("tail_over_900000_count") or 0),
        -int(rank_quality.get("tail_over_750000_count") or 0),
        int(top_10000_overlap.get("unique_hit_count") or 0),
        -int(top_10000_overlap.get("overlap_hit_count") or 0),
        int(summary.get("top_10000_hits") or 0),
        int(rank_quality.get("top_50000_hits") or 0),
        int(rank_quality.get("top_100000_hits") or 0),
        int(rank_quality.get("top_250000_hits") or 0),
        int(rank_quality.get("top_500000_hits") or 0),
        int(red5.get("top_100_hits") or 0),
        int(red5.get("top_1000_hits") or 0),
        int(red5.get("top_10000_hits") or 0),
        -float(summary.get("worst_rank") or 0),
        -float(summary.get("median_rank") or 0),
        -float(summary.get("best_rank") or 0),
    )


def int_metric(source: dict[str, Any], key: str) -> int:
    return int(source.get(key) or 0)


def numeric_metric(source: dict[str, Any], key: str) -> float | None:
    value = source.get(key)
    return float(value) if isinstance(value, int | float) else None


def compact_static_regression_summary(best: dict[str, Any]) -> dict[str, Any]:
    summary = best.get("summary") if isinstance(best.get("summary"), dict) else {}
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    configured_eval_window = int(best.get("eval_window") or 0)
    evaluated_draws = int(summary.get("evaluated_draws") or configured_eval_window)
    return {
        "status": "evaluated" if evaluated_draws else "unknown",
        "protocol": REGRESSION_PROTOCOL_VERSION,
        "source": "training_supervisor_best",
        "line_key": STATIC_100_LINE_KEY,
        "eval_window": evaluated_draws,
        "configured_eval_window": configured_eval_window,
        "top_100_hits": int_metric(summary, "top_100_hits"),
        "top_1000_hits": int_metric(summary, "top_1000_hits"),
        "top_10000_hits": int_metric(summary, "top_10000_hits"),
        "median_rank": numeric_metric(summary, "median_rank"),
        "best_rank": int_metric(summary, "best_rank") or None,
        "worst_rank": int_metric(summary, "worst_rank") or None,
        "red5": {
            "eval_window": evaluated_draws,
            "top_100_hits": int_metric(red5, "top_100_hits"),
            "top_1000_hits": int_metric(red5, "top_1000_hits"),
            "top_10000_hits": int_metric(red5, "top_10000_hits"),
            "median_rank": numeric_metric(red5, "median_rank"),
            "best_rank": int_metric(red5, "best_rank") or None,
        },
        "fallback_target_count": 0,
        "changed_target_count": 0,
        "leakage_passed": True,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
    }


def regression_target_indexes(*, history_len: int, train_window: int, eval_window: int) -> range:
    if train_window < 1:
        raise ValueError("train_window must be at least 1")
    if eval_window < 1:
        raise ValueError("eval_window must be at least 1")
    if history_len <= train_window:
        return range(0)
    return range(max(train_window, history_len - eval_window), history_len)


def dynamic_kdj_regression_summary(
    *,
    history: list[HistoryDraw],
    base_config: FrequencyRankerConfig,
    signals: list[dict[str, Any]],
    ranked_universe: Any,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
) -> dict[str, Any]:
    indexes = list(regression_target_indexes(history_len=len(history), train_window=train_window, eval_window=eval_window))
    if not indexes:
        return {
            "status": "skipped_insufficient_history",
            "protocol": REGRESSION_PROTOCOL_VERSION,
            "source": "dynamic_kdj_per_target",
            "line_key": DYNAMIC_KDJ_LINE_KEY,
            "eval_window": 0,
            "configured_eval_window": eval_window,
            "top_100_hits": 0,
            "top_1000_hits": 0,
            "top_10000_hits": 0,
            "red5": {
                "eval_window": 0,
                "top_100_hits": 0,
                "top_1000_hits": 0,
                "top_10000_hits": 0,
                "median_rank": None,
                "best_rank": None,
            },
            "fallback_target_count": 0,
            "changed_target_count": 0,
            "leakage_passed": True,
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        }

    exact_ranks: list[int] = []
    red5_ranks: list[int] = []
    fallback_target_count = 0
    changed_target_count = 0
    leakage_passed = True
    latest_signal_issue: str | None = None

    for target_index in indexes:
        target_draw = history[target_index]
        target_issue = history_issue(target_draw)
        dynamic_config, dynamic_metadata = dynamic_kdj_config_for_next(
            base_config=base_config,
            signals=signals,
            target_issue=target_issue,
        )
        if dynamic_metadata["fallback_static_base"]:
            fallback_target_count += 1
        else:
            changed_target_count += 1
        leakage_passed = leakage_passed and bool(dynamic_metadata["leakage_passed"])
        signal_issue = dynamic_metadata.get("latest_signal_issue")
        if signal_issue is not None and (latest_signal_issue is None or issue_sort_key(signal_issue) > issue_sort_key(latest_signal_issue)):
            latest_signal_issue = str(signal_issue)

        train_start = 0 if train_mode == "expanding" else max(0, target_index - train_window)
        train_history = history[train_start:target_index]
        ranked_target = rank_target_grid_with_red5(
            target_numbers=history_numbers(target_draw),
            train_history=train_history,
            configs=(dynamic_config,),
            ranked_universe=ranked_universe,
            target_draw_date=history_draw_date(target_draw),
            workers=1,
            pool=None,
        )[0]
        rank, _score, red5_match = ranked_target
        exact_ranks.append(int(rank))
        if red5_match is not None:
            red5_ranks.append(int(red5_match.rank))

    return {
        "status": "evaluated",
        "protocol": REGRESSION_PROTOCOL_VERSION,
        "source": "dynamic_kdj_per_target",
        "line_key": DYNAMIC_KDJ_LINE_KEY,
        "eval_window": len(exact_ranks),
        "configured_eval_window": eval_window,
        "top_100_hits": sum(rank <= 100 for rank in exact_ranks),
        "top_1000_hits": sum(rank <= 1000 for rank in exact_ranks),
        "top_10000_hits": sum(rank <= 10000 for rank in exact_ranks),
        "median_rank": median(exact_ranks) if exact_ranks else None,
        "best_rank": min(exact_ranks) if exact_ranks else None,
        "worst_rank": max(exact_ranks) if exact_ranks else None,
        "red5": {
            "eval_window": len(exact_ranks),
            "top_100_hits": sum(rank <= 100 for rank in red5_ranks),
            "top_1000_hits": sum(rank <= 1000 for rank in red5_ranks),
            "top_10000_hits": sum(rank <= 10000 for rank in red5_ranks),
            "median_rank": median(red5_ranks) if red5_ranks else None,
            "best_rank": min(red5_ranks) if red5_ranks else None,
        },
        "fallback_target_count": fallback_target_count,
        "changed_target_count": changed_target_count,
        "leakage_passed": leakage_passed,
        "latest_signal_issue": latest_signal_issue,
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        "top_n": top_n,
    }


def resolve_latest_training_run_id(conn: Connection, run_id: str | None = None) -> str | None:
    if run_id:
        return run_id
    with conn.cursor() as cur:
        row = cur.execute(
            """
            SELECT run_id
            FROM training_round_results
            ORDER BY created_at DESC, round_index DESC
            LIMIT 1
            """
        ).fetchone()
    return str(row[0]) if row else None


def training_best_candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    summary = row.get("best_summary") if isinstance(row.get("best_summary"), dict) else {}
    config = summary.get("config") if isinstance(summary.get("config"), dict) else row.get("best_config")
    if not isinstance(config, dict) or not config:
        return None
    return {
        "run_id": str(row["run_id"]),
        "source_round_index": int(row["round_index"]),
        "train_mode": str(row["train_mode"]),
        "train_window": int(row["train_window"]),
        "eval_window": int(row["eval_window"]),
        "top_n": int(row["top_n"]),
        "training_as_of_issue": str(row["as_of_issue"]),
        "training_history_fingerprint": str(row["history_fingerprint"]),
        "history_scope": str(row.get("history_scope") or ""),
        "regime_years": int(row.get("regime_years") or 0),
        "training_regime_start_date": row.get("regime_start_date").isoformat()
        if row.get("regime_start_date")
        else "",
        "summary": summary,
        "config": {key: float(value) for key, value in config.items() if isinstance(value, int | float)},
    }


def load_training_supervisor_best_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    ensure_training_supervisor_best_schema(conn)
    if run_id:
        query = """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_supervisor_best
            WHERE run_id = %s
            ORDER BY round_index DESC, updated_at DESC
            LIMIT 1
        """
        params: tuple[Any, ...] = (run_id,)
    else:
        query = """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_supervisor_best
            ORDER BY updated_at DESC
            LIMIT 1
        """
        params = ()
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(query, params).fetchone()
    if not row:
        return None
    return training_best_candidate_from_row(row)


def load_best_training_summary(conn: Connection, run_id: str | None = None) -> dict[str, Any] | None:
    checkpoint_best = load_training_supervisor_best_summary(conn, run_id)
    if checkpoint_best is not None:
        return checkpoint_best
    resolved_run_id = resolve_latest_training_run_id(conn, run_id)
    if not resolved_run_id:
        return None
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT run_id, round_index, train_mode, train_window, eval_window, top_n,
                   as_of_issue, history_fingerprint, history_scope, regime_years, regime_start_date,
                   best_summary, best_config, updated_at
            FROM training_round_results
            WHERE run_id = %s
            ORDER BY round_index ASC
            """,
            (resolved_run_id,),
        ).fetchall()
    best: dict[str, Any] | None = None
    for row in rows:
        candidate = training_best_candidate_from_row(row)
        if candidate is None:
            continue
        if best is None or training_summary_sort_key(candidate["summary"]) > training_summary_sort_key(best["summary"]):
            best = candidate
    return best


def load_current_history_for_training_scope(conn: Connection, best: dict[str, Any]) -> tuple[list, dict[str, Any]]:
    scope = str(best.get("history_scope") or "")
    regime_years = int(best.get("regime_years") or 0)
    if scope in {"full_history_audit", "current_regime_default"} and regime_years >= 1:
        selection = select_history(conn, scope=scope, regime_years=regime_years)
        return selection.dated_history, {
            "history_scope": selection.scope,
            "regime_years": selection.regime_years,
            "regime_start_date": selection.start_date.isoformat() if selection.start_date else "",
            "freshness_mode": "training_scope",
        }
    return load_history_with_dates(conn), {
        "history_scope": scope,
        "regime_years": regime_years,
        "regime_start_date": "",
        "freshness_mode": "legacy_full_history",
    }


def build_training_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    best = load_best_training_summary(conn, run_id)
    if best is None:
        raise RuntimeError("no training_round_results best config is available")
    history, history_context = load_current_history_for_training_scope(conn, best)
    if not history:
        raise RuntimeError("ssq_history is empty")
    latest_issue = str(history[-1][0])
    target_draw_date = infer_next_ssq_draw_date(history)
    current_history_fingerprint = fingerprint_history(history)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    config = FrequencyRankerConfig(**best["config"])
    matrix = ranked_universe or build_ranked_universe()
    resolved_top_n = min(top_n, len(matrix))
    candidates = top_candidates_for_next(
        history=history if best["train_mode"] == "expanding" else history[-best["train_window"] :],
        top_n=resolved_top_n,
        config=config,
        target_draw_date=target_draw_date,
        ranked_universe=matrix,
    )
    regression_summary = compact_static_regression_summary(best)
    metadata = {
        "line_key": STATIC_100_LINE_KEY,
        "line_label": STATIC_100_LINE_LABEL,
        "line_kind": "static",
        "snapshot_key": f"training-next-{latest_issue}-{config_hash(config)[:12]}",
        "run_id": best["run_id"],
        "source_round_index": best["source_round_index"],
        "as_of_issue": latest_issue,
        "next_issue": next_issue_hint(latest_issue),
        "next_draw_date": target_draw_date.isoformat() if target_draw_date else None,
        "train_mode": best["train_mode"],
        "train_window": best["train_window"],
        "eval_window": best["eval_window"],
        "top_n": resolved_top_n,
        "history_fingerprint": current_history_fingerprint,
        "training_as_of_issue": best["training_as_of_issue"],
        "training_history_fingerprint": best["training_history_fingerprint"],
        "history_scope": history_context["history_scope"],
        "regime_years": history_context["regime_years"],
        "regime_start_date": history_context["regime_start_date"],
        "training_regime_start_date": best.get("training_regime_start_date") or "",
        "freshness_mode": history_context["freshness_mode"],
        "training_freshness": training_freshness_metadata(
            training_as_of_issue=best["training_as_of_issue"],
            latest_issue=latest_issue,
            training_history_fingerprint=best["training_history_fingerprint"],
            current_history_fingerprint=current_history_fingerprint,
        ),
        "config_hash": config_hash(config),
        "config": best["config"],
        "prediction_metadata": {
            "line_key": STATIC_100_LINE_KEY,
            "line_label": STATIC_100_LINE_LABEL,
            "protocol": "static_training_best",
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
            "regression_100": regression_summary,
            "gauss_guardrail": {
                "sample_space": TOTAL_SSQ_RED_COMBINATIONS,
                "as_of_issue": latest_issue,
                "next_issue": next_issue_hint(latest_issue),
                "leakage_boundary": "snapshot uses history through as_of_issue only",
                "regression_window": regression_summary["eval_window"],
            },
            "riemann_guardrail": {
                "shared_history_space": True,
                "shared_candidate_universe": True,
                "structural_change": "none_static_best_config",
            },
            "fallback_static_base": False,
        },
        "generated_at": generated_at,
        "candidate_count": len(candidates),
    }
    return {"metadata": metadata, "candidates": candidates}


def dynamic_kdj_config_for_next(
    *,
    base_config: FrequencyRankerConfig,
    signals: list[dict[str, Any]],
    target_issue: str,
    min_objective_delta: float = 0.0,
    min_abs_offset: float = 0.005,
    slope_window: int = 3,
    neutral_band: float = 5.0,
) -> tuple[FrequencyRankerConfig, dict[str, Any]]:
    eligible = [signal for signal in signals if issue_less_than(signal.get("issue"), target_issue)]
    excluded = len(signals) - len(eligible)
    advice = weight_kdj_advice_from_signals(
        eligible,
        allowed_fields=CONFIG_WEIGHT_FIELDS,
        min_objective_delta=min_objective_delta,
        min_abs_offset=min_abs_offset,
        slope_window=slope_window,
        neutral_band=neutral_band,
    )
    values = config_values(base_config)
    applied_offsets: dict[str, float] = {}
    applied_fields: set[str] = set()
    for item in advice:
        if item.decision not in {"selected", "downweighted"} or not item.applied_offset:
            continue
        if item.weight_name in applied_fields:
            continue
        applied_fields.add(item.weight_name)
        offset = float(item.applied_offset)
        values[item.weight_name] = float(values[item.weight_name]) + offset
        applied_offsets[item.weight_name] = offset

    dynamic_config = clamp_frequency_config(FrequencyRankerConfig(**values))
    latest_signal_issue = max(
        (str(signal.get("issue") or "") for signal in eligible),
        key=issue_sort_key,
        default=None,
    )
    leakage_passed = all(issue_less_than(signal.get("issue"), target_issue) for signal in eligible)
    if latest_signal_issue is not None:
        leakage_passed = leakage_passed and issue_less_than(latest_signal_issue, target_issue)
    metadata = {
        "thresholds": {
            "min_objective_delta": min_objective_delta,
            "min_abs_offset": min_abs_offset,
            "slope_window": slope_window,
            "neutral_band": neutral_band,
        },
        "signal_count": len(signals),
        "eligible_signal_count": len(eligible),
        "excluded_signal_count": excluded,
        "latest_signal_issue": latest_signal_issue,
        "leakage_passed": leakage_passed,
        "fallback_static_base": not bool(applied_offsets),
        "applied_offsets": {field: round(value, 8) for field, value in sorted(applied_offsets.items())},
        "advice": [item.as_dict() for item in advice],
    }
    return dynamic_config, metadata


def build_dynamic_kdj_next_candidate_snapshot(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    best = load_best_training_summary(conn, run_id)
    if best is None:
        raise RuntimeError("no training_round_results best config is available")
    history, history_context = load_current_history_for_training_scope(conn, best)
    if not history:
        raise RuntimeError("ssq_history is empty")
    latest_issue = str(history[-1][0])
    next_issue = next_issue_hint(latest_issue)
    target_draw_date = infer_next_ssq_draw_date(history)
    current_history_fingerprint = fingerprint_history(history)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base_config = FrequencyRankerConfig(**best["config"])
    signals = load_recent_training_weight_signals(
        conn,
        signal_run_id=signal_run_id or CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
        as_of_issue=latest_issue,
        train_mode=best["train_mode"],
        train_window=best["train_window"],
        top_n=best["top_n"],
        limit=1000,
    )
    dynamic_config, dynamic_metadata = dynamic_kdj_config_for_next(
        base_config=base_config,
        signals=signals,
        target_issue=next_issue,
    )
    matrix = ranked_universe or build_ranked_universe()
    regression_summary = dynamic_kdj_regression_summary(
        history=history,
        base_config=base_config,
        signals=signals,
        ranked_universe=matrix,
        train_mode=best["train_mode"],
        train_window=best["train_window"],
        eval_window=best["eval_window"],
        top_n=best["top_n"],
    )
    resolved_top_n = min(top_n, len(matrix))
    candidates = top_candidates_for_next(
        history=history if best["train_mode"] == "expanding" else history[-best["train_window"] :],
        top_n=resolved_top_n,
        config=dynamic_config,
        target_draw_date=target_draw_date,
        ranked_universe=matrix,
    )
    dynamic_config_values = config_values(dynamic_config)
    metadata = {
        "line_key": DYNAMIC_KDJ_LINE_KEY,
        "line_label": DYNAMIC_KDJ_LINE_LABEL,
        "line_kind": "dynamic_kdj",
        "snapshot_key": f"training-next-dynamic-kdj-{latest_issue}-{config_hash(dynamic_config)[:12]}",
        "run_id": best["run_id"],
        "source_round_index": best["source_round_index"],
        "as_of_issue": latest_issue,
        "next_issue": next_issue,
        "next_draw_date": target_draw_date.isoformat() if target_draw_date else None,
        "train_mode": best["train_mode"],
        "train_window": best["train_window"],
        "eval_window": best["eval_window"],
        "top_n": resolved_top_n,
        "history_fingerprint": current_history_fingerprint,
        "training_as_of_issue": best["training_as_of_issue"],
        "training_history_fingerprint": best["training_history_fingerprint"],
        "history_scope": history_context["history_scope"],
        "regime_years": history_context["regime_years"],
        "regime_start_date": history_context["regime_start_date"],
        "training_regime_start_date": best.get("training_regime_start_date") or "",
        "freshness_mode": history_context["freshness_mode"],
        "training_freshness": training_freshness_metadata(
            training_as_of_issue=best["training_as_of_issue"],
            latest_issue=latest_issue,
            training_history_fingerprint=best["training_history_fingerprint"],
            current_history_fingerprint=current_history_fingerprint,
        ),
        "config_hash": config_hash(dynamic_config),
        "config": dynamic_config_values,
        "prediction_metadata": {
            "line_key": DYNAMIC_KDJ_LINE_KEY,
            "line_label": DYNAMIC_KDJ_LINE_LABEL,
            "protocol": "dynamic_kdj_next_issue",
            "base_config_hash": config_hash(base_config),
            "base_config": best["config"],
            "signal_run_id": signal_run_id or CANONICAL_TRAINING_WEIGHT_SIGNAL_RUN_ID,
            "target_issue": next_issue,
            "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
            "regression_100": regression_summary,
            **dynamic_metadata,
            "gauss_guardrail": {
                "sample_space": TOTAL_SSQ_RED_COMBINATIONS,
                "as_of_issue": latest_issue,
                "next_issue": next_issue,
                "leakage_boundary": "KDJ signals must have issue < next_issue",
                "leakage_passed": dynamic_metadata["leakage_passed"],
                "regression_window": regression_summary["eval_window"],
                "regression_leakage_passed": regression_summary["leakage_passed"],
            },
            "riemann_guardrail": {
                "shared_history_space": True,
                "shared_candidate_universe": True,
                "structural_change": "same base config plus per-issue KDJ weight offsets",
            },
        },
        "generated_at": generated_at,
        "candidate_count": len(candidates),
    }
    return {"metadata": metadata, "candidates": candidates}


def refresh_training_next_candidates_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
) -> dict[str, Any]:
    snapshot = build_training_next_candidate_snapshot(conn, run_id=run_id, top_n=top_n, ranked_universe=ranked_universe)
    replace_training_next_candidates_current(
        conn,
        metadata=snapshot["metadata"],
        candidates=snapshot["candidates"],
    )
    return snapshot["metadata"]


def refresh_dynamic_kdj_next_candidates_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
) -> dict[str, Any]:
    snapshot = build_dynamic_kdj_next_candidate_snapshot(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=ranked_universe,
        signal_run_id=signal_run_id,
    )
    replace_training_next_candidates_current(
        conn,
        metadata=snapshot["metadata"],
        candidates=snapshot["candidates"],
    )
    return snapshot["metadata"]


def refresh_training_prediction_lines_current(
    conn: Connection,
    *,
    run_id: str | None = None,
    top_n: int = 10000,
    ranked_universe: Any | None = None,
    signal_run_id: str | None = None,
) -> dict[str, Any]:
    static_metadata = refresh_training_next_candidates_current(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=ranked_universe,
    )
    dynamic_metadata = refresh_dynamic_kdj_next_candidates_current(
        conn,
        run_id=run_id,
        top_n=top_n,
        ranked_universe=ranked_universe,
        signal_run_id=signal_run_id,
    )
    return {
        "status": "ready",
        "lines": {
            STATIC_100_LINE_KEY: static_metadata,
            DYNAMIC_KDJ_LINE_KEY: dynamic_metadata,
        },
    }
