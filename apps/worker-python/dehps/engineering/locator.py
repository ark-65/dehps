from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from dehps.engineering.code_graph import CodeGraphBuilder
from dehps.engineering.contracts import CodeGraph, LocatedComponent
from dehps.research_autonomy.feature_catalog import FeatureCatalog
from dehps.research_autonomy.mechanism_catalog import MechanismCatalog
from dehps.research_planning.models import ExperimentPlan


class RepositoryLocator:
    def __init__(
        self,
        *,
        repository_root: Path | None = None,
        code_graph: CodeGraph | None = None,
        feature_catalog: FeatureCatalog | None = None,
        mechanism_catalog: MechanismCatalog | None = None,
    ) -> None:
        self.root = (repository_root or Path(__file__).resolve().parents[4]).resolve()
        self.code_graph = code_graph or CodeGraphBuilder(self.root).build()
        self.feature_catalog = feature_catalog or FeatureCatalog(self.root)
        self.mechanism_catalog = mechanism_catalog or MechanismCatalog()

    def locate(self, plan: ExperimentPlan) -> tuple[LocatedComponent, ...]:
        mechanism = plan.mechanism
        components: list[LocatedComponent] = []
        components.extend(self._mechanism_components(mechanism))
        components.extend(self._ranker_components(plan))
        components.extend(self._feature_components(plan))
        components.extend(self._baseline_components(plan))
        components.extend(self._metric_components(plan))
        components.extend(self._test_components(mechanism))
        return tuple(self._dedupe(components))

    def context_catalogs(self) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
        return (
            tuple(asdict(item) for item in self.feature_catalog.build()),
            tuple(asdict(item) for item in self.mechanism_catalog.build()),
        )

    def _mechanism_components(self, mechanism: str) -> list[LocatedComponent]:
        if mechanism == "ranking_model_disagreement":
            return [
                self._component(
                    "experiment",
                    "ranking_disagreement_package",
                    "apps/worker-python/dehps/experiments/ranking_disagreement",
                    "existing Round 24 isolated experiment package matches the mechanism",
                ),
                self._component(
                    "experiment_cli",
                    "ranking_disagreement_cli",
                    "apps/worker-python/dehps/experiments/ranking_disagreement/cli.py",
                    "existing CLI can be extended instead of duplicated",
                ),
                self._component(
                    "executor",
                    "ranking_disagreement_executor",
                    "apps/worker-python/dehps/experiments/ranking_disagreement/executor.py",
                    "existing executor owns isolated run orchestration",
                ),
                self._component(
                    "artifact_writer",
                    "ranking_disagreement_artifacts",
                    "apps/worker-python/dehps/experiments/ranking_disagreement/artifacts.py",
                    "existing artifact contract writer should be reused",
                ),
            ]
        return [
            self._component(
                "experiment",
                f"{mechanism}_experiment_package",
                f"apps/worker-python/dehps/experiments/{mechanism}",
                "no exact experiment package exists; add a mechanism-specific isolated package",
            )
        ]

    def _ranker_components(self, plan: ExperimentPlan) -> list[LocatedComponent]:
        keys = self._values(plan.model_contract)
        components = [
            self._component(
                "ranker",
                "frequency_ranker",
                "apps/worker-python/dehps/models/frequency_ranker.py",
                "baseline ranker implementation exists and should not be reimplemented",
            )
        ]
        if "disagreement" in plan.mechanism or "ranker" in " ".join(keys):
            components.append(
                self._component(
                    "ranker_adapter",
                    "ranking_disagreement_ranker_adapter",
                    "apps/worker-python/dehps/experiments/ranking_disagreement/ranker_adapter.py",
                    "existing adapter normalizes built-in rankers for disagreement experiments",
                )
            )
        return components

    def _feature_components(self, plan: ExperimentPlan) -> list[LocatedComponent]:
        components = [
            self._component(
                "feature",
                "red_ball_features",
                "apps/worker-python/dehps/features/red_ball_features.py",
                "structural red-ball features already exist",
            )
        ]
        if plan.mechanism == "ranking_model_disagreement":
            components.append(
                self._component(
                    "feature",
                    "ranking_disagreement_features",
                    "apps/worker-python/dehps/experiments/ranking_disagreement/features.py",
                    "disagreement-specific feature extraction already exists",
                )
            )
        return components

    def _baseline_components(self, plan: ExperimentPlan) -> list[LocatedComponent]:
        return [
            self._component(
                "baseline",
                "matched_budget_baselines",
                "apps/worker-python/dehps/experiments/ranking_disagreement/baselines.py",
                "existing matched-budget baseline evaluator should be reused",
            ),
            self._component(
                "null_model",
                "candidate_null_model",
                "apps/worker-python/dehps/candidates/null_model.py",
                "null-model utilities exist for same-budget comparisons",
            ),
        ]

    def _metric_components(self, plan: ExperimentPlan) -> list[LocatedComponent]:
        return [
            self._component(
                "metrics",
                "ranking_disagreement_metrics",
                "apps/worker-python/dehps/experiments/ranking_disagreement/metrics.py",
                "existing top-k and rank metrics implementation should be reused",
            ),
            self._component(
                "statistics",
                "ranking_disagreement_statistics",
                "apps/worker-python/dehps/experiments/ranking_disagreement/statistics.py",
                "existing statistical review implementation should be reused",
            ),
        ]

    def _test_components(self, mechanism: str) -> list[LocatedComponent]:
        matches = [
            file
            for file in self.code_graph.test_files
            if mechanism in file.path or mechanism.replace("_", "-") in file.path
        ]
        if not matches and mechanism == "ranking_model_disagreement":
            matches = [
                file
                for file in self.code_graph.test_files
                if "ranking_disagreement" in file.path
            ]
        return [
            LocatedComponent(
                kind="test",
                key=file.path.rsplit("/", 1)[-1].removesuffix(".py"),
                path=file.path,
                exists=True,
                reason="existing test covers part of this mechanism",
                symbols=tuple(symbol.name for symbol in file.symbols),
            )
            for file in matches
        ]

    def _component(self, kind: str, key: str, path: str, reason: str) -> LocatedComponent:
        target = self.root / path
        file = next((item for item in self.code_graph.source_files if item.path == path), None)
        return LocatedComponent(
            kind=kind,
            key=key,
            path=path,
            exists=target.exists(),
            reason=reason,
            symbols=() if file is None else tuple(symbol.name for symbol in file.symbols),
        )

    @staticmethod
    def _values(value: Any) -> list[str]:
        if isinstance(value, dict):
            return [text for nested in value.values() for text in RepositoryLocator._values(nested)]
        if isinstance(value, (list, tuple)):
            return [text for nested in value for text in RepositoryLocator._values(nested)]
        if value is None:
            return []
        return [str(value)]

    @staticmethod
    def _dedupe(components: list[LocatedComponent]) -> list[LocatedComponent]:
        seen: set[tuple[str, str, str]] = set()
        result: list[LocatedComponent] = []
        for component in components:
            key = (component.kind, component.key, component.path)
            if key in seen:
                continue
            seen.add(key)
            result.append(component)
        return result
