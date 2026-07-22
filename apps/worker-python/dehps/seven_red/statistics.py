from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from fractions import Fraction
from hashlib import sha256
from math import comb
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.seven_red.domain import LINE_KEY, RESEARCH_ONLY
from dehps.seven_red.inner_selection import SevenRedStrategyKind
from dehps.seven_red.random_control import RandomControlKind
from dehps.seven_red.walk_forward import (
    SEVEN_RED_WALK_FORWARD_CONTRACT_V1,
    SevenRedOuterArmKind,
    SevenRedWalkForwardSnapshot,
    SevenRedWalkForwardVerifier,
)


SEVEN_RED_STATISTICAL_PROTOCOL_VERSION = "seven_red_statistical_protocol.v1"
SEVEN_RED_PAIRED_COMPARISON_VERSION = "seven_red_paired_comparison.v1"
SEVEN_RED_STATISTICAL_SNAPSHOT_VERSION = "seven_red_statistical_snapshot.v1"
EXACT_SIGN_TEST = "exact_one_sided_greater_sign_test.v1"
HOLM_MULTIPLICITY = "holm_bonferroni_all_six_confirmatory.v1"
ALL_SEED_RANDOM_MEAN = "within_target_arithmetic_mean_all_protocol_seeds.v1"
CIRCULAR_BLOCK_BOOTSTRAP = "sha256_circular_moving_block_mean.v1"
NEAREST_RANK_PERCENTILE = "two_sided_nearest_rank_percentile.v1"
MINIMUM_BOOTSTRAP_RESAMPLES = 1_000
UINT64_SPACE = 1 << 64
BOOTSTRAP_WORD_DOMAIN = b"dehps.seven-red.bootstrap-start.v1\x00"


class SevenRedEndpoint(str, Enum):
    BEST_UNIQUE_MATCHED_RED = "best_unique_matched_red_count"
    EXACT_RED6_COVERAGE = "exact_red6_coverage"
    RED5_OR_BETTER_COVERAGE = "red5_or_better_coverage"
    UNIQUE_RED5_TICKET_COUNT = "unique_red5_ticket_count"
    SLOT_EXACT_RED6_COUNT = "slot_exact_red6_count"
    UNIQUE_TICKET_COUNT = "unique_ticket_count"
    DUPLICATE_SLOT_COUNT = "duplicate_slot_count"


class SevenRedComparisonId(str, Enum):
    RAW_VS_SIX_RED_TOP70 = "raw_vs_six_red_top70"
    RAW_VS_MATCHED_RANDOM_POOL = "raw_vs_matched_random_pool"
    RAW_VS_MATCHED_UNIFORM_LEGAL = "raw_vs_matched_uniform_legal"
    DIVERSIFIED_VS_SIX_RED_TOP70 = "diversified_vs_six_red_top70"
    DIVERSIFIED_VS_MATCHED_RANDOM_POOL = "diversified_vs_matched_random_pool"
    DIVERSIFIED_VS_MATCHED_UNIFORM_LEGAL = (
        "diversified_vs_matched_uniform_legal"
    )


CONFIRMATORY_COMPARISONS = tuple(SevenRedComparisonId)
DESCRIPTIVE_ENDPOINTS = tuple(SevenRedEndpoint)


SEVEN_RED_STATISTICAL_NORMATIVE_DEFINITION = {
    "contract": "seven-red-statistical-comparison.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependency": SEVEN_RED_WALK_FORWARD_CONTRACT_V1.normative_identity(),
    "confirmatory": {
        "endpoint": SevenRedEndpoint.BEST_UNIQUE_MATCHED_RED.value,
        "comparisons": [comparison.value for comparison in CONFIRMATORY_COMPARISONS],
        "sample_unit": "outer_target_issue",
        "alternative": "strategy_greater_than_comparator",
        "test": EXACT_SIGN_TEST,
        "multiplicity": HOLM_MULTIPLICITY,
    },
    "random_comparator": {
        "aggregation": ALL_SEED_RANDOM_MEAN,
        "order": "within_target_before_paired_test",
        "seed_as_independent_sample": False,
        "best_seed": None,
    },
    "dependence_sensitivity": {
        "interval": CIRCULAR_BLOCK_BOOTSTRAP,
        "percentile": NEAREST_RANK_PERCENTILE,
        "estimator": "mean_paired_difference",
        "overrides_exact_sign_test": False,
    },
    "arithmetic": "exact_Fraction_until_decimal_presentation",
    "output": {
        "numerical_evidence": True,
        "boolean_decision": None,
        "winner": None,
        "hypothesis_status": None,
        "production_action": None,
    },
    "non_goals": [
        "no_historical_execution_or_data_loading",
        "no_seed_pseudoreplication",
        "no_uncorrected_confirmatory_conclusion",
        "no_engineering_research_decision",
        "no_betting_or_production_action",
    ],
}

SEVEN_RED_STATISTICAL_GOLDEN_SUITE = {
    "suite": "seven_red_statistical_comparison_golden.v1",
    "sign_test": {
        "wins": 3,
        "losses": 1,
        "ties": 2,
        "one_sided_p": {"numerator": 5, "denominator": 16},
    },
    "holm_raw_p": ["1/100", "1/50", "1/25", "1/10", "1/5", "1/2"],
    "stochastic": False,
}

SEVEN_RED_STATISTICAL_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-statistical-comparison",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-statistical-comparison.schema.v1",
    normative_definition=SEVEN_RED_STATISTICAL_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_STATISTICAL_GOLDEN_SUITE,
)


class SevenRedStatisticalViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedStatisticalViolation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "seven_red_statistical_digest_invalid",
            f"{field_name} must be a lowercase sha256 digest",
            field=field_name,
        )
    return value


def _require_fraction(value: object, *, field_name: str) -> Fraction:
    if type(value) is not Fraction:
        _reject(
            "seven_red_statistical_fraction_invalid",
            f"{field_name} must use the exact Fraction representation",
            field=field_name,
        )
    return value


def fraction_payload(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_sequence_payload(values: tuple[Fraction, ...]) -> list[dict[str, int]]:
    return [fraction_payload(value) for value in values]


@dataclass(frozen=True)
class SevenRedStatisticalProtocol:
    walk_forward_protocol_digest: str
    confirmatory_endpoint: SevenRedEndpoint
    confirmatory_comparisons: tuple[SevenRedComparisonId, ...]
    alternative: str
    sign_test_contract: str
    alpha: Fraction
    minimum_effect: Fraction
    multiplicity_contract: str
    random_aggregation_contract: str
    confidence_level: Fraction
    bootstrap_block_length: int
    bootstrap_resample_count: int
    bootstrap_seed_digest: str
    bootstrap_contract: str
    percentile_contract: str
    protocol_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(
            self.walk_forward_protocol_digest,
            field_name="walk_forward_protocol_digest",
        )
        if self.confirmatory_endpoint is not SevenRedEndpoint.BEST_UNIQUE_MATCHED_RED:
            _reject(
                "seven_red_statistical_endpoint_invalid",
                "confirmatory endpoint is not the frozen best-unique-match endpoint",
            )
        if self.confirmatory_comparisons != CONFIRMATORY_COMPARISONS:
            _reject(
                "seven_red_statistical_comparison_family_invalid",
                "confirmatory comparison family or order is invalid",
            )
        if self.alternative != "greater":
            _reject(
                "seven_red_statistical_alternative_invalid",
                "confirmatory alternative must be one-sided greater",
            )
        if self.sign_test_contract != EXACT_SIGN_TEST:
            _reject("seven_red_statistical_sign_test_invalid", "sign-test contract is invalid")
        alpha = _require_fraction(self.alpha, field_name="alpha")
        minimum_effect = _require_fraction(
            self.minimum_effect, field_name="minimum_effect"
        )
        confidence = _require_fraction(
            self.confidence_level, field_name="confidence_level"
        )
        if not 0 < alpha < 1:
            _reject("seven_red_statistical_alpha_invalid", "alpha must be in (0,1)")
        if minimum_effect < 0:
            _reject(
                "seven_red_statistical_minimum_effect_invalid",
                "minimum effect must be non-negative",
            )
        if not Fraction(1, 2) < confidence < 1:
            _reject(
                "seven_red_statistical_confidence_invalid",
                "confidence level must be in (1/2,1)",
            )
        if self.multiplicity_contract != HOLM_MULTIPLICITY:
            _reject("seven_red_statistical_multiplicity_invalid", "multiplicity contract is invalid")
        if self.random_aggregation_contract != ALL_SEED_RANDOM_MEAN:
            _reject(
                "seven_red_statistical_random_aggregation_invalid",
                "random aggregation contract is invalid",
            )
        if (
            not isinstance(self.bootstrap_block_length, int)
            or isinstance(self.bootstrap_block_length, bool)
            or self.bootstrap_block_length < 2
        ):
            _reject(
                "seven_red_statistical_block_length_invalid",
                "bootstrap block length must be an explicit integer of at least two",
            )
        if (
            not isinstance(self.bootstrap_resample_count, int)
            or isinstance(self.bootstrap_resample_count, bool)
            or self.bootstrap_resample_count < MINIMUM_BOOTSTRAP_RESAMPLES
        ):
            _reject(
                "seven_red_statistical_resample_count_invalid",
                "bootstrap requires at least 1000 explicit resamples",
            )
        _require_digest(self.bootstrap_seed_digest, field_name="bootstrap_seed_digest")
        if self.bootstrap_contract != CIRCULAR_BLOCK_BOOTSTRAP:
            _reject("seven_red_statistical_bootstrap_invalid", "bootstrap contract is invalid")
        if self.percentile_contract != NEAREST_RANK_PERCENTILE:
            _reject("seven_red_statistical_percentile_invalid", "percentile contract is invalid")
        object.__setattr__(
            self,
            "protocol_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.statistical-protocol.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_STATISTICAL_PROTOCOL_VERSION,
            "walk_forward_protocol_digest": self.walk_forward_protocol_digest,
            "confirmatory_endpoint": self.confirmatory_endpoint.value,
            "confirmatory_comparisons": [
                comparison.value for comparison in self.confirmatory_comparisons
            ],
            "alternative": self.alternative,
            "sign_test_contract": self.sign_test_contract,
            "alpha": fraction_payload(self.alpha),
            "minimum_effect": fraction_payload(self.minimum_effect),
            "multiplicity_contract": self.multiplicity_contract,
            "random_aggregation_contract": self.random_aggregation_contract,
            "confidence_level": fraction_payload(self.confidence_level),
            "bootstrap_block_length": self.bootstrap_block_length,
            "bootstrap_resample_count": self.bootstrap_resample_count,
            "bootstrap_seed_digest": self.bootstrap_seed_digest,
            "bootstrap_contract": self.bootstrap_contract,
            "percentile_contract": self.percentile_contract,
            "boolean_decision": None,
            "default_policy": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "protocol_digest": self.protocol_digest}


@dataclass(frozen=True)
class SevenRedDescriptiveEndpointRow:
    target_issue: str
    source_key: str
    seed_digest: str | None
    endpoint_values: tuple[Fraction, ...]
    row_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target_issue, str)
            or len(self.target_issue) != 7
            or not self.target_issue.isdigit()
        ):
            _reject("seven_red_statistical_target_invalid", "target issue is invalid")
        if not isinstance(self.source_key, str) or not self.source_key:
            _reject("seven_red_statistical_source_key_invalid", "source key is invalid")
        if self.seed_digest is not None:
            _require_digest(self.seed_digest, field_name="seed_digest")
        if (
            not isinstance(self.endpoint_values, tuple)
            or len(self.endpoint_values) != len(DESCRIPTIVE_ENDPOINTS)
        ):
            _reject(
                "seven_red_statistical_endpoint_vector_invalid",
                "descriptive endpoint vector is invalid",
            )
        for value in self.endpoint_values:
            _require_fraction(value, field_name="endpoint_value")
            if value < 0:
                _reject(
                    "seven_red_statistical_endpoint_value_invalid",
                    "endpoint values must be non-negative",
                )
        object.__setattr__(
            self,
            "row_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.descriptive-endpoint-row.v1",
            ),
        )

    def value(self, endpoint: SevenRedEndpoint) -> Fraction:
        return self.endpoint_values[DESCRIPTIVE_ENDPOINTS.index(endpoint)]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "target_issue": self.target_issue,
            "source_key": self.source_key,
            "seed_digest": self.seed_digest,
            "endpoints": {
                endpoint.value: fraction_payload(value)
                for endpoint, value in zip(
                    DESCRIPTIVE_ENDPOINTS, self.endpoint_values, strict=True
                )
            },
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "row_digest": self.row_digest}


@dataclass(frozen=True)
class SevenRedPairedComparison:
    comparison_id: SevenRedComparisonId
    protocol_digest: str
    target_issues: tuple[str, ...]
    strategy_values: tuple[Fraction, ...]
    comparator_values: tuple[Fraction, ...]
    paired_differences: tuple[Fraction, ...]
    random_seed_row_digests: tuple[str, ...]
    win_count: int
    loss_count: int
    tie_count: int
    mean_difference: Fraction
    raw_sign_test_p_value: Fraction
    holm_adjusted_p_value: Fraction
    bootstrap_interval_lower: Fraction
    bootstrap_interval_upper: Fraction
    bootstrap_distribution_digest: str
    comparison_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.comparison_id, SevenRedComparisonId):
            _reject("seven_red_statistical_comparison_id_invalid", "comparison id is invalid")
        _require_digest(self.protocol_digest, field_name="protocol_digest")
        count = len(self.target_issues)
        if count < 1 or any(
            len(values) != count
            for values in (
                self.strategy_values,
                self.comparator_values,
                self.paired_differences,
            )
        ):
            _reject(
                "seven_red_statistical_pairing_invalid",
                "paired target/value vectors have inconsistent lengths",
            )
        if tuple(sorted(set(self.target_issues), key=int)) != self.target_issues:
            _reject(
                "seven_red_statistical_target_order_invalid",
                "paired targets must be unique and increasing",
            )
        for values in (
            self.strategy_values,
            self.comparator_values,
            self.paired_differences,
        ):
            for value in values:
                _require_fraction(value, field_name="paired_value")
        expected_differences = tuple(
            strategy - comparator
            for strategy, comparator in zip(
                self.strategy_values, self.comparator_values, strict=True
            )
        )
        if self.paired_differences != expected_differences:
            _reject(
                "seven_red_statistical_difference_mismatch",
                "paired differences do not match strategy minus comparator",
            )
        expected_counts = (
            sum(value > 0 for value in self.paired_differences),
            sum(value < 0 for value in self.paired_differences),
            sum(value == 0 for value in self.paired_differences),
        )
        if (self.win_count, self.loss_count, self.tie_count) != expected_counts:
            _reject("seven_red_statistical_sign_counts_mismatch", "sign counts are invalid")
        expected_mean = sum(self.paired_differences, start=Fraction(0)) / count
        if self.mean_difference != expected_mean:
            _reject("seven_red_statistical_mean_mismatch", "mean difference is invalid")
        expected_p = exact_greater_sign_test_p(self.win_count, self.loss_count)
        if self.raw_sign_test_p_value != expected_p:
            _reject("seven_red_statistical_sign_p_mismatch", "sign-test p-value is invalid")
        for field_name in (
            "mean_difference",
            "raw_sign_test_p_value",
            "holm_adjusted_p_value",
            "bootstrap_interval_lower",
            "bootstrap_interval_upper",
        ):
            _require_fraction(getattr(self, field_name), field_name=field_name)
        if not self.raw_sign_test_p_value <= self.holm_adjusted_p_value <= 1:
            _reject(
                "seven_red_statistical_holm_value_invalid",
                "Holm adjusted p-value must be between raw p and one",
            )
        if self.bootstrap_interval_lower > self.bootstrap_interval_upper:
            _reject(
                "seven_red_statistical_interval_invalid",
                "bootstrap interval bounds are reversed",
            )
        for digest in self.random_seed_row_digests:
            _require_digest(digest, field_name="random_seed_row_digest")
        _require_digest(
            self.bootstrap_distribution_digest,
            field_name="bootstrap_distribution_digest",
        )
        object.__setattr__(
            self,
            "comparison_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.paired-comparison.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_PAIRED_COMPARISON_VERSION,
            "comparison_id": self.comparison_id.value,
            "protocol_digest": self.protocol_digest,
            "target_issues": list(self.target_issues),
            "strategy_values": _fraction_sequence_payload(self.strategy_values),
            "comparator_values": _fraction_sequence_payload(self.comparator_values),
            "paired_differences": _fraction_sequence_payload(self.paired_differences),
            "random_seed_row_digests": list(self.random_seed_row_digests),
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "tie_count": self.tie_count,
            "mean_difference": fraction_payload(self.mean_difference),
            "raw_sign_test_p_value": fraction_payload(self.raw_sign_test_p_value),
            "holm_adjusted_p_value": fraction_payload(self.holm_adjusted_p_value),
            "bootstrap_interval_lower": fraction_payload(
                self.bootstrap_interval_lower
            ),
            "bootstrap_interval_upper": fraction_payload(
                self.bootstrap_interval_upper
            ),
            "bootstrap_distribution_digest": self.bootstrap_distribution_digest,
            "boolean_decision": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "comparison_digest": self.comparison_digest}


def exact_greater_sign_test_p(win_count: int, loss_count: int) -> Fraction:
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (win_count, loss_count)
    ):
        _reject("seven_red_statistical_sign_count_invalid", "sign counts are invalid")
    discordant = win_count + loss_count
    if discordant == 0:
        return Fraction(1)
    return Fraction(
        sum(comb(discordant, successes) for successes in range(win_count, discordant + 1)),
        1 << discordant,
    )


def holm_adjusted_p_values(
    raw_values: dict[SevenRedComparisonId, Fraction],
) -> dict[SevenRedComparisonId, Fraction]:
    if tuple(sorted(raw_values, key=lambda item: item.value)) != tuple(
        sorted(CONFIRMATORY_COMPARISONS, key=lambda item: item.value)
    ):
        _reject(
            "seven_red_statistical_holm_family_invalid",
            "Holm input must contain exactly the six confirmatory comparisons",
        )
    for value in raw_values.values():
        _require_fraction(value, field_name="raw_p_value")
        if not 0 <= value <= 1:
            _reject("seven_red_statistical_raw_p_invalid", "raw p-value is outside [0,1]")
    ordered = sorted(raw_values.items(), key=lambda item: (item[1], item[0].value))
    adjusted: dict[SevenRedComparisonId, Fraction] = {}
    running = Fraction(0)
    family_size = len(ordered)
    for index, (comparison, raw_p) in enumerate(ordered):
        candidate = min(Fraction(1), (family_size - index) * raw_p)
        running = max(running, candidate)
        adjusted[comparison] = running
    return adjusted


def _best_match(histogram: tuple[int, ...]) -> int:
    return max(index for index, count in enumerate(histogram) if count)


def _endpoint_vector(
    slot_histogram: tuple[int, ...],
    unique_histogram: tuple[int, ...],
    unique_ticket_count: int,
    duplicate_slot_count: int,
) -> tuple[Fraction, ...]:
    values = {
        SevenRedEndpoint.BEST_UNIQUE_MATCHED_RED: _best_match(unique_histogram),
        SevenRedEndpoint.EXACT_RED6_COVERAGE: int(unique_histogram[6] > 0),
        SevenRedEndpoint.RED5_OR_BETTER_COVERAGE: int(
            unique_histogram[5] + unique_histogram[6] > 0
        ),
        SevenRedEndpoint.UNIQUE_RED5_TICKET_COUNT: unique_histogram[5],
        SevenRedEndpoint.SLOT_EXACT_RED6_COUNT: slot_histogram[6],
        SevenRedEndpoint.UNIQUE_TICKET_COUNT: unique_ticket_count,
        SevenRedEndpoint.DUPLICATE_SLOT_COUNT: duplicate_slot_count,
    }
    return tuple(Fraction(values[endpoint]) for endpoint in DESCRIPTIVE_ENDPOINTS)


def _descriptive_rows(
    snapshot: SevenRedWalkForwardSnapshot,
) -> tuple[SevenRedDescriptiveEndpointRow, ...]:
    rows: list[SevenRedDescriptiveEndpointRow] = []
    for trial in snapshot.trials:
        for arm in trial.strategy_arms:
            rows.append(
                SevenRedDescriptiveEndpointRow(
                    target_issue=trial.target_issue,
                    source_key=arm.arm_kind.value,
                    seed_digest=None,
                    endpoint_values=_endpoint_vector(
                        arm.slot_hit_histogram,
                        arm.unique_ticket_hit_histogram,
                        arm.unique_ticket_count,
                        arm.duplicate_slot_count,
                    ),
                )
            )
        for matched in trial.matched_random_evidence:
            for random_row in matched.rows:
                rows.append(
                    SevenRedDescriptiveEndpointRow(
                        target_issue=trial.target_issue,
                        source_key=(
                            f"{matched.matched_family.value}:"
                            f"{random_row.control_kind.value}"
                        ),
                        seed_digest=random_row.seed_digest,
                        endpoint_values=_endpoint_vector(
                            random_row.slot_hit_histogram,
                            random_row.unique_ticket_hit_histogram,
                            random_row.unique_ticket_count,
                            random_row.duplicate_slot_count,
                        ),
                    )
                )
    return tuple(rows)


def _comparison_sources(
    comparison: SevenRedComparisonId,
) -> tuple[str, str, bool]:
    if comparison.value.startswith("raw_"):
        strategy = SevenRedOuterArmKind.RAW_TOP10.value
        family = SevenRedStrategyKind.RAW.value
    else:
        strategy = SevenRedOuterArmKind.DIVERSIFIED_TOP10.value
        family = SevenRedStrategyKind.DIVERSIFIED.value
    if comparison.value.endswith("six_red_top70"):
        return strategy, SevenRedOuterArmKind.SIX_RED_TOP70.value, False
    if comparison.value.endswith("random_pool"):
        return strategy, f"{family}:{RandomControlKind.RANDOM_FROM_POOL.value}", True
    return strategy, f"{family}:{RandomControlKind.UNIFORM_LEGAL.value}", True


def _bootstrap_start(
    *,
    protocol: SevenRedStatisticalProtocol,
    comparison: SevenRedComparisonId,
    resample_index: int,
    block_index: int,
    target_count: int,
) -> int:
    limit = (UINT64_SPACE // target_count) * target_count
    attempt = 0
    while True:
        payload = b"".join(
            (
                BOOTSTRAP_WORD_DOMAIN,
                bytes.fromhex(protocol.bootstrap_seed_digest),
                b"\x00",
                comparison.value.encode("ascii"),
                b"\x00",
                resample_index.to_bytes(8, "big"),
                block_index.to_bytes(8, "big"),
                attempt.to_bytes(8, "big"),
            )
        )
        word = int.from_bytes(sha256(payload).digest()[:8], "big")
        if word < limit:
            return word % target_count
        attempt += 1


def circular_block_bootstrap_interval(
    differences: tuple[Fraction, ...],
    *,
    protocol: SevenRedStatisticalProtocol,
    comparison: SevenRedComparisonId,
) -> tuple[Fraction, Fraction, str]:
    target_count = len(differences)
    if target_count < 1 or protocol.bootstrap_block_length > target_count:
        _reject(
            "seven_red_statistical_block_length_invalid",
            "bootstrap block length exceeds the paired target count",
        )
    block_count = (
        target_count + protocol.bootstrap_block_length - 1
    ) // protocol.bootstrap_block_length
    means: list[Fraction] = []
    for resample_index in range(protocol.bootstrap_resample_count):
        sample: list[Fraction] = []
        for block_index in range(block_count):
            start = _bootstrap_start(
                protocol=protocol,
                comparison=comparison,
                resample_index=resample_index,
                block_index=block_index,
                target_count=target_count,
            )
            sample.extend(
                differences[(start + offset) % target_count]
                for offset in range(protocol.bootstrap_block_length)
            )
        means.append(sum(sample[:target_count], start=Fraction(0)) / target_count)
    ordered = tuple(sorted(means))
    tail = (Fraction(1) - protocol.confidence_level) / 2
    lower_rank = max(1, _ceil_fraction(tail * len(ordered)))
    upper_rank = min(
        len(ordered), _ceil_fraction((Fraction(1) - tail) * len(ordered))
    )
    distribution_digest = canonical_digest(
        {
            "comparison_id": comparison.value,
            "ordered_means": _fraction_sequence_payload(ordered),
            "block_length": protocol.bootstrap_block_length,
            "resample_count": protocol.bootstrap_resample_count,
            "seed_digest": protocol.bootstrap_seed_digest,
        },
        domain="dehps.seven-red.bootstrap-distribution.v1",
    )
    return ordered[lower_rank - 1], ordered[upper_rank - 1], distribution_digest


def _ceil_fraction(value: Fraction) -> int:
    return (value.numerator + value.denominator - 1) // value.denominator


def _unadjusted_comparison(
    *,
    comparison: SevenRedComparisonId,
    protocol: SevenRedStatisticalProtocol,
    target_issues: tuple[str, ...],
    rows_by_key: dict[tuple[str, str, str | None], SevenRedDescriptiveEndpointRow],
    seed_digests: tuple[str, ...],
) -> SevenRedPairedComparison:
    strategy_key, comparator_key, is_random = _comparison_sources(comparison)
    strategy_values: list[Fraction] = []
    comparator_values: list[Fraction] = []
    random_digests: list[str] = []
    endpoint = protocol.confirmatory_endpoint
    for issue in target_issues:
        strategy_values.append(rows_by_key[(issue, strategy_key, None)].value(endpoint))
        if is_random:
            seed_rows = tuple(
                rows_by_key[(issue, comparator_key, seed)] for seed in seed_digests
            )
            comparator_values.append(
                sum((row.value(endpoint) for row in seed_rows), start=Fraction(0))
                / len(seed_rows)
            )
            random_digests.extend(row.row_digest for row in seed_rows)
        else:
            comparator_values.append(
                rows_by_key[(issue, comparator_key, None)].value(endpoint)
            )
    strategy_tuple = tuple(strategy_values)
    comparator_tuple = tuple(comparator_values)
    differences = tuple(
        strategy - comparator
        for strategy, comparator in zip(
            strategy_tuple, comparator_tuple, strict=True
        )
    )
    wins = sum(value > 0 for value in differences)
    losses = sum(value < 0 for value in differences)
    ties = sum(value == 0 for value in differences)
    lower, upper, distribution_digest = circular_block_bootstrap_interval(
        differences,
        protocol=protocol,
        comparison=comparison,
    )
    raw_p = exact_greater_sign_test_p(wins, losses)
    return SevenRedPairedComparison(
        comparison_id=comparison,
        protocol_digest=protocol.protocol_digest,
        target_issues=target_issues,
        strategy_values=strategy_tuple,
        comparator_values=comparator_tuple,
        paired_differences=differences,
        random_seed_row_digests=tuple(random_digests),
        win_count=wins,
        loss_count=losses,
        tie_count=ties,
        mean_difference=sum(differences, start=Fraction(0)) / len(differences),
        raw_sign_test_p_value=raw_p,
        holm_adjusted_p_value=raw_p,
        bootstrap_interval_lower=lower,
        bootstrap_interval_upper=upper,
        bootstrap_distribution_digest=distribution_digest,
    )


@dataclass(frozen=True)
class SevenRedStatisticalSnapshot:
    source_walk_forward: SevenRedWalkForwardSnapshot = field(repr=False)
    protocol: SevenRedStatisticalProtocol
    descriptive_rows: tuple[SevenRedDescriptiveEndpointRow, ...]
    comparisons: tuple[SevenRedPairedComparison, ...]
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_walk_forward, SevenRedWalkForwardSnapshot):
            _reject("seven_red_statistical_source_invalid", "walk-forward source is invalid")
        if not isinstance(self.protocol, SevenRedStatisticalProtocol):
            _reject("seven_red_statistical_protocol_invalid", "statistical protocol is invalid")
        if (
            self.protocol.walk_forward_protocol_digest
            != self.source_walk_forward.protocol.protocol_digest
        ):
            _reject(
                "seven_red_statistical_protocol_binding_invalid",
                "statistical protocol does not bind the walk-forward protocol",
            )
        if tuple(row.comparison_id for row in self.comparisons) != CONFIRMATORY_COMPARISONS:
            _reject(
                "seven_red_statistical_result_family_invalid",
                "result family must contain all six canonical comparisons",
            )
        if any(
            row.protocol_digest != self.protocol.protocol_digest
            or row.target_issues != self.source_walk_forward.protocol.outer_target_issues
            for row in self.comparisons
        ):
            _reject(
                "seven_red_statistical_result_binding_invalid",
                "every comparison must bind the exact protocol and target tuple",
            )
        expected_adjusted = holm_adjusted_p_values(
            {
                row.comparison_id: row.raw_sign_test_p_value
                for row in self.comparisons
            }
        )
        if any(
            row.holm_adjusted_p_value != expected_adjusted[row.comparison_id]
            for row in self.comparisons
        ):
            _reject(
                "seven_red_statistical_holm_replay_mismatch",
                "comparison Holm values do not replay over the complete family",
            )
        expected_rows = _descriptive_rows(self.source_walk_forward)
        if self.descriptive_rows != expected_rows:
            _reject(
                "seven_red_statistical_descriptive_rows_mismatch",
                "descriptive rows do not replay from the walk-forward source",
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.statistical-snapshot.v1",
            ),
        )

    @classmethod
    def compile(
        cls,
        *,
        source_walk_forward: SevenRedWalkForwardSnapshot,
        protocol: SevenRedStatisticalProtocol,
    ) -> SevenRedStatisticalSnapshot:
        if not isinstance(source_walk_forward, SevenRedWalkForwardSnapshot):
            _reject("seven_red_statistical_source_invalid", "walk-forward source is invalid")
        SevenRedWalkForwardVerifier().verify(source_walk_forward)
        if not isinstance(protocol, SevenRedStatisticalProtocol):
            _reject("seven_red_statistical_protocol_invalid", "statistical protocol is invalid")
        if protocol.walk_forward_protocol_digest != source_walk_forward.protocol.protocol_digest:
            _reject(
                "seven_red_statistical_protocol_binding_invalid",
                "statistical protocol does not bind the walk-forward protocol",
            )
        if protocol.bootstrap_block_length > len(source_walk_forward.trials):
            _reject(
                "seven_red_statistical_block_length_invalid",
                "bootstrap block length exceeds target count",
            )
        rows = _descriptive_rows(source_walk_forward)
        rows_by_key = {
            (row.target_issue, row.source_key, row.seed_digest): row for row in rows
        }
        if len(rows_by_key) != len(rows):
            _reject(
                "seven_red_statistical_descriptive_row_duplicate",
                "descriptive source rows contain duplicate keys",
            )
        targets = source_walk_forward.protocol.outer_target_issues
        seeds = source_walk_forward.protocol.seed_policy.seed_digests
        unadjusted = tuple(
            _unadjusted_comparison(
                comparison=comparison,
                protocol=protocol,
                target_issues=targets,
                rows_by_key=rows_by_key,
                seed_digests=seeds,
            )
            for comparison in CONFIRMATORY_COMPARISONS
        )
        adjusted = holm_adjusted_p_values(
            {
                row.comparison_id: row.raw_sign_test_p_value
                for row in unadjusted
            }
        )
        comparisons = tuple(
            replace(row, holm_adjusted_p_value=adjusted[row.comparison_id])
            for row in unadjusted
        )
        return cls(
            source_walk_forward=source_walk_forward,
            protocol=protocol,
            descriptive_rows=rows,
            comparisons=comparisons,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_STATISTICAL_SNAPSHOT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_STATISTICAL_CONTRACT_V1.normative_identity(),
            "source_walk_forward_snapshot_digest": self.source_walk_forward.snapshot_digest,
            "protocol": self.protocol.as_dict(),
            "descriptive_rows": [row.as_dict() for row in self.descriptive_rows],
            "comparisons": [row.as_dict() for row in self.comparisons],
            "boolean_decision": None,
            "winner": None,
            "hypothesis_status": None,
            "evidence_mutation": None,
            "production_action": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}


class SevenRedStatisticalVerifier:
    def verify(self, snapshot: SevenRedStatisticalSnapshot) -> None:
        if not isinstance(snapshot, SevenRedStatisticalSnapshot):
            _reject("seven_red_statistical_snapshot_invalid", "snapshot is invalid")
        replay = SevenRedStatisticalSnapshot.compile(
            source_walk_forward=snapshot.source_walk_forward,
            protocol=snapshot.protocol,
        )
        if replay.snapshot_digest != snapshot.snapshot_digest:
            _reject(
                "seven_red_statistical_replay_mismatch",
                "statistical snapshot does not match deterministic replay",
                expected=replay.snapshot_digest,
                actual=snapshot.snapshot_digest,
            )
