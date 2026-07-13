from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from dehps.models.frequency_ranker import FrequencyRankerConfig


@dataclass(frozen=True)
class AdvisorContext:
    base_config: FrequencyRankerConfig
    signals: tuple[dict, ...] = ()
    settings: Mapping[str, object] | None = None


@dataclass(frozen=True)
class AdvisorCandidate:
    config: FrequencyRankerConfig
    source_key: str
    protocol_version: str


class TrainingAdvisor(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def protocol_version(self) -> str: ...

    def propose(self, context: AdvisorContext, budget: int) -> Sequence[FrequencyRankerConfig]: ...
