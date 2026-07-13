from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from dehps.models.frequency_ranker import FrequencyRankerConfig


MergeReserved = Callable[
    [Sequence[FrequencyRankerConfig], Sequence[FrequencyRankerConfig]],
    tuple[FrequencyRankerConfig, ...],
]


@dataclass(frozen=True)
class ReservedCandidateSource:
    key: str
    configs: tuple[FrequencyRankerConfig, ...]
    budget: int
    capacity: int | None = None
    include_when_zero_budget: bool = False


@dataclass(frozen=True)
class CandidateComposition:
    configs: tuple[FrequencyRankerConfig, ...]
    source_configs: Mapping[str, tuple[FrequencyRankerConfig, ...]]


@dataclass(frozen=True)
class CandidateSourceComposer:
    """Compose candidate sources in one deterministic, budget-aware path.

    The injected merge/refill operations preserve the established runtime ordering
    and deduplication rules while making source orchestration independently testable.
    """

    merge_reserved: Callable[..., tuple[FrequencyRankerConfig, ...]]
    refill: Callable[..., tuple[FrequencyRankerConfig, ...]]
    config_hash: Callable[[FrequencyRankerConfig], str]

    def compose(
        self,
        *,
        normal_pool: tuple[FrequencyRankerConfig, ...],
        normal_budget: int,
        reserved_sources: tuple[ReservedCandidateSource, ...],
        max_configs: int,
    ) -> CandidateComposition:
        configs = normal_pool[: max(0, normal_budget)]
        source_configs: dict[str, tuple[FrequencyRankerConfig, ...]] = {
            "normal": configs,
        }
        for source in reserved_sources:
            source_configs[source.key] = source.configs
            if source.budget <= 0 and not source.include_when_zero_budget:
                continue
            configs = self.merge_reserved(
                configs,
                source.configs,
                max_configs=max(
                    0,
                    max_configs if source.capacity is None else source.capacity,
                ),
                reserved_budget=max(0, source.budget),
            )
        configs = self.refill(configs, normal_pool, max_configs=max_configs)
        selected_hashes = {self.config_hash(config) for config in configs}
        source_configs["normal"] = tuple(
            config for config in normal_pool if self.config_hash(config) in selected_hashes
        )
        return CandidateComposition(tuple(configs), source_configs)
