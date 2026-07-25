from __future__ import annotations

from dataclasses import dataclass

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.walk_forward.contracts import (
    THEORETICAL_PROBABILITY,
    BlindTestFeatureView,
    ProbeState,
)

from .convergence import CONVERGED


@dataclass(frozen=True)
class PreparedTheoreticalBaseline:
    state: ProbeState

    def predict(self, view: BlindTestFeatureView) -> tuple[float, ...]:
        return (THEORETICAL_PROBABILITY,) * 33


def prepare_theoretical_baseline(
    *,
    feature_manifest_digest: str,
) -> PreparedTheoreticalBaseline:
    model_digest = canonical_digest(
        {"probability": {"numerator": 6, "denominator": 33}},
        domain="dehps.m4.probe.theoretical-baseline.v1",
    )
    state_payload = {
        "probe_id": "THEORETICAL_BASELINE",
        "probe_type": "theoretical_uniform_baseline",
        "fit_scope": "none",
        "model_parameters_digest": model_digest,
        "feature_manifest_digest": feature_manifest_digest,
        "seed_policy": {"mode": "none"},
    }
    state = ProbeState(
        probe_id="THEORETICAL_BASELINE",
        probe_type="theoretical_uniform_baseline",
        training_start_issue=None,
        training_end_issue=None,
        training_issue_count=0,
        training_row_count=0,
        feature_manifest_digest=feature_manifest_digest,
        preprocessing_state_digest="none",
        hyperparameter_selection_digest="none",
        model_parameters_digest=model_digest,
        convergence_status=CONVERGED,
        hyperparameters={},
        state_digest=canonical_digest(
            state_payload, domain="dehps.m4.probe-state.v1"
        ),
        seed_policy={"mode": "none"},
    )
    return PreparedTheoreticalBaseline(state=state)
