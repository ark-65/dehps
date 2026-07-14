from dehps.pattern_discovery.service import PatternDiscoveryService
from pattern_fixtures import HISTORY


def test_screening_counts_multiplicity_by_family() -> None:
    service = PatternDiscoveryService()
    discovered = service.discover(draws=HISTORY, persist=False)
    screened = service.screen(discovered["patterns"], multiplicity_complete=True)

    ap_results = [
        result for result in screened["results"]
        if result.pattern.multiplicity_family == "arithmetic_progression_len_3"
    ]
    assert ap_results
    assert all(result.significance.multiplicity_count >= len(ap_results) for result in ap_results)
