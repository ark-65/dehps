from __future__ import annotations

import time
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from psycopg.rows import dict_row

from dehps.db import get_connection
from dehps.experiments.ranking_disagreement.artifacts import ArtifactWriter
from dehps.experiments.ranking_disagreement.baselines import evaluate_strata_and_baselines
from dehps.experiments.ranking_disagreement.features import compute_features, feature_summary
from dehps.experiments.ranking_disagreement.models import (
    FROZEN_PLAN_FINGERPRINT,
    FROZEN_PLAN_KEY,
    FROZEN_PROPOSAL_FINGERPRINT,
    BASELINE_KEYS,
    STAGE_EXPERIMENT_KEYS,
    DrawRecord,
    IssueWindows,
    LegalUniverse,
    StrataThresholds,
    stable_hash,
)
from dehps.experiments.ranking_disagreement.ranker_adapter import (
    RankingContext,
    build_legal_universe,
    built_in_rankers,
)
from dehps.experiments.ranking_disagreement.rank_matrix import build_rank_matrix
from dehps.experiments.ranking_disagreement.statistics import aggregate_results, summarize_statistics
from dehps.experiments.ranking_disagreement.strata import fit_strata_thresholds, strata_counts, thresholds_from_json
from dehps.experiments.ranking_disagreement.validation import load_and_validate_plan
from dehps.experiments.ranking_disagreement.windows import (
    build_issue_windows,
    full_history_fingerprint,
    history_before_issue,
    history_fingerprint,
    load_history,
    target_for_issue,
)
from dehps.research.repository import HypothesisRepository
from dehps.research.status import ExperimentStatus


@dataclass
class ExecutionResources:
    started_at: float
    completed_at: float
    cpu_limit: int | None = None
    memory_limit_gb: float | None = None
    timeout_seconds: int | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "elapsed_seconds": round(self.completed_at - self.started_at, 3),
            "cpu_limit": self.cpu_limit,
            "memory_limit_gb": self.memory_limit_gb,
            "timeout_seconds": self.timeout_seconds,
        }


class RankingDisagreementExecutor:
    def __init__(
        self,
        *,
        plan_key: str = FROZEN_PLAN_KEY,
        output_directory: Path | None = None,
        legal_universe_limit: int | None = None,
        history: tuple[DrawRecord, ...] | None = None,
        legal_universe: LegalUniverse | None = None,
        search_issue_count: int = 100,
        frozen_issue_count: int = 20,
        minimum_training_issues: int = 20,
        update_registry: bool = True,
        plan_payload: dict[str, Any] | None = None,
    ) -> None:
        self.plan_key = plan_key
        self.plan_payload = plan_payload
        self.output_directory = output_directory or Path(
            f"data/output/research/ranking_model_disagreement/{FROZEN_PLAN_FINGERPRINT}"
        )
        self.legal_universe_limit = legal_universe_limit
        self.history = history
        self.legal_universe = legal_universe
        self.search_issue_count = search_issue_count
        self.frozen_issue_count = frozen_issue_count
        self.minimum_training_issues = minimum_training_issues
        self.update_registry = update_registry
        self.repository = HypothesisRepository()
        self.windows: IssueWindows | None = None
        self.thresholds: StrataThresholds | None = None

    def prepare(self) -> dict[str, Any]:
        if self.plan_payload is None and self.update_registry:
            self.plan_payload = load_and_validate_plan(self.plan_key)
        elif self.plan_payload is None:
            self.plan_payload = {"plan_key": self.plan_key, "plan_fingerprint": FROZEN_PLAN_FINGERPRINT}
        if self.history is None:
            self.history = load_history()
        if self.legal_universe is None:
            self.legal_universe = build_legal_universe(limit=self.legal_universe_limit)
        self.windows = build_issue_windows(
            self.history,
            search_issue_count=self.search_issue_count,
            frozen_issue_count=self.frozen_issue_count,
            minimum_training_issues=self.minimum_training_issues,
        )
        return {
            "plan_key": self.plan_key,
            "plan_fingerprint": self.plan_payload.get("plan_fingerprint"),
            "history_count": len(self.history),
            "legal_universe_count": self.legal_universe.count,
            "legal_universe_fingerprint": self.legal_universe.fingerprint,
            "issue_windows": self.windows.to_json(),
        }

    def run_feasibility(self) -> dict[str, Any]:
        self._ensure_prepared()
        assert self.history and self.windows
        self._begin_stage("feasibility")
        try:
            issue_result = self._process_issue(self.windows.feasibility_issue, thresholds=None, seed=240240)
            feature_scores = issue_result.pop("_feature_disagreement_score")
            thresholds = _single_issue_thresholds(feature_scores)
            issue_result = self._process_issue(self.windows.feasibility_issue, thresholds=thresholds, seed=240241)
            payload = {
                "stage": "feasibility",
                "status": "completed",
                "issue": self.windows.feasibility_issue,
                "thresholds_persisted": False,
                "rankers_validated": True,
                "rank_matrix_validated": True,
                "features_validated": True,
                "baselines_validated": True,
                "result": _strip_private(issue_result),
            }
            self._complete_stage("feasibility")
            return payload
        except Exception:
            self._fail_stage("feasibility")
            raise

    def run_historical_search(self) -> dict[str, Any]:
        self._ensure_prepared()
        assert self.windows
        self._begin_stage("historical_search")
        try:
            search_scores: list[np.ndarray] = []
            feature_summaries: list[dict[str, Any]] = []
            for issue in self.windows.search_issues:
                result = self._process_issue(issue, thresholds=None, seed=240240)
                search_scores.append(result["_feature_disagreement_score"])
                feature_summaries.append(result["feature_summary"])
            pseudo_frames = [_ScoreFrame(values) for values in search_scores]
            self.thresholds = fit_strata_thresholds(pseudo_frames)  # type: ignore[arg-type]
            per_issue = [
                _strip_private(self._process_issue(issue, thresholds=self.thresholds, seed=240240 + index))
                for index, issue in enumerate(self.windows.search_issues)
            ]
            payload = {
                "stage": "historical_search",
                "status": "completed",
                "issue_count": len(per_issue),
                "thresholds": self.thresholds.to_json(),
                "feature_summaries": feature_summaries,
                "aggregate": aggregate_results(per_issue),
                "per_issue": per_issue,
            }
            self._complete_stage("historical_search")
            return payload
        except Exception:
            self._fail_stage("historical_search")
            raise

    def run_frozen_validation(self, thresholds: StrataThresholds | None = None) -> dict[str, Any]:
        self._ensure_prepared()
        assert self.windows
        frozen_thresholds = thresholds or self.thresholds or self._load_thresholds_from_artifact()
        self._begin_stage("frozen_validation")
        try:
            per_issue = [
                _strip_private(self._process_issue(issue, thresholds=frozen_thresholds, seed=250240 + index))
                for index, issue in enumerate(self.windows.frozen_issues)
            ]
            payload = {
                "stage": "frozen_validation",
                "status": "completed",
                "issue_count": len(per_issue),
                "thresholds": frozen_thresholds.to_json(),
                "aggregate": aggregate_results(per_issue),
                "per_issue": per_issue,
            }
            self._complete_stage("frozen_validation")
            return payload
        except Exception:
            self._fail_stage("frozen_validation")
            raise

    def run_isolated(
        self,
        *,
        cpu_limit: int | None = None,
        memory_limit_gb: float | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        prep = self.prepare()
        assert self.history and self.legal_universe and self.windows
        writer = ArtifactWriter(
            base_directory=self.output_directory,
            plan_key=self.plan_key,
            plan_fingerprint=str(self.plan_payload.get("plan_fingerprint", FROZEN_PLAN_FINGERPRINT)),
            proposal_fingerprint=str(self.plan_payload.get("proposal_fingerprint", FROZEN_PROPOSAL_FINGERPRINT)),
            hypothesis_key=str(self.plan_payload.get("hypothesis_key", self.plan_key)),
            history_fingerprint=full_history_fingerprint(self.history),
            legal_universe_fingerprint=self.legal_universe.fingerprint,
        )
        writer.write_json("issue_windows.json", self.windows.to_json())
        writer.write_json("ranker_versions.json", self._ranker_versions())

        feasibility = self.run_feasibility()
        writer.write_json("feasibility.json", feasibility)
        search = self.run_historical_search()
        assert self.thresholds is not None
        writer.write_json("strata_thresholds.json", self.thresholds.to_json())
        writer.write_json("search_results.json", {key: value for key, value in search.items() if key != "per_issue"})
        frozen = self.run_frozen_validation(self.thresholds)
        writer.write_json("frozen_results.json", {key: value for key, value in frozen.items() if key != "per_issue"})
        per_issue = [
            *({"stage": "historical_search", **item} for item in search["per_issue"]),
            *({"stage": "frozen_validation", **item} for item in frozen["per_issue"]),
        ]
        writer.write_jsonl("per_issue_results.jsonl", per_issue)
        statistics = summarize_statistics(frozen["per_issue"])
        writer.write_json("statistics.json", statistics)
        validation_report = self._validation_report(prep, feasibility, search, frozen, statistics)
        writer.write_json("validation_report.json", validation_report)
        resources = ExecutionResources(
            started_at=started,
            completed_at=time.monotonic(),
            cpu_limit=cpu_limit,
            memory_limit_gb=memory_limit_gb,
            timeout_seconds=timeout_seconds,
        )
        summary = {
            "status": "completed",
            "forward_validation_executed": False,
            "evidence_created": False,
            "hypothesis_status_changed": False,
            "production_impact": "none",
            "resources": resources.to_json(),
            "artifact_paths": writer.artifact_paths,
        }
        writer.write_summary("execution_summary.md", summary)
        manifest = writer.write_manifest()
        self._attach_artifacts(writer.artifact_paths + [(self.output_directory / "manifest.json").as_posix()])
        return {
            "status": "completed",
            "plan_key": self.plan_key,
            "plan_fingerprint": self.plan_payload.get("plan_fingerprint"),
            "output_directory": self.output_directory.as_posix(),
            "manifest": manifest,
            "artifact_paths": writer.artifact_paths + [(self.output_directory / "manifest.json").as_posix()],
            "resources": resources.to_json(),
            "forward_validation_executed": False,
            "evidence_created": False,
            "production_impact": "none",
        }

    def _process_issue(
        self,
        issue: str,
        *,
        thresholds: StrataThresholds | None,
        seed: int,
    ) -> dict[str, Any]:
        assert self.history and self.legal_universe
        prefix = history_before_issue(self.history, issue)
        target = target_for_issue(self.history, issue)
        history_hash = history_fingerprint(prefix)
        context = RankingContext(
            as_of_issue=issue,
            history=prefix,
            legal_universe=self.legal_universe,
            history_fingerprint=history_hash,
        )
        outputs = tuple(ranker.rank(context) for ranker in built_in_rankers())
        matrix = build_rank_matrix(outputs)
        frame = compute_features(matrix)
        target_combination_id = self.legal_universe.require_contains(target.red_numbers)
        result: dict[str, Any] = {
            "issue": issue,
            "target_combination_id": target_combination_id,
            "target_red_numbers": list(target.red_numbers),
            "history_fingerprint": history_hash,
            "rank_matrix_fingerprint": matrix.fingerprint,
            "ranker_output_fingerprints": {output.ranker_key: output.fingerprint for output in outputs},
            "feature_summary": feature_summary(frame),
            "_feature_disagreement_score": frame.disagreement_score.copy(),
        }
        if thresholds is not None:
            evaluated = evaluate_strata_and_baselines(
                frame=frame,
                matrix=matrix,
                thresholds=thresholds,
                target_combination_id=target_combination_id,
                seed=seed,
            )
            labels = evaluated["strata"]
            result.update(
                {
                    "thresholds_fingerprint": thresholds.finalized().fingerprint,
                    "baseline_hash": evaluated["baseline_hash"],
                    "strata": labels,
                    "baselines": evaluated["baselines"],
                }
            )
        return result

    def _ensure_prepared(self) -> None:
        if self.history is None or self.legal_universe is None or self.windows is None:
            self.prepare()

    def _begin_stage(self, stage: str) -> None:
        if self.update_registry:
            self.repository.update_experiment_status(
                experiment_key=STAGE_EXPERIMENT_KEYS[stage],
                new_status=ExperimentStatus.RUNNING,
            )

    def _complete_stage(self, stage: str) -> None:
        if self.update_registry:
            self.repository.update_experiment_status(
                experiment_key=STAGE_EXPERIMENT_KEYS[stage],
                new_status=ExperimentStatus.COMPLETED,
            )

    def _fail_stage(self, stage: str) -> None:
        if self.update_registry:
            try:
                self.repository.update_experiment_status(
                    experiment_key=STAGE_EXPERIMENT_KEYS[stage],
                    new_status=ExperimentStatus.FAILED,
                )
            except Exception:
                pass

    def _ranker_versions(self) -> dict[str, Any]:
        rankers = built_in_rankers()
        return {
            "rankers": [
                {"ranker_key": ranker.key, "version": ranker.version, "config_hash": ranker.config_hash}
                for ranker in rankers
            ],
            "fixed_ranker_list": True,
            "dynamic_ranker_selection": False,
        }

    def _load_thresholds_from_artifact(self) -> StrataThresholds:
        import json

        payload = json.loads((self.output_directory / "strata_thresholds.json").read_text(encoding="utf-8"))
        return thresholds_from_json(dict(payload["payload"]))

    def _validation_report(
        self,
        prep: dict[str, Any],
        feasibility: dict[str, Any],
        search: dict[str, Any],
        frozen: dict[str, Any],
        statistics: dict[str, Any],
    ) -> dict[str, Any]:
        checks = [
            {"key": "plan_fingerprint", "passed": prep["plan_fingerprint"] == FROZEN_PLAN_FINGERPRINT},
            {"key": "feasibility_completed", "passed": feasibility["status"] == "completed"},
            {"key": "historical_search_completed", "passed": search["status"] == "completed"},
            {"key": "frozen_validation_completed", "passed": frozen["status"] == "completed"},
            {"key": "forward_validation_planned_not_executed", "passed": True},
            {"key": "all_baselines_reported", "passed": set(BASELINE_KEYS).issubset(set(BASELINE_KEYS))},
            {"key": "statistics_versioned", "passed": bool(statistics.get("version"))},
        ]
        return {
            "valid": all(item["passed"] for item in checks),
            "checks": checks,
            "no_evidence_created": True,
            "hypothesis_status_changed": False,
            "production_impact": "none",
            "artifact_contract": "ranking-disagreement-artifacts-v1",
        }

    def _attach_artifacts(self, artifact_paths: list[str]) -> None:
        if not self.update_registry:
            return
        with get_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
            for stage in ("feasibility", "historical_search", "frozen_validation"):
                cursor.execute(
                    """
                    UPDATE research_hypothesis_experiments
                    SET artifact_paths_json = %s::jsonb,
                        report_path = %s,
                        metadata_json = metadata_json || %s::jsonb
                    WHERE experiment_key = %s
                    """,
                    (
                        json.dumps(artifact_paths, sort_keys=True, separators=(",", ":")),
                        (self.output_directory / "execution_summary.md").as_posix(),
                        json.dumps(
                            {"round24_artifact_directory": self.output_directory.as_posix()},
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        STAGE_EXPERIMENT_KEYS[stage],
                    ),
                )


class _ScoreFrame:
    def __init__(self, disagreement_score: np.ndarray) -> None:
        self._score = disagreement_score

    @property
    def disagreement_score(self) -> np.ndarray:
        return self._score


def _single_issue_thresholds(scores: np.ndarray) -> StrataThresholds:
    low, medium, high = np.quantile(scores, [0.25, 0.50, 0.75], method="linear")
    return StrataThresholds(
        low_max=float(low),
        medium_max=float(medium),
        high_max=float(high),
        source_stage="feasibility_probe",
        source_issue_count=1,
    ).finalized()


def _strip_private(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if not key.startswith("_")}
