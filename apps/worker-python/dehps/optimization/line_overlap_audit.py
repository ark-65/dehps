from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.config import ROOT_DIR
from dehps.optimization.next_candidates import (
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
    NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW,
    STATIC_100_LINE_KEY,
)
from dehps.storage.postgres_store import (
    TOTAL_SSQ_RED_COMBINATIONS,
    ensure_training_line_round_results_schema,
)


LINE_KEYS = (STATIC_100_LINE_KEY, DYNAMIC_KDJ_LINE_KEY, NEAR_DYNAMIC_KDJ_LINE_KEY)
LINE_LABELS = {
    STATIC_100_LINE_KEY: "static_100 主线",
    DYNAMIC_KDJ_LINE_KEY: "dynamic_kdj 动态线",
    NEAR_DYNAMIC_KDJ_LINE_KEY: "dynamic_kdj_near 临期动态线",
}
EXACT_CUTOFFS = (100, 1000, 10000)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/line-overlap-audits"


def default_output_dir() -> Path:
    return DEFAULT_OUTPUT_DIR


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    return value


def _safe_file_part(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    return text.strip("-")[:80] or "none"


def _issue_sort_key(issue: object) -> tuple[int, int | str]:
    text = str(issue)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def _issue_list(issues: set[str]) -> list[str]:
    return sorted(issues, key=_issue_sort_key)


def _int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _target_hit(target: dict[str, Any], field: str, rank_field: str, cutoff: int) -> bool:
    if target.get(field) is True:
        return True
    rank = _int_or_none(target.get(rank_field))
    return rank is not None and rank <= cutoff


def _normalize_target_result(target: dict[str, Any]) -> dict[str, Any] | None:
    issue = str(target.get("issue") or "")
    if not issue:
        return None
    rank = _int_or_none(target.get("rank"))
    red5_rank = _int_or_none(target.get("red5_rank"))
    normalized = dict(target)
    normalized["issue"] = issue
    normalized["rank"] = rank
    normalized["red5_rank"] = red5_rank
    normalized["hit_top_100"] = rank is not None and rank <= 100
    normalized["hit_top_1000"] = rank is not None and rank <= 1000
    normalized["hit_top_10000"] = rank is not None and rank <= 10000
    normalized["hit_red5_top_100"] = red5_rank is not None and red5_rank <= 100
    normalized["hit_red5_top_1000"] = red5_rank is not None and red5_rank <= 1000
    normalized["hit_red5_top_10000"] = red5_rank is not None and red5_rank <= 10000
    return normalized


def _targets_by_issue(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    targets = summary.get("target_results")
    if not isinstance(targets, list):
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        normalized = _normalize_target_result(target)
        if normalized is not None:
            indexed[normalized["issue"]] = normalized
    return indexed


def _hit_set(targets: dict[str, dict[str, Any]], *, rank_field: str, cutoff: int) -> set[str]:
    hits: set[str] = set()
    for issue, target in targets.items():
        rank = _int_or_none(target.get(rank_field))
        if rank is not None and rank <= cutoff:
            hits.add(issue)
    return hits


def _rank(targets: dict[str, dict[str, Any]], issue: str, field: str = "rank") -> int | None:
    target = targets.get(issue)
    if target is None:
        return None
    return _int_or_none(target.get(field))


def _line_summary(row: dict[str, Any], targets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    red5 = summary.get("red5") if isinstance(summary.get("red5"), dict) else {}
    exact_top100 = _hit_set(targets, rank_field="rank", cutoff=100)
    exact_top1000 = _hit_set(targets, rank_field="rank", cutoff=1000)
    exact_top10000 = _hit_set(targets, rank_field="rank", cutoff=10000)
    red5_top100 = _hit_set(targets, rank_field="red5_rank", cutoff=100)
    target_issues = _issue_list(set(targets))
    return {
        "line_key": str(row.get("line_key") or ""),
        "line_label": str(row.get("line_label") or LINE_LABELS.get(str(row.get("line_key") or ""), "")),
        "status": str(row.get("status") or summary.get("status") or ""),
        "target_result_count": len(targets),
        "target_issues": target_issues,
        "window_start_issue": target_issues[0] if target_issues else summary.get("window_start_issue"),
        "window_end_issue": target_issues[-1] if target_issues else summary.get("window_end_issue"),
        "eval_window": int(summary.get("eval_window") or summary.get("evaluated_draws") or row.get("eval_window") or 0),
        "reported_exact_top_100_hits": int(row.get("exact_top_100_hits") or summary.get("top_100_hits") or 0),
        "reported_exact_top_1000_hits": int(row.get("exact_top_1000_hits") or summary.get("top_1000_hits") or 0),
        "reported_exact_top_10000_hits": int(row.get("exact_top_10000_hits") or summary.get("top_10000_hits") or 0),
        "target_exact_top_100_hits": len(exact_top100),
        "target_exact_top_1000_hits": len(exact_top1000),
        "target_exact_top_10000_hits": len(exact_top10000),
        "reported_red5_top_100_hits": int(row.get("red5_top_100_hits") or red5.get("top_100_hits") or 0),
        "target_red5_top_100_hits": len(red5_top100),
        "leakage_passed": bool(row.get("leakage_passed", summary.get("leakage_passed", False))),
        "fallback_target_count": int(row.get("fallback_target_count") or summary.get("fallback_target_count") or 0),
        "changed_target_count": int(row.get("changed_target_count") or summary.get("changed_target_count") or 0),
        "missing_target_results": len(targets) == 0,
    }


def _pairwise_exact_overlap(
    *,
    left_key: str,
    right_key: str,
    left_targets: dict[str, dict[str, Any]],
    right_targets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    common = set(left_targets) & set(right_targets)
    left_hits = _hit_set(left_targets, rank_field="rank", cutoff=100) & common
    right_hits = _hit_set(right_targets, rank_field="rank", cutoff=100) & common
    bands = {}
    for cutoff in EXACT_CUTOFFS:
        rescued = {
            issue
            for issue in common
            if (_rank(left_targets, issue) or TOTAL_SSQ_RED_COMBINATIONS + 1) > cutoff
            and (_rank(right_targets, issue) or TOTAL_SSQ_RED_COMBINATIONS + 1) <= cutoff
        }
        lost = {
            issue
            for issue in common
            if (_rank(left_targets, issue) or TOTAL_SSQ_RED_COMBINATIONS + 1) <= cutoff
            and (_rank(right_targets, issue) or TOTAL_SSQ_RED_COMBINATIONS + 1) > cutoff
        }
        both = {
            issue
            for issue in common
            if (_rank(left_targets, issue) or TOTAL_SSQ_RED_COMBINATIONS + 1) <= cutoff
            and (_rank(right_targets, issue) or TOTAL_SSQ_RED_COMBINATIONS + 1) <= cutoff
        }
        bands[f"top_{cutoff}"] = {
            "rescued_by_right": _issue_list(rescued),
            "lost_by_right": _issue_list(lost),
            "shared_hits": _issue_list(both),
            "rescued_by_right_count": len(rescued),
            "lost_by_right_count": len(lost),
            "shared_hit_count": len(both),
        }
    return {
        "left_line_key": left_key,
        "right_line_key": right_key,
        "common_issue_count": len(common),
        "common_issues": _issue_list(common),
        "left_only_exact_top100": _issue_list(left_hits - right_hits),
        "right_only_exact_top100": _issue_list(right_hits - left_hits),
        "shared_exact_top100": _issue_list(left_hits & right_hits),
        "neither_exact_top100_count": len(common - left_hits - right_hits),
        "exact_bands": bands,
    }


def _three_way_exact_overlap(targets_by_line: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    shared = set(targets_by_line.get(STATIC_100_LINE_KEY, {}))
    for line in (DYNAMIC_KDJ_LINE_KEY, NEAR_DYNAMIC_KDJ_LINE_KEY):
        shared &= set(targets_by_line.get(line, {}))
    hits = {
        line: _hit_set(targets_by_line.get(line, {}), rank_field="rank", cutoff=100) & shared
        for line in LINE_KEYS
    }
    return {
        "shared_issue_count": len(shared),
        "shared_issues": _issue_list(shared),
        "static_only_top100": _issue_list(hits[STATIC_100_LINE_KEY] - hits[DYNAMIC_KDJ_LINE_KEY] - hits[NEAR_DYNAMIC_KDJ_LINE_KEY]),
        "dynamic_only_top100": _issue_list(hits[DYNAMIC_KDJ_LINE_KEY] - hits[STATIC_100_LINE_KEY] - hits[NEAR_DYNAMIC_KDJ_LINE_KEY]),
        "near_only_top100": _issue_list(hits[NEAR_DYNAMIC_KDJ_LINE_KEY] - hits[STATIC_100_LINE_KEY] - hits[DYNAMIC_KDJ_LINE_KEY]),
        "static_dynamic_shared_top100": _issue_list(
            hits[STATIC_100_LINE_KEY] & hits[DYNAMIC_KDJ_LINE_KEY] - hits[NEAR_DYNAMIC_KDJ_LINE_KEY]
        ),
        "static_near_shared_top100": _issue_list(
            hits[STATIC_100_LINE_KEY] & hits[NEAR_DYNAMIC_KDJ_LINE_KEY] - hits[DYNAMIC_KDJ_LINE_KEY]
        ),
        "dynamic_near_shared_top100": _issue_list(
            hits[DYNAMIC_KDJ_LINE_KEY] & hits[NEAR_DYNAMIC_KDJ_LINE_KEY] - hits[STATIC_100_LINE_KEY]
        ),
        "all_three_top100": _issue_list(hits[STATIC_100_LINE_KEY] & hits[DYNAMIC_KDJ_LINE_KEY] & hits[NEAR_DYNAMIC_KDJ_LINE_KEY]),
    }


def _near_window_rows(targets_by_line: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    near_targets = targets_by_line.get(NEAR_DYNAMIC_KDJ_LINE_KEY, {})
    rows = []
    for issue in _issue_list(set(near_targets)):
        ranks = {line: _rank(targets_by_line.get(line, {}), issue) for line in LINE_KEYS}
        red5_ranks = {line: _rank(targets_by_line.get(line, {}), issue, "red5_rank") for line in LINE_KEYS}
        ranked_lines = [(line, rank) for line, rank in ranks.items() if rank is not None]
        best_line = min(ranked_lines, key=lambda item: item[1])[0] if ranked_lines else None
        rows.append(
            {
                "issue": issue,
                "ranks": ranks,
                "red5_ranks": red5_ranks,
                "best_exact_line": best_line,
                "exact_top100_lines": [line for line, rank in ranks.items() if rank is not None and rank <= 100],
                "red5_top100_lines": [line for line, rank in red5_ranks.items() if rank is not None and rank <= 100],
            }
        )
    return rows


def build_line_overlap_audit(
    rows: list[dict[str, Any]],
    *,
    run_id: str,
    round_index: int,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows_by_line = {str(row.get("line_key")): dict(row) for row in rows if str(row.get("line_key")) in LINE_KEYS}
    targets_by_line = {line: _targets_by_issue(rows_by_line.get(line, {})) for line in LINE_KEYS}
    line_summaries = {
        line: _line_summary(rows_by_line.get(line, {"line_key": line}), targets_by_line[line])
        for line in LINE_KEYS
    }
    exact_top100_sets = {
        line: _issue_list(_hit_set(targets_by_line[line], rank_field="rank", cutoff=100))
        for line in LINE_KEYS
    }
    red5_top100_sets = {
        line: _issue_list(_hit_set(targets_by_line[line], rank_field="red5_rank", cutoff=100))
        for line in LINE_KEYS
    }
    pairwise = {
        f"{STATIC_100_LINE_KEY}_vs_{DYNAMIC_KDJ_LINE_KEY}": _pairwise_exact_overlap(
            left_key=STATIC_100_LINE_KEY,
            right_key=DYNAMIC_KDJ_LINE_KEY,
            left_targets=targets_by_line[STATIC_100_LINE_KEY],
            right_targets=targets_by_line[DYNAMIC_KDJ_LINE_KEY],
        ),
        f"{STATIC_100_LINE_KEY}_vs_{NEAR_DYNAMIC_KDJ_LINE_KEY}": _pairwise_exact_overlap(
            left_key=STATIC_100_LINE_KEY,
            right_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
            left_targets=targets_by_line[STATIC_100_LINE_KEY],
            right_targets=targets_by_line[NEAR_DYNAMIC_KDJ_LINE_KEY],
        ),
        f"{DYNAMIC_KDJ_LINE_KEY}_vs_{NEAR_DYNAMIC_KDJ_LINE_KEY}": _pairwise_exact_overlap(
            left_key=DYNAMIC_KDJ_LINE_KEY,
            right_key=NEAR_DYNAMIC_KDJ_LINE_KEY,
            left_targets=targets_by_line[DYNAMIC_KDJ_LINE_KEY],
            right_targets=targets_by_line[NEAR_DYNAMIC_KDJ_LINE_KEY],
        ),
    }
    near_rows = _near_window_rows(targets_by_line)
    near_hits = len(exact_top100_sets[NEAR_DYNAMIC_KDJ_LINE_KEY])
    missing_lines = [line for line in LINE_KEYS if line not in rows_by_line]
    missing_target_results = [line for line, summary in line_summaries.items() if summary["missing_target_results"]]
    return json_safe(
        {
            "report_key": f"line-overlap-audit:{run_id}:r{round_index}",
            "run_id": run_id,
            "round_index": round_index,
            "generated_at": generated_at,
            "status": "ready" if not missing_lines and not missing_target_results else "partial",
            "line_keys": list(LINE_KEYS),
            "line_summaries": line_summaries,
            "exact_top100_sets": exact_top100_sets,
            "red5_top100_sets": red5_top100_sets,
            "three_way_exact_top100_on_shared_issues": _three_way_exact_overlap(targets_by_line),
            "pairwise_exact_overlap": pairwise,
            "near_window": {
                "success_window": NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW,
                "success_top100_goal": NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
                "available_target_count": len(near_rows),
                "exact_top100_hits": near_hits,
                "goal_reached_in_available_targets": near_hits >= NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL,
                "rows": near_rows,
            },
            "warnings": {
                "missing_line_rows": missing_lines,
                "missing_target_results": missing_target_results,
                "partial_report_reason": "older dynamic rows may not contain target_results" if missing_target_results else "",
            },
            "guardrails": {
                "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
                "exact_hit_definition": "red6 target rank <= cutoff",
                "primary_metric": "exact red6 Top100",
                "red5_role": "auxiliary support only",
                "leakage_boundary": "target_results must be generated with target issue excluded from its training history",
                "evidence_level": "training_diagnostics_overlap_audit_not_prediction_claim",
                "null_top100_probability_per_draw": round(100 / TOTAL_SSQ_RED_COMBINATIONS, 10),
            },
        }
    )


def resolve_line_overlap_round(
    conn: Connection,
    *,
    run_id: str | None = None,
    round_index: int | None = None,
) -> tuple[str, int]:
    ensure_training_line_round_results_schema(conn)
    if run_id and round_index is not None:
        return run_id, round_index
    params: list[Any] = []
    run_filter = ""
    if run_id:
        run_filter = "WHERE run_id = %s"
        params.append(run_id)
    with conn.cursor() as cur:
        row = cur.execute(
            f"""
            SELECT run_id, round_index
            FROM training_line_round_results
            {run_filter}
            GROUP BY run_id, round_index
            ORDER BY max(generated_at) DESC, round_index DESC
            LIMIT 1
            """,
            tuple(params),
        ).fetchone()
    if not row:
        raise RuntimeError("no training_line_round_results rows are available")
    resolved_run_id = str(row[0])
    resolved_round_index = int(row[1])
    if round_index is not None:
        return resolved_run_id, round_index
    return resolved_run_id, resolved_round_index


def load_training_line_round_rows(
    conn: Connection,
    *,
    run_id: str,
    round_index: int,
) -> list[dict[str, Any]]:
    ensure_training_line_round_results_schema(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT run_id, round_index, line_key, line_label, line_kind, policy_key,
                   policy_params, as_of_issue, history_fingerprint, train_mode, train_window,
                   eval_window, top_n, base_config_hash, status,
                   exact_top_100_hits, exact_top_1000_hits, exact_top_10000_hits,
                   red5_top_100_hits, red5_top_1000_hits, red5_top_10000_hits,
                   median_rank, best_rank, worst_rank, fallback_target_count,
                   changed_target_count, leakage_passed, summary, training_payload,
                   generated_at
            FROM training_line_round_results
            WHERE run_id = %s
              AND round_index = %s
              AND line_key IN (%s, %s, %s)
            ORDER BY line_key
            """,
            (run_id, round_index, *LINE_KEYS),
        ).fetchall()
    return [json_safe(dict(row)) for row in rows]


def write_line_overlap_audit(
    conn: Connection,
    *,
    run_id: str | None = None,
    round_index: int | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    resolved_run_id, resolved_round_index = resolve_line_overlap_round(conn, run_id=run_id, round_index=round_index)
    rows = load_training_line_round_rows(conn, run_id=resolved_run_id, round_index=resolved_round_index)
    payload = build_line_overlap_audit(rows, run_id=resolved_run_id, round_index=resolved_round_index)
    target_dir = output_dir or default_output_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    file_key = f"line-overlap-audit-{_safe_file_part(resolved_run_id)}-r{resolved_round_index}"
    json_path = target_dir / f"{file_key}.json"
    md_path = target_dir / f"{file_key}.md"
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(md_path)
    json_path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_line_overlap_audit(payload), encoding="utf-8")
    return payload


def _format_issue_list(issues: list[str], *, limit: int = 24) -> str:
    if not issues:
        return "none"
    shown = issues[:limit]
    suffix = f" ... +{len(issues) - limit}" if len(issues) > limit else ""
    return ", ".join(shown) + suffix


def _rank_text(rank: object) -> str:
    value = _int_or_none(rank)
    return str(value) if value is not None else "-"


def render_line_overlap_audit(payload: dict[str, Any]) -> str:
    line_summaries = payload.get("line_summaries") if isinstance(payload.get("line_summaries"), dict) else {}
    summary_rows = []
    for line in LINE_KEYS:
        summary = line_summaries.get(line) if isinstance(line_summaries.get(line), dict) else {}
        summary_rows.append(
            "| "
            + " | ".join(
                [
                    f"`{line}`",
                    str(summary.get("status") or ""),
                    str(summary.get("target_result_count") or 0),
                    f"{summary.get('target_exact_top_100_hits')}/{summary.get('reported_exact_top_100_hits')}",
                    f"{summary.get('target_exact_top_1000_hits')}/{summary.get('reported_exact_top_1000_hits')}",
                    f"{summary.get('target_exact_top_10000_hits')}/{summary.get('reported_exact_top_10000_hits')}",
                    f"{summary.get('target_red5_top_100_hits')}/{summary.get('reported_red5_top_100_hits')}",
                    "yes" if summary.get("leakage_passed") else "no",
                ]
            )
            + " |"
        )
    three_way = (
        payload.get("three_way_exact_top100_on_shared_issues")
        if isinstance(payload.get("three_way_exact_top100_on_shared_issues"), dict)
        else {}
    )
    static_dynamic = (
        payload.get("pairwise_exact_overlap", {}).get(f"{STATIC_100_LINE_KEY}_vs_{DYNAMIC_KDJ_LINE_KEY}")
        if isinstance(payload.get("pairwise_exact_overlap"), dict)
        else {}
    )
    static_dynamic_bands = (
        static_dynamic.get("exact_bands") if isinstance(static_dynamic, dict) and isinstance(static_dynamic.get("exact_bands"), dict) else {}
    )
    movement_rows = []
    for cutoff in EXACT_CUTOFFS:
        band = static_dynamic_bands.get(f"top_{cutoff}") if isinstance(static_dynamic_bands.get(f"top_{cutoff}"), dict) else {}
        movement_rows.append(
            "| "
            + " | ".join(
                [
                    f"Top{cutoff}",
                    str(band.get("rescued_by_right_count") or 0),
                    _format_issue_list(band.get("rescued_by_right") or []),
                    str(band.get("lost_by_right_count") or 0),
                    _format_issue_list(band.get("lost_by_right") or []),
                    str(band.get("shared_hit_count") or 0),
                ]
            )
            + " |"
        )
    near_window = payload.get("near_window") if isinstance(payload.get("near_window"), dict) else {}
    near_rows = near_window.get("rows") if isinstance(near_window.get("rows"), list) else []
    near_table_rows = []
    for row in near_rows:
        if not isinstance(row, dict):
            continue
        ranks = row.get("ranks") if isinstance(row.get("ranks"), dict) else {}
        red5_ranks = row.get("red5_ranks") if isinstance(row.get("red5_ranks"), dict) else {}
        near_table_rows.append(
            "| "
            + " | ".join(
                [
                    str(row.get("issue") or ""),
                    _rank_text(ranks.get(STATIC_100_LINE_KEY)),
                    _rank_text(ranks.get(DYNAMIC_KDJ_LINE_KEY)),
                    _rank_text(ranks.get(NEAR_DYNAMIC_KDJ_LINE_KEY)),
                    ", ".join(row.get("exact_top100_lines") or []) or "none",
                    ", ".join(row.get("red5_top100_lines") or []) or "none",
                    str(row.get("best_exact_line") or "none"),
                    _rank_text(red5_ranks.get(NEAR_DYNAMIC_KDJ_LINE_KEY)),
                ]
            )
            + " |"
        )
    near_table = "\n".join(near_table_rows) if near_table_rows else "| none | - | - | - | none | none | none | - |"
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), dict) else {}
    guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), dict) else {}
    return f"""# Three-Line Overlap Audit

- Run: `{payload.get("run_id")}`
- Round: `{payload.get("round_index")}`
- Status: `{payload.get("status")}`
- Generated at: `{payload.get("generated_at")}`

## Line Summary

Target/reported columns are shown as `from_target_results/reported_summary`.

| Line | Status | Targets | Exact Top100 | Exact Top1000 | Exact Top10000 | Red5 Top100 | Leakage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
{chr(10).join(summary_rows)}

## Exact Top100 Overlap

- Comparable all-line shared issues: `{three_way.get("shared_issue_count", 0)}`
- Static only: `{_format_issue_list(three_way.get("static_only_top100") or [])}`
- Dynamic only: `{_format_issue_list(three_way.get("dynamic_only_top100") or [])}`
- Near only: `{_format_issue_list(three_way.get("near_only_top100") or [])}`
- Static + dynamic shared: `{_format_issue_list(three_way.get("static_dynamic_shared_top100") or [])}`
- Dynamic + near shared: `{_format_issue_list(three_way.get("dynamic_near_shared_top100") or [])}`
- All three shared: `{_format_issue_list(three_way.get("all_three_top100") or [])}`

## Static To Dynamic Movement

| Cutoff | Rescued by dynamic | Issues | Lost by dynamic | Issues | Shared hits |
| --- | ---: | --- | ---: | --- | ---: |
{chr(10).join(movement_rows)}

## Near Window

- Available near targets: `{near_window.get("available_target_count", 0)}`
- Exact Top100 hits: `{near_window.get("exact_top100_hits", 0)}/{near_window.get("success_window", NEAR_DYNAMIC_KDJ_SUCCESS_WINDOW)}` target `{near_window.get("success_top100_goal", NEAR_DYNAMIC_KDJ_SUCCESS_TOP100_GOAL)}`
- Goal reached in available targets: `{near_window.get("goal_reached_in_available_targets", False)}`

| Issue | Static rank | Dynamic rank | Near rank | Exact Top100 lines | Red5 Top100 lines | Best exact line | Near red5 rank |
| --- | ---: | ---: | ---: | --- | --- | --- | ---: |
{near_table}

## Warnings

- Missing line rows: `{_format_issue_list(warnings.get("missing_line_rows") or [])}`
- Missing target results: `{_format_issue_list(warnings.get("missing_target_results") or [])}`

## Guardrails

- Legal red-ball sample space: `{guardrails.get("legal_sample_space", TOTAL_SSQ_RED_COMBINATIONS)}`
- Primary metric: exact red6 Top100.
- Red5 is auxiliary support only.
- This report compares structural overlap and movement; it is not a settled prediction claim.
- Null Top100 probability per draw: `{guardrails.get("null_top100_probability_per_draw")}`
"""
