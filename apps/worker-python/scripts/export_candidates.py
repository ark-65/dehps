from __future__ import annotations

import argparse
import csv
from pathlib import Path

from dehps.config import ROOT_DIR
from dehps.domain.combination import iter_ssq_red_combinations
from dehps.scoring.strategy import keep_by_baseline, score_numbers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", default=str(ROOT_DIR / "data/output/baseline_candidates.csv"))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["numbers", "score", "anomaly_penalty"])
        for numbers in iter_ssq_red_combinations():
            if keep_by_baseline(numbers):
                scored = score_numbers(numbers)
                writer.writerow([" ".join(map(str, numbers)), scored["score"], scored["anomaly_penalty"]])
                count += 1
                if count >= args.limit:
                    break
    print({"exported": count, "output": str(output)})


if __name__ == "__main__":
    main()

