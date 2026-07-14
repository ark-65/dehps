from dehps.pattern_discovery.catalog import DEFAULT_PATTERN_CATALOG


def test_pattern_catalog_has_required_machine_readable_coverage() -> None:
    specs = DEFAULT_PATTERN_CATALOG.list_specs()

    assert DEFAULT_PATTERN_CATALOG.validate_minimum_coverage(30)
    assert len({spec.pattern_type for spec in specs}) >= 30
    assert {"arithmetic_spacing", "cooccurrence_graph", "residual_model"}.issubset(
        set(DEFAULT_PATTERN_CATALOG.families())
    )
