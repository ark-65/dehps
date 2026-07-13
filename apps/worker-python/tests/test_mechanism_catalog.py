from dehps.research_autonomy.mechanism_catalog import MechanismCatalog
from research_autonomy_fixtures import rejected_family, rejected_hypothesis


def test_mechanism_catalog_contains_required_ten_families() -> None:
    mechanisms = MechanismCatalog().build()
    assert len(mechanisms) == 10
    assert {item.key for item in mechanisms} >= {
        "multivariate_residual_persistence", "cooccurrence_graph_drift",
        "ranking_model_disagreement", "candidate_space_density_shift", "regime_change_detection",
    }


def test_rejected_registry_records_are_linked_to_mechanism_memory() -> None:
    mechanisms = MechanismCatalog().build((rejected_hypothesis(),), (rejected_family(),))
    nonlinear = next(item for item in mechanisms if item.key == "feature_interaction_nonlinearity")
    assert "rejected-family" in nonlinear.known_hypothesis_families
    assert "rejected-1" in nonlinear.rejected_variations
    assert nonlinear.maturity == "rejected_region_known"
