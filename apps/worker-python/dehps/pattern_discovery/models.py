from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any


ROUND28_SCHEMA_VERSION = "autonomous-pattern-discovery-v1"
DEFAULT_PATTERN_GENERATOR_VERSION = "pattern-discovery-deterministic-v1"
LEGAL_UNIVERSE_FINGERPRINT = "ssq-red-1-33-choose-6-v1"


class PatternLifecycleStatus(str, Enum):
    DISCOVERED = "discovered"
    SCREENED = "screened"
    FROZEN_PENDING = "frozen_pending"
    FROZEN_SUPPORTED = "frozen_supported"
    FROZEN_REJECTED = "frozen_rejected"
    FORWARD_PENDING = "forward_pending"
    FORWARD_SUPPORTED = "forward_supported"
    FORWARD_REJECTED = "forward_rejected"
    INCONCLUSIVE = "inconclusive"
    INVALIDATED = "invalidated"


class PatternValidationWindow(str, Enum):
    SEARCH = "search"
    FROZEN = "frozen"
    FORWARD = "forward"


class PatternDecision(str, Enum):
    SUPPORTED = "supported"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    INVALIDATED = "invalidated"


class SynthesizedFeatureMode(str, Enum):
    DECLARATIVE = "declarative"
    COMPOSABLE = "composable"
    RUNTIME_INTERPRETED = "runtime_interpreted"


class SynthesizedStrategyType(str, Enum):
    SINGLE_FEATURE_RANK = "single_feature_rank"
    WEIGHTED_LINEAR_RANK = "weighted_linear_rank"
    QUANTILE_FILTER_THEN_RANK = "quantile_filter_then_rank"
    RESIDUAL_RERANK = "residual_rerank"
    STRATIFIED_CANDIDATE_ALLOCATION = "stratified_candidate_allocation"
    RANK_ENSEMBLE = "rank_ensemble"


ALLOWED_FEATURE_OPERATIONS = frozenset(
    {
        "count",
        "ratio",
        "sum",
        "mean",
        "median",
        "min",
        "max",
        "span",
        "difference",
        "absolute_difference",
        "mod",
        "bucket",
        "contains",
        "all",
        "any",
        "not",
        "and",
        "or",
        "window_count",
        "rolling_mean",
        "zscore",
        "residual",
        "rank",
        "quantile",
        "linear_combination",
    }
)


FORBIDDEN_DECLARATIVE_TOKENS = frozenset(
    {"eval", "exec", "import", "__", "open(", "subprocess", "os.", "sys.", "sql", "shell", "$("}
)


ALLOWED_STRATEGY_TYPES = frozenset(item.value for item in SynthesizedStrategyType)


@dataclass(frozen=True)
class PatternSearchBudget:
    families: int = 10
    patterns_per_family: int = 20
    feature_candidates: int = 50
    strategy_candidates: int = 30
    weight_candidates: int = 200
    cpu_slots: int = 16
    memory_gb: int = 20

    def __post_init__(self) -> None:
        limits = {
            "families": 10,
            "patterns_per_family": 20,
            "feature_candidates": 50,
            "strategy_candidates": 30,
            "weight_candidates": 200,
            "cpu_slots": 16,
            "memory_gb": 20,
        }
        for name, maximum in limits.items():
            value = int(getattr(self, name))
            if value < 0 or value > maximum:
                raise ValueError(f"{name} must be between 0 and {maximum}")

    def exhausted(self, *, family_count: int = 0, pattern_count: int = 0) -> bool:
        return family_count > self.families or pattern_count > self.families * self.patterns_per_family

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatternCandidate:
    pattern_key: str
    pattern_family: str
    description: str
    input_boundary: dict[str, Any]
    formula: dict[str, Any]
    parameters: dict[str, Any]
    observed_support: float
    expected_support: float
    effect_size: float
    stability_score: float
    novelty_score: float
    complexity_score: float
    search_issue_range: dict[str, Any]
    history_fingerprint: str
    legal_universe_fingerprint: str
    null_definition: dict[str, Any]
    failure_condition: dict[str, Any]
    leakage_risks: tuple[str, ...]
    source_artifacts: tuple[str, ...]
    pattern_type: str | None = None
    lifecycle_status: PatternLifecycleStatus = PatternLifecycleStatus.DISCOVERED
    parent_pattern_key: str | None = None
    multiplicity_family: str | None = None
    generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pattern_key.strip():
            raise ValueError("pattern_key is required")
        if not self.pattern_family.strip():
            raise ValueError("pattern_family is required")
        if not isinstance(self.formula, dict) or not self.formula:
            raise ValueError("pattern formula must be a non-empty object")
        if not isinstance(self.parameters, dict):
            raise ValueError("pattern parameters must be an object")
        if not isinstance(self.null_definition, dict) or not self.null_definition:
            raise ValueError("null_definition is required")
        if not isinstance(self.failure_condition, dict) or not self.failure_condition:
            raise ValueError("failure_condition is required")
        for name in ("stability_score", "novelty_score", "complexity_score"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.legal_universe_fingerprint != LEGAL_UNIVERSE_FINGERPRINT:
            raise ValueError("unexpected legal universe fingerprint")

    @property
    def formula_hash(self) -> str:
        return stable_hash(
            {
                "family": self.pattern_family,
                "type": self.pattern_type or self.pattern_family,
                "formula": self.formula,
                "parameters": self.parameters,
                "input_boundary": self.input_boundary,
                "legal_universe": self.legal_universe_fingerprint,
            }
        )

    @property
    def content_hash(self) -> str:
        return stable_hash(self)

    def stable_json(self) -> str:
        return stable_json(self)


@dataclass(frozen=True)
class PatternSignificanceResult:
    pattern_key: str
    raw_p_value: float
    family_adjusted_p_value: float
    sequential_adjusted_p_value: float
    effect_size: float
    confidence_interval: tuple[float, float]
    expected_count: float
    observed_count: float
    multiplicity_count: int
    interpretable: bool
    blocker_codes: tuple[str, ...]
    direction: str
    method: str
    nulls: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("raw_p_value", "family_adjusted_p_value", "sequential_adjusted_p_value"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.multiplicity_count < 1:
            raise ValueError("multiplicity_count must be at least 1")


@dataclass(frozen=True)
class PatternNoveltyReport:
    pattern_key: str
    is_novel: bool
    novelty_score: float
    duplicate_pattern_keys: tuple[str, ...]
    renamed_duplicate_keys: tuple[str, ...]
    rejected_family_near_retries: tuple[str, ...]
    parent_pattern_key: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SynthesizedFeature:
    feature_key: str
    source_pattern_keys: tuple[str, ...]
    description: str
    execution_mode: SynthesizedFeatureMode
    formula: dict[str, Any]
    parameters: dict[str, Any]
    allowed_operations: tuple[str, ...]
    input_boundary: dict[str, Any]
    output_contract: dict[str, Any]
    null_dependency: dict[str, Any]
    failure_condition: dict[str, Any]
    source_pattern_hashes: tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.feature_key.strip():
            raise ValueError("feature_key is required")
        invalid = sorted(set(self.allowed_operations) - ALLOWED_FEATURE_OPERATIONS)
        if invalid:
            raise ValueError(f"unsupported feature operation(s): {', '.join(invalid)}")
        _reject_arbitrary_program(self.formula)


@dataclass(frozen=True)
class SynthesizedStrategy:
    strategy_key: str
    strategy_type: SynthesizedStrategyType
    source_feature_keys: tuple[str, ...]
    source_pattern_keys: tuple[str, ...]
    description: str
    scoring_expression: dict[str, Any]
    parameters: dict[str, Any]
    candidate_boundary: dict[str, Any]
    baseline_strategy: dict[str, Any]
    validation_protocol: dict[str, Any]
    failure_condition: dict[str, Any]
    production_impact: str = "none"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.strategy_type.value not in ALLOWED_STRATEGY_TYPES:
            raise ValueError(f"unsupported strategy type: {self.strategy_type}")
        if self.production_impact != "none":
            raise ValueError("pattern strategies must declare production_impact='none'")
        _reject_arbitrary_program(self.scoring_expression)
        if len(json.dumps(jsonable(self.parameters), sort_keys=True)) > 4096:
            raise ValueError("strategy parameters are unbounded")


@dataclass(frozen=True)
class PatternValidation:
    validation_key: str
    pattern_key: str
    window: PatternValidationWindow
    decision: PatternDecision
    significance: PatternSignificanceResult
    issue_range: dict[str, Any]
    frozen_threshold: dict[str, Any]
    immutable: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PatternSearchCycle:
    cycle_key: str
    search_issue_range: dict[str, Any]
    budget: PatternSearchBudget
    patterns: tuple[PatternCandidate, ...]
    validations: tuple[PatternValidation, ...] = ()
    features: tuple[SynthesizedFeature, ...] = ()
    strategies: tuple[SynthesizedStrategy, ...] = ()
    submitted_request_key: str | None = None
    status: str = "completed"
    writes: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return sha256(stable_json(value).encode("utf-8")).hexdigest()


def history_fingerprint(draws: list[tuple[str, tuple[int, ...]]] | tuple[tuple[str, tuple[int, ...]], ...]) -> str:
    return stable_hash({"history": [(issue, tuple(numbers)) for issue, numbers in draws]})


def pattern_key(prefix: str, payload: Any) -> str:
    return f"{prefix}-{stable_hash(payload)[:16]}"


def _reject_arbitrary_program(value: Any) -> None:
    text = stable_json(value).lower()
    for token in FORBIDDEN_DECLARATIVE_TOKENS:
        if token in text:
            raise ValueError(f"declarative contract contains forbidden token: {token}")


def lifecycle_transition_allowed(
    current: PatternLifecycleStatus,
    new: PatternLifecycleStatus,
) -> bool:
    if current == PatternLifecycleStatus.FROZEN_REJECTED and new == PatternLifecycleStatus.FORWARD_SUPPORTED:
        return False
    allowed = {
        PatternLifecycleStatus.DISCOVERED: {
            PatternLifecycleStatus.SCREENED,
            PatternLifecycleStatus.INVALIDATED,
            PatternLifecycleStatus.INCONCLUSIVE,
        },
        PatternLifecycleStatus.SCREENED: {
            PatternLifecycleStatus.FROZEN_PENDING,
            PatternLifecycleStatus.FROZEN_REJECTED,
            PatternLifecycleStatus.INVALIDATED,
        },
        PatternLifecycleStatus.FROZEN_PENDING: {
            PatternLifecycleStatus.FROZEN_SUPPORTED,
            PatternLifecycleStatus.FROZEN_REJECTED,
            PatternLifecycleStatus.INCONCLUSIVE,
            PatternLifecycleStatus.INVALIDATED,
        },
        PatternLifecycleStatus.FROZEN_SUPPORTED: {
            PatternLifecycleStatus.FORWARD_PENDING,
            PatternLifecycleStatus.INCONCLUSIVE,
            PatternLifecycleStatus.INVALIDATED,
        },
        PatternLifecycleStatus.FORWARD_PENDING: {
            PatternLifecycleStatus.FORWARD_SUPPORTED,
            PatternLifecycleStatus.FORWARD_REJECTED,
            PatternLifecycleStatus.INCONCLUSIVE,
            PatternLifecycleStatus.INVALIDATED,
        },
        PatternLifecycleStatus.FROZEN_REJECTED: {
            PatternLifecycleStatus.INCONCLUSIVE,
            PatternLifecycleStatus.INVALIDATED,
        },
        PatternLifecycleStatus.FORWARD_SUPPORTED: {PatternLifecycleStatus.INVALIDATED},
        PatternLifecycleStatus.FORWARD_REJECTED: {PatternLifecycleStatus.INVALIDATED},
        PatternLifecycleStatus.INCONCLUSIVE: {
            PatternLifecycleStatus.FROZEN_PENDING,
            PatternLifecycleStatus.FORWARD_PENDING,
            PatternLifecycleStatus.INVALIDATED,
        },
        PatternLifecycleStatus.INVALIDATED: set(),
    }
    return new in allowed[current]
