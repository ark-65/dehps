from dehps.features.pattern_complexity import calculate_pattern_complexity


def test_simple_pattern_has_penalty():
    simple = calculate_pattern_complexity([1, 2, 3, 4, 5, 6])
    natural = calculate_pattern_complexity([3, 8, 14, 19, 25, 33])
    assert simple["anomaly_penalty"] > natural["anomaly_penalty"]
    assert simple["structure_naturalness_score"] < natural["structure_naturalness_score"]

