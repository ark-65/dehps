from dehps.pattern_discovery.models import PatternSearchBudget
from dehps.pattern_discovery.service import PatternDiscoveryService
from pattern_fixtures import HISTORY


def test_pattern_discovery_stops_at_budget_limit() -> None:
    result = PatternDiscoveryService().discover(
        draws=HISTORY,
        budget=PatternSearchBudget(families=1, patterns_per_family=1),
        persist=False,
    )

    assert len(result["patterns"]) == 1
    assert result["stopped_by_budget"] is True
    assert result["validation"].valid
