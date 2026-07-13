from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.models.frequency_ranker import FrequencyRankerConfig


@dataclass(frozen=True)
class FeatureDescriptor:
    key: str
    category: str
    input_fields: tuple[str, ...]
    temporal_scope: str
    causal_status: str
    leakage_risk: str
    implementation_path: str
    used_by_models: tuple[str, ...]
    known_failures: tuple[str, ...]
    current_status: str
    contains_future_information: bool = False
    used_in_production_model: bool = False


CATEGORY_BY_PREFIX = {
    "frequency": "frequency", "short_hot": "frequency", "omission": "omission",
    "red_omission": "omission", "long_omission": "omission", "previous": "transition",
    "dynamic": "transition", "lagged": "transition", "repeat": "transition",
    "recent": "trend", "span": "trend", "sum": "trend", "consecutive": "trend",
    "weekday": "calendar", "qian_kun": "distribution", "zone": "distribution",
    "parity": "distribution", "big_small": "distribution", "prime": "distribution",
    "mod012": "distribution", "tail": "distribution", "structural": "structural",
}


class FeatureCatalog:
    def __init__(self, repository_root: Path | None = None) -> None:
        self.root = (repository_root or Path(__file__).resolve().parents[4]).resolve()

    def build(self, rejected_hypotheses=(), rejected_families=()) -> tuple[FeatureDescriptor, ...]:
        descriptors: dict[str, FeatureDescriptor] = {}
        production = FrequencyRankerConfig()
        for field in fields(FrequencyRankerConfig):
            key = field.name.removesuffix("_weight")
            category = next(
                (value for prefix, value in CATEGORY_BY_PREFIX.items() if key.startswith(prefix)),
                "structural",
            )
            descriptors[key] = self._descriptor(
                key,
                category,
                "apps/worker-python/dehps/models/frequency_ranker.py",
                temporal_scope="history_before_target" if category != "structural" else "candidate_only",
                production=bool(getattr(production, field.name)),
            )
        for key in calculate_red_ball_features((1, 2, 3, 8, 13, 21)):
            descriptors.setdefault(
                key,
                self._descriptor(
                    key,
                    "structural",
                    "apps/worker-python/dehps/features/red_ball_features.py",
                    temporal_scope="candidate_only",
                    production=True,
                ),
            )
        manual = (
            ("cooccurrence_graph_drift", "cooccurrence", "apps/worker-python/dehps/training/runtime.py"),
            ("temporal_residual", "residual", "apps/worker-python/dehps/training/runtime.py"),
            ("history_regime", "regime", "apps/worker-python/dehps/training/runtime.py"),
            ("candidate_rank_signature_diversity", "candidate_diversity", "apps/worker-python/dehps/training/runtime.py"),
            ("advisor_rank_disagreement", "model_disagreement", "apps/worker-python/dehps/training/runtime_advisors.py"),
        )
        for key, category, path in manual:
            descriptors[key] = self._descriptor(
                key, category, path, temporal_scope="history_before_target", production=False,
                status="diagnostic_only",
            )
        rejected_text = " ".join(
            [item.mechanism for item in rejected_hypotheses]
            + [item.mechanism for item in rejected_families]
        ).lower()
        result: list[FeatureDescriptor] = []
        for key, item in sorted(descriptors.items()):
            failures = ("associated_with_rejected_registry_record",) if key in rejected_text else ()
            result.append(
                FeatureDescriptor(**{**item.__dict__, "known_failures": failures})
            )
        keys = [item.key for item in result]
        if len(keys) != len(set(keys)):
            raise ValueError("feature catalog keys must be unique")
        for item in result:
            if not (self.root / item.implementation_path).is_file():
                raise ValueError(f"feature implementation path does not exist: {item.implementation_path}")
        return tuple(result)

    @staticmethod
    def _descriptor(
        key: str,
        category: str,
        path: str,
        *,
        temporal_scope: str,
        production: bool,
        status: str = "implemented",
    ) -> FeatureDescriptor:
        return FeatureDescriptor(
            key=key,
            category=category,
            input_fields=("issue", "draw_date", "red_numbers"),
            temporal_scope=temporal_scope,
            causal_status="observational_structural",
            leakage_risk="low_if_target_excluded",
            implementation_path=path,
            used_by_models=("frequency_ranker",),
            known_failures=(),
            current_status=status,
            contains_future_information=False,
            used_in_production_model=production,
        )
