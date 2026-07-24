from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dehps.training.research_fingerprint import SeedPolicy


INFORMATION_THEORY_CONTRACT_VERSION = "m4-information-theory-contract-v1"
PREREGISTRATION_SCHEMA_VERSION = "dehps-m4-information-theory-preregistration.v1"
DECISION_POLICY_SCHEMA_VERSION = "dehps-m4-information-theory-decision-policy.v1"
P2_INPUT_SCHEMA_VERSION = "dehps-m4-information-theory-p2-input.v1"


@dataclass(frozen=True)
class RandomizedTaskContract:
    task_key: str
    seed_policy: SeedPolicy
    replicate_count: int

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RandomizedTaskContract":
        raw_policy = payload.get("seed_policy")
        if not isinstance(raw_policy, Mapping):
            raise ValueError("randomized task requires seed_policy")
        raw_seeds = raw_policy.get("seeds")
        if raw_seeds is None:
            seed_range = raw_policy.get("seed_range")
            if (
                not isinstance(seed_range, list)
                or len(seed_range) != 2
                or int(seed_range[1]) <= int(seed_range[0])
            ):
                raise ValueError("seed_policy requires seeds or [start,stop) seed_range")
            raw_seeds = range(int(seed_range[0]), int(seed_range[1]))
        policy = SeedPolicy(
            seeds=tuple(int(value) for value in raw_seeds),
            aggregation=str(raw_policy.get("aggregation", "distribution")),
            selection_policy=str(raw_policy.get("selection_policy", "no_best_seed")),
        )
        count = int(payload.get("replicate_count", 0))
        if count < 1:
            raise ValueError("randomized task replicate_count must be positive")
        if len(policy.seeds) != count:
            raise ValueError("replicate_count must equal normalized seed count")
        return cls(
            task_key=str(payload.get("task_key", "")),
            seed_policy=policy,
            replicate_count=count,
        )


@dataclass(frozen=True)
class DeterministicTaskContract:
    task_key: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DeterministicTaskContract":
        if payload.get("seed_policy") not in (None, "none"):
            raise ValueError("deterministic task cannot carry a seed policy")
        return cls(task_key=str(payload.get("task_key", "")))
