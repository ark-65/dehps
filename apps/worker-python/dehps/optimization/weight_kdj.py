from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_KDJ_WINDOW = 9
DEFAULT_KDJ_SMOOTHING = 1 / 3


@dataclass(frozen=True)
class WeightProbeResult:
    weight_name: str
    weight_value: float
    objective_score: float
    config_hash: str
    rank: int | None = None


@dataclass(frozen=True)
class WeightKdjState:
    rsv: float
    k_value: float
    d_value: float
    j_value: float


@dataclass(frozen=True)
class WeightKdjSignal:
    signal_run_id: str
    issue: str
    draw_date: str | None
    weight_name: str
    train_mode: str
    train_window: int
    eval_window: int
    top_n: int
    history_fingerprint: str
    source: str
    base_value: float
    close_value: float
    issue_low_value: float
    issue_high_value: float
    rolling_low_value: float
    rolling_high_value: float
    rsv: float
    k_value: float
    d_value: float
    j_value: float
    recommended_offset: float
    best_objective_score: float
    objective_delta: float
    sample_count: int
    probe_results: list[dict]
    advisor_metadata: dict


def clamp_ratio(value: float, *, low: float = 0.0, high: float = 100.0) -> float:
    return min(high, max(low, value))


def rsv_from_interval(*, close_value: float, low_value: float, high_value: float) -> float:
    if high_value <= low_value:
        return 50.0
    return clamp_ratio(((close_value - low_value) / (high_value - low_value)) * 100)


def next_kdj_state(
    *,
    close_value: float,
    rolling_low_value: float,
    rolling_high_value: float,
    previous: WeightKdjState | None = None,
    smoothing: float = DEFAULT_KDJ_SMOOTHING,
) -> WeightKdjState:
    previous_k = previous.k_value if previous else 50.0
    previous_d = previous.d_value if previous else 50.0
    rsv = rsv_from_interval(close_value=close_value, low_value=rolling_low_value, high_value=rolling_high_value)
    k_value = smoothing * rsv + (1 - smoothing) * previous_k
    d_value = smoothing * k_value + (1 - smoothing) * previous_d
    return WeightKdjState(rsv=rsv, k_value=k_value, d_value=d_value, j_value=3 * k_value - 2 * d_value)


def rolling_bounds(values: Iterable[tuple[float, float]], *, current_low: float, current_high: float) -> tuple[float, float]:
    lows = [current_low]
    highs = [current_high]
    for low, high in values:
        lows.append(low)
        highs.append(high)
    return min(lows), max(highs)


def recommended_offset_from_j(
    *,
    j_value: float,
    step: float,
    max_multiplier: float = 2.0,
) -> float:
    scaled = ((j_value - 50.0) / 50.0) * step
    limit = abs(step * max_multiplier)
    return min(limit, max(-limit, scaled))


def signal_from_probe_results(
    *,
    signal_run_id: str,
    issue: str,
    draw_date: str | None,
    weight_name: str,
    train_mode: str,
    train_window: int,
    eval_window: int,
    top_n: int,
    history_fingerprint: str,
    source: str,
    base_value: float,
    step: float,
    probe_results: list[WeightProbeResult],
    rolling_issue_bounds: Iterable[tuple[float, float]],
    previous_state: WeightKdjState | None,
) -> tuple[WeightKdjSignal, WeightKdjState]:
    if not probe_results:
        raise ValueError("probe_results must not be empty")

    ordered = sorted(probe_results, key=lambda result: (result.objective_score, -abs(result.weight_value - base_value)), reverse=True)
    best = ordered[0]
    issue_low_value = min(result.weight_value for result in probe_results)
    issue_high_value = max(result.weight_value for result in probe_results)
    rolling_low_value, rolling_high_value = rolling_bounds(
        rolling_issue_bounds,
        current_low=issue_low_value,
        current_high=issue_high_value,
    )
    state = next_kdj_state(
        close_value=best.weight_value,
        rolling_low_value=rolling_low_value,
        rolling_high_value=rolling_high_value,
        previous=previous_state,
    )
    baseline = next((result for result in probe_results if result.weight_value == base_value), None)
    baseline_score = baseline.objective_score if baseline else best.objective_score
    recommended_offset = recommended_offset_from_j(j_value=state.j_value, step=step)

    signal = WeightKdjSignal(
        signal_run_id=signal_run_id,
        issue=issue,
        draw_date=draw_date,
        weight_name=weight_name,
        train_mode=train_mode,
        train_window=train_window,
        eval_window=eval_window,
        top_n=top_n,
        history_fingerprint=history_fingerprint,
        source=source,
        base_value=base_value,
        close_value=best.weight_value,
        issue_low_value=issue_low_value,
        issue_high_value=issue_high_value,
        rolling_low_value=rolling_low_value,
        rolling_high_value=rolling_high_value,
        rsv=state.rsv,
        k_value=state.k_value,
        d_value=state.d_value,
        j_value=state.j_value,
        recommended_offset=recommended_offset,
        best_objective_score=best.objective_score,
        objective_delta=best.objective_score - baseline_score,
        sample_count=len(probe_results),
        probe_results=[
            {
                "weight_name": result.weight_name,
                "weight_value": result.weight_value,
                "objective_score": result.objective_score,
                "config_hash": result.config_hash,
                "rank": result.rank,
            }
            for result in probe_results
        ],
        advisor_metadata={
            "mode": "kdj_response_interval",
            "step": step,
            "recommended_offset_formula": "((J - 50) / 50) * step, clamped to +/-2*step",
        },
    )
    return signal, state
