from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from math import isfinite
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
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/training-watch"
DEFAULT_ROUND_LIMIT = 5000
DEFAULT_STALE_MINUTES = 30
SAFE_FILENAME_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
SAFE_INTEGER_TEXT_PATTERN = re.compile(r"[0-9]+")
MAX_SAFE_FILENAME_COMPONENT_LENGTH = 96


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


def safe_score(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def safe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


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
            "window": safe_int(rank_homogeneity.get("window")),
            "observed": safe_int(rank_homogeneity.get("observed")),
            "unique_signature_count": safe_int(rank_homogeneity.get("unique_signature_count")),
            "max_unique_signatures": safe_int(rank_homogeneity.get("max_unique_signatures")),
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
        }
    if navigation:
        result["experimental_navigation_candidate"] = {
            "source": navigation.get("source"),
            "reason": navigation.get("reason"),
            "config_hash": navigation.get("config_hash"),
        }
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

    if latest_age is not None and latest_age > stale_minutes:
        severity = "warn"
        actions.append("inspect_training_log")
        notes.append(f"Latest round is stale: {latest_age:.1f} minutes since update.")

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
        notes.append(
            "Rank homogeneity guardrail is active: "
            f"{rank_homogeneity.get('reason')} "
            f"unique_signatures={rank_homogeneity.get('unique_signature_count')}."
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

    if "prepare_restart_with_more_exploration" in actions and lock.get("active"):
        notes.append(
            "Restart preparation is not launch-ready while a heavy-job lock is active: "
            f"owner={lock.get('owner')} pid={lock.get('pid')}. "
            "Stop or transfer the current supervisor before starting a fresh run."
        )

    if not actions:
        actions.append("continue_current_run")

    return {
        "severity": severity,
        "action": actions[0],
        "actions": actions,
        "notes": notes,
    }


def restart_readiness_summary(*, recommendation: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    raw_actions = recommendation.get("actions")
    actions = [str(item) for item in raw_actions] if isinstance(raw_actions, list) else []
    if not actions and recommendation.get("action"):
        actions = [str(recommendation.get("action"))]
    requested = "prepare_restart_with_more_exploration" in actions
    if not requested:
        return {
            "requested": False,
            "ready": False,
            "status": "not_requested",
            "blockers": [],
        }

    blockers: list[str] = []
    lock_active = bool(lock.get("active"))
    owner = lock.get("owner")
    if lock_active and owner == "training-supervisor":
        blockers.append("active_training_supervisor_lock")
    elif lock_active:
        blockers.append("active_heavy_job_lock")

    return {
        "requested": True,
        "ready": not blockers,
        "status": "ready_for_fresh_supervisor_after_operator_review"
        if not blockers
        else "blocked_by_active_heavy_job_lock",
        "blockers": blockers,
        "owner": owner,
        "pid": lock.get("pid"),
        "pid_active": lock.get("pid_active"),
        "heartbeat_at": lock.get("heartbeat_at"),
    }


def summarize_watch(run_id: str | None, *, limit: int, stale_minutes: int) -> dict[str, Any]:
    limit = positive_int_or_default(limit, default=DEFAULT_ROUND_LIMIT)
    stale_minutes = positive_int_or_default(stale_minutes, default=DEFAULT_STALE_MINUTES)
    generated_at = utc_now()
    resolved_run_id = resolve_run_id(run_id)
    rows = load_rounds(resolved_run_id, limit=limit) if resolved_run_id else []
    round_stats = (
        load_round_stats(resolved_run_id)
        if resolved_run_id
        else {
            "round_count": 0,
            "latest_round": None,
            "last_improved_round": None,
            "stagnation_rounds": 0,
            "improvement_count": 0,
            "best_objective_seen": None,
        }
    )
    latest = rows[-1] if rows else {}
    prefilter = latest.get("prefilter") if isinstance(latest.get("prefilter"), dict) else {}
    advisors = advisor_summary(prefilter)
    gates = gate_summary(prefilter)
    lock = heavy_lock_summary()
    recommendation = recommendation_summary(
        rows=rows,
        lock=lock,
        advisors=advisors,
        gates=gates,
        now=generated_at,
        stale_minutes=stale_minutes,
        round_stats=round_stats,
    )
    return {
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
        "advisor_summary": advisors,
        "gate_summary": gates,
        "heavy_job_lock": lock,
        "recommendation": recommendation,
        "restart_readiness": restart_readiness_summary(recommendation=recommendation, lock=lock),
        "guardrail": "Historical response-surface monitoring only; no predictive claim and no automatic promotion without controls.",
    }


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
            gate_lines.append(
                "- Rank homogeneity: "
                f"active={rank_homogeneity.get('active')} "
                f"reason={markdown_inline_text(rank_homogeneity.get('reason'))} "
                f"unique_signatures={rank_homogeneity.get('unique_signature_count')}"
            )
        if restart_champion:
            gate_lines.append(
                "- Restart champion: "
                f"active={restart_champion.get('active')} "
                f"reason={markdown_inline_text(restart_champion.get('reason'))} "
                f"rank_vector_changed={restart_champion.get('rank_vector_changed')} "
                f"changed_targets={restart_champion.get('changed_target_count')} "
                f"full_eval_rank={restart_champion.get('full_eval_rank')} "
                f"max_abs_delta={restart_champion.get('max_abs_delta')}"
            )
        if navigation:
            gate_lines.append(
                "- Experimental navigation: "
                f"source={markdown_inline_text(navigation.get('source'))} "
                f"reason={markdown_inline_text(navigation.get('reason'))}"
            )
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
        restart_section = (
            "## Restart Readiness\n\n"
            f"- Ready for fresh supervisor: {restart_readiness.get('ready')}\n"
            f"- Status: {markdown_inline_text(restart_readiness.get('status'))}\n"
            f"- Blockers: {markdown_inline_text(blockers)}\n"
            f"- Lock owner/PID: {markdown_inline_text(restart_readiness.get('owner'))} / {restart_readiness.get('pid')}\n"
            f"- Heartbeat: {markdown_inline_text(restart_readiness.get('heartbeat_at'))}\n\n"
        )
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

{gate_section}\
{restart_section}\
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch active DEHPS training and write advisor-only progress judgement.")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=DEFAULT_ROUND_LIMIT)
    parser.add_argument("--stale-minutes", type=int, default=DEFAULT_STALE_MINUTES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    payload = summarize_watch(args.run_id, limit=args.limit, stale_minutes=args.stale_minutes)
    json_path, md_path = write_outputs(payload, args.output_dir)
    print(
        json.dumps(
            {
                "run_id": payload.get("run_id"),
                "round_count": payload.get("round_count"),
                "round_window_count": payload.get("round_window_count"),
                "severity": payload.get("recommendation", {}).get("severity"),
                "action": payload.get("recommendation", {}).get("action"),
                "json_path": str(json_path),
                "report_path": str(md_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
