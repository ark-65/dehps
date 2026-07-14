from dehps.pattern_discovery.novelty import PatternNoveltyDetector
from pattern_fixtures import ap_candidate


def test_pattern_novelty_detects_formula_duplicate_and_rejected_family_retry() -> None:
    candidate = ap_candidate()
    report = PatternNoveltyDetector().evaluate(
        candidate,
        [
            {
                "pattern_key": "existing",
                "pattern_family": candidate.pattern_family,
                "formula_hash": candidate.formula_hash,
                "parameters": candidate.parameters,
                "lifecycle_status": "frozen_rejected",
            }
        ],
        rejected_family_keys=[candidate.pattern_family],
    )

    assert report.is_novel is False
    assert "existing" in report.duplicate_pattern_keys
    assert "existing" in report.rejected_family_near_retries


def test_pattern_novelty_ignores_the_same_persisted_pattern_key() -> None:
    candidate = ap_candidate()
    report = PatternNoveltyDetector().evaluate(
        candidate,
        [
            {
                "pattern_key": candidate.pattern_key,
                "pattern_family": candidate.pattern_family,
                "formula_hash": candidate.formula_hash,
                "parameters": candidate.parameters,
                "lifecycle_status": "discovered",
            }
        ],
    )

    assert report.is_novel is True
    assert report.duplicate_pattern_keys == ()
