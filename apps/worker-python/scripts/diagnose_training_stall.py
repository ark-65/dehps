from __future__ import annotations

"""Create a read-only, deduplicated root-cause dossier for a parked training run."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.config import ROOT_DIR


DEFAULT_WATCH_PATH = ROOT_DIR / "data/output/optimization/training-watch/training-watch-latest.json"
DEFAULT_RESEARCH_PATH = ROOT_DIR / "data/output/optimization/research-lane/isolated-research-lane-latest.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/optimization/stall-diagnosis"


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return _mapping(value)


def _dynamic_acceptance(research: dict[str, Any]) -> dict[str, Any]:
    report_path = str(research.get("report_path") or "")
    research_root = Path(report_path).parent if report_path else DEFAULT_RESEARCH_PATH.parent
    candidates = sorted((research_root / "dynamic-kdj").glob("dynamic-kdj-backtest-*.json"))
    if not candidates:
        return {}
    return _mapping(_load_json(candidates[-1]).get("acceptance"))


def build_diagnosis(watch: dict[str, Any], research: dict[str, Any]) -> dict[str, Any]:
    forward_wait = _mapping(watch.get("forward_wait"))
    forward_evidence = _mapping(watch.get("forward_evidence"))
    repetition = _mapping(watch.get("round_repetition"))
    compute = _mapping(watch.get("compute_capability"))
    accelerator = _mapping(compute.get("accelerator"))
    supervisor = _mapping(watch.get("supervisor_status"))
    input_boundary = _mapping(supervisor.get("prediction_input_boundary"))
    dynamic = _dynamic_acceptance(research)

    paired = _integer(forward_evidence.get("paired_issue_count")) or 0
    required_pairs = _integer(forward_evidence.get("min_paired_issues")) or 0
    config_streak = _integer(repetition.get("latest_config_repeat_streak")) or 0
    metric_streak = _integer(repetition.get("latest_metric_repeat_streak")) or 0
    stagnation = _integer(watch.get("current_run_stagnation_rounds")) or 0
    research_runs = research.get("runs") if isinstance(research.get("runs"), list) else []
    dynamic_run = next((row for row in research_runs if _mapping(row).get("name") == "dynamic_kdj_frozen_backtest"), {})
    dynamic_elapsed = _mapping(dynamic_run).get("elapsed_seconds")

    dimensions = [
        {
            "key": "forward_evidence",
            "status": "blocked" if paired < required_pairs else "review_ready",
            "evidence": {"paired_issues": paired, "required_paired_issues": required_pairs, "pending_issue": forward_wait.get("next_pending_issue")},
            "cause": "No new independent draw outcome is available for the completed prediction snapshot." if paired < required_pairs else "Enough paired forward observations exist for human review.",
            "recovery": "Keep promotion quarantined; evaluate the already frozen snapshot when its draw is synced.",
        },
        {
            "key": "search_geometry",
            "status": "stalled" if repetition.get("active") is True else "clear",
            "evidence": {
                "config_repeat_streak": config_streak,
                "metric_repeat_streak": metric_streak,
                "current_run_stagnation_rounds": stagnation,
                "observed_familywise_hypothesis_count": forward_wait.get("observed_familywise_hypothesis_count"),
            },
            "cause": "The adaptive search revisited an identical configuration and metric signature." if repetition.get("active") is True else "No repeated-round signature is currently active.",
            "recovery": "Do not spend another same-history round on this search state; require a bounded, preregistered recovery audit or a new draw.",
        },
        {
            "key": "dynamic_kdj_model",
            "status": "rejected_by_frozen_audit" if dynamic.get("passed") is False else "not_yet_audited",
            "evidence": {
                "audit_status": dynamic.get("status"),
                "failures": dynamic.get("failures") or [],
                "static_objective": dynamic.get("static_objective"),
                "dynamic_objective": dynamic.get("dynamic_objective"),
                "null_objective": dynamic.get("null_objective"),
            },
            "cause": "Dynamic KDJ failed its frozen static/null and tail-risk gates." if dynamic.get("passed") is False else "No completed dynamic-KDJ frozen audit was available.",
            "recovery": "Keep this source research-only until a newly preregistered frozen audit passes; do not use it as evidence of main-line improvement.",
        },
        {
            "key": "compute",
            "status": "cpu_only" if accelerator.get("gpu_training_enabled") is not True else "gpu_validated",
            "evidence": {
                "logical_cpu_count": _mapping(compute.get("cpu")).get("logical_count"),
                "configured_workers": _mapping(compute.get("cpu")).get("configured_workers"),
                "gpu_probe_status": accelerator.get("probe_status"),
                "gpu_speedup": accelerator.get("probe_full_end_to_end_speedup"),
                "gpu_changed_score_cells": accelerator.get("probe_rounded_changed_cell_count"),
                "research_dynamic_elapsed_seconds": dynamic_elapsed,
            },
            "cause": "The OpenCL probe changed rounded scores and was slower end-to-end, so GPU execution is not equivalent." if accelerator.get("gpu_training_enabled") is not True else "GPU execution passed the current equivalence gate.",
            "recovery": "Keep deterministic CPU parallelism for ranking; profile the isolated backtest separately before changing GPU kernels or worker allocation.",
        },
        {
            "key": "data_and_leakage",
            "status": "passed" if input_boundary.get("status") == "passed" else "needs_review",
            "evidence": {
                "input_boundary_status": input_boundary.get("status"),
                "training_fields": input_boundary.get("training_fields") or [],
                "ticket_distribution_observed": input_boundary.get("ticket_distribution_observed"),
                "research_status": research.get("status"),
            },
            "cause": "No input-boundary violation is currently reported; aggregate ticket data remains excluded from draw-probability training." if input_boundary.get("status") == "passed" else "The prediction input boundary needs review before interpreting the stall.",
            "recovery": "Continue sync/conflict and leakage gates; do not broaden draw predictors with unidentifiable ticket aggregates.",
        },
    ]
    critical = [row["key"] for row in dimensions if row["status"] in {"blocked", "stalled", "rejected_by_frozen_audit"}]
    payload = {
        "protocol": "dehps-stall-root-cause-v1",
        "run_id": watch.get("run_id"),
        "history_issue": forward_wait.get("history_latest_issue"),
        "status": "root_causes_identified" if critical else "no_active_root_cause",
        "critical_dimensions": critical,
        "dimensions": dimensions,
        "selection_changed": False,
        "promotion_allowed": False,
        "synthesis": "The observed stall is a combined search-homogeneity and dynamic-model-quality failure under an intentionally limited forward-evidence sample; it is not evidence of data corruption or a reason to relax leakage controls.",
    }
    return payload


def fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def render_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "# DEHPS Training Stall Root-Cause Dossier",
        "",
        f"- Run: `{payload.get('run_id')}`",
        f"- History issue: `{payload.get('history_issue')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Critical dimensions: `{', '.join(payload.get('critical_dimensions') or []) or 'none'}`",
        "- Boundary: this dossier is read-only and cannot select, promote, or rewrite prediction candidates.",
        "",
        "## Dimensions",
        "",
    ]
    for dimension in payload.get("dimensions") or []:
        rows.extend(
            [
                f"### {dimension.get('key')} — {dimension.get('status')}",
                "",
                f"Cause: {dimension.get('cause')}",
                "",
                f"Recovery: {dimension.get('recovery')}",
                "",
                f"Evidence: `{json.dumps(dimension.get('evidence'), ensure_ascii=False, sort_keys=True)}`",
                "",
            ]
        )
    rows.extend(["## Synthesis", "", str(payload.get("synthesis") or ""), ""])
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a read-only DEHPS training-stall root-cause dossier.")
    parser.add_argument("--watch-path", type=Path, default=DEFAULT_WATCH_PATH)
    parser.add_argument("--research-path", type=Path, default=DEFAULT_RESEARCH_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    diagnosis = build_diagnosis(_load_json(args.watch_path), _load_json(args.research_path))
    state_hash = fingerprint(diagnosis)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    latest_path = args.output_dir / "stall-diagnosis-latest.json"
    previous = _load_json(latest_path)
    if previous.get("state_fingerprint") == state_hash:
        print(json.dumps({"status": "unchanged", "state_fingerprint": state_hash}, ensure_ascii=False))
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    diagnosis["generated_at"] = datetime.now(timezone.utc).isoformat()
    diagnosis["state_fingerprint"] = state_hash
    json_path = args.output_dir / f"stall-diagnosis-{stamp}.json"
    markdown_path = args.output_dir / f"stall-diagnosis-{stamp}.md"
    diagnosis["json_path"] = str(json_path)
    diagnosis["report_path"] = str(markdown_path)
    serialized = json.dumps(diagnosis, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    json_path.write_text(serialized, encoding="utf-8")
    latest_path.write_text(serialized, encoding="utf-8")
    markdown_path.write_text(render_markdown(diagnosis), encoding="utf-8")
    print(json.dumps({"status": "written", "json_path": str(json_path), "report_path": str(markdown_path), "critical_dimensions": diagnosis["critical_dimensions"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
