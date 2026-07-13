from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class ObjectivePolicy:
    version: str
    top_100_reward: float
    top_1000_reward: float
    top_10000_reward: float
    baseline_unique_top_100_reward: float
    baseline_unique_top_1000_reward: float
    baseline_unique_top_10000_reward: float
    baseline_overlap_top_100_penalty: float
    baseline_overlap_top_1000_penalty: float
    baseline_overlap_top_10000_penalty: float
    red5_top_100_reward: float
    red5_top_1000_reward: float
    red5_top_10000_reward: float
    rank_top_50000_reward: float
    rank_top_100000_reward: float
    rank_top_250000_reward: float
    rank_top_500000_reward: float
    worst_rank_reward: float
    median_rank_reward: float
    worst_rank_penalty_weight: float
    p95_rank_penalty_weight: float
    median_rank_penalty_weight: float
    tail_over_750000_penalty: float
    tail_over_900000_penalty: float
    tail_over_1000000_penalty: float

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @property
    def policy_hash(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def objective_policy_hash(policy: ObjectivePolicy) -> str:
    return policy.policy_hash


DEFAULT_OBJECTIVE_POLICY = ObjectivePolicy(
    version="rank_objective_v1",
    top_100_reward=1200,
    top_1000_reward=180,
    top_10000_reward=3,
    baseline_unique_top_100_reward=250,
    baseline_unique_top_1000_reward=60,
    baseline_unique_top_10000_reward=4,
    baseline_overlap_top_100_penalty=80,
    baseline_overlap_top_1000_penalty=20,
    baseline_overlap_top_10000_penalty=3,
    red5_top_100_reward=5,
    red5_top_1000_reward=1,
    red5_top_10000_reward=0.2,
    rank_top_50000_reward=0.10,
    rank_top_100000_reward=0.05,
    rank_top_250000_reward=0.02,
    rank_top_500000_reward=0.01,
    worst_rank_reward=6.0,
    median_rank_reward=8.0,
    worst_rank_penalty_weight=12.0,
    p95_rank_penalty_weight=6.0,
    median_rank_penalty_weight=2.0,
    tail_over_750000_penalty=0.15,
    tail_over_900000_penalty=0.50,
    tail_over_1000000_penalty=1.25,
)
