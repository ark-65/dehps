"""Frozen P2.3 probe registry; probes never calculate metrics."""

from .contracts import PreparedProbe, ProbePrediction
from .convergence import (
    CONVERGED,
    CONVERGED_WITH_WARNING,
    FAILED_CONVERGENCE,
    INSUFFICIENT_CLASS_VARIATION,
    INVALID_FEATURE_MATRIX,
)
from .empirical_baseline import prepare_empirical_baseline
from .logistic_regression import prepare_logistic_probe
from .registry import FORMAL_PROBE_REGISTRY, prepare_probe
from .theoretical_baseline import prepare_theoretical_baseline

__all__ = [
    "CONVERGED",
    "CONVERGED_WITH_WARNING",
    "FAILED_CONVERGENCE",
    "FORMAL_PROBE_REGISTRY",
    "INSUFFICIENT_CLASS_VARIATION",
    "INVALID_FEATURE_MATRIX",
    "PreparedProbe",
    "ProbePrediction",
    "prepare_empirical_baseline",
    "prepare_logistic_probe",
    "prepare_probe",
    "prepare_theoretical_baseline",
]
