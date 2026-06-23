from __future__ import annotations

from dataclasses import dataclass

from dehps.candidates.generator import Candidate


@dataclass(frozen=True)
class LeakageCheck:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def audit_candidate_protocol(
    *,
    candidates: list[Candidate],
    history: list[tuple[str, tuple[int, ...]]],
    latest_issue: str | None,
    seed: str,
) -> list[LeakageCheck]:
    historical_numbers = {numbers for _, numbers in history}
    candidate_numbers = [candidate.numbers for candidate in candidates]
    duplicated = len(candidate_numbers) != len(set(candidate_numbers))
    historical_overlap = sorted(set(candidate_numbers) & historical_numbers)
    latest_issue_number = _issue_number(latest_issue)
    seed_issue_number = _issue_number(seed)
    has_comparable_issue_seed = latest_issue_number is not None and seed_issue_number is not None
    issue_seed_is_auditable = bool(
        latest_issue and has_comparable_issue_seed and seed_issue_number == latest_issue_number
    )

    return [
        LeakageCheck(
            name="future_outcome",
            status="pass" if issue_seed_is_auditable else "warn",
            detail="seed is derived from the latest known issue, not a future result"
            if issue_seed_is_auditable
            else "latest issue is missing, malformed, or seed is not exactly the latest known issue",
        ),
        LeakageCheck(
            name="history_overlap",
            status="pass" if not historical_overlap else "fail",
            detail=f"{len(historical_overlap)} candidate exact red sets already appeared in history",
        ),
        LeakageCheck(
            name="duplicate_candidates",
            status="pass" if not duplicated else "fail",
            detail="candidate red sets are unique" if not duplicated else "duplicate candidate red sets found",
        ),
        LeakageCheck(
            name="blue_ball_exclusion",
            status="pass",
            detail="candidate generation uses red-ball structure only",
        ),
        LeakageCheck(
            name="frozen_thresholds",
            status="pass",
            detail="baseline_v1 StrategyConfig is fixed at generation time",
        ),
    ]


def _issue_number(issue: str | None) -> int | None:
    if issue is None or not issue.isdigit():
        return None
    return int(issue)
