from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CandidateBudgetPolicy:
    exploitation_share: float = 0.40
    exploration_share: float = 0.30
    replay_share: float = 0.20
    baseline_share: float = 0.10

    def shares(self) -> dict[str, float]:
        return {
            "exploitation": self.exploitation_share,
            "exploration": self.exploration_share,
            "replay": self.replay_share,
            "baseline": self.baseline_share,
        }


DEFAULT_CANDIDATE_BUDGET_POLICY = CandidateBudgetPolicy()
CANDIDATE_BUDGET_SHARES = DEFAULT_CANDIDATE_BUDGET_POLICY.shares()


@dataclass(frozen=True)
class ReservedCandidateBudget:
    name: str
    share: float
    available: int


@dataclass(frozen=True)
class CandidateBudget:
    counts: tuple[tuple[str, int], ...]

    @property
    def total(self) -> int:
        return sum(value for _name, value in self.counts)

    def as_dict(self) -> dict[str, int]:
        return dict(self.counts)


def _reserved_candidate_count(total: int, share: float, *, available: int) -> int:
    if total <= 0 or available <= 0 or share <= 0:
        return 0
    bounded_share = min(1.0, max(0.0, share))
    return min(available, max(1, int(ceil(total * bounded_share))))


def allocate_candidate_budget(
    total: int,
    policy: CandidateBudgetPolicy = DEFAULT_CANDIDATE_BUDGET_POLICY,
    *,
    reserved: tuple[ReservedCandidateBudget, ...] = (),
) -> CandidateBudget:
    shares = policy.shares()
    if total <= 0:
        counts = [(name, 0) for name in shares]
        counts.extend((item.name, 0) for item in reserved if item.share > 0)
        return CandidateBudget(tuple(counts))

    reserved_counts: list[tuple[str, int]] = []
    available = total
    for item in reserved:
        count = _reserved_candidate_count(
            total,
            item.share,
            available=min(available, max(0, item.available)),
        )
        available -= count
        if item.share > 0:
            reserved_counts.append((item.name, count))

    normal_budget = available
    names = tuple(shares)
    counts = {name: 0 for name in names}
    remaining = normal_budget
    for name in names:
        if remaining > 0:
            counts[name] = 1
            remaining -= 1
    raw = {name: normal_budget * share - counts[name] for name, share in shares.items()}
    for name in sorted(names, key=lambda item: raw[item], reverse=True):
        if remaining <= 0:
            break
        add = min(max(0, int(raw[name])), remaining)
        counts[name] += add
        remaining -= add
    for name in sorted(names, key=lambda item: raw[item] - int(raw[item]), reverse=True):
        if remaining <= 0:
            break
        counts[name] += 1
        remaining -= 1
    return CandidateBudget(tuple(counts.items()) + tuple(reserved_counts))
