from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternFamilySpec:
    family_key: str
    pattern_type: str
    title: str
    description: str
    formula_schema: dict[str, object]
    nulls: tuple[str, ...]
    max_parameters: int = 8


def _spec(family: str, pattern_type: str, title: str, *, nulls: tuple[str, ...]) -> PatternFamilySpec:
    return PatternFamilySpec(
        family_key=family,
        pattern_type=pattern_type,
        title=title,
        description=f"{title} pattern over SSQ red-ball combinations.",
        formula_schema={
            "operator": pattern_type,
            "inputs": ["red_numbers"],
            "parameters": "bounded JSON object",
            "output": "count|ratio|score",
        },
        nulls=nulls,
    )


PATTERN_FAMILY_SPECS: tuple[PatternFamilySpec, ...] = (
    _spec("arithmetic_spacing", "arithmetic_progression_len_6", "Full six-term arithmetic progression", nulls=("legal_universe", "random_history_permutation")),
    _spec("arithmetic_spacing", "arithmetic_progression_len_5", "Five-term arithmetic progression subsequence", nulls=("legal_universe", "same_sum", "same_span")),
    _spec("arithmetic_spacing", "arithmetic_progression_len_4", "Four-term arithmetic progression subsequence", nulls=("legal_universe", "same_sum", "same_odd_even")),
    _spec("arithmetic_spacing", "arithmetic_progression_len_3", "Three-term arithmetic progression subsequence", nulls=("legal_universe", "same_span", "same_odd_even")),
    _spec("arithmetic_spacing", "gap_vector", "Sorted gap vector", nulls=("legal_universe", "same_sum")),
    _spec("arithmetic_spacing", "minimum_gap", "Minimum adjacent gap", nulls=("legal_universe",)),
    _spec("arithmetic_spacing", "maximum_gap", "Maximum adjacent gap", nulls=("legal_universe",)),
    _spec("consecutive", "consecutive_pair_count", "Consecutive pair count", nulls=("legal_universe", "same_sum")),
    _spec("consecutive", "consecutive_run_length", "Longest consecutive run", nulls=("legal_universe",)),
    _spec("consecutive", "edge_consecutive", "Edge-near consecutive number", nulls=("legal_universe",)),
    _spec("odd_even", "odd_even_ratio", "Odd/even ratio", nulls=("legal_universe",)),
    _spec("odd_even", "odd_even_alternation", "Odd/even alternation", nulls=("legal_universe",)),
    _spec("sum_span", "sum_bucket", "Sum bucket", nulls=("legal_universe", "same_span")),
    _spec("sum_span", "span_bucket", "Span bucket", nulls=("legal_universe", "same_sum")),
    _spec("sum_span", "center_of_mass", "Combination center of mass", nulls=("legal_universe",)),
    _spec("tail_mod", "tail_digit_histogram", "Tail digit histogram", nulls=("legal_universe",)),
    _spec("tail_mod", "mod_3_residue", "Modulo-3 residue profile", nulls=("legal_universe", "same_odd_even")),
    _spec("tail_mod", "mod_5_residue", "Modulo-5 residue profile", nulls=("legal_universe",)),
    _spec("tail_mod", "mod_7_residue", "Modulo-7 residue profile", nulls=("legal_universe",)),
    _spec("prime_number_theory", "prime_count", "Prime count", nulls=("legal_universe", "same_sum")),
    _spec("prime_number_theory", "square_number_count", "Square number count", nulls=("legal_universe",)),
    _spec("prime_number_theory", "fibonacci_number_count", "Fibonacci-number count", nulls=("legal_universe",)),
    _spec("zone", "low_mid_high_zone", "Low/mid/high zone allocation", nulls=("legal_universe", "same_sum")),
    _spec("zone", "third_zone_entropy", "Third-zone entropy", nulls=("legal_universe",)),
    _spec("zone", "edge_center_balance", "Edge-center balance", nulls=("legal_universe",)),
    _spec("cooccurrence_graph", "pair_cooccurrence_lift", "Pair co-occurrence lift", nulls=("random_history_permutation",)),
    _spec("cooccurrence_graph", "triple_cooccurrence_lift", "Triple co-occurrence lift", nulls=("random_history_permutation",)),
    _spec("cooccurrence_graph", "graph_degree_cluster", "Co-occurrence graph degree cluster", nulls=("random_history_permutation",)),
    _spec("temporal_omission", "omission_age_bucket", "Omission age bucket", nulls=("random_history_permutation",)),
    _spec("temporal_omission", "recency_decay_score", "Recency decay score", nulls=("random_history_permutation",)),
    _spec("temporal_omission", "draw_interval_pattern", "Draw interval pattern", nulls=("random_history_permutation",)),
    _spec("residual_model", "baseline_rank_residual", "Baseline rank residual", nulls=("sequential_null", "random_history_permutation")),
    _spec("residual_model", "tail_risk_residual", "Tail-risk residual", nulls=("sequential_null",)),
    _spec("residual_model", "line_overlap_residual", "Line-overlap residual", nulls=("sequential_null",)),
    _spec("structural", "mirror_pair_count", "Mirror pair count", nulls=("legal_universe",)),
    _spec("structural", "decade_coverage", "Decade coverage", nulls=("legal_universe",)),
)


class PatternCatalog:
    def __init__(self, specs: tuple[PatternFamilySpec, ...] = PATTERN_FAMILY_SPECS) -> None:
        self.specs = specs

    def list_specs(self) -> tuple[PatternFamilySpec, ...]:
        return self.specs

    def by_type(self, pattern_type: str) -> PatternFamilySpec:
        for spec in self.specs:
            if spec.pattern_type == pattern_type:
                return spec
        raise KeyError(f"unknown pattern type: {pattern_type}")

    def families(self) -> tuple[str, ...]:
        return tuple(sorted({spec.family_key for spec in self.specs}))

    def validate_minimum_coverage(self, minimum: int = 30) -> bool:
        return len({spec.pattern_type for spec in self.specs}) >= minimum


DEFAULT_PATTERN_CATALOG = PatternCatalog()
