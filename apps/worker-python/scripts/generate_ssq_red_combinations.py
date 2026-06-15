from __future__ import annotations

import argparse
import time

from dehps.db import get_connection
from dehps.domain.combination import iter_ssq_red_combinations
from dehps.features.gua_encoder import encode_odd_even_gua, encode_small_big_gua
from dehps.features.pattern_complexity import calculate_pattern_complexity
from dehps.features.red_ball_features import calculate_red_ball_features


def build_row(numbers: tuple[int, ...]) -> tuple:
    features = calculate_red_ball_features(numbers)
    complexity = calculate_pattern_complexity(numbers)
    return (
        list(numbers),
        *numbers,
        features["sum_value"],
        features["span_value"],
        features["odd_count"],
        features["even_count"],
        features["small_count"],
        features["big_count"],
        features["zone_1_count"],
        features["zone_2_count"],
        features["zone_3_count"],
        features["consecutive_pair_count"],
        features["max_consecutive_run"],
        features["min_gap"],
        features["max_gap"],
        features["is_arithmetic_sequence"],
        encode_odd_even_gua(numbers),
        encode_small_big_gua(numbers),
        complexity["pattern_complexity_score"],
        complexity["anomaly_penalty"],
        complexity["structure_naturalness_score"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()

    started = time.time()
    inserted = 0
    skipped = 0
    sql = """
    INSERT INTO ssq_red_combinations (
      numbers, n1, n2, n3, n4, n5, n6, sum_value, span_value, odd_count, even_count,
      small_count, big_count, zone_1_count, zone_2_count, zone_3_count,
      consecutive_pair_count, max_consecutive_run, min_gap, max_gap, is_arithmetic_sequence,
      gua_odd_even, gua_small_big, pattern_complexity_score, anomaly_penalty, structure_naturalness_score
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (numbers) DO NOTHING
    """
    with get_connection() as conn:
        batch = []
        for idx, numbers in enumerate(iter_ssq_red_combinations(), start=1):
            batch.append(build_row(numbers))
            if len(batch) >= args.batch_size:
                with conn.cursor() as cur:
                    cur.executemany(sql, batch)
                    rowcount = cur.rowcount if cur.rowcount > 0 else 0
                inserted += rowcount
                skipped += len(batch) - rowcount
                batch.clear()
            if args.limit and idx >= args.limit:
                break
        if batch:
            with conn.cursor() as cur:
                cur.executemany(sql, batch)
                rowcount = cur.rowcount if cur.rowcount > 0 else 0
            inserted += rowcount
            skipped += len(batch) - rowcount
    print({"inserted": inserted, "skipped": skipped, "elapsed_seconds": round(time.time() - started, 2)})


if __name__ == "__main__":
    main()
