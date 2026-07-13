from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FormalEvidenceBundle:
    training_failures: tuple[dict[str, Any], ...]
    candidate_sources: tuple[dict[str, Any], ...]
    forward_evidence: dict[str, Any]
    data_boundary: dict[str, Any]
    sequential_null: dict[str, Any]
    frozen_validation: dict[str, Any]
    training_run_ids: tuple[str, ...]
    model_paths: tuple[str, ...]
    source_paths: tuple[str, ...]


class FormalEvidenceReader:
    """Read versioned JSON diagnostics and source files without interpreting prose."""

    def __init__(self, repository_root: Path | None = None) -> None:
        self.root = (repository_root or Path(__file__).resolve().parents[4]).resolve()

    def read(self) -> FormalEvidenceBundle:
        watch_path = self.root / "data/output/optimization/training-watch/training-watch-latest.json"
        stall_path = self.root / "data/output/optimization/stall-diagnosis/stall-diagnosis-latest.json"
        watch = self._object(watch_path)
        stall = self._object(stall_path)
        failures = tuple(
            {
                "key": str(item.get("key") or "unknown"),
                "status": str(item.get("status") or "unavailable"),
                "cause": str(item.get("cause") or "formal diagnostic did not provide a cause"),
                "recovery": str(item.get("recovery") or "no recovery declared"),
                "run_id": stall.get("run_id"),
                "evidence": dict(item.get("evidence") or {}),
            }
            for item in stall.get("dimensions", [])
            if isinstance(item, dict)
        )
        survival = dict(watch.get("candidate_source_survival") or {})
        sources = tuple(
            {
                "source_key": str(key),
                "state": str(value.get("state") or "unknown"),
                "generated": int(value.get("generated") or 0),
                "prefilter_selected": int(value.get("prefilter_selected") or 0),
                "full_eval_top5": int(value.get("full_eval_top5") or 0),
                "round_best_rounds": int(value.get("round_best_rounds") or 0),
                "frozen_frontier_rounds": int(value.get("frozen_frontier_rounds") or 0),
                "search_navigation_rounds": int(value.get("search_navigation_rounds") or 0),
            }
            for key, value in sorted(dict(survival.get("sources") or {}).items())
            if isinstance(value, dict)
        )
        forward = dict(watch.get("forward_evidence") or {})
        boundary = dict(watch.get("prediction_input_boundary") or {})
        sequential = dict(watch.get("sequential_null_audit") or {})
        diagnostics = dict(watch.get("self_diagnostics") or {})
        frozen = {
            "status": str(diagnostics.get("synthesis", {}).get("status") or "unavailable"),
            "promotion_gate_passed": bool(
                diagnostics.get("synthesis", {}).get("guardrails", {}).get("promotion_gate_passed", False)
            ),
            "selection_uses_frozen_validation": bool(
                diagnostics.get("decision_surface", {}).get("selection_uses_frozen_validation", False)
            ),
            "historical_holdout_quarantined": True,
        }
        model_paths = tuple(
            path.relative_to(self.root).as_posix()
            for directory in ("apps/worker-python/dehps/models", "apps/worker-python/dehps/advisors")
            for path in sorted((self.root / directory).glob("*.py"))
        )
        return FormalEvidenceBundle(
            training_failures=failures,
            candidate_sources=sources,
            forward_evidence={
                "status": str(forward.get("status") or "unavailable"),
                "protocol": str(forward.get("protocol") or "unavailable"),
                "paired_issue_count": int(forward.get("paired_issue_count") or 0),
                "min_paired_issues": int(forward.get("min_paired_issues") or 20),
                "review_ready": bool(forward.get("review_ready", False)),
                "promotion_eligible": bool(forward.get("promotion_eligible", False)),
                "blockers": tuple(str(value) for value in forward.get("blockers", [])),
            },
            data_boundary={
                "protocol": str(boundary.get("protocol") or "unavailable"),
                "status": str(boundary.get("status") or "unavailable"),
                "training_fields": tuple(str(value) for value in boundary.get("training_fields", [])),
                "excluded_fields": tuple(
                    str(value) for value in boundary.get("available_market_aggregate_fields_excluded", [])
                ),
                "future_information_allowed": False,
                "ticket_distribution_observed": bool(boundary.get("ticket_distribution_observed", False)),
            },
            sequential_null=sequential,
            frozen_validation=frozen,
            training_run_ids=tuple(
                sorted({str(value) for value in (watch.get("run_id"), stall.get("run_id")) if value})
            ),
            model_paths=model_paths,
            source_paths=tuple(
                path.relative_to(self.root).as_posix()
                for path in (watch_path, stall_path)
                if path.is_file()
            ),
        )

    @staticmethod
    def _object(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError(f"formal evidence must be a JSON object: {path}")
        return value
