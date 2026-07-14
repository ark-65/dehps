from dehps.pattern_discovery.arithmetic import ArithmeticProgressionExtractor, ap_subsequences


def test_arithmetic_progression_extractor_detects_lengths_and_difference() -> None:
    signatures = set(ap_subsequences((3, 6, 9, 12, 15, 18)))

    assert (6, 3, 3) in signatures
    assert (5, 3, 3) in signatures
    assert (4, 6, 3) in signatures
    assert (3, 12, 3) in signatures


def test_arithmetic_progression_extractor_emits_pattern_candidates() -> None:
    patterns = ArithmeticProgressionExtractor().extract_draw_patterns(
        [("001", (1, 2, 3, 10, 20, 30)), ("002", (2, 4, 6, 8, 10, 12))],
        max_patterns=100,
    )
    parameters = {tuple(pattern.parameters[key] for key in ("length", "start", "difference")) for pattern in patterns}

    assert (3, 1, 1) in parameters
    assert (6, 2, 2) in parameters
    assert all(pattern.search_issue_range for pattern in patterns)
