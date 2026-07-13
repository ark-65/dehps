from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from dehps.advisors.neural_kdj_adapter import NeuralKdjAdvisorAdapter
from dehps.advisors.protocol import AdvisorCandidate, AdvisorContext
from dehps.advisors.registry import AdvisorRegistry
from dehps.advisors.ridge_kdj_adapter import RidgeKdjAdvisorAdapter
from dehps.advisors.target_weight_inversion_adapter import TargetWeightInversionAdvisorAdapter
from dehps.advisors.weight_kdj_adapter import WeightKdjAdvisorAdapter
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.neural_kdj_advisor import (
    NeuralKdjOffsetAdvice,
    neural_kdj_advice_to_frequency_ranker_config_candidates,
    numpy_neural_kdj_offset_v0,
)
from dehps.optimization.ridge_kdj_advisor import (
    RidgeKdjOffsetAdvice,
    numpy_ridge_kdj_offset_v0,
    ridge_kdj_advice_to_frequency_ranker_config_candidates,
)
from dehps.optimization.weight_kdj import WeightKdjAdvice, weight_kdj_advice_from_signals
from dehps.search.fields import ALL_FIELDS


@dataclass(frozen=True)
class RuntimeAdvisorSettings:
    enable_weight_kdj: bool
    enable_ridge_kdj: bool
    enable_neural_kdj: bool
    enable_target_weight_inversion: bool
    weight_min_objective_delta: float
    weight_min_abs_offset: float
    weight_slope_window: int
    weight_neutral_band: float
    ridge_step: float
    ridge_alpha: float
    ridge_min_confidence: float
    ridge_min_train_rows: int
    ridge_min_validation_rows: int
    neural_step: float
    neural_seed: int
    neural_hidden_units: int
    neural_epochs: int
    neural_min_confidence: float


@dataclass(frozen=True)
class RuntimeAdvisorOutcome:
    candidates: tuple[AdvisorCandidate, ...]
    configs_by_source: dict[str, tuple[FrequencyRankerConfig, ...]]
    weight_advice: tuple[WeightKdjAdvice, ...]
    ridge_advice: tuple[RidgeKdjOffsetAdvice, ...]
    neural_advice: tuple[NeuralKdjOffsetAdvice, ...]


def weight_kdj_candidate_configs(
    base: FrequencyRankerConfig,
    advice: Sequence[WeightKdjAdvice],
    *,
    max_configs: int,
) -> tuple[FrequencyRankerConfig, ...]:
    if max_configs <= 0:
        return ()
    configs: list[FrequencyRankerConfig] = []
    usable = [
        item
        for item in advice
        if item.decision in {"selected", "downweighted"} and item.applied_offset
    ]

    def add(config: FrequencyRankerConfig) -> None:
        if len(configs) < max_configs and config not in configs:
            configs.append(config)

    for item in usable:
        add(
            replace(
                base,
                **{
                    item.weight_name: getattr(base, item.weight_name)
                    + item.applied_offset
                },
            )
        )
        if len(configs) >= max_configs:
            return tuple(configs)
    selected = [item for item in usable if item.decision == "selected"]
    if len(selected) >= 2:
        values = dict(base.__dict__)
        combined_fields: set[str] = set()
        for item in selected:
            if item.weight_name in combined_fields:
                continue
            combined_fields.add(item.weight_name)
            values[item.weight_name] += item.applied_offset / 2
            if len(combined_fields) >= 4:
                break
        add(FrequencyRankerConfig(**values))
    return tuple(configs[:max_configs])


@dataclass(frozen=True)
class RuntimeAdvisorOrchestrator:
    """Own every production advisor proposal path behind one registry call."""

    def propose(
        self,
        *,
        base_config: FrequencyRankerConfig,
        signals: list[dict],
        budgets: dict[str, int],
        target_weight_inversion_configs: tuple[FrequencyRankerConfig, ...],
        settings: RuntimeAdvisorSettings,
    ) -> RuntimeAdvisorOutcome:
        weight_advice = (
            weight_kdj_advice_from_signals(
                signals,
                allowed_fields=ALL_FIELDS,
                min_objective_delta=settings.weight_min_objective_delta,
                min_abs_offset=settings.weight_min_abs_offset,
                slope_window=settings.weight_slope_window,
                neutral_band=settings.weight_neutral_band,
            )
            if settings.enable_weight_kdj
            else ()
        )
        ridge_advice = (
            numpy_ridge_kdj_offset_v0(
                signals,
                step=settings.ridge_step,
                ridge_alpha=settings.ridge_alpha,
                min_train_rows=settings.ridge_min_train_rows,
                min_validation_rows=settings.ridge_min_validation_rows,
            )
            if settings.enable_ridge_kdj
            else ()
        )
        neural_advice = (
            numpy_neural_kdj_offset_v0(
                signals,
                step=settings.neural_step,
                seed=settings.neural_seed,
                hidden_units=settings.neural_hidden_units,
                epochs=settings.neural_epochs,
            )
            if settings.enable_neural_kdj
            else ()
        )
        advisors = []
        if settings.enable_weight_kdj:
            advisors.append(
                WeightKdjAdvisorAdapter(
                    lambda _context, budget: weight_kdj_candidate_configs(
                        base_config,
                        weight_advice,
                        max_configs=budget,
                    )
                )
            )
        if settings.enable_ridge_kdj:
            advisors.append(
                RidgeKdjAdvisorAdapter(
                    lambda _context, budget: ridge_kdj_advice_to_frequency_ranker_config_candidates(
                        base_config,
                        ridge_advice,
                        max_configs=budget,
                        min_confidence=settings.ridge_min_confidence,
                    )
                )
            )
        if settings.enable_neural_kdj:
            advisors.append(
                NeuralKdjAdvisorAdapter(
                    lambda _context, budget: neural_kdj_advice_to_frequency_ranker_config_candidates(
                        base_config,
                        neural_advice,
                        max_configs=budget,
                        min_confidence=settings.neural_min_confidence,
                    )
                )
            )
        if settings.enable_target_weight_inversion:
            advisors.append(
                TargetWeightInversionAdvisorAdapter(
                    lambda _context, budget: target_weight_inversion_configs[:budget]
                )
            )
        candidates = AdvisorRegistry.build(advisors).propose(
            AdvisorContext(base_config=base_config, signals=tuple(signals)),
            budgets=budgets,
        )
        keys = (
            "weight_kdj",
            "ridge_kdj",
            "neural_kdj",
            "target_weight_inversion",
        )
        configs_by_source = {
            key: tuple(
                candidate.config
                for candidate in candidates
                if candidate.source_key == key
            )
            for key in keys
        }
        return RuntimeAdvisorOutcome(
            candidates=candidates,
            configs_by_source=configs_by_source,
            weight_advice=tuple(weight_advice),
            ridge_advice=tuple(ridge_advice),
            neural_advice=tuple(neural_advice),
        )
