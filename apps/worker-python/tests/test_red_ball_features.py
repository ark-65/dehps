from dehps.features.red_ball_features import calculate_red_ball_features


def test_red_ball_features_for_full_run():
    assert calculate_red_ball_features([1, 2, 3, 4, 5, 6]) == {
        "sum_value": 21,
        "span_value": 5,
        "odd_count": 3,
        "even_count": 3,
        "small_count": 6,
        "big_count": 0,
        "zone_1_count": 6,
        "zone_2_count": 0,
        "zone_3_count": 0,
        "consecutive_pair_count": 5,
        "max_consecutive_run": 6,
        "min_gap": 1,
        "max_gap": 1,
        "is_arithmetic_sequence": True,
    }

