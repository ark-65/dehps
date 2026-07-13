from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineComparison:
    unique_reward: float = 0.0
    overlap_penalty: float = 0.0
    acceptable: bool = True


@dataclass(frozen=True)
class LeakageReport:
    passed: bool = True
    failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationResult:
    objective: float
    top_100_hits: int
    top_1000_hits: int
    top_10000_hits: int
    median_rank: float
    p95_rank: float | None
    worst_rank: int
    tail_risk: float | None
    tail_over_750000_count: int
    tail_over_900000_count: int
    tail_over_1000000_count: int
    baseline_comparison: BaselineComparison
    leakage_report: LeakageReport
    valid: bool = True
    has_forward_evidence: bool = True
    config_hash: str = ""

    @property
    def primary_score(self) -> tuple[int, int, int]:
        return (self.top_100_hits, self.top_1000_hits, self.top_10000_hits)
