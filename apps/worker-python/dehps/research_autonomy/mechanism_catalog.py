from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MechanismDescriptor:
    key: str
    title: str
    description: str
    required_inputs: tuple[str, ...]
    compatible_models: tuple[str, ...]
    known_hypothesis_families: tuple[str, ...]
    rejected_variations: tuple[str, ...]
    reopen_conditions: tuple[str, ...]
    maturity: str


MECHANISMS = (
    ("univariate_temporal_residual", "Univariate temporal residual", "Test residual persistence for one preregistered feature."),
    ("multivariate_residual_persistence", "Multivariate residual persistence", "Test whether independent residual components persist across time."),
    ("cooccurrence_graph_drift", "Co-occurrence graph drift", "Test time-isolated drift in number co-occurrence geometry."),
    ("ranking_model_disagreement", "Ranking model disagreement", "Test whether preregistered ranker disagreement identifies informative tails."),
    ("candidate_space_density_shift", "Candidate-space density shift", "Test changes in local rank-signature density without using outcomes."),
    ("regime_change_detection", "Regime change detection", "Test a frozen change-point rule against a stationary baseline."),
    ("multi_scale_frequency_residual", "Multi-scale frequency residual", "Test residual disagreement across fixed temporal windows."),
    ("omission_survival_process", "Omission survival process", "Test calibrated omission survival against empirical frequency."),
    ("feature_interaction_nonlinearity", "Feature interaction nonlinearity", "Test a preregistered interaction against additive same-budget baseline."),
    ("ensemble_rank_diversification", "Ensemble rank diversification", "Test deterministic rank diversification against best component ranker."),
)


class MechanismCatalog:
    def build(self, rejected_hypotheses=(), rejected_families=()) -> tuple[MechanismDescriptor, ...]:
        records = tuple(rejected_hypotheses) + tuple(rejected_families)
        result: list[MechanismDescriptor] = []
        for key, title, description in MECHANISMS:
            related = []
            for item in records:
                text = f"{item.family_key} {item.title} {item.mechanism}".lower().replace("_", " ")
                if key.replace("_", " ") in text or self._semantic_alias(key, text):
                    related.append(item)
            result.append(
                MechanismDescriptor(
                    key=key,
                    title=title,
                    description=description,
                    required_inputs=("issue", "draw_date", "red_numbers"),
                    compatible_models=("frequency_ranker", "ridge_kdj_adapter", "neural_kdj_adapter"),
                    known_hypothesis_families=tuple(sorted({item.family_key for item in related})),
                    rejected_variations=tuple(sorted({item.hypothesis_key if hasattr(item, "hypothesis_key") else item.family_key for item in related})),
                    reopen_conditions=tuple(sorted({item.reopen_condition for item in related if item.reopen_condition})),
                    maturity="rejected_region_known" if related else "proposal_ready",
                )
            )
        return tuple(result)

    @staticmethod
    def _semantic_alias(key: str, text: str) -> bool:
        aliases = {
            "feature_interaction_nonlinearity": (
                "neural", "interaction", "nonlinear", "structural mlp", "kdj", "random split"
            ),
            "multi_scale_frequency_residual": ("frequency", "temporal residual"),
            "univariate_temporal_residual": ("temporal residual",),
        }
        return any(alias in text for alias in aliases.get(key, ()))
