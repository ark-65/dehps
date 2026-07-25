from __future__ import annotations

from math import fsum, log, log1p
from typing import Any

from .errors import MetricKernelError
from .probability import theoretical_number_probability


LN_2 = log(2.0)


def nats_to_bits(value: float) -> float:
    return float(value) / LN_2


def bits_to_nats(value: float) -> float:
    return float(value) * LN_2


def bernoulli_log_loss_nats(target: int, clipped_probability: float) -> float:
    if target not in (0, 1):
        raise MetricKernelError("invalid_target_value", "target must be 0 or 1")
    if clipped_probability <= 0.0 or clipped_probability >= 1.0:
        raise MetricKernelError(
            "unclipped_probability",
            "log-loss probability must already be clipped into (0,1)",
        )
    return -log(clipped_probability) if target == 1 else -log1p(-clipped_probability)


def theoretical_baseline_loss() -> dict[str, Any]:
    probability = theoretical_number_probability()
    p = float(probability)
    nats = fsum(
        (
            6 * -log(p),
            27 * -log1p(-p),
        )
    )
    return {
        "baseline_identity": "NUMBER_EVENT_COMPOSITE_BASELINE",
        "probability": {
            "numerator": 6,
            "denominator": 33,
            "float_probability": p,
        },
        "theoretical_baseline_nats_per_issue": nats,
        "theoretical_baseline_bits_per_issue": nats_to_bits(nats),
        "statistical_meaning": "composite_bernoulli_number_event_score_not_joint_entropy",
    }
