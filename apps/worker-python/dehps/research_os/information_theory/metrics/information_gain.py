from __future__ import annotations

from dataclasses import dataclass

from .log_loss import nats_to_bits


@dataclass(frozen=True)
class ObservedLogLossGain:
    nats_per_issue: float
    bits_per_issue: float
    direction: str
    eligible_for_pe1: bool = True
    eligible_for_final_pe2: bool = False


def observed_log_loss_gain(
    *,
    baseline_nats_per_issue: float,
    probe_nats_per_issue: float,
) -> ObservedLogLossGain:
    gain = baseline_nats_per_issue - probe_nats_per_issue
    direction = "positive_probe_better" if gain > 0 else (
        "negative_probe_worse" if gain < 0 else "zero_equal"
    )
    return ObservedLogLossGain(
        nats_per_issue=gain,
        bits_per_issue=nats_to_bits(gain),
        direction=direction,
    )
