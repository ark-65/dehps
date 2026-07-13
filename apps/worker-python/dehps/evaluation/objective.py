from __future__ import annotations

from dataclasses import dataclass

from dehps.evaluation.objective_policy import ObjectivePolicy
from dehps.evaluation.tail_risk import calculate_tail_risk_penalty


@dataclass(frozen=True)
class TrainingMetrics:
    top_100_hits: int
    top_1000_hits: int
    top_10000_hits: int
    median_rank: float
    worst_rank: int
    p95_rank: float | None
    tail_over_750000_count: int
    tail_over_900000_count: int
    tail_over_1000000_count: int
    baseline_unique_reward: float
    baseline_overlap_penalty: float
    red5_top_100_hits: int
    red5_top_1000_hits: int
    red5_top_10000_hits: int
    rank_quality_reward: float
    universe_size: int
    tail_risk_penalty: float | None = None


@dataclass(frozen=True)
class ObjectiveResult:
    hit_reward: float
    baseline_unique_reward: float
    baseline_overlap_penalty: float
    red5_reward: float
    rank_quality_reward: float
    rank_penalty: float
    tail_risk_penalty: float
    objective: float
    policy_version: str
    policy_hash: str

    def as_legacy_dict(self) -> dict[str, float]:
        return {
            "hitReward": self.hit_reward,
            "baselineUniqueReward": self.baseline_unique_reward,
            "baselineOverlapPenalty": self.baseline_overlap_penalty,
            "red5Reward": self.red5_reward,
            "rankQualityReward": self.rank_quality_reward,
            "rankPenalty": self.rank_penalty,
            "tailRiskPenalty": self.tail_risk_penalty,
            "objectiveScore": self.objective,
        }


def evaluate_objective(metrics: TrainingMetrics, policy: ObjectivePolicy) -> ObjectiveResult:
    safe_universe = max(1, metrics.universe_size)
    hit_reward = (
        metrics.top_100_hits * policy.top_100_reward
        + metrics.top_1000_hits * policy.top_1000_reward
        + metrics.top_10000_hits * policy.top_10000_reward
    )
    red5_reward = (
        metrics.red5_top_100_hits * policy.red5_top_100_reward
        + metrics.red5_top_1000_hits * policy.red5_top_1000_reward
        + metrics.red5_top_10000_hits * policy.red5_top_10000_reward
    )
    rank_penalty = metrics.median_rank / safe_universe + metrics.worst_rank / safe_universe / 4
    tail_risk_penalty = metrics.tail_risk_penalty
    if not tail_risk_penalty:
        tail_risk_penalty = calculate_tail_risk_penalty(
            median_rank=metrics.median_rank,
            worst_rank=metrics.worst_rank,
            p95_rank=metrics.p95_rank,
            tail_over_750000_count=metrics.tail_over_750000_count,
            tail_over_900000_count=metrics.tail_over_900000_count,
            tail_over_1000000_count=metrics.tail_over_1000000_count,
            universe_size=safe_universe,
            policy=policy,
        )
    objective = (
        hit_reward
        + metrics.baseline_unique_reward
        + red5_reward
        + metrics.rank_quality_reward
        - rank_penalty
        - tail_risk_penalty
        - metrics.baseline_overlap_penalty
    )
    return ObjectiveResult(
        hit_reward=round(hit_reward, 6),
        baseline_unique_reward=round(metrics.baseline_unique_reward, 6),
        baseline_overlap_penalty=round(metrics.baseline_overlap_penalty, 6),
        red5_reward=round(red5_reward, 6),
        rank_quality_reward=round(metrics.rank_quality_reward, 6),
        rank_penalty=round(rank_penalty, 6),
        tail_risk_penalty=round(tail_risk_penalty, 6),
        objective=round(objective, 6),
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
    )
