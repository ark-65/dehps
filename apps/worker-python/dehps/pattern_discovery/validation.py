from __future__ import annotations

from dataclasses import dataclass

from dehps.pattern_discovery.models import (
    PatternCandidate,
    PatternLifecycleStatus,
    PatternSearchBudget,
    SynthesizedFeature,
    SynthesizedStrategy,
    lifecycle_transition_allowed,
)


@dataclass(frozen=True)
class PatternValidationCheck:
    key: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class PatternValidationReport:
    valid: bool
    checks: tuple[PatternValidationCheck, ...]
    blockers: tuple[str, ...]


class PatternContractValidator:
    def validate_candidate(self, candidate: PatternCandidate) -> PatternValidationReport:
        checks = (
            PatternValidationCheck("formula", bool(candidate.formula), "formula must be explicit"),
            PatternValidationCheck("parameters", isinstance(candidate.parameters, dict), "parameters must be bounded JSON"),
            PatternValidationCheck("null", bool(candidate.null_definition), "null must be declared"),
            PatternValidationCheck("failure", bool(candidate.failure_condition), "failure condition must be declared"),
            PatternValidationCheck(
                "search_boundary",
                bool(candidate.search_issue_range),
                "search issue range must be explicit",
            ),
            PatternValidationCheck(
                "generator",
                bool(candidate.generator_version),
                "generator version must be explicit",
            ),
        )
        return _report(checks)

    def validate_budget(
        self,
        budget: PatternSearchBudget,
        *,
        family_count: int,
        pattern_count: int,
    ) -> PatternValidationReport:
        checks = (
            PatternValidationCheck(
                "family_budget",
                family_count <= budget.families,
                "family count must stay within Round28 budget",
            ),
            PatternValidationCheck(
                "pattern_budget",
                pattern_count <= budget.families * budget.patterns_per_family,
                "pattern count must stay within Round28 budget",
            ),
        )
        return _report(checks)

    def validate_feature(self, feature: SynthesizedFeature) -> PatternValidationReport:
        checks = (
            PatternValidationCheck("mode", feature.execution_mode.value in {"declarative", "composable", "runtime_interpreted"}, "feature must be declarative/composable/runtime_interpreted"),
            PatternValidationCheck("source_patterns", bool(feature.source_pattern_keys), "feature needs source patterns"),
            PatternValidationCheck("output", bool(feature.output_contract), "feature output contract is required"),
        )
        return _report(checks)

    def validate_strategy(self, strategy: SynthesizedStrategy) -> PatternValidationReport:
        checks = (
            PatternValidationCheck("type", bool(strategy.strategy_type.value), "strategy type must be allow-listed"),
            PatternValidationCheck("source_features", bool(strategy.source_feature_keys), "strategy needs source features"),
            PatternValidationCheck("production", strategy.production_impact == "none", "strategy must not change production"),
        )
        return _report(checks)

    def validate_lifecycle_transition(
        self,
        current: PatternLifecycleStatus,
        new: PatternLifecycleStatus,
    ) -> PatternValidationReport:
        checks = (
            PatternValidationCheck(
                "transition_allowed",
                lifecycle_transition_allowed(current, new),
                f"{current.value} -> {new.value} transition must be legal",
            ),
        )
        return _report(checks)


def _report(checks: tuple[PatternValidationCheck, ...]) -> PatternValidationReport:
    blockers = tuple(check.key for check in checks if not check.passed)
    return PatternValidationReport(valid=not blockers, checks=checks, blockers=blockers)
