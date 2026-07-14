from engineering_fixtures import planner


def test_engineering_context_reads_plan_repository_catalogs_code_and_tests() -> None:
    service = planner()
    plan = service.load_plan(None)

    context = service.build_context(plan)

    assert context.plan_key == plan.plan_key
    assert context.plan_fingerprint == plan.plan_fingerprint
    assert context.feature_catalog
    assert context.mechanism_catalog
    assert any(file.path.endswith("frequency_ranker.py") for file in context.code_graph.source_files)
    assert any(path.endswith("test_ranking_disagreement_metrics.py") for path in context.existing_tests)
    assert "FrequencyRankerConfig" in context.current_interfaces
