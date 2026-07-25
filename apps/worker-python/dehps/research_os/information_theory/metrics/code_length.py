from __future__ import annotations

from math import log2
from typing import Any

from dehps.research_os.information_theory.synthetic import (
    full_combination_probability,
    legal_combination_count,
)

from .errors import MetricKernelError


def joint_uniform_code_length() -> dict[str, Any]:
    size = legal_combination_count()
    probability = full_combination_probability()
    return {
        "representation": "LEGAL_SIX_RED_JOINT_UNIFORM",
        "combination_space_size": size,
        "joint_uniform_probability": {
            "numerator": probability.numerator,
            "denominator": probability.denominator,
            "float_probability": float(probability),
        },
        "joint_code_length_bits": log2(size),
        "source": "P2.1 exact C(33,6) helper",
    }


def reject_marginal_product_as_joint(representation: str) -> None:
    if representation not in {
        "LEGAL_SIX_RED_JOINT_DISTRIBUTION",
        "LEGAL_SIX_RED_JOINT_UNIFORM",
    }:
        raise MetricKernelError(
            "joint_probability_contract_violation",
            "33 marginal Bernoulli probabilities cannot be labeled a legal six-red joint distribution",
        )
