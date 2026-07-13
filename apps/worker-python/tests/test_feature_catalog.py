from dehps.research_autonomy.feature_catalog import FeatureCatalog


def test_feature_catalog_has_unique_implemented_keys_and_all_required_categories() -> None:
    features = FeatureCatalog().build()
    keys = [item.key for item in features]
    categories = {item.category for item in features}
    assert len(keys) == len(set(keys))
    assert {
        "frequency", "omission", "structural", "transition", "cooccurrence", "trend",
        "calendar", "distribution", "residual", "regime", "candidate_diversity",
        "model_disagreement",
    }.issubset(categories)
    assert all(item.implementation_path for item in features)
    assert all(item.contains_future_information is False for item in features)


def test_feature_catalog_marks_current_production_features() -> None:
    by_key = {item.key: item for item in FeatureCatalog().build()}
    assert by_key["frequency"].used_in_production_model is True
    assert by_key["omission"].used_in_production_model is True
    assert by_key["advisor_rank_disagreement"].current_status == "diagnostic_only"
