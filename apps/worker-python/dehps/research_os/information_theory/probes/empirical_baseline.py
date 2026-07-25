from __future__ import annotations

from dataclasses import dataclass

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.walk_forward.contracts import (
    BlindTestFeatureView,
    ProbeState,
    TrainingDatasetView,
    TrainFeatureView,
)
from dehps.research_os.information_theory.walk_forward.errors import WalkForwardError

from .convergence import CONVERGED


@dataclass(frozen=True)
class PreparedEmpiricalBaseline:
    state: ProbeState
    probabilities: tuple[float, ...]

    def predict(self, view: BlindTestFeatureView) -> tuple[float, ...]:
        return self.probabilities


def prepare_empirical_baseline(
    dataset: TrainingDatasetView,
    train_view: TrainFeatureView,
) -> PreparedEmpiricalBaseline:
    if not isinstance(dataset, TrainingDatasetView):
        raise WalkForwardError(
            "target_access_boundary_violation",
            "empirical probe requires a training-only dataset view",
        )
    issue_ids = train_view.issue_ids
    counts = [
        sum(dataset.issue(issue_id).target_vector[offset] for issue_id in issue_ids)
        for offset in range(33)
    ]
    denominator = len(issue_ids) + 1.0
    probabilities = tuple((count + 0.5) / denominator for count in counts)
    model_payload = {
        "smoothing": "beta_binomial_jeffreys_alpha_0_5_beta_0_5",
        "counts": counts,
        "training_issue_count": len(issue_ids),
        "probabilities": list(probabilities),
    }
    model_digest = canonical_digest(
        model_payload, domain="dehps.m4.probe.empirical-baseline.v1"
    )
    state_payload = {
        "probe_id": "EMPIRICAL_BASELINE",
        "training_start_issue": min(issue_ids),
        "training_end_issue": max(issue_ids),
        "model_parameters_digest": model_digest,
        "feature_manifest_digest": train_view.feature_manifest_digest,
    }
    state = ProbeState(
        probe_id="EMPIRICAL_BASELINE",
        probe_type="expanding_empirical_baseline",
        training_start_issue=min(issue_ids),
        training_end_issue=max(issue_ids),
        training_issue_count=len(issue_ids),
        training_row_count=len(issue_ids) * 33,
        feature_manifest_digest=train_view.feature_manifest_digest,
        preprocessing_state_digest="none",
        hyperparameter_selection_digest="none",
        model_parameters_digest=model_digest,
        convergence_status=CONVERGED,
        hyperparameters={
            "smoothing": "beta_binomial_jeffreys_alpha_0_5_beta_0_5"
        },
        state_digest=canonical_digest(
            state_payload, domain="dehps.m4.probe-state.v1"
        ),
        seed_policy={"mode": "none"},
    )
    return PreparedEmpiricalBaseline(state=state, probabilities=probabilities)
