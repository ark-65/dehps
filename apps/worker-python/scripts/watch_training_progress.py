from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone, tzinfo
from math import comb, isfinite
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.db import get_connection
from dehps.runtime.heavy_job import describe_heavy_job_owner


ADVISOR_KEYS = (
    "weight_kdj_advisor",
    "ridge_kdj_advisor",
    "neural_kdj_advisor",
    "target_weight_inversion_advisor",
)
ROUND_REPETITION_METRIC_FIELDS = (
    "top_100_hits",
    "top_1000_hits",
    "top_10000_hits",
    "red5_top_100_hits",
    "red5_top_1000_hits",
    "red5_top_10000_hits",
    "median_rank",
    "best_rank",
    "worst_rank",
    "objective_score",
)
DEFAULT_SUPERVISOR_OUTPUT_DIR = ROOT_DIR / "data/output/optimization"
DEFAULT_OUTPUT_DIR = DEFAULT_SUPERVISOR_OUTPUT_DIR / "training-watch"
DEFAULT_ROUND_LIMIT = 5000
DEFAULT_STALE_MINUTES = 30
DEFAULT_ADVISOR_SIGNAL_MAX_ISSUE_LAG = 1
SAFE_FILENAME_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
SAFE_INTEGER_TEXT_PATTERN = re.compile(r"[0-9]+")
MAX_SAFE_FILENAME_COMPONENT_LENGTH = 96
EXPECTED_SSQ_RED_COMBINATION_COUNT = comb(33, 6)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(moment: datetime | None = None) -> str:
    return (moment or utc_now()).strftime("%Y%m%d-%H%M%S")


def isoformat(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_timezone() -> tzinfo:
    return datetime.now().astimezone().tzinfo or timezone.utc


def parse_iso_datetime(value: Any, *, default_timezone: tzinfo = timezone.utc) -> datetime | None:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=default_timezone)
    return moment.astimezone(timezone.utc)


def observed_age_minutes(
    value: Any,
    *,
    now: datetime,
    default_timezone: tzinfo = timezone.utc,
) -> float | None:
    moment = parse_iso_datetime(value, default_timezone=default_timezone)
    if moment is None:
        return None
    return round(max(0.0, (now - moment).total_seconds() / 60.0), 6)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not SAFE_INTEGER_TEXT_PATTERN.fullmatch(text):
            return None
        return int(text)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if isfinite(value) and value.is_integer() else None
    try:
        parsed = int(value)
    except (OverflowError, TypeError, ValueError):
        return None
    try:
        if not isinstance(value, str) and value != parsed:
            return None
    except Exception:
        return None
    return parsed


def positive_int_or_default(value: Any, *, default: int) -> int:
    parsed = safe_int(value)
    return parsed if parsed is not None and parsed > 0 else default


def safe_filename_component(
    value: Any,
    *,
    default: str = "none",
    max_length: int = MAX_SAFE_FILENAME_COMPONENT_LENGTH,
) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return default
    normalized = SAFE_FILENAME_COMPONENT_PATTERN.sub("_", text).strip("_-")
    if not normalized:
        return default
    if max_length <= 0 or len(normalized) <= max_length:
        return normalized
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    prefix_length = max(1, max_length - len(digest) - 1)
    prefix = normalized[:prefix_length].rstrip("_-") or normalized[:prefix_length]
    return f"{prefix}_{digest}"[:max_length]


def markdown_inline_text(value: Any) -> str:
    text = "" if value is None else str(value)
    single_line = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").splitlines())
    return single_line.replace("\\", "\\\\").replace("|", "\\|")


def markdown_inline_code(value: Any) -> str:
    text = "" if value is None else str(value)
    single_line = " ".join(text.replace("\r\n", "\n").replace("\r", "\n").splitlines())
    if not single_line:
        return "``"
    longest_tick_run = max((len(match.group(0)) for match in re.finditer(r"`+", single_line)), default=0)
    fence = "`" * (longest_tick_run + 1)
    padding = " " if single_line.startswith("`") or single_line.endswith("`") else ""
    return f"{fence}{padding}{single_line}{padding}{fence}"


def compact_count_map(value: Any, *, limit: int = 5) -> str:
    if not isinstance(value, dict) or not value:
        return "{}"
    items = sorted(
        value.items(),
        key=lambda item: (-(safe_int(item[1]) or 0), str(item[0])),
    )
    parts = [f"{key}={count}" for key, count in items[:limit]]
    overflow = len(items) - limit
    if overflow > 0:
        parts.append(f"+{overflow} more")
    return ", ".join(parts)


def compact_inline_list(value: Any, *, limit: int = 5) -> str:
    if not isinstance(value, list) or not value:
        return "[]"
    parts = [str(item) for item in value[:limit]]
    overflow = len(value) - limit
    if overflow > 0:
        parts.append(f"+{overflow} more")
    return "[" + ", ".join(parts) + "]"


def compact_observed_fields(fields: list[tuple[str, Any]]) -> str:
    parts = []
    for label, value in fields:
        if value is None or value == "":
            continue
        parts.append(f"{label}={value}")
    return " ".join(parts)


def safe_string_list(value: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list) or limit <= 0:
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def compact_decimal(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    parsed = safe_float(value)
    if parsed is None:
        return "" if value is None else str(value)
    return f"{parsed:.8f}".rstrip("0").rstrip(".")


def canonical_round_signature(value: Any) -> str | None:
    if value is None:
        return None
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def latest_repeat_streak(values: list[str | None]) -> int:
    if not values or values[-1] is None:
        return 0
    latest = values[-1]
    streak = 0
    for value in reversed(values):
        if value != latest:
            break
        streak += 1
    return streak


def summarize_round_repetition(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "not_available",
            "reason": "no_recent_rounds",
            "window_count": 0,
        }

    config_hashes = [canonical_round_signature(row.get("best_config")) for row in rows]
    metric_hashes = [
        canonical_round_signature(
            {field: row.get(field) for field in ROUND_REPETITION_METRIC_FIELDS}
        )
        for row in rows
    ]
    config_counts: dict[str, int] = {}
    for config_hash in config_hashes:
        if config_hash:
            config_counts[config_hash] = config_counts.get(config_hash, 0) + 1
    metric_counts: dict[str, int] = {}
    for metric_hash in metric_hashes:
        if metric_hash:
            metric_counts[metric_hash] = metric_counts.get(metric_hash, 0) + 1

    dominant_config_hash, dominant_config_count = max(
        config_counts.items(),
        key=lambda item: (item[1], item[0]),
        default=(None, 0),
    )
    dominant_metric_hash, dominant_metric_count = max(
        metric_counts.items(),
        key=lambda item: (item[1], item[0]),
        default=(None, 0),
    )
    window_count = len(rows)
    latest_config_streak = latest_repeat_streak(config_hashes)
    latest_metric_streak = latest_repeat_streak(metric_hashes)
    unique_config_count = len(config_counts)
    unique_metric_signature_count = len(metric_counts)
    same_config_repeated = (
        window_count >= 3
        and unique_config_count == 1
        and latest_config_streak == window_count
    )
    same_metrics_repeated = (
        window_count >= 3
        and unique_metric_signature_count == 1
        and latest_metric_streak == window_count
    )
    if same_config_repeated and same_metrics_repeated:
        reason = "same_config_and_metrics_repeated"
    elif same_config_repeated:
        reason = "same_config_repeated"
    elif same_metrics_repeated:
        reason = "same_metrics_repeated"
    else:
        reason = "recent_rounds_vary"

    return {
        "status": "ready",
        "reason": reason,
        "active": reason != "recent_rounds_vary",
        "window_count": window_count,
        "latest_round": safe_int(rows[-1].get("round_index")),
        "observed_config_count": sum(1 for item in config_hashes if item),
        "unique_config_count": unique_config_count,
        "dominant_config_hash": dominant_config_hash,
        "dominant_config_repeat_count": dominant_config_count,
        "latest_config_hash": config_hashes[-1],
        "latest_config_repeat_streak": latest_config_streak,
        "unique_metric_signature_count": unique_metric_signature_count,
        "dominant_metric_signature_hash": dominant_metric_hash,
        "dominant_metric_repeat_count": dominant_metric_count,
        "latest_metric_signature_hash": metric_hashes[-1],
        "latest_metric_repeat_streak": latest_metric_streak,
        "metric_fields": list(ROUND_REPETITION_METRIC_FIELDS),
        "interpretation": (
            "Diagnostic only: repeated historical round outputs are a search-observability "
            "signal, not predictive evidence or a restart decision."
        ),
    }


def random_null_expectation_summary(supervisor_status: dict[str, Any]) -> dict[str, Any]:
    ranked_universe_size = safe_int(supervisor_status.get("ranked_universe_size"))
    eval_window = safe_int(supervisor_status.get("eval_window"))
    top_n = safe_int(supervisor_status.get("top_n"))
    result: dict[str, Any] = {
        "model": "ranked_uniform_per_draw",
        "ranked_universe_size": ranked_universe_size,
        "eval_window": eval_window,
        "bands": {},
    }
    if ranked_universe_size is None or ranked_universe_size <= 0:
        result["status"] = "missing_ranked_universe_size"
        return result

    band_sizes: list[int] = []
    for raw_band_size in (100, 1000, top_n):
        band_size = safe_int(raw_band_size)
        if band_size is None or band_size <= 0 or band_size in band_sizes:
            continue
        band_sizes.append(band_size)

    bands: dict[str, dict[str, Any]] = {}
    for band_size in band_sizes:
        capped_band_size = min(band_size, ranked_universe_size)
        per_draw_probability = capped_band_size / ranked_universe_size
        band: dict[str, Any] = {
            "band_size": capped_band_size,
            "per_draw_probability": round(per_draw_probability, 8),
        }
        if eval_window is not None and eval_window > 0:
            band["expected_eval_hits"] = round(eval_window * per_draw_probability, 6)
        bands[f"top_{band_size}"] = band

    result["status"] = "estimated"
    result["bands"] = bands
    return result


def compact_random_null_expectation(value: Any, *, limit: int = 5) -> str:
    if not isinstance(value, dict):
        return "{}"
    bands = value.get("bands") if isinstance(value.get("bands"), dict) else {}
    if not bands:
        status = value.get("status")
        return f"status={status}" if status else "{}"
    items = sorted(
        bands.items(),
        key=lambda item: safe_int(item[1].get("band_size"))
        if isinstance(item[1], dict)
        else 0,
    )
    parts: list[str] = []
    for label, band in items[:limit]:
        if not isinstance(band, dict):
            continue
        parts.append(
            f"{label}:p={compact_decimal(band.get('per_draw_probability'))},"
            f"eval_expected={compact_decimal(band.get('expected_eval_hits'))}"
        )
    overflow = len(items) - limit
    if overflow > 0:
        parts.append(f"+{overflow} more")
    return "; ".join(parts) if parts else "{}"


def isoformat_date(value: Any) -> str | None:
    if value is None:
        return None
    formatter = getattr(value, "isoformat", None)
    return str(formatter()) if callable(formatter) else str(value)


def load_parser_sync_duplicate_checks() -> dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                history = cur.execute(
                    """
                    WITH checked AS (
                      SELECT
                        issue,
                        draw_date,
                        blue_number,
                        COALESCE(array_length(red_numbers, 1), 0) AS red_length,
                        (
                          SELECT count(*)
                          FROM unnest(red_numbers) AS red(value)
                          WHERE value IS NULL OR value < 1 OR value > 33
                        ) AS invalid_red_value_count,
                        (
                          SELECT count(*)
                          FROM (
                            SELECT value
                            FROM unnest(red_numbers) AS red(value)
                            GROUP BY value
                            HAVING count(*) > 1
                          ) duplicate_values
                        ) AS duplicate_red_value_count
                      FROM ssq_history
                    ),
                    duplicate_issues AS (
                      SELECT COALESCE(sum(issue_count - 1), 0) AS duplicate_issue_count
                      FROM (
                        SELECT issue, count(*) AS issue_count
                        FROM ssq_history
                        GROUP BY issue
                        HAVING count(*) > 1
                      ) issues
                    )
                    SELECT
                      count(*) AS draw_count,
                      min(issue) AS first_issue,
                      max(issue) AS latest_issue,
                      min(draw_date) AS first_draw_date,
                      max(draw_date) AS latest_draw_date,
                      (SELECT duplicate_issue_count FROM duplicate_issues) AS duplicate_issue_count,
                      count(*) FILTER (WHERE red_length != 6) AS invalid_red_length_count,
                      count(*) FILTER (WHERE invalid_red_value_count > 0) AS red_out_of_range_count,
                      count(*) FILTER (WHERE duplicate_red_value_count > 0) AS duplicate_red_numbers_count,
                      count(*) FILTER (
                        WHERE blue_number IS NOT NULL AND (blue_number < 1 OR blue_number > 16)
                      ) AS blue_out_of_range_count
                    FROM checked
                    """
                ).fetchone() or {}
                history_issues = [
                    str(row["issue"])
                    for row in cur.execute(
                        "SELECT issue FROM ssq_history ORDER BY issue"
                    ).fetchall()
                    if row.get("issue")
                ]
                universe = cur.execute(
                    """
                    SELECT
                      count(*) AS combination_count,
                      count(DISTINCT numbers) AS distinct_combination_count,
                      count(*) FILTER (
                        WHERE NOT (
                          COALESCE(array_length(numbers, 1), 0) = 6
                          AND 1 <= n1 AND n1 < n2 AND n2 < n3 AND n3 < n4
                          AND n4 < n5 AND n5 < n6 AND n6 <= 33
                          AND numbers = ARRAY[n1, n2, n3, n4, n5, n6]::smallint[]
                        )
                      ) AS invalid_combination_shape_count
                    FROM ssq_red_combinations
                    """
                ).fetchone() or {}
                latest_sync = cur.execute(
                    """
                    SELECT
                      run_key, source, status, started_at, finished_at, fetched_count,
                      inserted_count, updated_count, skipped_count, conflict_count, error_message
                    FROM ssq_sync_runs
                    ORDER BY started_at DESC, id DESC
                    LIMIT 1
                    """
                ).fetchone()
                conflict_row = cur.execute(
                    "SELECT count(*) AS recorded_data_conflict_count FROM ssq_data_conflicts"
                ).fetchone() or {}
    except Exception as exc:
        return {
            "status": "unavailable",
            "reason": "db_integrity_query_failed",
            "error": str(exc),
        }

    duplicate_issue_count = safe_int(history.get("duplicate_issue_count")) or 0
    invalid_red_length_count = safe_int(history.get("invalid_red_length_count")) or 0
    red_out_of_range_count = safe_int(history.get("red_out_of_range_count")) or 0
    duplicate_red_numbers_count = safe_int(history.get("duplicate_red_numbers_count")) or 0
    blue_out_of_range_count = safe_int(history.get("blue_out_of_range_count")) or 0
    combination_count = safe_int(universe.get("combination_count")) or 0
    distinct_combination_count = safe_int(universe.get("distinct_combination_count")) or 0
    invalid_combination_shape_count = safe_int(universe.get("invalid_combination_shape_count")) or 0
    duplicate_combination_count = max(0, combination_count - distinct_combination_count)
    latest_sync_status = latest_sync.get("status") if isinstance(latest_sync, dict) else None

    history_ok = (
        duplicate_issue_count == 0
        and invalid_red_length_count == 0
        and red_out_of_range_count == 0
        and duplicate_red_numbers_count == 0
        and blue_out_of_range_count == 0
    )
    universe_complete = combination_count == EXPECTED_SSQ_RED_COMBINATION_COUNT
    universe_ok = (
        universe_complete
        and duplicate_combination_count == 0
        and invalid_combination_shape_count == 0
    )
    latest_sync_ok = latest_sync_status not in {"failed", "error"}
    latest_sync_summary = (
        {
            "run_key": latest_sync.get("run_key"),
            "source": latest_sync.get("source"),
            "status": latest_sync_status,
            "started_at": isoformat(latest_sync.get("started_at")),
            "finished_at": isoformat(latest_sync.get("finished_at")),
            "fetched_count": safe_int(latest_sync.get("fetched_count")),
            "inserted_count": safe_int(latest_sync.get("inserted_count")),
            "updated_count": safe_int(latest_sync.get("updated_count")),
            "skipped_count": safe_int(latest_sync.get("skipped_count")),
            "conflict_count": safe_int(latest_sync.get("conflict_count")),
            "error_message": latest_sync.get("error_message"),
        }
        if isinstance(latest_sync, dict)
        else None
    )

    return {
        "status": "checked",
        "ok": history_ok and universe_ok and latest_sync_ok,
        "history_ok": history_ok,
        "history_draw_count": safe_int(history.get("draw_count")) or 0,
        "history_first_issue": history.get("first_issue"),
        "history_latest_issue": history.get("latest_issue"),
        "history_first_draw_date": isoformat_date(history.get("first_draw_date")),
        "history_latest_draw_date": isoformat_date(history.get("latest_draw_date")),
        "_history_issues": history_issues,
        "history_duplicate_issue_count": duplicate_issue_count,
        "history_invalid_red_length_count": invalid_red_length_count,
        "history_red_out_of_range_count": red_out_of_range_count,
        "history_duplicate_red_numbers_count": duplicate_red_numbers_count,
        "history_blue_out_of_range_count": blue_out_of_range_count,
        "universe_ok": universe_ok,
        "red_combination_universe_count": combination_count,
        "expected_red_combination_universe_count": EXPECTED_SSQ_RED_COMBINATION_COUNT,
        "red_combination_universe_complete": universe_complete,
        "red_combination_duplicate_count": duplicate_combination_count,
        "red_combination_invalid_shape_count": invalid_combination_shape_count,
        "latest_sync_ok": latest_sync_ok,
        "latest_sync": latest_sync_summary,
        "recorded_data_conflict_count": (
            safe_int(conflict_row.get("recorded_data_conflict_count")) or 0
        ),
    }


def compact_parser_sync_duplicate_checks(value: Any) -> str:
    if not isinstance(value, dict):
        return "" if value is None else str(value)
    status = value.get("status")
    if status != "checked":
        parts = [f"status={status or 'unknown'}"]
        reason = value.get("reason")
        if reason:
            parts.append(f"reason={reason}")
        error = value.get("error")
        if error:
            parts.append(f"error={error}")
        return " ".join(parts)

    latest_sync = value.get("latest_sync") if isinstance(value.get("latest_sync"), dict) else {}
    issue_range = ""
    if value.get("history_first_issue") or value.get("history_latest_issue"):
        issue_range = f" issues={value.get('history_first_issue')}..{value.get('history_latest_issue')}"
    return (
        f"status=checked ok={value.get('ok')} "
        f"history_ok={value.get('history_ok')} draws={value.get('history_draw_count')}{issue_range} "
        f"dup_issues={value.get('history_duplicate_issue_count')} "
        f"dup_red_draws={value.get('history_duplicate_red_numbers_count')} "
        f"invalid_red_len={value.get('history_invalid_red_length_count')} "
        f"red_oob={value.get('history_red_out_of_range_count')} "
        f"blue_oob={value.get('history_blue_out_of_range_count')} "
        f"universe_ok={value.get('universe_ok')} "
        f"universe={value.get('red_combination_universe_count')}/"
        f"{value.get('expected_red_combination_universe_count')} "
        f"universe_dups={value.get('red_combination_duplicate_count')} "
        f"universe_invalid={value.get('red_combination_invalid_shape_count')} "
        f"latest_sync_status={latest_sync.get('status')} "
        f"latest_sync_conflicts={latest_sync.get('conflict_count')} "
        f"recorded_conflicts={value.get('recorded_data_conflict_count')}"
    )


def default_round_stats() -> dict[str, Any]:
    return {
        "round_count": 0,
        "latest_round": None,
        "last_improved_round": None,
        "stagnation_rounds": 0,
        "improvement_count": 0,
        "best_objective_seen": None,
    }


def db_read_error_summary(stage: str, exc: Exception) -> dict[str, str]:
    return {
        "stage": stage,
        "error_type": exc.__class__.__name__,
        "error": str(exc),
    }


def latest_supervisor_run_id_from_status_file(
    *,
    output_dir: Path = DEFAULT_SUPERVISOR_OUTPUT_DIR,
) -> str | None:
    try:
        paths = list(output_dir.glob("training-supervisor-*.json"))
    except OSError:
        return None
    candidates: list[tuple[float, str, Path]] = []
    for path in paths:
        try:
            if path.is_file():
                candidates.append((path.stat().st_mtime, path.name, path))
        except OSError:
            continue
    for _, _, path in sorted(candidates, reverse=True):
        try:
            status = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(status, dict) and status.get("run_id"):
            return str(status["run_id"])
    return None


def resolve_run_id(run_id: str | None) -> str | None:
    if run_id:
        return run_id
    with get_connection() as conn:
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


def load_rounds(run_id: str, *, limit: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            return list(
                cur.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT run_id, round_index, phase, step, improved, top_100_hits, top_1000_hits,
                               top_10000_hits, red5_top_100_hits, red5_top_1000_hits,
                               red5_top_10000_hits, median_rank, best_rank, worst_rank,
                               objective_score, best_config, best_summary, top_results,
                               target_results, prefilter, created_at, updated_at
                        FROM training_round_results
                        WHERE run_id = %s
                        ORDER BY round_index DESC
                        LIMIT %s
                    ) recent_rounds
                    ORDER BY round_index ASC
                    """,
                    (run_id, limit),
                ).fetchall()
            )


def load_round_stats(run_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            rows = list(
                cur.execute(
                    """
                    SELECT round_index, improved, objective_score
                    FROM training_round_results
                    WHERE run_id = %s
                    ORDER BY round_index ASC
                    """,
                    (run_id,),
                ).fetchall()
            )
    improvement = improvement_summary(rows)
    objective_values = [safe_float(row.get("objective_score")) for row in rows]
    objective_values = [value for value in objective_values if value is not None]
    return {
        "round_count": len(rows),
        "latest_round": improvement["latest_round"],
        "last_improved_round": improvement["last_improved_round"],
        "stagnation_rounds": improvement["stagnation_rounds"],
        "improvement_count": improvement["improvement_count"],
        "best_objective_seen": max(objective_values) if objective_values else None,
    }


def default_line_progress() -> dict[str, Any]:
    return {
        "status": "not_available",
        "latest_round": None,
        "lines": {},
        "comparison": {},
    }


def line_metric_vector(row: dict[str, Any], *, prefix: str) -> list[int | None]:
    return [
        safe_int(row.get(f"{prefix}_top_100_hits")),
        safe_int(row.get(f"{prefix}_top_1000_hits")),
        safe_int(row.get(f"{prefix}_top_10000_hits")),
    ]


def vector_delta(left: list[int | None], right: list[int | None]) -> list[int | None]:
    deltas: list[int | None] = []
    for left_value, right_value in zip(left, right, strict=True):
        if left_value is None or right_value is None:
            deltas.append(None)
        else:
            deltas.append(left_value - right_value)
    return deltas


def summarize_line_rounds(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return default_line_progress()

    by_line: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        line_key = str(row.get("line_key") or "")
        if not line_key:
            continue
        by_line.setdefault(line_key, []).append(row)

    latest_round = max(
        (safe_int(row.get("round_index")) or 0 for row in rows),
        default=None,
    )
    lines: dict[str, dict[str, Any]] = {}
    for line_key, line_rows in sorted(by_line.items()):
        latest = line_rows[-1]
        exact = line_metric_vector(latest, prefix="exact")
        red5 = line_metric_vector(latest, prefix="red5")
        recent_exact_totals = [
            sum(safe_int(row.get(name)) or 0 for row in line_rows)
            for name in ("exact_top_100_hits", "exact_top_1000_hits", "exact_top_10000_hits")
        ]
        recent_red5_totals = [
            sum(safe_int(row.get(name)) or 0 for row in line_rows)
            for name in ("red5_top_100_hits", "red5_top_1000_hits", "red5_top_10000_hits")
        ]
        lines[line_key] = {
            "line_key": line_key,
            "line_label": latest.get("line_label"),
            "line_kind": latest.get("line_kind"),
            "round_index": safe_int(latest.get("round_index")),
            "status": latest.get("status"),
            "policy_key": latest.get("policy_key"),
            "policy_params": latest.get("policy_params") if isinstance(latest.get("policy_params"), dict) else {},
            "exact_top_100_1000_10000": exact,
            "red5_top_100_1000_10000": red5,
            "recent_round_count": len(line_rows),
            "recent_exact_top_100_1000_10000_total": recent_exact_totals,
            "recent_red5_top_100_1000_10000_total": recent_red5_totals,
            "fallback_target_count": safe_int(latest.get("fallback_target_count")),
            "changed_target_count": safe_int(latest.get("changed_target_count")),
            "leakage_passed": latest.get("leakage_passed"),
            "generated_at": isoformat(latest.get("generated_at")),
            "updated_at": isoformat(latest.get("updated_at")),
        }

    comparison: dict[str, Any] = {}
    baseline = lines.get("static_100")
    dynamic = lines.get("dynamic_kdj")
    if baseline and dynamic:
        comparison = {
            "baseline_line_key": "static_100",
            "challenger_line_key": "dynamic_kdj",
            "exact_delta_dynamic_minus_static": vector_delta(
                dynamic["exact_top_100_1000_10000"],
                baseline["exact_top_100_1000_10000"],
            ),
            "red5_delta_dynamic_minus_static": vector_delta(
                dynamic["red5_top_100_1000_10000"],
                baseline["red5_top_100_1000_10000"],
            ),
            "recent_exact_total_delta_dynamic_minus_static": vector_delta(
                dynamic["recent_exact_top_100_1000_10000_total"],
                baseline["recent_exact_top_100_1000_10000_total"],
            ),
            "recent_red5_total_delta_dynamic_minus_static": vector_delta(
                dynamic["recent_red5_top_100_1000_10000_total"],
                baseline["recent_red5_top_100_1000_10000_total"],
            ),
        }

    return {
        "status": "ready",
        "latest_round": latest_round,
        "lines": lines,
        "comparison": comparison,
    }


def load_line_progress(run_id: str, *, limit: int) -> dict[str, Any]:
    with get_connection() as conn:
        table = conn.execute("SELECT to_regclass('public.training_line_round_results')").fetchone()
        if not table or not table[0]:
            return default_line_progress()
        with conn.cursor(row_factory=dict_row) as cur:
            rows = list(
                cur.execute(
                    """
                    WITH recent_rounds AS (
                        SELECT DISTINCT round_index
                        FROM training_line_round_results
                        WHERE run_id = %s
                        ORDER BY round_index DESC
                        LIMIT %s
                    )
                    SELECT line.run_id, line.round_index, line.line_key, line.line_label, line.line_kind,
                           line.policy_key, line.policy_params, line.status,
                           line.exact_top_100_hits, line.exact_top_1000_hits, line.exact_top_10000_hits,
                           line.red5_top_100_hits, line.red5_top_1000_hits, line.red5_top_10000_hits,
                           line.fallback_target_count, line.changed_target_count, line.leakage_passed,
                           line.generated_at, line.updated_at
                    FROM training_line_round_results line
                    JOIN recent_rounds USING (round_index)
                    WHERE line.run_id = %s
                    ORDER BY line.round_index ASC, line.line_key ASC
                    """,
                    (run_id, limit, run_id),
                ).fetchall()
            )
    return summarize_line_rounds(rows)


def supervisor_progress_summary(progress: Any) -> dict[str, Any]:
    if not isinstance(progress, dict):
        return {}
    target_index = safe_int(progress.get("target_index"))
    target_total = safe_int(progress.get("target_total"))
    target_complete = (
        target_index is not None
        and target_total is not None
        and target_total > 0
        and target_index >= target_total
    )
    return {
        "logged_at": progress.get("logged_at"),
        "round": safe_int(progress.get("round")),
        "target_index": target_index,
        "target_total": target_total,
        "target_complete": target_complete,
        "issue": progress.get("issue"),
        "train_draws": safe_int(progress.get("train_draws")),
        "elapsed_seconds": safe_float(progress.get("elapsed_seconds")),
    }


def supervisor_status_summary(status: dict[str, Any], *, path: Path) -> dict[str, Any]:
    deadline_present = "deadline" in status
    deadline = status.get("deadline") if deadline_present else None
    run_mode = status.get("run_mode")
    if run_mode is None and deadline_present and deadline is None:
        run_mode = "continuous"
    return {
        "available": True,
        "path": str(path),
        "run_id": status.get("run_id"),
        "status": status.get("status"),
        "pid": safe_int(status.get("pid")),
        "started_at": status.get("started_at"),
        "updated_at": status.get("updated_at"),
        "deadline": deadline,
        "run_mode": run_mode,
        "report_path": status.get("report_path"),
        "legal_universe_size": safe_int(status.get("legal_universe_size")),
        "ranked_universe_size": safe_int(status.get("ranked_universe_size") or status.get("universe_size")),
        "excluded_universe_count": safe_int(status.get("excluded_universe_count")),
        "history_scope": status.get("history_scope"),
        "train_mode": status.get("train_mode"),
        "train_window": safe_int(status.get("train_window")),
        "eval_window": safe_int(status.get("eval_window")),
        "top_n": safe_int(status.get("top_n")),
        "regime_start_date": status.get("regime_start_date"),
        "regime_years": safe_float(status.get("regime_years")),
        "latest_progress": supervisor_progress_summary(status.get("latest_progress")),
    }


def load_supervisor_status(
    run_id: str | None,
    *,
    output_dir: Path = DEFAULT_SUPERVISOR_OUTPUT_DIR,
) -> dict[str, Any]:
    if not run_id:
        return {"available": False, "reason": "missing_run_id"}
    path = output_dir / f"training-supervisor-{safe_filename_component(run_id)}.json"
    if not path.exists():
        return {"available": False, "reason": "status_file_missing", "path": str(path)}
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "available": False,
            "reason": "status_file_invalid_json",
            "path": str(path),
            "error": str(exc),
        }
    except OSError as exc:
        return {
            "available": False,
            "reason": "status_file_unreadable",
            "path": str(path),
            "error": str(exc),
        }
    if not isinstance(status, dict):
        return {
            "available": False,
            "reason": "status_file_invalid_root",
            "path": str(path),
        }
    if str(status.get("run_id") or "") != str(run_id):
        return {
            "available": False,
            "reason": "status_run_id_mismatch",
            "path": str(path),
            "observed_run_id": status.get("run_id"),
        }
    return supervisor_status_summary(status, path=path)


def add_supervisor_status_observation_ages(
    supervisor_status: dict[str, Any],
    *,
    now: datetime,
    stale_minutes: int,
    default_timezone: tzinfo | None = None,
) -> dict[str, Any]:
    if not supervisor_status.get("available"):
        return dict(supervisor_status)

    status_tz = default_timezone or local_timezone()
    enriched = dict(supervisor_status)
    enriched["updated_at_age_minutes"] = observed_age_minutes(
        enriched.get("updated_at"),
        now=now,
        default_timezone=status_tz,
    )
    enriched["timestamp_timezone_assumption"] = "aware_or_local_timezone_for_naive_supervisor_status"

    progress = (
        dict(enriched.get("latest_progress"))
        if isinstance(enriched.get("latest_progress"), dict)
        else {}
    )
    if progress:
        progress_age = observed_age_minutes(
            progress.get("logged_at"),
            now=now,
            default_timezone=status_tz,
        )
        progress["age_minutes"] = progress_age
        progress["fresh"] = (
            None
            if progress_age is None
            else progress_age <= stale_minutes
        )
        progress["freshness_threshold_minutes"] = stale_minutes
        enriched["latest_progress"] = progress
    return enriched


def supervisor_progress_note(supervisor_status: dict[str, Any]) -> str | None:
    if not supervisor_status.get("available"):
        return None
    progress = (
        supervisor_status.get("latest_progress")
        if isinstance(supervisor_status.get("latest_progress"), dict)
        else {}
    )
    parts = [f"status={supervisor_status.get('status')}"]
    if supervisor_status.get("pid") is not None:
        parts.append(f"pid={supervisor_status.get('pid')}")
    if supervisor_status.get("run_mode"):
        parts.append(f"run_mode={supervisor_status.get('run_mode')}")
    if supervisor_status.get("deadline") is not None:
        parts.append(f"deadline={supervisor_status.get('deadline')}")
    if progress.get("round") is not None:
        parts.append(f"round={progress.get('round')}")
    if progress.get("target_index") is not None and progress.get("target_total") is not None:
        parts.append(f"target={progress.get('target_index')}/{progress.get('target_total')}")
    if progress.get("issue"):
        parts.append(f"issue={progress.get('issue')}")
    if progress.get("elapsed_seconds") is not None:
        parts.append(f"elapsed_seconds={progress.get('elapsed_seconds')}")
    if progress.get("age_minutes") is not None:
        parts.append(f"progress_age_minutes={progress.get('age_minutes')}")
    if progress.get("fresh") is not None:
        parts.append(f"progress_fresh={progress.get('fresh')}")
    if supervisor_status.get("updated_at"):
        parts.append(f"updated_at={supervisor_status.get('updated_at')}")
    return "Supervisor status file reports current progress: " + " ".join(parts) + "."


def supervisor_round_boundary_summary(
    *,
    supervisor_status: dict[str, Any] | None,
    round_stats: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(supervisor_status, dict) or not supervisor_status.get("available"):
        return {}
    progress = (
        supervisor_status.get("latest_progress")
        if isinstance(supervisor_status.get("latest_progress"), dict)
        else {}
    )
    if not progress:
        return {}

    progress_round = safe_int(progress.get("round"))
    latest_db_round = safe_int((round_stats or {}).get("latest_round"))
    round_lag = (
        progress_round - latest_db_round
        if progress_round is not None and latest_db_round is not None
        else None
    )
    target_complete = safe_bool(progress.get("target_complete"))
    if target_complete is True and round_lag is not None and round_lag > 0:
        status = "target_complete_waiting_round_result"
    elif target_complete is True and round_lag == 0:
        status = "target_complete_round_recorded"
    elif target_complete is False:
        status = "target_in_progress"
    elif round_lag is not None and round_lag < 0:
        status = "db_round_ahead_of_progress"
    else:
        status = "target_state_unknown"

    return {
        "status": status,
        "supervisor_progress_round": progress_round,
        "latest_db_round": latest_db_round,
        "round_lag": round_lag,
        "target_index": safe_int(progress.get("target_index")),
        "target_total": safe_int(progress.get("target_total")),
        "target_complete": target_complete,
        "progress_fresh": safe_bool(progress.get("fresh")),
        "progress_age_minutes": safe_float(progress.get("age_minutes")),
    }


def heavy_lock_summary() -> dict[str, Any]:
    status = describe_heavy_job_owner()
    metadata = status.metadata or {}
    return {
        "active": status.active,
        "pid_active": status.pid_active,
        "reason": status.reason,
        "error": status.error,
        "owner": metadata.get("owner"),
        "pid": metadata.get("pid"),
        "status": metadata.get("status"),
        "started_at": metadata.get("started_at"),
        "heartbeat_at": metadata.get("heartbeat_at"),
        "context": metadata.get("context") if isinstance(metadata.get("context"), dict) else {},
    }


def add_heavy_lock_observation_ages(lock: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    enriched = dict(lock)
    lock_age_minutes = observed_age_minutes(enriched.get("started_at"), now=now)
    heartbeat_age_minutes = observed_age_minutes(enriched.get("heartbeat_at"), now=now)
    enriched["lock_age_minutes"] = lock_age_minutes
    enriched["lock_age_hours"] = (
        round(lock_age_minutes / 60.0, 6) if lock_age_minutes is not None else None
    )
    enriched["heartbeat_age_minutes"] = heartbeat_age_minutes
    return enriched


def advisor_summary(prefilter: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in ADVISOR_KEYS:
        row = prefilter.get(key) if isinstance(prefilter.get(key), dict) else {}
        advice = row.get("advice") if isinstance(row.get("advice"), list) else []
        top_advice = [
            {
                "weight_name": item.get("weight_name"),
                "decision": item.get("decision"),
                "suggested_offset": item.get("suggested_offset", item.get("applied_offset", item.get("offset"))),
                "confidence": item.get("confidence"),
                "validation_metric": item.get("validation_metric"),
                "baseline_metric": item.get("baseline_metric"),
            }
            for item in advice[:8]
            if isinstance(item, dict)
        ]
        result[key] = {
            "enabled": bool(row.get("enabled")),
            "budget": safe_int(row.get("budget")),
            "candidate_count": safe_int(row.get("candidate_count")) or 0,
            "selected_count": safe_int(row.get("selected_count")) or 0,
            "downweighted_count": safe_int(row.get("downweighted_count")) or 0,
            "rejected_count": safe_int(row.get("rejected_count")) or 0,
            "latest_signal_issue": row.get("latest_signal_issue") or row.get("latest_issue"),
            "selected_fields": row.get("selected_fields") if isinstance(row.get("selected_fields"), list) else [],
            "top_advice": top_advice,
        }
    return result


def advisor_signal_freshness_summary(
    advisors: dict[str, dict[str, Any]],
    *,
    history_latest_issue: Any,
    history_issues: list[Any] | None = None,
    max_issue_lag: int = DEFAULT_ADVISOR_SIGNAL_MAX_ISSUE_LAG,
) -> dict[str, Any]:
    latest_issue = str(history_latest_issue or "").strip()
    allowed_lag = max(0, int(max_issue_lag))
    rows: dict[str, dict[str, Any]] = {}
    stale_advisors: list[str] = []
    missing_advisors: list[str] = []
    future_advisors: list[str] = []
    latest_number = safe_int(latest_issue)
    issue_positions = {
        str(issue): index
        for index, issue in enumerate(history_issues or [])
        if str(issue or "").strip()
    }

    for key, advisor in advisors.items():
        if not isinstance(advisor, dict) or not advisor.get("enabled"):
            rows[key] = {
                "status": "disabled",
                "latest_signal_issue": (
                    advisor.get("latest_signal_issue")
                    if isinstance(advisor, dict)
                    else None
                ),
                "history_latest_issue": latest_issue or None,
                "issue_lag": None,
            }
            continue
        signal_issue = str(advisor.get("latest_signal_issue") or "").strip()
        signal_number = safe_int(signal_issue)
        if signal_issue in issue_positions and latest_issue in issue_positions:
            issue_lag = issue_positions[latest_issue] - issue_positions[signal_issue]
        elif (
            latest_number is not None
            and signal_number is not None
            and latest_issue[:4] == signal_issue[:4]
        ):
            issue_lag = latest_number - signal_number
        else:
            issue_lag = None
        if not latest_issue:
            status = "history_latest_issue_missing"
        elif not signal_issue:
            status = "signal_issue_missing"
            missing_advisors.append(key)
        elif issue_lag is not None and issue_lag < 0:
            status = "signal_issue_ahead_of_history"
            future_advisors.append(key)
        elif issue_lag is not None and issue_lag > allowed_lag:
            status = "stale"
            stale_advisors.append(key)
        elif issue_lag is None and signal_issue > latest_issue:
            status = "signal_issue_ahead_of_history"
            future_advisors.append(key)
        elif issue_lag is None and signal_issue < latest_issue:
            status = "stale_unknown_lag"
            stale_advisors.append(key)
        else:
            status = "current"
        rows[key] = {
            "status": status,
            "latest_signal_issue": signal_issue or None,
            "history_latest_issue": latest_issue or None,
            "issue_lag": issue_lag,
        }

    if future_advisors:
        status = "signal_issue_ahead_of_history"
    elif stale_advisors:
        status = "stale"
    elif missing_advisors:
        status = "signal_issue_missing"
    elif not latest_issue:
        status = "history_latest_issue_missing"
    else:
        status = "current"
    return {
        "status": status,
        "history_latest_issue": latest_issue or None,
        "max_allowed_issue_lag": allowed_lag,
        "stale_advisors": stale_advisors,
        "missing_advisors": missing_advisors,
        "future_advisors": future_advisors,
        "advisors": rows,
    }


def safe_score(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def score_greater(left: list[Any], right: list[Any]) -> bool:
    if not left or not right:
        return False
    try:
        return tuple(left) > tuple(right)
    except TypeError:
        return False


def safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def experimental_navigation_candidate_present(
    navigation: dict[str, Any],
    search_base: dict[str, Any] | None = None,
) -> bool:
    search_base = search_base if isinstance(search_base, dict) else {}
    return bool(
        navigation.get("source")
        or navigation.get("config_hash")
        or search_base.get("exploration_navigation_config_hash")
        or safe_bool(navigation.get("eligible")) is True
        or safe_bool(search_base.get("exploration_navigation_eligible")) is True
    )


def experimental_navigation_eligibility_reason(search_base: dict[str, Any]) -> str:
    eligible = safe_bool(search_base.get("exploration_navigation_eligible"))
    if eligible is True:
        return "eligible"
    if not search_base.get("exploration_navigation_config_hash"):
        return "no_experimental_navigation_candidate"

    quality_reason = search_base.get("exploration_navigation_quality_reason")
    if quality_reason and quality_reason != "passed":
        return str(quality_reason)

    distance = safe_float(search_base.get("exploration_navigation_config_distance"))
    min_distance = safe_float(search_base.get("min_config_distance"))
    if distance is not None and min_distance is not None and distance < min_distance:
        return "below_min_config_distance"

    rank_vector_changed = safe_bool(search_base.get("exploration_navigation_rank_vector_changed"))
    if rank_vector_changed is False:
        return "rank_vector_unchanged"

    frozen_primary_score = safe_score(search_base.get("exploration_navigation_frozen_primary_score"))
    baseline_frozen_primary_score = safe_score(
        search_base.get("exploration_navigation_baseline_frozen_primary_score")
    )
    if score_greater(frozen_primary_score, baseline_frozen_primary_score):
        return "primary_lift_candidate_uses_standard_search_path"

    return "ineligible_by_search_base_rules" if eligible is False else ""


def gate_summary(prefilter: dict[str, Any]) -> dict[str, dict[str, Any]]:
    promotion = prefilter.get("promotion_gate") if isinstance(prefilter.get("promotion_gate"), dict) else {}
    eval_guard = (
        prefilter.get("eval_slice_overfit_guardrail")
        if isinstance(prefilter.get("eval_slice_overfit_guardrail"), dict)
        else {}
    )
    stale_gate = (
        prefilter.get("stale_round_best_search_base_gate")
        if isinstance(prefilter.get("stale_round_best_search_base_gate"), dict)
        else {}
    )
    rank_homogeneity = (
        prefilter.get("rank_homogeneity_guardrail")
        if isinstance(prefilter.get("rank_homogeneity_guardrail"), dict)
        else {}
    )
    restart_champion = (
        prefilter.get("rank_homogeneity_restart_champion")
        if isinstance(prefilter.get("rank_homogeneity_restart_champion"), dict)
        else {}
    )
    navigation = (
        prefilter.get("experimental_navigation_candidate")
        if isinstance(prefilter.get("experimental_navigation_candidate"), dict)
        else {}
    )
    search_base = prefilter.get("search_base") if isinstance(prefilter.get("search_base"), dict) else {}
    decision = prefilter.get("decision_round_best") if isinstance(prefilter.get("decision_round_best"), dict) else {}
    blocked_candidates = decision.get("blocked_candidates") if isinstance(decision.get("blocked_candidates"), list) else []

    result: dict[str, dict[str, Any]] = {}
    if promotion:
        result["promotion_gate"] = {
            "passed": bool(promotion.get("passed")),
            "reason": promotion.get("reason"),
            "tail_passed": bool(promotion.get("tail_passed")),
            "objective_passed": bool(promotion.get("objective_passed")),
            "primary_hit_passed": bool(promotion.get("primary_hit_passed")),
            "candidate_primary_score": safe_score(promotion.get("candidate_primary_score")),
            "incumbent_primary_score": safe_score(promotion.get("incumbent_primary_score")),
        }
    if eval_guard:
        result["eval_slice_overfit_guardrail"] = {
            "active": bool(eval_guard.get("active")),
            "reason": eval_guard.get("reason"),
            "force_primary_gate": bool(eval_guard.get("force_primary_gate")),
            "rank_homogeneity_active": bool(eval_guard.get("rank_homogeneity_active")),
            "rank_homogeneity_unique_signature_count": safe_int(
                eval_guard.get("rank_homogeneity_unique_signature_count")
            ),
            "round_best_eval_primary_score": safe_score(eval_guard.get("round_best_eval_primary_score")),
            "round_best_frozen_primary_score": safe_score(eval_guard.get("round_best_frozen_primary_score")),
            "incumbent_frozen_primary_score": safe_score(eval_guard.get("incumbent_frozen_primary_score")),
            "suspicious_candidate_count": safe_int(eval_guard.get("suspicious_candidate_count")) or 0,
            "issue_counts": eval_guard.get("issue_counts") if isinstance(eval_guard.get("issue_counts"), dict) else {},
            "source_counts": eval_guard.get("source_counts") if isinstance(eval_guard.get("source_counts"), dict) else {},
        }
    if stale_gate:
        result["stale_round_best_search_base_gate"] = {
            "active": bool(stale_gate.get("active")),
            "reason": stale_gate.get("reason"),
            "require_frozen_primary_challenger": bool(stale_gate.get("require_frozen_primary_challenger")),
            "allow_unpromoted_round_best": bool(stale_gate.get("allow_unpromoted_round_best")),
            "threshold": safe_int(stale_gate.get("threshold")),
        }
    if rank_homogeneity:
        result["rank_homogeneity_guardrail"] = {
            "active": bool(rank_homogeneity.get("active")),
            "reason": rank_homogeneity.get("reason"),
            "stagnation_rounds": safe_int(rank_homogeneity.get("stagnation_rounds")),
            "stagnation_threshold": safe_int(rank_homogeneity.get("stagnation_threshold")),
            "window": safe_int(rank_homogeneity.get("window")),
            "observed": safe_int(rank_homogeneity.get("observed")),
            "unique_signature_count": safe_int(rank_homogeneity.get("unique_signature_count")),
            "max_unique_signatures": safe_int(rank_homogeneity.get("max_unique_signatures")),
            "signature_hashes": safe_string_list(rank_homogeneity.get("signatures")),
        }
    if restart_champion:
        result["rank_homogeneity_restart_champion"] = {
            "active": bool(restart_champion.get("active")),
            "reason": restart_champion.get("reason"),
            "source": restart_champion.get("source"),
            "config_hash": restart_champion.get("config_hash"),
            "full_eval_rank": safe_int(restart_champion.get("full_eval_rank")),
            "rank_vector_changed": safe_bool(restart_champion.get("rank_vector_changed")),
            "changed_target_count": safe_int(restart_champion.get("changed_target_count")),
            "max_abs_delta": safe_int(restart_champion.get("max_abs_delta")),
            "primary_weight_pattern": restart_champion.get("primary_weight_pattern"),
            "context_field_movement_count": safe_int(restart_champion.get("context_field_movement_count")),
            "frozen_primary_score": safe_score(restart_champion.get("frozen_primary_score")),
            "baseline_frozen_primary_score": safe_score(restart_champion.get("baseline_frozen_primary_score")),
            "source_frontier_secondary_score": safe_score(restart_champion.get("source_frontier_secondary_score")),
            "baseline_source_frontier_secondary_score": safe_score(
                restart_champion.get("baseline_source_frontier_secondary_score")
            ),
            "tail_over_1000000_delta": safe_int(restart_champion.get("tail_over_1000000_delta")),
            "source_frontier_score_improved": safe_bool(
                restart_champion.get("source_frontier_score_improved")
            ),
            "source_frontier_primary_score_improved": safe_bool(
                restart_champion.get("source_frontier_primary_score_improved")
            ),
            "source_frontier_secondary_score_improved": safe_bool(
                restart_champion.get("source_frontier_secondary_score_improved")
            ),
            "source_frontier_improvement_basis": restart_champion.get("source_frontier_improvement_basis"),
            "unique_rank_signature_count": safe_int(restart_champion.get("unique_rank_signature_count")),
        }
    if navigation:
        candidate_present = experimental_navigation_candidate_present(navigation, search_base)
        navigation_summary: dict[str, Any] = {
            "source": navigation.get("source"),
            "reason": navigation.get("reason"),
            "config_hash": navigation.get("config_hash"),
            "candidate_present": candidate_present,
        }
        if search_base:
            eligible = safe_bool(search_base.get("exploration_navigation_eligible"))
            if eligible is not None:
                navigation_summary["eligible"] = eligible
            eligibility_reason = experimental_navigation_eligibility_reason(search_base)
            if eligibility_reason:
                navigation_summary["eligibility_reason"] = eligibility_reason
            for source_key, output_key, parser in (
                ("exploration_navigation_config_distance", "config_distance", safe_float),
                ("min_config_distance", "min_config_distance", safe_float),
                ("exploration_navigation_rank_vector_changed", "rank_vector_changed", safe_bool),
                ("exploration_navigation_tail_over_1000000_delta", "tail_over_1000000_delta", safe_int),
                (
                    "exploration_navigation_source_frontier_score_improved",
                    "source_frontier_score_improved",
                    safe_bool,
                ),
            ):
                parsed = parser(search_base.get(source_key))
                if parsed is not None:
                    navigation_summary[output_key] = parsed
            if search_base.get("exploration_navigation_quality_reason") is not None:
                navigation_summary["quality_reason"] = search_base.get(
                    "exploration_navigation_quality_reason"
                )
            frozen_primary_score = safe_score(search_base.get("exploration_navigation_frozen_primary_score"))
            if frozen_primary_score:
                navigation_summary["frozen_primary_score"] = frozen_primary_score
            baseline_frozen_primary_score = safe_score(
                search_base.get("exploration_navigation_baseline_frozen_primary_score")
            )
            if baseline_frozen_primary_score:
                navigation_summary["baseline_frozen_primary_score"] = baseline_frozen_primary_score
        result["experimental_navigation_candidate"] = navigation_summary
    if decision:
        result["decision_round_best"] = {
            "source": decision.get("source"),
            "reason": decision.get("reason"),
            "frozen_primary_lift_required": bool(decision.get("frozen_primary_lift_required")),
            "selected_frozen_primary_score": safe_score(decision.get("selected_frozen_primary_score")),
            "frozen_primary_lift_baseline_score": safe_score(decision.get("frozen_primary_lift_baseline_score")),
            "blocked_candidate_count": len(blocked_candidates),
            "blocked_candidate_sources": [
                str(item.get("source"))
                for item in blocked_candidates[:5]
                if isinstance(item, dict) and item.get("source")
            ],
        }
    return result


def round_age_minutes(row: dict[str, Any], *, now: datetime) -> float | None:
    updated_at = row.get("updated_at") or row.get("created_at")
    if not isinstance(updated_at, datetime):
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return max(0.0, (now - updated_at.astimezone(timezone.utc)).total_seconds() / 60.0)


def improvement_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    improved_rounds = [safe_int(row.get("round_index")) for row in rows if row.get("improved")]
    improved_rounds = [item for item in improved_rounds if item is not None]
    latest_round = safe_int(rows[-1].get("round_index")) if rows else None
    last_improved_round = max(improved_rounds) if improved_rounds else None
    return {
        "latest_round": latest_round,
        "last_improved_round": last_improved_round,
        "stagnation_rounds": (latest_round - last_improved_round) if latest_round and last_improved_round else latest_round or 0,
        "improvement_count": len(improved_rounds),
    }


def recommendation_summary(
    *,
    rows: list[dict[str, Any]],
    lock: dict[str, Any],
    advisors: dict[str, dict[str, Any]],
    now: datetime,
    stale_minutes: int,
    round_stats: dict[str, Any] | None = None,
    gates: dict[str, dict[str, Any]] | None = None,
    supervisor_status: dict[str, Any] | None = None,
    round_repetition: dict[str, Any] | None = None,
    advisor_signal_freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not rows:
        return {
            "severity": "alert",
            "action": "no_rounds",
            "notes": ["No training_round_results rows found for this run."],
        }

    latest = rows[-1]
    improvement = round_stats or improvement_summary(rows)
    latest_age = round_age_minutes(latest, now=now)
    notes: list[str] = []
    actions: list[str] = []
    severity = "ok"

    if lock.get("active") and lock.get("owner") == "training-supervisor":
        notes.append("Training process is active under the heavy-job lock.")
    else:
        severity = "warn"
        notes.append("Training heavy-job lock is not active; verify whether the supervisor stopped.")
    progress_note = supervisor_progress_note(supervisor_status or {})
    if progress_note:
        notes.append(progress_note)
    round_boundary = supervisor_round_boundary_summary(
        supervisor_status=supervisor_status,
        round_stats=improvement,
    )
    if round_boundary.get("status") == "target_complete_waiting_round_result":
        notes.append(
            "Supervisor target boundary reached but round results are not visible yet: "
            f"progress_round={round_boundary.get('supervisor_progress_round')} "
            f"latest_db_round={round_boundary.get('latest_db_round')} "
            f"round_lag={round_boundary.get('round_lag')} "
            "wait for DB/report flush before restart decisions."
        )
    supervisor_progress = (
        supervisor_status.get("latest_progress")
        if isinstance(supervisor_status, dict)
        and isinstance(supervisor_status.get("latest_progress"), dict)
        else {}
    )
    supervisor_progress_age = safe_float(supervisor_progress.get("age_minutes"))
    if supervisor_progress.get("fresh") is False:
        severity = "warn" if severity == "ok" else severity
        actions.append("inspect_training_log")
        age_text = (
            f"{supervisor_progress_age:.1f}"
            if supervisor_progress_age is not None
            else "unknown"
        )
        notes.append(
            "Supervisor progress is stale: "
            f"{age_text} minutes since latest_progress.logged_at."
        )

    if latest_age is not None and latest_age > stale_minutes:
        severity = "warn"
        actions.append("inspect_training_log")
        notes.append(f"Latest round is stale: {latest_age:.1f} minutes since update.")

    advisor_freshness = (
        advisor_signal_freshness
        if isinstance(advisor_signal_freshness, dict)
        else {}
    )
    freshness_status = advisor_freshness.get("status")
    if freshness_status == "signal_issue_ahead_of_history":
        severity = "alert"
        actions.append("inspect_advisor_signal_leakage")
        notes.append(
            "Advisor signal issue is ahead of the latest history issue; stop promotion and inspect the leakage boundary: "
            f"advisors={advisor_freshness.get('future_advisors')}."
        )
    elif freshness_status == "stale":
        severity = "warn" if severity == "ok" else severity
        actions.append("refresh_advisor_signals")
        notes.append(
            "Advisor signals lag the latest history beyond the allowed boundary: "
            f"history_latest={advisor_freshness.get('history_latest_issue')} "
            f"max_lag={advisor_freshness.get('max_allowed_issue_lag')} "
            f"advisors={advisor_freshness.get('stale_advisors')}."
        )
    elif freshness_status == "signal_issue_missing":
        severity = "warn" if severity == "ok" else severity
        actions.append("inspect_advisor_signals")
        notes.append(
            "Enabled advisor signal issue metadata is missing: "
            f"advisors={advisor_freshness.get('missing_advisors')}."
        )

    stagnation_rounds = int(improvement["stagnation_rounds"] or 0)
    if stagnation_rounds >= 32:
        severity = "alert"
        actions.append("prepare_restart_with_more_exploration")
        notes.append("Stagnation is very high; prepare a new run with broader exploration and controls.")
    elif stagnation_rounds >= 16:
        severity = "warn" if severity == "ok" else severity
        actions.append("watch_stagnation_recovery")
        notes.append("Stagnation crossed the supervisor recovery threshold; check if diversity injection improves the next rounds.")
    else:
        notes.append("Stagnation is below the intervention threshold.")

    if isinstance(round_repetition, dict) and round_repetition.get("active"):
        notes.append(
            "Round repetition diagnostic is active: "
            f"{round_repetition.get('reason')} "
            f"window={round_repetition.get('window_count')} "
            f"config_streak={round_repetition.get('latest_config_repeat_streak')} "
            f"metric_streak={round_repetition.get('latest_metric_repeat_streak')}; "
            "treat as search observability, not predictive evidence or a restart decision."
        )

    neural = advisors.get("neural_kdj_advisor", {})
    neural_candidates = int(neural.get("candidate_count") or 0)
    neural_top = neural.get("top_advice") if isinstance(neural.get("top_advice"), list) else []
    neural_confidence = safe_float(neural_top[0].get("confidence")) if neural_top and isinstance(neural_top[0], dict) else None
    if neural_candidates == 0:
        notes.append("Neural advisor produced no candidate in the latest round; keep neural budget conservative.")
    elif neural_confidence is not None and neural_confidence < 0.05:
        notes.append("Neural advisor produced candidates, but confidence is low; keep it advisor-only and do not increase its budget yet.")
    else:
        notes.append("Neural advisor produced candidates; require control experiments before any promotion.")

    ridge = advisors.get("ridge_kdj_advisor", {})
    if int(ridge.get("candidate_count") or 0) > 0:
        notes.append("Ridge advisor remains a viable lightweight candidate source.")

    gates = gates or {}
    promotion = gates.get("promotion_gate") if isinstance(gates.get("promotion_gate"), dict) else {}
    if promotion and not promotion.get("passed"):
        notes.append(
            "Promotion gate blocked the latest round: "
            f"{promotion.get('reason')} "
            f"candidate_primary={promotion.get('candidate_primary_score')} "
            f"incumbent_primary={promotion.get('incumbent_primary_score')}."
        )
    eval_guard = (
        gates.get("eval_slice_overfit_guardrail")
        if isinstance(gates.get("eval_slice_overfit_guardrail"), dict)
        else {}
    )
    if eval_guard.get("active"):
        source_counts = compact_count_map(eval_guard.get("source_counts"))
        issue_counts = compact_count_map(eval_guard.get("issue_counts"))
        notes.append(
            "Eval-slice overfit guardrail is active: "
            f"{eval_guard.get('reason')} "
            f"eval_primary={eval_guard.get('round_best_eval_primary_score')} "
            f"frozen_primary={eval_guard.get('round_best_frozen_primary_score')} "
            f"suspicious_candidates={eval_guard.get('suspicious_candidate_count')} "
            f"sources={source_counts} issues={issue_counts}."
        )
    stale_gate = (
        gates.get("stale_round_best_search_base_gate")
        if isinstance(gates.get("stale_round_best_search_base_gate"), dict)
        else {}
    )
    if stale_gate.get("active"):
        notes.append(
            "Search-base gate requires a frozen-primary challenger before leaving the incumbent search base."
        )
    rank_homogeneity = (
        gates.get("rank_homogeneity_guardrail")
        if isinstance(gates.get("rank_homogeneity_guardrail"), dict)
        else {}
    )
    if rank_homogeneity.get("active"):
        signature_hashes = compact_inline_list(rank_homogeneity.get("signature_hashes"), limit=3)
        notes.append(
            "Rank homogeneity guardrail is active: "
            f"{rank_homogeneity.get('reason')} "
            f"window={rank_homogeneity.get('window')} "
            f"observed={rank_homogeneity.get('observed')} "
            f"unique_signatures={rank_homogeneity.get('unique_signature_count')}/"
            f"{rank_homogeneity.get('max_unique_signatures')} "
            f"stagnation={rank_homogeneity.get('stagnation_rounds')}/"
            f"{rank_homogeneity.get('stagnation_threshold')} "
            f"signature_hashes={signature_hashes}."
        )
    restart_champion = (
        gates.get("rank_homogeneity_restart_champion")
        if isinstance(gates.get("rank_homogeneity_restart_champion"), dict)
        else {}
    )
    if restart_champion.get("active"):
        notes.append(
            "Rank-homogeneity restart champion observed: "
            f"{restart_champion.get('reason')} "
            f"rank_vector_changed={restart_champion.get('rank_vector_changed')} "
            f"changed_targets={restart_champion.get('changed_target_count')} "
            f"full_eval_rank={restart_champion.get('full_eval_rank')} "
            f"max_abs_delta={restart_champion.get('max_abs_delta')}."
        )
    navigation = (
        gates.get("experimental_navigation_candidate")
        if isinstance(gates.get("experimental_navigation_candidate"), dict)
        else {}
    )
    if navigation.get("eligible") is False:
        note_prefix = (
            "No experimental navigation candidate is available:"
            if navigation.get("eligibility_reason") == "no_experimental_navigation_candidate"
            else "Experimental navigation candidate is not search-base eligible:"
        )
        fields = [
            ("source", navigation.get("source")),
            ("reason", navigation.get("eligibility_reason")),
            ("quality", navigation.get("quality_reason")),
            ("rank_vector_changed", navigation.get("rank_vector_changed")),
        ]
        if navigation.get("config_distance") is not None:
            fields.extend(
                [
                    ("config_distance", navigation.get("config_distance")),
                    ("min_config_distance", navigation.get("min_config_distance")),
                ]
            )
        notes.append(f"{note_prefix} {compact_observed_fields(fields)}.")

    decision = (
        gates.get("decision_round_best")
        if isinstance(gates.get("decision_round_best"), dict)
        else {}
    )
    if decision and (restart_champion.get("active") or navigation.get("source")):
        blocked_sources = decision.get("blocked_candidate_sources")
        fields = [
            ("selected_source", decision.get("source")),
            ("selected_reason", decision.get("reason")),
            ("selected_frozen_primary", decision.get("selected_frozen_primary_score")),
            ("navigation_source", navigation.get("source")),
            ("navigation_eligible", navigation.get("eligible")),
            (
                "navigation_reason",
                navigation.get("eligibility_reason") or navigation.get("reason"),
            ),
            ("restart_source", restart_champion.get("source")),
            ("restart_frozen_primary", restart_champion.get("frozen_primary_score")),
            ("restart_frontier_basis", restart_champion.get("source_frontier_improvement_basis")),
        ]
        if isinstance(blocked_sources, list) and blocked_sources:
            fields.append(("blocked_sources", compact_inline_list(blocked_sources)))
        notes.append(f"Recovery decision: {compact_observed_fields(fields)}.")

    if "prepare_restart_with_more_exploration" in actions and lock.get("active"):
        lock_age_hours = safe_float(lock.get("lock_age_hours"))
        heartbeat_age_minutes = safe_float(lock.get("heartbeat_age_minutes"))
        age_details = []
        if lock_age_hours is not None:
            age_details.append(f"lock_age_hours={lock_age_hours}")
        if heartbeat_age_minutes is not None:
            age_details.append(f"heartbeat_age_minutes={heartbeat_age_minutes}")
        age_suffix = f" {' '.join(age_details)}." if age_details else "."
        notes.append(
            "Restart preparation is not launch-ready while a heavy-job lock is active: "
            f"owner={lock.get('owner')} pid={lock.get('pid')}{age_suffix} "
            "Wait for active work to finish, or stop/transfer the lock owner before starting a fresh run."
        )

    if not actions:
        actions.append("continue_current_run")

    return {
        "severity": severity,
        "action": actions[0],
        "actions": actions,
        "notes": notes,
    }


def supervisor_progress_readiness_context(supervisor_status: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(supervisor_status, dict) or not supervisor_status.get("available"):
        return {}
    progress = (
        supervisor_status.get("latest_progress")
        if isinstance(supervisor_status.get("latest_progress"), dict)
        else {}
    )
    return {
        "supervisor_run_id": supervisor_status.get("run_id"),
        "supervisor_status": supervisor_status.get("status"),
        "supervisor_pid": supervisor_status.get("pid"),
        "supervisor_run_mode": supervisor_status.get("run_mode"),
        "supervisor_deadline": supervisor_status.get("deadline"),
        "supervisor_updated_age_minutes": supervisor_status.get("updated_at_age_minutes"),
        "supervisor_progress_age_minutes": progress.get("age_minutes"),
        "supervisor_progress_fresh": progress.get("fresh"),
        "supervisor_progress_stale_minutes": progress.get("freshness_threshold_minutes"),
        "supervisor_progress_round": progress.get("round"),
        "supervisor_target_index": progress.get("target_index"),
        "supervisor_target_total": progress.get("target_total"),
        "supervisor_target_complete": progress.get("target_complete"),
    }


def restart_candidate_readiness_context(
    gates: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    if not isinstance(gates, dict):
        return {}
    restart_champion = (
        gates.get("rank_homogeneity_restart_champion")
        if isinstance(gates.get("rank_homogeneity_restart_champion"), dict)
        else {}
    )
    navigation = (
        gates.get("experimental_navigation_candidate")
        if isinstance(gates.get("experimental_navigation_candidate"), dict)
        else {}
    )
    if not restart_champion and not navigation:
        return {}

    context: dict[str, Any] = {}
    if restart_champion:
        context.update(
            {
                "restart_candidate_active": bool(restart_champion.get("active")),
                "restart_candidate_source": restart_champion.get("source"),
                "restart_candidate_reason": restart_champion.get("reason"),
                "restart_candidate_rank_vector_changed": restart_champion.get(
                    "rank_vector_changed"
                ),
                "restart_candidate_changed_target_count": restart_champion.get(
                    "changed_target_count"
                ),
                "restart_candidate_full_eval_rank": restart_champion.get("full_eval_rank"),
                "restart_candidate_frozen_primary_score": restart_champion.get(
                    "frozen_primary_score"
                ),
                "restart_candidate_baseline_frozen_primary_score": restart_champion.get(
                    "baseline_frozen_primary_score"
                ),
                "restart_candidate_primary_score_improved": restart_champion.get(
                    "source_frontier_primary_score_improved"
                ),
                "restart_candidate_secondary_score_improved": restart_champion.get(
                    "source_frontier_secondary_score_improved"
                ),
                "restart_candidate_improvement_basis": restart_champion.get(
                    "source_frontier_improvement_basis"
                ),
                "restart_candidate_tail_over_1000000_delta": restart_champion.get(
                    "tail_over_1000000_delta"
                ),
            }
        )
    if navigation:
        candidate_present = navigation.get("candidate_present")
        if candidate_present is None:
            candidate_present = experimental_navigation_candidate_present(navigation)
        context["experimental_navigation_candidate_present"] = bool(candidate_present)
        for key in (
            "eligible",
            "eligibility_reason",
            "quality_reason",
            "rank_vector_changed",
            "config_distance",
            "min_config_distance",
        ):
            if navigation.get(key) is not None:
                context[f"experimental_navigation_{key}"] = navigation.get(key)
    return {key: value for key, value in context.items() if value is not None}


def navigation_distance_ready(candidate_context: dict[str, Any]) -> bool:
    distance = safe_float(candidate_context.get("experimental_navigation_config_distance"))
    minimum = safe_float(candidate_context.get("experimental_navigation_min_config_distance"))
    return distance is not None and minimum is not None and distance >= minimum


def restart_candidate_evidence_blockers(candidate_context: dict[str, Any]) -> list[str]:
    if not candidate_context:
        return []

    primary_improved = (
        candidate_context.get("restart_candidate_primary_score_improved") is True
    )
    secondary_improved = (
        candidate_context.get("restart_candidate_secondary_score_improved") is True
    )
    checks = {
        "restart_candidate": candidate_context.get("restart_candidate_active") is True,
        "restart_rank_vector_changed": (
            candidate_context.get("restart_candidate_rank_vector_changed") is True
        ),
        "restart_changed_targets": (
            (safe_int(candidate_context.get("restart_candidate_changed_target_count")) or 0)
            > 0
        ),
        "restart_full_eval_rank": (
            (safe_int(candidate_context.get("restart_candidate_full_eval_rank")) or 0) > 0
        ),
        "restart_frontier_improved": primary_improved or secondary_improved,
        "restart_improvement_basis": candidate_context.get(
            "restart_candidate_improvement_basis"
        )
        in {"primary", "secondary"},
        "navigation_eligible": (
            candidate_context.get("experimental_navigation_eligible") is True
        ),
        "navigation_quality": (
            candidate_context.get("experimental_navigation_quality_reason") == "passed"
        ),
        "navigation_rank_vector_changed": (
            candidate_context.get("experimental_navigation_rank_vector_changed") is True
        ),
        "navigation_distance": navigation_distance_ready(candidate_context),
    }
    return [name for name, passed in checks.items() if not passed]


def restart_blocker_stage(
    blockers: list[str],
    progress_context: dict[str, Any],
) -> str:
    if not blockers:
        return "clear"
    if "active_training_supervisor_lock" not in blockers:
        return "active_heavy_job_lock"

    progress_fresh = progress_context.get("supervisor_progress_fresh")
    if progress_fresh is not True:
        return "active_training_supervisor_progress_unknown_or_stale"

    if progress_context.get("supervisor_run_mode") != "continuous":
        return "active_training_supervisor_fresh_progress"

    target_complete = progress_context.get("supervisor_target_complete")
    if target_complete is True and "restart_candidate_evidence" in blockers:
        return "restart_candidate_evidence_incomplete"
    if target_complete is True:
        return "active_continuous_supervisor_target_complete"
    if target_complete is False:
        return "active_continuous_supervisor_target_incomplete"
    return "active_continuous_supervisor_target_unknown"


def restart_readiness_summary(
    *,
    recommendation: dict[str, Any],
    lock: dict[str, Any],
    supervisor_status: dict[str, Any] | None = None,
    gates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw_actions = recommendation.get("actions")
    actions = [str(item) for item in raw_actions] if isinstance(raw_actions, list) else []
    if not actions and recommendation.get("action"):
        actions = [str(recommendation.get("action"))]
    requested = "prepare_restart_with_more_exploration" in actions
    if not requested:
        result = {
            "requested": False,
            "ready": False,
            "status": "not_requested",
            "blockers": [],
            "blocker_stage": "not_requested",
            "operator_action": "continue_current_training_watch",
        }
        result.update(supervisor_progress_readiness_context(supervisor_status))
        return result

    progress_context = supervisor_progress_readiness_context(supervisor_status)
    candidate_context = restart_candidate_readiness_context(gates)
    evidence_blockers = restart_candidate_evidence_blockers(candidate_context)

    blockers: list[str] = []
    lock_active = bool(lock.get("active"))
    owner = lock.get("owner")
    if lock_active and owner == "training-supervisor":
        blockers.append("active_training_supervisor_lock")
    elif lock_active:
        blockers.append("active_heavy_job_lock")
    if evidence_blockers:
        blockers.append("restart_candidate_evidence")
    blocker_stage = restart_blocker_stage(blockers, progress_context)
    if not blockers:
        operator_action = "operator_review_then_start_fresh_supervisor"
    elif "active_training_supervisor_lock" in blockers:
        if (
            progress_context.get("supervisor_progress_fresh") is True
            and progress_context.get("supervisor_run_mode") == "continuous"
            and progress_context.get("supervisor_target_complete") is False
        ):
            operator_action = (
                "wait_for_continuous_training_supervisor_target_boundary_before_restart"
            )
        elif (
            progress_context.get("supervisor_progress_fresh") is True
            and progress_context.get("supervisor_run_mode") == "continuous"
            and "restart_candidate_evidence" in blockers
        ):
            operator_action = (
                "continue_current_training_supervisor_until_restart_candidate_evidence_improves"
            )
        elif (
            progress_context.get("supervisor_progress_fresh") is True
            and progress_context.get("supervisor_run_mode") == "continuous"
        ):
            operator_action = "operator_review_then_stop_continuous_training_supervisor_before_restart"
        elif progress_context.get("supervisor_progress_fresh") is True:
            operator_action = "wait_for_active_training_supervisor_to_finish_or_stop_before_restart"
        else:
            operator_action = "stop_or_transfer_active_training_supervisor_before_restart"
    elif "restart_candidate_evidence" in blockers:
        operator_action = "wait_for_restart_candidate_evidence_before_starting_fresh_supervisor"
    else:
        operator_action = "wait_for_or_clear_active_heavy_job_lock_before_restart"

    if not blockers:
        status = "ready_for_fresh_supervisor_after_operator_review"
    elif blocker_stage == "restart_candidate_evidence_incomplete":
        status = "blocked_by_restart_candidate_evidence"
    elif "restart_candidate_evidence" in blockers and "active_heavy_job_lock" not in blockers:
        status = "blocked_by_restart_candidate_evidence"
    elif "active_training_supervisor_lock" in blockers:
        status = "blocked_by_active_training_supervisor_lock"
    else:
        status = "blocked_by_active_heavy_job_lock"

    result = {
        "requested": True,
        "ready": not blockers,
        "status": status,
        "blockers": blockers,
        "blocker_stage": blocker_stage,
        "operator_action": operator_action,
        "owner": owner,
        "pid": lock.get("pid"),
        "pid_active": lock.get("pid_active"),
        "heartbeat_at": lock.get("heartbeat_at"),
        "lock_age_minutes": lock.get("lock_age_minutes"),
        "lock_age_hours": lock.get("lock_age_hours"),
        "heartbeat_age_minutes": lock.get("heartbeat_age_minutes"),
    }
    if candidate_context:
        result["restart_candidate_evidence_ready"] = not evidence_blockers
        result["restart_candidate_evidence_blockers"] = evidence_blockers
    result.update(progress_context)
    result.update(candidate_context)
    return result


def evidence_context_summary(
    *,
    supervisor_status: dict[str, Any],
    gates: dict[str, dict[str, Any]],
    parser_sync_duplicate_checks: dict[str, Any] | None = None,
    round_repetition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    promotion = gates.get("promotion_gate") if isinstance(gates.get("promotion_gate"), dict) else {}
    eval_guard = (
        gates.get("eval_slice_overfit_guardrail")
        if isinstance(gates.get("eval_slice_overfit_guardrail"), dict)
        else {}
    )
    decision = gates.get("decision_round_best") if isinstance(gates.get("decision_round_best"), dict) else {}
    rank_homogeneity = (
        gates.get("rank_homogeneity_guardrail")
        if isinstance(gates.get("rank_homogeneity_guardrail"), dict)
        else {}
    )

    failure_modes: list[str] = []
    if promotion and not promotion.get("passed"):
        failure_modes.append(f"promotion_gate:{promotion.get('reason')}")
    if eval_guard.get("active"):
        failure_modes.append(f"eval_slice_overfit:{eval_guard.get('reason')}")
    if rank_homogeneity.get("active"):
        failure_modes.append(f"rank_homogeneity:{rank_homogeneity.get('reason')}")
    round_repetition = round_repetition if isinstance(round_repetition, dict) else {}
    if round_repetition.get("active"):
        failure_modes.append(
            "round_repetition:"
            f"{round_repetition.get('reason')}:"
            f"window={round_repetition.get('window_count')}"
        )
    blocked_count = safe_int(decision.get("blocked_candidate_count")) or 0
    if blocked_count > 0:
        blocked_sources = compact_inline_list(decision.get("blocked_candidate_sources"))
        failure_modes.append(f"blocked_candidates:{blocked_count}:{blocked_sources}")
    parser_sync_duplicate_checks = parser_sync_duplicate_checks or {
        "status": "not_loaded",
        "reason": "parser_sync_duplicate_checks_not_passed",
    }
    if parser_sync_duplicate_checks.get("status") != "checked" or not parser_sync_duplicate_checks.get("ok"):
        failure_modes.append(f"parser_sync_duplicates:{parser_sync_duplicate_checks.get('status')}")

    search_diagnostics: dict[str, Any] = {}
    if round_repetition.get("status") == "ready":
        search_diagnostics["round_repetition"] = {
            "active": round_repetition.get("active"),
            "reason": round_repetition.get("reason"),
            "window_count": round_repetition.get("window_count"),
            "latest_round": round_repetition.get("latest_round"),
            "latest_config_repeat_streak": round_repetition.get("latest_config_repeat_streak"),
            "latest_metric_repeat_streak": round_repetition.get("latest_metric_repeat_streak"),
            "interpretation": round_repetition.get("interpretation"),
        }

    return {
        "legal_sample_space": {
            "domain": "ssq_red_ball_combinations",
            "legal_universe_size": supervisor_status.get("legal_universe_size"),
            "ranked_universe_size": supervisor_status.get("ranked_universe_size"),
            "excluded_universe_count": supervisor_status.get("excluded_universe_count"),
        },
        "historical_window": {
            "history_scope": supervisor_status.get("history_scope"),
            "train_mode": supervisor_status.get("train_mode"),
            "train_window": supervisor_status.get("train_window"),
            "eval_window": supervisor_status.get("eval_window"),
            "regime_start_date": supervisor_status.get("regime_start_date"),
            "regime_years": supervisor_status.get("regime_years"),
            "top_n": supervisor_status.get("top_n"),
        },
        "baseline_or_null_model": {
            "operational_baseline": "incumbent_config_frozen_primary_baseline",
            "random_null_model": "ranked_uniform_per_draw",
            "random_null_expectation": random_null_expectation_summary(supervisor_status),
            "baseline_score": decision.get("frozen_primary_lift_baseline_score"),
        },
        "leakage_checks": {
            "promotion_gate_reason": promotion.get("reason"),
            "eval_slice_overfit_guardrail_active": bool(eval_guard.get("active")),
            "eval_slice_overfit_guardrail_reason": eval_guard.get("reason"),
            "suspicious_candidate_count": safe_int(eval_guard.get("suspicious_candidate_count")) or 0,
            "frozen_primary_lift_required": bool(decision.get("frozen_primary_lift_required")),
            "parser_sync_duplicate_checks": parser_sync_duplicate_checks,
        },
        "search_diagnostics": search_diagnostics,
        "training_status": {
            "status": supervisor_status.get("status"),
            "run_id": supervisor_status.get("run_id"),
            "pid": supervisor_status.get("pid"),
        },
        "evidence_level": "operational_training_diagnostic_no_predictive_claim",
        "risk": "Historical response-surface behavior is hypothesis evidence only; this watch does not support guaranteed hits or low-risk betting.",
        "uncertainty": "Frozen validation can remain at baseline even when eval-slice metrics look strong.",
        "failure_modes": failure_modes[:6],
    }


def summarize_watch(run_id: str | None, *, limit: int, stale_minutes: int) -> dict[str, Any]:
    limit = positive_int_or_default(limit, default=DEFAULT_ROUND_LIMIT)
    stale_minutes = positive_int_or_default(stale_minutes, default=DEFAULT_STALE_MINUTES)
    generated_at = utc_now()
    db_read_errors: list[dict[str, str]] = []
    try:
        resolved_run_id = resolve_run_id(run_id)
    except Exception as exc:
        db_read_errors.append(db_read_error_summary("resolve_run_id", exc))
        resolved_run_id = run_id or latest_supervisor_run_id_from_status_file()

    rows: list[dict[str, Any]] = []
    round_stats = default_round_stats()
    if resolved_run_id:
        try:
            rows = load_rounds(resolved_run_id, limit=limit)
        except Exception as exc:
            db_read_errors.append(db_read_error_summary("load_rounds", exc))
        try:
            round_stats = load_round_stats(resolved_run_id)
        except Exception as exc:
            db_read_errors.append(db_read_error_summary("load_round_stats", exc))
    line_progress = default_line_progress()
    if resolved_run_id:
        try:
            line_progress = load_line_progress(resolved_run_id, limit=limit)
        except Exception as exc:
            db_read_errors.append(db_read_error_summary("load_line_progress", exc))
    round_repetition = summarize_round_repetition(rows)
    latest = rows[-1] if rows else {}
    prefilter = latest.get("prefilter") if isinstance(latest.get("prefilter"), dict) else {}
    advisors = advisor_summary(prefilter)
    gates = gate_summary(prefilter)
    supervisor_status = add_supervisor_status_observation_ages(
        load_supervisor_status(resolved_run_id),
        now=generated_at,
        stale_minutes=stale_minutes,
    )
    lock = add_heavy_lock_observation_ages(heavy_lock_summary(), now=generated_at)
    parser_sync_duplicate_checks = load_parser_sync_duplicate_checks()
    history_issues = parser_sync_duplicate_checks.pop("_history_issues", [])
    advisor_signal_freshness = advisor_signal_freshness_summary(
        advisors,
        history_latest_issue=parser_sync_duplicate_checks.get("history_latest_issue"),
        history_issues=history_issues,
    )
    recommendation = recommendation_summary(
        rows=rows,
        lock=lock,
        advisors=advisors,
        gates=gates,
        now=generated_at,
        stale_minutes=stale_minutes,
        round_stats=round_stats,
        supervisor_status=supervisor_status,
        round_repetition=round_repetition,
        advisor_signal_freshness=advisor_signal_freshness,
    )
    if db_read_errors:
        actions = [
            "inspect_training_db",
            *[
                action
                for action in recommendation.get("actions", [])
                if action != "inspect_training_db"
            ],
        ]
        failed_stages = ", ".join(error["stage"] for error in db_read_errors)
        recommendation = {
            **recommendation,
            "severity": "alert",
            "action": actions[0],
            "actions": actions,
            "notes": [
                (
                    "Training database read failed during "
                    f"{failed_stages}; supervisor status-file context is diagnostic-only until DB reads recover."
                ),
                *recommendation.get("notes", []),
            ],
        }
    payload = {
        "generated_at": isoformat(generated_at),
        "run_id": resolved_run_id,
        "round_limit": limit,
        "round_window_count": len(rows),
        "stale_minutes": stale_minutes,
        "round_count": round_stats["round_count"],
        "latest_round": round_stats["latest_round"],
        "last_improved_round": round_stats["last_improved_round"],
        "stagnation_rounds": round_stats["stagnation_rounds"],
        "improvement_count": round_stats["improvement_count"],
        "latest_round_age_minutes": round_age_minutes(latest, now=generated_at) if latest else None,
        "latest_metrics": {
            "phase": latest.get("phase"),
            "step": safe_float(latest.get("step")),
            "improved": bool(latest.get("improved")) if latest else False,
            "top_100_hits": safe_int(latest.get("top_100_hits")),
            "top_1000_hits": safe_int(latest.get("top_1000_hits")),
            "top_10000_hits": safe_int(latest.get("top_10000_hits")),
            "red5_top_10000_hits": safe_int(latest.get("red5_top_10000_hits")),
            "median_rank": safe_float(latest.get("median_rank")),
            "best_rank": safe_int(latest.get("best_rank")),
            "worst_rank": safe_int(latest.get("worst_rank")),
            "objective_score": safe_float(latest.get("objective_score")),
            "best_objective_seen": round_stats["best_objective_seen"],
        },
        "candidate_budget": prefilter.get("candidate_budget") if isinstance(prefilter.get("candidate_budget"), dict) else {},
        "round_repetition": round_repetition,
        "line_progress": line_progress,
        "advisor_summary": advisors,
        "advisor_signal_freshness": advisor_signal_freshness,
        "gate_summary": gates,
        "db_read_errors": db_read_errors,
        "supervisor_status": supervisor_status,
        "supervisor_round_boundary": supervisor_round_boundary_summary(
            supervisor_status=supervisor_status,
            round_stats=round_stats,
        ),
        "evidence_context": evidence_context_summary(
            supervisor_status=supervisor_status,
            gates=gates,
            parser_sync_duplicate_checks=parser_sync_duplicate_checks,
            round_repetition=round_repetition,
        ),
        "heavy_job_lock": lock,
        "recommendation": recommendation,
        "restart_readiness": restart_readiness_summary(
            recommendation=recommendation,
            lock=lock,
            supervisor_status=supervisor_status,
            gates=gates,
        ),
        "guardrail": "Historical response-surface monitoring only; no predictive claim and no automatic promotion without controls.",
    }
    return attach_operator_summary(payload)


def markdown_metric_vector(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        return ""
    return " / ".join("" if item is None else str(item) for item in value[:3])


def render_line_progress_markdown(line_progress: Any) -> str:
    if not isinstance(line_progress, dict) or line_progress.get("status") != "ready":
        return ""
    lines = line_progress.get("lines") if isinstance(line_progress.get("lines"), dict) else {}
    if not lines:
        return ""
    rows = "\n".join(
        "| "
        f"{markdown_inline_code(line_key)} | "
        f"{line.get('round_index')} | "
        f"{markdown_inline_text(markdown_metric_vector(line.get('exact_top_100_1000_10000')))} | "
        f"{markdown_inline_text(markdown_metric_vector(line.get('red5_top_100_1000_10000')))} | "
        f"{markdown_inline_text(markdown_metric_vector(line.get('recent_exact_top_100_1000_10000_total')))} | "
        f"{markdown_inline_text(markdown_metric_vector(line.get('recent_red5_top_100_1000_10000_total')))} | "
        f"{markdown_inline_text(line.get('status'))} | "
        f"{markdown_inline_text(line.get('policy_key'))} |"
        for line_key, line in sorted(lines.items())
        if isinstance(line, dict)
    )
    comparison = line_progress.get("comparison") if isinstance(line_progress.get("comparison"), dict) else {}
    comparison_line = ""
    if comparison:
        comparison_line = (
            "\nDynamic minus static latest exact delta: "
            f"{markdown_inline_text(markdown_metric_vector(comparison.get('exact_delta_dynamic_minus_static')))}; "
            "red5 delta: "
            f"{markdown_inline_text(markdown_metric_vector(comparison.get('red5_delta_dynamic_minus_static')))}.\n"
        )
    return f"""## Line Progress

| Line | Round | Exact Top100/1000/10000 | Red5 Top100/1000/10000 | Recent exact total | Recent red5 total | Status | Policy |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
{rows}
{comparison_line}
"""


def render_round_repetition_markdown(round_repetition: Any) -> str:
    if not isinstance(round_repetition, dict) or round_repetition.get("status") != "ready":
        return ""
    return (
        "## Round Repetition Diagnostic\n\n"
        "- Status: "
        f"active={round_repetition.get('active')} "
        f"reason={markdown_inline_text(round_repetition.get('reason'))} "
        f"window={round_repetition.get('window_count')} "
        f"latest_round={round_repetition.get('latest_round')}\n"
        "- Config repeats: "
        f"unique={round_repetition.get('unique_config_count')}/"
        f"{round_repetition.get('observed_config_count')} "
        f"dominant={markdown_inline_text(round_repetition.get('dominant_config_hash'))} "
        f"dominant_count={round_repetition.get('dominant_config_repeat_count')} "
        f"latest_streak={round_repetition.get('latest_config_repeat_streak')}\n"
        "- Metric repeats: "
        f"unique={round_repetition.get('unique_metric_signature_count')}/"
        f"{round_repetition.get('window_count')} "
        f"dominant={markdown_inline_text(round_repetition.get('dominant_metric_signature_hash'))} "
        f"dominant_count={round_repetition.get('dominant_metric_repeat_count')} "
        f"latest_streak={round_repetition.get('latest_metric_repeat_streak')}\n"
        "- Interpretation: "
        f"{markdown_inline_text(round_repetition.get('interpretation'))}\n\n"
    )


def render_markdown(payload: dict[str, Any]) -> str:
    latest = payload["latest_metrics"]
    rec = payload["recommendation"]
    window_line = ""
    if payload.get("round_window_count") is not None or payload.get("round_limit") is not None:
        window_line = f"\n- Recent window: {payload.get('round_window_count')} / limit {payload.get('round_limit')}"
    advisor_rows = "\n".join(
        f"| {markdown_inline_text(key)} | {value.get('candidate_count', 0)} | {value.get('selected_count', 0)} | "
        f"{value.get('rejected_count', 0)} | "
        f"{markdown_inline_text(', '.join(str(item) for item in value.get('selected_fields', [])[:6]))} |"
        for key, value in payload["advisor_summary"].items()
    )
    advisor_freshness = (
        payload.get("advisor_signal_freshness")
        if isinstance(payload.get("advisor_signal_freshness"), dict)
        else {}
    )
    advisor_freshness_rows = "\n".join(
        f"| {markdown_inline_text(key)} | {markdown_inline_text(value.get('status'))} | "
        f"{markdown_inline_text(value.get('latest_signal_issue'))} | {value.get('issue_lag')} |"
        for key, value in (advisor_freshness.get("advisors") or {}).items()
        if isinstance(value, dict)
    )
    note_rows = "\n".join(f"- {markdown_inline_text(note)}" for note in rec.get("notes", []))
    gates = payload.get("gate_summary") if isinstance(payload.get("gate_summary"), dict) else {}
    gate_section = ""
    if gates:
        promotion = gates.get("promotion_gate") if isinstance(gates.get("promotion_gate"), dict) else {}
        eval_guard = (
            gates.get("eval_slice_overfit_guardrail")
            if isinstance(gates.get("eval_slice_overfit_guardrail"), dict)
            else {}
        )
        stale_gate = (
            gates.get("stale_round_best_search_base_gate")
            if isinstance(gates.get("stale_round_best_search_base_gate"), dict)
            else {}
        )
        rank_homogeneity = (
            gates.get("rank_homogeneity_guardrail")
            if isinstance(gates.get("rank_homogeneity_guardrail"), dict)
            else {}
        )
        restart_champion = (
            gates.get("rank_homogeneity_restart_champion")
            if isinstance(gates.get("rank_homogeneity_restart_champion"), dict)
            else {}
        )
        navigation = (
            gates.get("experimental_navigation_candidate")
            if isinstance(gates.get("experimental_navigation_candidate"), dict)
            else {}
        )
        decision = gates.get("decision_round_best") if isinstance(gates.get("decision_round_best"), dict) else {}
        gate_lines = ["## Gate Snapshot", ""]
        if promotion:
            gate_lines.append(
                "- Promotion gate: "
                f"passed={promotion.get('passed')} "
                f"reason={markdown_inline_text(promotion.get('reason'))} "
                f"candidate_primary={promotion.get('candidate_primary_score')} "
                f"incumbent_primary={promotion.get('incumbent_primary_score')}"
            )
        if eval_guard:
            source_counts = compact_count_map(eval_guard.get("source_counts"))
            issue_counts = compact_count_map(eval_guard.get("issue_counts"))
            gate_lines.append(
                "- Eval-slice overfit guardrail: "
                f"active={eval_guard.get('active')} "
                f"reason={markdown_inline_text(eval_guard.get('reason'))} "
                f"eval_primary={eval_guard.get('round_best_eval_primary_score')} "
                f"frozen_primary={eval_guard.get('round_best_frozen_primary_score')} "
                f"suspicious={eval_guard.get('suspicious_candidate_count')} "
                f"sources={markdown_inline_text(source_counts)} "
                f"issues={markdown_inline_text(issue_counts)}"
            )
        if stale_gate:
            gate_lines.append(
                "- Search-base gate: "
                f"active={stale_gate.get('active')} "
                f"reason={markdown_inline_text(stale_gate.get('reason'))} "
                f"require_frozen_primary_challenger={stale_gate.get('require_frozen_primary_challenger')}"
            )
        if rank_homogeneity:
            signature_hashes = compact_inline_list(rank_homogeneity.get("signature_hashes"), limit=3)
            gate_lines.append(
                "- Rank homogeneity: "
                f"active={rank_homogeneity.get('active')} "
                f"reason={markdown_inline_text(rank_homogeneity.get('reason'))} "
                f"window={rank_homogeneity.get('window')} "
                f"observed={rank_homogeneity.get('observed')} "
                f"unique_signatures={rank_homogeneity.get('unique_signature_count')}/"
                f"{rank_homogeneity.get('max_unique_signatures')} "
                f"stagnation={rank_homogeneity.get('stagnation_rounds')}/"
                f"{rank_homogeneity.get('stagnation_threshold')} "
                f"signature_hashes={markdown_inline_text(signature_hashes)}"
            )
        if restart_champion:
            gate_lines.append(
                "- Restart champion: "
                f"active={restart_champion.get('active')} "
                f"reason={markdown_inline_text(restart_champion.get('reason'))} "
                f"rank_vector_changed={restart_champion.get('rank_vector_changed')} "
                f"changed_targets={restart_champion.get('changed_target_count')} "
                f"full_eval_rank={restart_champion.get('full_eval_rank')} "
                f"max_abs_delta={restart_champion.get('max_abs_delta')} "
                f"primary_pattern={markdown_inline_text(restart_champion.get('primary_weight_pattern'))} "
                f"context_moves={restart_champion.get('context_field_movement_count')} "
                f"frozen_primary={restart_champion.get('frozen_primary_score')} "
                f"tail1000000_delta={restart_champion.get('tail_over_1000000_delta')} "
                f"source_frontier_improved={restart_champion.get('source_frontier_score_improved')} "
                f"frontier_basis={markdown_inline_text(restart_champion.get('source_frontier_improvement_basis'))} "
                f"primary_improved={restart_champion.get('source_frontier_primary_score_improved')} "
                f"secondary_improved={restart_champion.get('source_frontier_secondary_score_improved')} "
                f"unique_signatures={restart_champion.get('unique_rank_signature_count')}"
            )
        if navigation:
            navigation_details = [
                "- Experimental navigation:"
            ]
            navigation_fields = [
                ("source", "source"),
                ("reason", "reason"),
                ("eligible", "eligible"),
                ("eligibility_reason", "eligibility_reason"),
                ("quality", "quality_reason"),
                ("rank_vector_changed", "rank_vector_changed"),
            ]
            if navigation.get("config_distance") is not None:
                navigation_fields.extend(
                    [
                        ("config_distance", "config_distance"),
                        ("min_config_distance", "min_config_distance"),
                    ]
                )
            navigation_details.append(
                compact_observed_fields(
                    [
                        (label, markdown_inline_text(navigation.get(key)))
                        for label, key in navigation_fields
                    ]
                )
            )
            gate_lines.append(" ".join(navigation_details))
        if decision:
            blocked_sources = compact_inline_list(decision.get("blocked_candidate_sources"))
            gate_lines.append(
                "- Decision round best: "
                f"source={markdown_inline_text(decision.get('source'))} "
                f"reason={markdown_inline_text(decision.get('reason'))} "
                f"selected_frozen_primary={decision.get('selected_frozen_primary_score')} "
                f"blocked_candidates={decision.get('blocked_candidate_count')} "
                f"blocked_sources={markdown_inline_text(blocked_sources)}"
            )
        gate_section = "\n".join(gate_lines) + "\n\n"
    restart_readiness = (
        payload.get("restart_readiness")
        if isinstance(payload.get("restart_readiness"), dict)
        else {}
    )
    restart_section = ""
    if restart_readiness.get("requested"):
        blockers = compact_inline_list(restart_readiness.get("blockers"))
        operator_action_line = ""
        if restart_readiness.get("operator_action"):
            operator_action_line = (
                "- Operator action: "
                f"{markdown_inline_text(restart_readiness.get('operator_action'))}\n"
            )
        blocker_stage_line = ""
        if restart_readiness.get("blocker_stage"):
            blocker_stage_line = (
                "- Blocker stage: "
                f"{markdown_inline_text(restart_readiness.get('blocker_stage'))}\n"
            )
        lock_age_line = ""
        if restart_readiness.get("lock_age_hours") is not None:
            lock_age_line = f"- Lock age: {restart_readiness.get('lock_age_hours')} hours\n"
        heartbeat_age_line = ""
        if restart_readiness.get("heartbeat_age_minutes") is not None:
            heartbeat_age_line = (
                f"- Heartbeat age: {restart_readiness.get('heartbeat_age_minutes')} minutes\n"
            )
        restart_candidate_lines = ""
        if restart_readiness.get("restart_candidate_active") is not None:
            restart_candidate_lines += (
                "- Restart candidate: "
                f"active={restart_readiness.get('restart_candidate_active')} "
                f"source={markdown_inline_text(restart_readiness.get('restart_candidate_source'))} "
                f"reason={markdown_inline_text(restart_readiness.get('restart_candidate_reason'))} "
                f"rank_vector_changed={restart_readiness.get('restart_candidate_rank_vector_changed')} "
                f"changed_targets={restart_readiness.get('restart_candidate_changed_target_count')} "
                f"full_eval_rank={restart_readiness.get('restart_candidate_full_eval_rank')}\n"
            )
            restart_candidate_lines += (
                "- Restart candidate evidence: "
                f"frozen_primary={restart_readiness.get('restart_candidate_frozen_primary_score')} "
                f"baseline_frozen_primary={restart_readiness.get('restart_candidate_baseline_frozen_primary_score')} "
                f"primary_improved={restart_readiness.get('restart_candidate_primary_score_improved')} "
                f"secondary_improved={restart_readiness.get('restart_candidate_secondary_score_improved')} "
                f"frontier_basis={markdown_inline_text(restart_readiness.get('restart_candidate_improvement_basis'))} "
                f"tail1000000_delta={restart_readiness.get('restart_candidate_tail_over_1000000_delta')}\n"
            )
        if restart_readiness.get("restart_candidate_evidence_ready") is not None:
            evidence_blockers = compact_inline_list(
                restart_readiness.get("restart_candidate_evidence_blockers")
            )
            restart_candidate_lines += (
                "- Restart candidate evidence gate: "
                f"ready={restart_readiness.get('restart_candidate_evidence_ready')} "
                f"blockers={markdown_inline_text(evidence_blockers)}\n"
            )
        if restart_readiness.get("experimental_navigation_eligible") is not None:
            restart_candidate_lines += (
                "- Experimental navigation readiness: "
                f"eligible={restart_readiness.get('experimental_navigation_eligible')} "
                f"reason={markdown_inline_text(restart_readiness.get('experimental_navigation_eligibility_reason'))} "
                f"quality={markdown_inline_text(restart_readiness.get('experimental_navigation_quality_reason'))} "
                f"rank_vector_changed={restart_readiness.get('experimental_navigation_rank_vector_changed')} "
                f"config_distance={restart_readiness.get('experimental_navigation_config_distance')} "
                f"min_config_distance={restart_readiness.get('experimental_navigation_min_config_distance')}\n"
            )
        supervisor_progress_lines = ""
        if restart_readiness.get("supervisor_progress_fresh") is not None:
            if restart_readiness.get("supervisor_status") is not None:
                supervisor_progress_lines += (
                    f"- Supervisor status: {markdown_inline_text(restart_readiness.get('supervisor_status'))}\n"
                )
            if restart_readiness.get("supervisor_run_mode") is not None:
                supervisor_progress_lines += (
                    f"- Supervisor run mode: {markdown_inline_text(restart_readiness.get('supervisor_run_mode'))}\n"
                )
            if restart_readiness.get("supervisor_deadline") is not None:
                supervisor_progress_lines += (
                    f"- Supervisor deadline: {markdown_inline_text(restart_readiness.get('supervisor_deadline'))}\n"
                )
            if restart_readiness.get("supervisor_progress_stale_minutes") is not None:
                supervisor_progress_lines += (
                    f"- Supervisor progress fresh: {restart_readiness.get('supervisor_progress_fresh')} "
                    f"(threshold {restart_readiness.get('supervisor_progress_stale_minutes')} minutes)\n"
                )
            else:
                supervisor_progress_lines += (
                    "- Supervisor progress fresh: "
                    f"{restart_readiness.get('supervisor_progress_fresh')} "
                    f"(age={restart_readiness.get('supervisor_progress_age_minutes')} minutes, "
                    f"round={restart_readiness.get('supervisor_progress_round')})\n"
                )
            if restart_readiness.get("supervisor_progress_round") is not None:
                supervisor_progress_lines += (
                    f"- Supervisor progress round: {restart_readiness.get('supervisor_progress_round')}\n"
                )
            if (
                restart_readiness.get("supervisor_target_index") is not None
                and restart_readiness.get("supervisor_target_total") is not None
            ):
                supervisor_progress_lines += (
                    "- Supervisor target progress: "
                    f"{restart_readiness.get('supervisor_target_index')} / "
                    f"{restart_readiness.get('supervisor_target_total')} "
                    f"complete={restart_readiness.get('supervisor_target_complete')}\n"
                )
            if restart_readiness.get("supervisor_progress_age_minutes") is not None:
                supervisor_progress_lines += (
                    "- Supervisor progress age: "
                    f"{restart_readiness.get('supervisor_progress_age_minutes')} minutes\n"
                )
            if restart_readiness.get("supervisor_updated_age_minutes") is not None:
                supervisor_progress_lines += (
                    "- Supervisor status age: "
                    f"{restart_readiness.get('supervisor_updated_age_minutes')} minutes\n"
                )
        restart_section = (
            "## Restart Readiness\n\n"
            f"- Ready for fresh supervisor: {restart_readiness.get('ready')}\n"
            f"- Status: {markdown_inline_text(restart_readiness.get('status'))}\n"
            f"- Blockers: {markdown_inline_text(blockers)}\n"
            f"{blocker_stage_line}"
            f"{operator_action_line}"
            f"- Lock owner/PID: {markdown_inline_text(restart_readiness.get('owner'))} / {restart_readiness.get('pid')}\n"
            f"- Heartbeat: {markdown_inline_text(restart_readiness.get('heartbeat_at'))}\n"
            f"{lock_age_line}"
            f"{heartbeat_age_line}"
            f"{restart_candidate_lines}"
            f"{supervisor_progress_lines}\n"
        )
    line_progress_section = render_line_progress_markdown(payload.get("line_progress"))
    round_repetition_section = render_round_repetition_markdown(
        payload.get("round_repetition")
    )
    supervisor_status = (
        payload.get("supervisor_status")
        if isinstance(payload.get("supervisor_status"), dict)
        else {}
    )
    supervisor_section = ""
    if supervisor_status.get("available"):
        progress = (
            supervisor_status.get("latest_progress")
            if isinstance(supervisor_status.get("latest_progress"), dict)
            else {}
        )
        progress_lines = ""
        if progress:
            progress_age_line = ""
            if progress.get("age_minutes") is not None:
                progress_age_line = f"- Progress age: {progress.get('age_minutes')} minutes\n"
            progress_fresh_line = ""
            if progress.get("fresh") is not None:
                progress_fresh_line = (
                    f"- Progress fresh: {progress.get('fresh')} "
                    f"(threshold {progress.get('freshness_threshold_minutes')} minutes)\n"
                )
            progress_lines = (
                f"- Progress round: {progress.get('round')}\n"
                f"- Target progress: {progress.get('target_index')} / {progress.get('target_total')}\n"
                f"- Target complete: {progress.get('target_complete')}\n"
                f"- Issue: {markdown_inline_text(progress.get('issue'))}\n"
                f"- Train draws: {progress.get('train_draws')}\n"
                f"- Elapsed seconds: {progress.get('elapsed_seconds')}\n"
                f"- Progress logged at: {markdown_inline_text(progress.get('logged_at'))}\n"
                f"{progress_age_line}"
                f"{progress_fresh_line}"
            )
        round_boundary = (
            payload.get("supervisor_round_boundary")
            if isinstance(payload.get("supervisor_round_boundary"), dict)
            else {}
        )
        round_boundary_line = ""
        if round_boundary:
            round_boundary_line = (
                "- Round boundary: "
                f"status={markdown_inline_text(round_boundary.get('status'))} "
                f"progress_round={round_boundary.get('supervisor_progress_round')} "
                f"latest_db_round={round_boundary.get('latest_db_round')} "
                f"round_lag={round_boundary.get('round_lag')} "
                f"target_complete={round_boundary.get('target_complete')}\n"
            )
        supervisor_section = (
            "## Supervisor Progress\n\n"
            f"- Status/PID: {markdown_inline_text(supervisor_status.get('status'))} / {supervisor_status.get('pid')}\n"
            f"- Run mode: {markdown_inline_text(supervisor_status.get('run_mode'))}\n"
            f"- Deadline: {markdown_inline_text(supervisor_status.get('deadline'))}\n"
            f"- Updated at: {markdown_inline_text(supervisor_status.get('updated_at'))}\n"
            f"- Updated age: {supervisor_status.get('updated_at_age_minutes')} minutes\n"
            f"- Status file: {markdown_inline_code(supervisor_status.get('path'))}\n"
            f"{progress_lines}\n"
            f"{round_boundary_line}"
        )
    evidence_context = (
        payload.get("evidence_context")
        if isinstance(payload.get("evidence_context"), dict)
        else {}
    )
    evidence_section = ""
    if evidence_context:
        legal = (
            evidence_context.get("legal_sample_space")
            if isinstance(evidence_context.get("legal_sample_space"), dict)
            else {}
        )
        historical = (
            evidence_context.get("historical_window")
            if isinstance(evidence_context.get("historical_window"), dict)
            else {}
        )
        baseline = (
            evidence_context.get("baseline_or_null_model")
            if isinstance(evidence_context.get("baseline_or_null_model"), dict)
            else {}
        )
        leakage = (
            evidence_context.get("leakage_checks")
            if isinstance(evidence_context.get("leakage_checks"), dict)
            else {}
        )
        search_diagnostics = (
            evidence_context.get("search_diagnostics")
            if isinstance(evidence_context.get("search_diagnostics"), dict)
            else {}
        )
        repetition = (
            search_diagnostics.get("round_repetition")
            if isinstance(search_diagnostics.get("round_repetition"), dict)
            else {}
        )
        search_line = ""
        if repetition:
            search_line = (
                "- Search diagnostics: "
                f"round_repetition_active={repetition.get('active')} "
                f"reason={markdown_inline_text(repetition.get('reason'))} "
                f"window={repetition.get('window_count')} "
                f"config_streak={repetition.get('latest_config_repeat_streak')} "
                f"metric_streak={repetition.get('latest_metric_repeat_streak')} "
                f"interpretation={markdown_inline_text(repetition.get('interpretation'))}\n"
            )
        failure_modes = compact_inline_list(evidence_context.get("failure_modes"))
        random_null_expectation = compact_random_null_expectation(
            baseline.get("random_null_expectation")
        )
        evidence_section = (
            "## Evidence Context\n\n"
            "- Legal sample space: "
            f"domain={markdown_inline_text(legal.get('domain'))} "
            f"legal_universe={legal.get('legal_universe_size')} "
            f"ranked_universe={legal.get('ranked_universe_size')} "
            f"excluded={legal.get('excluded_universe_count')}\n"
            "- Historical window: "
            f"scope={markdown_inline_text(historical.get('history_scope'))} "
            f"mode={markdown_inline_text(historical.get('train_mode'))} "
            f"train_window={historical.get('train_window')} "
            f"eval_window={historical.get('eval_window')} "
            f"regime_start={markdown_inline_text(historical.get('regime_start_date'))} "
            f"regime_years={historical.get('regime_years')} "
            f"top_n={historical.get('top_n')}\n"
            "- Baseline/null model: "
            f"operational={markdown_inline_text(baseline.get('operational_baseline'))} "
            f"random_null={markdown_inline_text(baseline.get('random_null_model'))} "
            f"random_null_eval={markdown_inline_text(random_null_expectation)} "
            f"baseline_score={baseline.get('baseline_score')}\n"
            "- Leakage checks: "
            f"promotion_gate={markdown_inline_text(leakage.get('promotion_gate_reason'))} "
            f"eval_overfit_active={leakage.get('eval_slice_overfit_guardrail_active')} "
            f"eval_reason={markdown_inline_text(leakage.get('eval_slice_overfit_guardrail_reason'))} "
            f"suspicious={leakage.get('suspicious_candidate_count')} "
            f"frozen_required={leakage.get('frozen_primary_lift_required')} "
            "parser_sync_duplicates="
            f"{markdown_inline_text(compact_parser_sync_duplicate_checks(leakage.get('parser_sync_duplicate_checks')))}\n"
            f"{search_line}"
            "- Evidence/risk: "
            f"{markdown_inline_text(evidence_context.get('evidence_level'))}; "
            f"{markdown_inline_text(evidence_context.get('risk'))}\n"
            f"- Uncertainty: {markdown_inline_text(evidence_context.get('uncertainty'))}\n"
            f"- Failure modes: {markdown_inline_text(failure_modes)}\n\n"
        )
    db_read_errors = (
        payload.get("db_read_errors")
        if isinstance(payload.get("db_read_errors"), list)
        else []
    )
    db_error_section = ""
    if db_read_errors:
        db_error_rows = "\n".join(
            "- "
            f"stage={markdown_inline_text(error.get('stage'))} "
            f"type={markdown_inline_text(error.get('error_type'))} "
            f"error={markdown_inline_text(error.get('error'))}"
            for error in db_read_errors
            if isinstance(error, dict)
        )
        db_error_section = f"## Database Read Errors\n\n{db_error_rows}\n\n"
    return f"""# DEHPS Training Watch

- Generated at: {payload.get("generated_at")}
- Run id: {markdown_inline_code(payload.get("run_id") or "")}
- Rounds: {payload.get("round_count")}{window_line}
- Latest round: {payload.get("latest_round")}
- Last improved round: {payload.get("last_improved_round")}
- Stagnation rounds: {payload.get("stagnation_rounds")}
- Severity: {markdown_inline_code(rec.get("severity"))}
- Action: {markdown_inline_code(rec.get("action"))}

## Latest Metrics

- Phase/step: {markdown_inline_text(latest.get("phase"))} / {latest.get("step")}
- Improved: {latest.get("improved")}
- Top100/1000/10000: {latest.get("top_100_hits")} / {latest.get("top_1000_hits")} / {latest.get("top_10000_hits")}
- Red5 Top10000: {latest.get("red5_top_10000_hits")}
- Rank best/median/worst: {latest.get("best_rank")} / {latest.get("median_rank")} / {latest.get("worst_rank")}
- Objective latest/best seen: {latest.get("objective_score")} / {latest.get("best_objective_seen")}

## Advisor Snapshot

| Advisor | Candidates | Selected | Rejected | Selected fields |
| --- | ---: | ---: | ---: | --- |
{advisor_rows}

## Advisor Signal Freshness

- Status: `{advisor_freshness.get("status")}`
- History latest issue: `{advisor_freshness.get("history_latest_issue")}`
- Max allowed issue lag: `{advisor_freshness.get("max_allowed_issue_lag")}`

| Advisor | Status | Latest signal issue | Issue lag |
| --- | --- | --- | ---: |
{advisor_freshness_rows}

{gate_section}\
{round_repetition_section}\
{line_progress_section}\
{restart_section}\
{supervisor_section}\
{evidence_section}\
{db_error_section}\
## Heavy Job Lock

```json
{json.dumps(payload.get("heavy_job_lock", {}), ensure_ascii=False, indent=2)}
```

## Judgement

{note_rows}

## Guardrail

{payload.get("guardrail")}
"""


def write_outputs(payload: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = attach_operator_summary(payload)
    stamp = utc_stamp()
    run_id = safe_filename_component(payload.get("run_id"))
    json_path = output_dir / f"training-watch-{run_id}-{stamp}.json"
    md_path = output_dir / f"training-watch-{run_id}-{stamp}.md"
    latest_json = output_dir / "training-watch-latest.json"
    latest_md = output_dir / "training-watch-latest.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    md_text = render_markdown(payload)
    atomic_write_text(json_path, json_text)
    atomic_write_text(md_path, md_text)
    atomic_write_text(latest_json, json_text)
    atomic_write_text(latest_md, md_text)
    return json_path, md_path


def cli_evidence_context_summary(payload: dict[str, Any]) -> dict[str, Any]:
    evidence_context = (
        payload.get("evidence_context")
        if isinstance(payload.get("evidence_context"), dict)
        else {}
    )
    if not evidence_context:
        return {}

    legal = (
        evidence_context.get("legal_sample_space")
        if isinstance(evidence_context.get("legal_sample_space"), dict)
        else {}
    )
    historical = (
        evidence_context.get("historical_window")
        if isinstance(evidence_context.get("historical_window"), dict)
        else {}
    )
    baseline = (
        evidence_context.get("baseline_or_null_model")
        if isinstance(evidence_context.get("baseline_or_null_model"), dict)
        else {}
    )
    leakage = (
        evidence_context.get("leakage_checks")
        if isinstance(evidence_context.get("leakage_checks"), dict)
        else {}
    )
    search_diagnostics = (
        evidence_context.get("search_diagnostics")
        if isinstance(evidence_context.get("search_diagnostics"), dict)
        else {}
    )
    repetition = (
        search_diagnostics.get("round_repetition")
        if isinstance(search_diagnostics.get("round_repetition"), dict)
        else {}
    )
    parser_checks = (
        leakage.get("parser_sync_duplicate_checks")
        if isinstance(leakage.get("parser_sync_duplicate_checks"), dict)
        else {}
    )
    random_null_expectation = (
        baseline.get("random_null_expectation")
        if isinstance(baseline.get("random_null_expectation"), dict)
        else {}
    )
    return {
        "evidence_level": evidence_context.get("evidence_level"),
        "risk": evidence_context.get("risk"),
        "uncertainty": evidence_context.get("uncertainty"),
        "failure_modes": (
            evidence_context.get("failure_modes")
            if isinstance(evidence_context.get("failure_modes"), list)
            else []
        ),
        "legal_sample_space": {
            "domain": legal.get("domain"),
            "legal_universe_size": legal.get("legal_universe_size"),
            "ranked_universe_size": legal.get("ranked_universe_size"),
            "excluded_universe_count": legal.get("excluded_universe_count"),
        },
        "historical_window": {
            "history_scope": historical.get("history_scope"),
            "train_mode": historical.get("train_mode"),
            "train_window": historical.get("train_window"),
            "eval_window": historical.get("eval_window"),
            "regime_start_date": historical.get("regime_start_date"),
            "top_n": historical.get("top_n"),
        },
        "baseline_or_null_model": {
            "operational_baseline": baseline.get("operational_baseline"),
            "random_null_model": baseline.get("random_null_model"),
            "random_null_expectation_status": random_null_expectation.get("status"),
            "baseline_score": baseline.get("baseline_score"),
        },
        "leakage_checks": {
            "promotion_gate_reason": leakage.get("promotion_gate_reason"),
            "eval_slice_overfit_guardrail_active": leakage.get("eval_slice_overfit_guardrail_active"),
            "suspicious_candidate_count": leakage.get("suspicious_candidate_count"),
            "frozen_primary_lift_required": leakage.get("frozen_primary_lift_required"),
            "parser_sync_duplicate_status": parser_checks.get("status"),
            "parser_sync_duplicate_ok": parser_checks.get("ok"),
        },
        "search_diagnostics": {
            "round_repetition": {
                "active": repetition.get("active"),
                "reason": repetition.get("reason"),
                "window_count": repetition.get("window_count"),
                "latest_config_repeat_streak": repetition.get("latest_config_repeat_streak"),
                "latest_metric_repeat_streak": repetition.get("latest_metric_repeat_streak"),
                "interpretation": repetition.get("interpretation"),
            }
        }
        if repetition
        else {},
    }


def operator_summary(payload: dict[str, Any]) -> dict[str, Any]:
    recommendation = (
        payload.get("recommendation")
        if isinstance(payload.get("recommendation"), dict)
        else {}
    )
    summary = {
        "run_id": payload.get("run_id"),
        "round_count": payload.get("round_count"),
        "round_window_count": payload.get("round_window_count"),
        "severity": recommendation.get("severity"),
        "action": recommendation.get("action"),
    }
    evidence_context = cli_evidence_context_summary(payload)
    if evidence_context:
        summary["evidence_context"] = evidence_context
    db_read_errors = (
        payload.get("db_read_errors")
        if isinstance(payload.get("db_read_errors"), list)
        else []
    )
    if db_read_errors:
        summary["db_read_errors"] = [
            {
                "stage": error.get("stage"),
                "error_type": error.get("error_type"),
                "error": error.get("error"),
            }
            for error in db_read_errors
            if isinstance(error, dict)
        ]
    round_boundary = (
        payload.get("supervisor_round_boundary")
        if isinstance(payload.get("supervisor_round_boundary"), dict)
        else {}
    )
    if round_boundary:
        summary["supervisor_round_boundary"] = {
            "status": round_boundary.get("status"),
            "supervisor_progress_round": round_boundary.get("supervisor_progress_round"),
            "latest_db_round": round_boundary.get("latest_db_round"),
            "round_lag": round_boundary.get("round_lag"),
            "target_index": round_boundary.get("target_index"),
            "target_total": round_boundary.get("target_total"),
            "target_complete": round_boundary.get("target_complete"),
            "progress_fresh": round_boundary.get("progress_fresh"),
            "progress_age_minutes": round_boundary.get("progress_age_minutes"),
        }
    line_progress = (
        payload.get("line_progress")
        if isinstance(payload.get("line_progress"), dict)
        else {}
    )
    if line_progress:
        summary["line_progress"] = {
            "status": line_progress.get("status"),
            "latest_round": line_progress.get("latest_round"),
            "lines": line_progress.get("lines") or {},
            "comparison": line_progress.get("comparison") or {},
        }
    round_repetition = (
        payload.get("round_repetition")
        if isinstance(payload.get("round_repetition"), dict)
        else {}
    )
    if round_repetition and round_repetition.get("status") == "ready":
        summary["round_repetition"] = {
            "active": round_repetition.get("active"),
            "reason": round_repetition.get("reason"),
            "window_count": round_repetition.get("window_count"),
            "latest_round": round_repetition.get("latest_round"),
            "unique_config_count": round_repetition.get("unique_config_count"),
            "observed_config_count": round_repetition.get("observed_config_count"),
            "dominant_config_repeat_count": round_repetition.get(
                "dominant_config_repeat_count"
            ),
            "latest_config_repeat_streak": round_repetition.get(
                "latest_config_repeat_streak"
            ),
            "dominant_config_hash": round_repetition.get("dominant_config_hash"),
            "unique_metric_signature_count": round_repetition.get(
                "unique_metric_signature_count"
            ),
            "dominant_metric_repeat_count": round_repetition.get(
                "dominant_metric_repeat_count"
            ),
            "latest_metric_repeat_streak": round_repetition.get(
                "latest_metric_repeat_streak"
            ),
            "dominant_metric_signature_hash": round_repetition.get(
                "dominant_metric_signature_hash"
            ),
            "interpretation": round_repetition.get("interpretation"),
        }
    advisor_freshness = (
        payload.get("advisor_signal_freshness")
        if isinstance(payload.get("advisor_signal_freshness"), dict)
        else {}
    )
    if advisor_freshness:
        summary["advisor_signal_freshness"] = {
            "status": advisor_freshness.get("status"),
            "history_latest_issue": advisor_freshness.get("history_latest_issue"),
            "max_allowed_issue_lag": advisor_freshness.get("max_allowed_issue_lag"),
            "stale_advisors": advisor_freshness.get("stale_advisors") or [],
            "missing_advisors": advisor_freshness.get("missing_advisors") or [],
            "future_advisors": advisor_freshness.get("future_advisors") or [],
            "advisors": advisor_freshness.get("advisors") or {},
        }
    gates = (
        payload.get("gate_summary")
        if isinstance(payload.get("gate_summary"), dict)
        else {}
    )
    rank_homogeneity = (
        gates.get("rank_homogeneity_guardrail")
        if isinstance(gates.get("rank_homogeneity_guardrail"), dict)
        else {}
    )
    if rank_homogeneity.get("active"):
        rank_summary: dict[str, Any] = {
            "reason": rank_homogeneity.get("reason"),
            "unique_signature_count": rank_homogeneity.get("unique_signature_count"),
            "signature_hashes": rank_homogeneity.get("signature_hashes") or [],
        }
        for key in (
            "stagnation_rounds",
            "stagnation_threshold",
            "window",
            "observed",
            "max_unique_signatures",
        ):
            if rank_homogeneity.get(key) is not None:
                rank_summary[key] = rank_homogeneity.get(key)
        summary["rank_homogeneity"] = rank_summary
    restart_champion = (
        gates.get("rank_homogeneity_restart_champion")
        if isinstance(gates.get("rank_homogeneity_restart_champion"), dict)
        else {}
    )
    if restart_champion.get("active"):
        summary["rank_homogeneity_restart_champion"] = {
            "source": restart_champion.get("source"),
            "reason": restart_champion.get("reason"),
            "rank_vector_changed": restart_champion.get("rank_vector_changed"),
            "changed_target_count": restart_champion.get("changed_target_count"),
            "full_eval_rank": restart_champion.get("full_eval_rank"),
            "frozen_primary_score": restart_champion.get("frozen_primary_score"),
            "tail_over_1000000_delta": restart_champion.get("tail_over_1000000_delta"),
            "source_frontier_score_improved": restart_champion.get(
                "source_frontier_score_improved"
            ),
            "source_frontier_improvement_basis": restart_champion.get(
                "source_frontier_improvement_basis"
            ),
        }
    navigation = (
        gates.get("experimental_navigation_candidate")
        if isinstance(gates.get("experimental_navigation_candidate"), dict)
        else {}
    )
    if navigation:
        candidate_present = navigation.get("candidate_present")
        if candidate_present is None:
            candidate_present = experimental_navigation_candidate_present(navigation)
        navigation_summary = {
            "source": navigation.get("source"),
            "reason": navigation.get("reason"),
            "candidate_present": bool(candidate_present),
        }
        for key in (
            "eligible",
            "eligibility_reason",
            "quality_reason",
            "rank_vector_changed",
            "config_distance",
            "min_config_distance",
        ):
            if navigation.get(key) is not None:
                navigation_summary[key] = navigation.get(key)
        summary["experimental_navigation_candidate"] = navigation_summary
    decision = (
        gates.get("decision_round_best")
        if isinstance(gates.get("decision_round_best"), dict)
        else {}
    )
    if decision:
        summary["decision_round_best"] = {
            "source": decision.get("source"),
            "reason": decision.get("reason"),
            "selected_frozen_primary_score": decision.get("selected_frozen_primary_score"),
            "blocked_candidate_count": decision.get("blocked_candidate_count"),
            "blocked_candidate_sources": decision.get("blocked_candidate_sources") or [],
        }
    restart_readiness = (
        payload.get("restart_readiness")
        if isinstance(payload.get("restart_readiness"), dict)
        else {}
    )
    if restart_readiness.get("requested"):
        readiness = {
            "ready": restart_readiness.get("ready"),
            "status": restart_readiness.get("status"),
            "blockers": restart_readiness.get("blockers") or [],
            "operator_action": restart_readiness.get("operator_action"),
            "owner": restart_readiness.get("owner"),
            "pid": restart_readiness.get("pid"),
            "heartbeat_age_minutes": restart_readiness.get("heartbeat_age_minutes"),
        }
        for key in (
            "blocker_stage",
            "supervisor_run_id",
            "supervisor_pid",
            "supervisor_progress_fresh",
            "supervisor_progress_age_minutes",
            "supervisor_progress_round",
            "supervisor_target_index",
            "supervisor_target_total",
            "supervisor_target_complete",
            "supervisor_run_mode",
            "supervisor_deadline",
            "restart_candidate_active",
            "restart_candidate_source",
            "restart_candidate_reason",
            "restart_candidate_rank_vector_changed",
            "restart_candidate_changed_target_count",
            "restart_candidate_full_eval_rank",
            "restart_candidate_frozen_primary_score",
            "restart_candidate_baseline_frozen_primary_score",
            "restart_candidate_primary_score_improved",
            "restart_candidate_secondary_score_improved",
            "restart_candidate_improvement_basis",
            "restart_candidate_tail_over_1000000_delta",
            "restart_candidate_evidence_ready",
            "restart_candidate_evidence_blockers",
            "experimental_navigation_candidate_present",
            "experimental_navigation_eligible",
            "experimental_navigation_eligibility_reason",
            "experimental_navigation_quality_reason",
            "experimental_navigation_rank_vector_changed",
            "experimental_navigation_config_distance",
            "experimental_navigation_min_config_distance",
        ):
            if restart_readiness.get(key) is not None:
                readiness[key] = restart_readiness.get(key)
        summary["restart_readiness"] = readiness
    return summary


def attach_operator_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = operator_summary(payload)
    payload["operator_summary"] = summary
    payload["severity"] = summary.get("severity")
    payload["action"] = summary.get("action")
    return payload


def cli_summary(payload: dict[str, Any], json_path: Path, md_path: Path) -> dict[str, Any]:
    summary = operator_summary(payload)
    summary["json_path"] = str(json_path)
    summary["report_path"] = str(md_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch active DEHPS training and write advisor-only progress judgement.")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=DEFAULT_ROUND_LIMIT)
    parser.add_argument("--stale-minutes", type=int, default=DEFAULT_STALE_MINUTES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    payload = summarize_watch(args.run_id, limit=args.limit, stale_minutes=args.stale_minutes)
    json_path, md_path = write_outputs(payload, args.output_dir)
    print(json.dumps(cli_summary(payload, json_path, md_path), ensure_ascii=False))


if __name__ == "__main__":
    main()
