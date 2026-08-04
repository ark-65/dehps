"""P2.4 calibration exports with an import-safe lazy package boundary."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_CONTRACTS = "dehps.research_os.information_theory.calibration.contracts"
_MECHANISMS = "dehps.research_os.information_theory.calibration.mechanisms"
_RUNNER = "dehps.research_os.information_theory.calibration.runner"

_EXPORTS = {
    "CALIBRATION_RUN_MANIFEST_DIGEST": (
        _CONTRACTS,
        "CALIBRATION_RUN_MANIFEST_DIGEST",
    ),
    "P24CalibrationManifest": (_CONTRACTS, "P24CalibrationManifest"),
    "load_calibration_manifest": (_CONTRACTS, "load_calibration_manifest"),
    "validate_calibration_manifest": (_CONTRACTS, "validate_calibration_manifest"),
    "CalibrationError": (_MECHANISMS, "CalibrationError"),
    "CalibratedScenario": (_MECHANISMS, "CalibratedScenario"),
    "calibrate_scenario": (_MECHANISMS, "calibrate_scenario"),
    "generate_calibration_dataset": (_MECHANISMS, "generate_calibration_dataset"),
    "P24CalibrationRunResult": (_RUNNER, "P24CalibrationRunResult"),
    "run_p24_calibration": (_RUNNER, "run_p24_calibration"),
}

__all__ = [
    "CALIBRATION_RUN_MANIFEST_DIGEST",
    "CalibratedScenario",
    "CalibrationError",
    "P24CalibrationManifest",
    "P24CalibrationRunResult",
    "calibrate_scenario",
    "generate_calibration_dataset",
    "load_calibration_manifest",
    "run_p24_calibration",
    "validate_calibration_manifest",
]


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
