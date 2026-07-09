from __future__ import annotations

from dehps.optimization.line_overlap_audit import build_line_overlap_audit, render_line_overlap_audit
from dehps.optimization.next_candidates import (
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    STATIC_100_LINE_KEY,
)


def _target(issue: str, rank: int, red5_rank: int | None = None) -> dict:
    return {
        "issue": issue,
        "red_numbers": [1, 2, 3, 4, 5, 6],
        "rank": rank,
        "score": 0.5,
        "hit_top_100": rank <= 100,
        "hit_top_1000": rank <= 1000,
        "hit_top_10000": rank <= 10000,
        "red5_rank": red5_rank,
        "hit_red5_top_100": red5_rank is not None and red5_rank <= 100,
        "hit_red5_top_1000": red5_rank is not None and red5_rank <= 1000,
        "hit_red5_top_10000": red5_rank is not None and red5_rank <= 10000,
    }


def _line_row(line_key: str, targets: list[dict]) -> dict:
    return {
        "run_id": "run-1",
        "round_index": 7,
        "line_key": line_key,
        "line_label": line_key,
        "line_kind": line_key,
        "status": "evaluated",
        "eval_window": len(targets),
        "exact_top_100_hits": sum(target["rank"] <= 100 for target in targets),
        "exact_top_1000_hits": sum(target["rank"] <= 1000 for target in targets),
        "exact_top_10000_hits": sum(target["rank"] <= 10000 for target in targets),
        "red5_top_100_hits": sum(
            target.get("red5_rank") is not None and target["red5_rank"] <= 100 for target in targets
        ),
        "fallback_target_count": 0,
        "changed_target_count": len(targets),
        "leakage_passed": True,
        "summary": {
            "status": "evaluated",
            "target_results": targets,
            "red5": {
                "top_100_hits": sum(
                    target.get("red5_rank") is not None and target["red5_rank"] <= 100 for target in targets
                )
            },
        },
    }


def test_build_line_overlap_audit_reports_exclusive_hits_and_rescues():
    rows = [
        _line_row(
            STATIC_100_LINE_KEY,
            [
                _target("2026001", 50, 90),
                _target("2026002", 500, 120),
                _target("2026003", 20000, 2000),
            ],
        ),
        _line_row(
            DYNAMIC_KDJ_LINE_KEY,
            [
                _target("2026001", 500, 80),
                _target("2026002", 70, 70),
                _target("2026003", 9000, 900),
            ],
        ),
        _line_row(
            NEAR_DYNAMIC_KDJ_LINE_KEY,
            [
                _target("2026002", 80, 75),
                _target("2026003", 30000, 95),
                _target("2026004", 20, 40),
            ],
        ),
    ]

    audit = build_line_overlap_audit(rows, run_id="run-1", round_index=7, generated_at="2026-07-09T00:00:00Z")

    assert audit["status"] == "ready"
    assert audit["warnings"]["missing_line_rows"] == []
    assert audit["warnings"]["missing_target_results"] == []
    static_dynamic = audit["pairwise_exact_overlap"][f"{STATIC_100_LINE_KEY}_vs_{DYNAMIC_KDJ_LINE_KEY}"]
    assert static_dynamic["left_only_exact_top100"] == ["2026001"]
    assert static_dynamic["right_only_exact_top100"] == ["2026002"]
    assert static_dynamic["exact_bands"]["top_100"]["rescued_by_right"] == ["2026002"]
    assert static_dynamic["exact_bands"]["top_100"]["lost_by_right"] == ["2026001"]
    three_way = audit["three_way_exact_top100_on_shared_issues"]
    assert three_way["shared_issues"] == ["2026002", "2026003"]
    assert three_way["dynamic_near_shared_top100"] == ["2026002"]
    assert audit["near_window"]["available_target_count"] == 3
    assert audit["near_window"]["exact_top100_hits"] == 2
    assert audit["line_summaries"][NEAR_DYNAMIC_KDJ_LINE_KEY]["target_result_count"] == 3


def test_render_line_overlap_audit_mentions_missing_target_results():
    audit = build_line_overlap_audit(
        [
            _line_row(STATIC_100_LINE_KEY, [_target("2026001", 50)]),
            {
                "run_id": "run-1",
                "round_index": 7,
                "line_key": DYNAMIC_KDJ_LINE_KEY,
                "line_label": DYNAMIC_KDJ_LINE_KEY,
                "status": "evaluated",
                "summary": {"status": "evaluated"},
            },
        ],
        run_id="run-1",
        round_index=7,
        generated_at="2026-07-09T00:00:00Z",
    )

    report = render_line_overlap_audit(audit)

    assert audit["status"] == "partial"
    assert DYNAMIC_KDJ_LINE_KEY in audit["warnings"]["missing_target_results"]
    assert NEAR_DYNAMIC_KDJ_LINE_KEY in audit["warnings"]["missing_line_rows"]
    assert "Missing target results" in report
    assert "exact red6 Top100" in report
