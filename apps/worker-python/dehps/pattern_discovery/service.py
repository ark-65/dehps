from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Iterable

from dehps.agents.errors import AgentRequestConflictError, AgentRequestValidationError
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import AgentRequest, AgentRequestStatus, AgentRequestType, AgentRiskLevel
from dehps.agents.roles import AgentRole
from dehps.agents.service import AgentRequestService
from dehps.pattern_discovery.arithmetic import APSignature, ArithmeticProgressionExtractor
from dehps.pattern_discovery.catalog import DEFAULT_PATTERN_CATALOG, PatternCatalog
from dehps.pattern_discovery.extractors import PatternExtractionResult, PatternExtractorSuite
from dehps.pattern_discovery.models import (
    ROUND28_SCHEMA_VERSION,
    PatternCandidate,
    PatternDecision,
    PatternLifecycleStatus,
    PatternNoveltyReport,
    PatternSearchBudget,
    PatternSearchCycle,
    PatternSignificanceResult,
    PatternValidation,
    PatternValidationWindow,
    SynthesizedFeature,
    SynthesizedFeatureMode,
    SynthesizedStrategy,
    SynthesizedStrategyType,
    jsonable,
    pattern_key,
    stable_hash,
)
from dehps.pattern_discovery.novelty import PatternNoveltyDetector
from dehps.pattern_discovery.repository import PatternDiscoveryRepository
from dehps.pattern_discovery.significance import PatternSignificanceReviewer
from dehps.pattern_discovery.validation import PatternContractValidator


DrawRecord = tuple[str, tuple[int, ...]]


@dataclass(frozen=True)
class PatternScreeningResult:
    pattern: PatternCandidate
    significance: PatternSignificanceResult
    novelty: PatternNoveltyReport
    accepted: bool
    blockers: tuple[str, ...]


class PatternFeatureSynthesizer:
    def synthesize(self, pattern: PatternCandidate) -> SynthesizedFeature:
        feature_formula = {
            "operator": "pattern_match_score",
            "source_formula_hash": pattern.formula_hash,
            "match": pattern.formula,
            "normalization": "observed_minus_expected_rate",
        }
        return SynthesizedFeature(
            feature_key=pattern_key("feature", {"pattern": pattern.pattern_key, "formula": feature_formula}),
            source_pattern_keys=(pattern.pattern_key,),
            description=f"Declarative feature for {pattern.description}",
            execution_mode=SynthesizedFeatureMode.DECLARATIVE,
            formula=feature_formula,
            parameters={
                "pattern_family": pattern.pattern_family,
                "pattern_type": pattern.pattern_type,
                "pattern_parameters": pattern.parameters,
            },
            allowed_operations=("count", "ratio", "difference", "contains", "residual"),
            input_boundary=dict(pattern.input_boundary),
            output_contract={"type": "numeric", "range": [-1.0, 1.0], "higher_is_more_pattern_like": True},
            null_dependency=dict(pattern.null_definition),
            failure_condition=dict(pattern.failure_condition),
            source_pattern_hashes=(pattern.formula_hash,),
        )


class PatternStrategySynthesizer:
    def synthesize(self, feature: SynthesizedFeature, pattern: PatternCandidate | None = None) -> SynthesizedStrategy:
        expression = {
            "operator": "weighted_linear_rank",
            "terms": [{"feature_key": feature.feature_key, "weight": 1.0}],
            "tie_breaker": "baseline_rank",
        }
        return SynthesizedStrategy(
            strategy_key=pattern_key("strategy", {"feature": feature.feature_key, "expression": expression}),
            strategy_type=SynthesizedStrategyType.SINGLE_FEATURE_RANK,
            source_feature_keys=(feature.feature_key,),
            source_pattern_keys=feature.source_pattern_keys,
            description=f"Rank candidates by synthesized feature {feature.feature_key}.",
            scoring_expression=expression,
            parameters={"weights": {feature.feature_key: 1.0}, "max_weight_candidates": 1},
            candidate_boundary={"domain": "ssq_red_ball", "production_impact": "none"},
            baseline_strategy={"baseline": "current_research_baseline", "must_compare": True},
            validation_protocol={
                "search": "pattern_search_window_only",
                "frozen": "predeclared_frozen_window",
                "forward": "future_unseen_issues",
                "no_random_split": True,
            },
            failure_condition=(pattern.failure_condition if pattern else {"frozen": "no positive adjusted evidence"}),
            production_impact="none",
        )


class PatternDiscoveryService:
    def __init__(
        self,
        *,
        repository: PatternDiscoveryRepository | None = None,
        extractor_suite: PatternExtractorSuite | None = None,
        catalog: PatternCatalog | None = None,
        significance_reviewer: PatternSignificanceReviewer | None = None,
        novelty_detector: PatternNoveltyDetector | None = None,
        validator: PatternContractValidator | None = None,
        agent_repository: AgentRequestRepository | None = None,
        agent_service: AgentRequestService | None = None,
    ) -> None:
        self.repository = repository or PatternDiscoveryRepository()
        self.extractor_suite = extractor_suite or PatternExtractorSuite()
        self.catalog = catalog or DEFAULT_PATTERN_CATALOG
        self.significance_reviewer = significance_reviewer or PatternSignificanceReviewer()
        self.novelty_detector = novelty_detector or PatternNoveltyDetector()
        self.validator = validator or PatternContractValidator()
        self.feature_synthesizer = PatternFeatureSynthesizer()
        self.strategy_synthesizer = PatternStrategySynthesizer()
        self.agent_repository = agent_repository or AgentRequestRepository()
        self.agent_service = agent_service or AgentRequestService(self.agent_repository)

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()
        self.agent_repository.ensure_schema()

    def discover(
        self,
        *,
        draws: Iterable[DrawRecord] | None = None,
        budget: PatternSearchBudget | None = None,
        persist: bool = False,
        residuals: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        budget = budget or PatternSearchBudget()
        if persist:
            self.ensure_schema()
        history = tuple(draws) if draws is not None else self.repository.load_history()
        extraction = self.extractor_suite.extract(history, budget=budget, residuals=residuals)
        validation = self.validator.validate_budget(
            budget,
            family_count=len(extraction.family_counts),
            pattern_count=len(extraction.patterns),
        )
        writes: list[str] = []
        if persist:
            for pattern in extraction.patterns:
                stored = self.repository.upsert_pattern(pattern)
                self.repository.append_observations(stored)
                writes.append(stored.pattern_key)
        return {
            "schema_version": ROUND28_SCHEMA_VERSION,
            "dry_run": not persist,
            "patterns": extraction.patterns,
            "family_counts": extraction.family_counts,
            "stopped_by_budget": extraction.stopped_by_budget,
            "budget": budget,
            "validation": validation,
            "writes": writes,
        }

    def screen(
        self,
        patterns: Iterable[PatternCandidate],
        *,
        persist: bool = False,
        multiplicity_complete: bool = True,
        existing_patterns: Iterable[dict[str, Any] | PatternCandidate] | None = None,
    ) -> dict[str, Any]:
        patterns_tuple = tuple(patterns)
        family_counts = Counter(pattern.multiplicity_family or pattern.pattern_family for pattern in patterns_tuple)
        existing = tuple(existing_patterns if existing_patterns is not None else (self.repository.existing_pattern_summaries() if persist else ()))
        results: list[PatternScreeningResult] = []
        validations: list[PatternValidation] = []
        for pattern in patterns_tuple:
            multiplicity = max(1, family_counts[pattern.multiplicity_family or pattern.pattern_family])
            significance = self.significance_reviewer.review(
                pattern,
                multiplicity_count=multiplicity,
                multiplicity_complete=multiplicity_complete,
                sequential_search_count=len(patterns_tuple) or 1,
            )
            novelty = self.novelty_detector.evaluate(pattern, existing)
            blockers = tuple(significance.blocker_codes) + tuple(novelty.reasons)
            accepted = significance.interpretable and novelty.is_novel and significance.effect_size > 0
            results.append(PatternScreeningResult(pattern, significance, novelty, accepted, blockers))
            decision = PatternDecision.SUPPORTED if accepted else PatternDecision.REJECTED
            validations.append(
                PatternValidation(
                    validation_key=pattern_key(
                        "pattern-validation",
                        {
                            "pattern": pattern.pattern_key,
                            "window": PatternValidationWindow.SEARCH.value,
                            "significance": significance,
                        },
                    ),
                    pattern_key=pattern.pattern_key,
                    window=PatternValidationWindow.SEARCH,
                    decision=decision,
                    significance=significance,
                    issue_range=pattern.search_issue_range,
                    frozen_threshold={
                        "raw_p_value": 0.05,
                        "family_adjusted_p_value": 0.05,
                        "effect_direction": "positive",
                    },
                )
            )
        if persist:
            self.ensure_schema()
            for validation in validations:
                self.repository.append_validation(validation)
        return {"results": tuple(results), "validations": tuple(validations), "writes": tuple(v.validation_key for v in validations) if persist else ()}

    def synthesize_features(
        self,
        patterns: Iterable[PatternCandidate],
        *,
        limit: int = 50,
        persist: bool = False,
    ) -> dict[str, Any]:
        features = tuple(self.feature_synthesizer.synthesize(pattern) for pattern in tuple(patterns)[:limit])
        reports = tuple(self.validator.validate_feature(feature) for feature in features)
        if persist:
            self.ensure_schema()
            for feature in features:
                self.repository.append_feature(feature)
        return {"features": features, "validation": reports, "writes": tuple(f.feature_key for f in features) if persist else ()}

    def synthesize_strategies(
        self,
        features: Iterable[SynthesizedFeature],
        *,
        patterns: Iterable[PatternCandidate] = (),
        limit: int = 30,
        persist: bool = False,
    ) -> dict[str, Any]:
        pattern_by_key = {pattern.pattern_key: pattern for pattern in patterns}
        strategies = tuple(
            self.strategy_synthesizer.synthesize(
                feature,
                pattern_by_key.get(feature.source_pattern_keys[0]) if feature.source_pattern_keys else None,
            )
            for feature in tuple(features)[:limit]
        )
        reports = tuple(self.validator.validate_strategy(strategy) for strategy in strategies)
        if persist:
            self.ensure_schema()
            for strategy in strategies:
                self.repository.append_strategy(strategy)
        return {"strategies": strategies, "validation": reports, "writes": tuple(s.strategy_key for s in strategies) if persist else ()}

    def cycle(
        self,
        *,
        draws: Iterable[DrawRecord] | None = None,
        budget: PatternSearchBudget | None = None,
        persist: bool = False,
        submit: bool = False,
        requested_by: str = "research:pattern-discovery",
    ) -> PatternSearchCycle:
        budget = budget or PatternSearchBudget()
        discovered = self.discover(draws=draws, budget=budget, persist=persist)
        patterns = tuple(discovered["patterns"])
        screened = self.screen(patterns, persist=persist, multiplicity_complete=not discovered["stopped_by_budget"])
        accepted_patterns = tuple(result.pattern for result in screened["results"] if result.accepted)
        feature_result = self.synthesize_features(accepted_patterns, limit=budget.feature_candidates, persist=persist)
        strategy_result = self.synthesize_strategies(
            feature_result["features"],
            patterns=accepted_patterns,
            limit=budget.strategy_candidates,
            persist=persist,
        )
        request_key = None
        if submit and strategy_result["strategies"]:
            first_accepted = next(result for result in screened["results"] if result.pattern == accepted_patterns[0])
            request = self.submit_pattern_hypothesis(
                pattern=accepted_patterns[0],
                feature=feature_result["features"][0],
                strategy=strategy_result["strategies"][0],
                significance=first_accepted.significance,
                budget=budget,
                requested_by=requested_by,
            )
            request_key = request.request_key
        cycle = PatternSearchCycle(
            cycle_key=pattern_key(
                "pattern-cycle",
                {
                    "patterns": [pattern.pattern_key for pattern in patterns],
                    "budget": budget,
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            ),
            search_issue_range=patterns[0].search_issue_range if patterns else {},
            budget=budget,
            patterns=patterns,
            validations=tuple(screened["validations"]),
            features=tuple(feature_result["features"]),
            strategies=tuple(strategy_result["strategies"]),
            submitted_request_key=request_key,
            status="completed" if patterns else "no_patterns",
            writes=tuple(
                str(item)
                for item in (
                    *discovered["writes"],
                    *screened["writes"],
                    *feature_result["writes"],
                    *strategy_result["writes"],
                    *((request_key,) if request_key else ()),
                )
            ),
        )
        if persist:
            self.repository.append_cycle(cycle)
        return cycle

    def submit_pattern_hypothesis(
        self,
        *,
        pattern: PatternCandidate,
        feature: SynthesizedFeature,
        strategy: SynthesizedStrategy,
        significance: PatternSignificanceResult,
        budget: PatternSearchBudget | None = None,
        requested_by: str,
        request_key: str | None = None,
    ) -> AgentRequest:
        self.agent_repository.ensure_schema()
        budget = budget or PatternSearchBudget()
        hypothesis_key = pattern_key("pattern-hypothesis", {"pattern": pattern.pattern_key, "strategy": strategy.strategy_key})
        payload = {
            "hypothesis_key": hypothesis_key,
            "scientific_question": f"Does pattern {pattern.pattern_key} improve isolated candidate ranking versus matched nulls?",
            "null_hypothesis": "The synthesized pattern strategy has no positive frozen/forward lift over matched baselines.",
            "failure_condition": pattern.failure_condition,
            "source_pattern_keys": [pattern.pattern_key],
            "formulas": {"pattern": pattern.formula, "feature": feature.formula, "strategy": strategy.scoring_expression},
            "significance": jsonable(significance),
            "feature_contracts": [jsonable(feature)],
            "strategy_contract": jsonable(strategy),
            "null": pattern.null_definition,
            "matched_baselines": pattern.null_definition.get("matched", {}),
            "multiplicity": {
                "family": pattern.multiplicity_family or pattern.pattern_family,
                "count": significance.multiplicity_count,
                "complete": significance.interpretable,
            },
            "search_budget": budget.snapshot(),
            "production_impact": "none",
            "status": "submitted",
            "non_goals": [
                "do_not_modify_source_code",
                "do_not_modify_production_ranker",
                "do_not_execute_training",
                "do_not_update_registry_without_reviewer",
            ],
        }
        key = request_key or self._proposal_request_key(hypothesis_key, pattern, feature, strategy)
        try:
            request = self.agent_service.create_draft(
                request_key=key,
                request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
                requested_by_role=AgentRole.RESEARCH,
                requested_by=requested_by,
                title=f"Pattern hypothesis: {pattern.pattern_type or pattern.pattern_family}",
                summary=(
                    "Autonomous Pattern Discovery proposal only; Reviewer approval is required before "
                    "Hypothesis Registry conversion."
                ),
                payload=payload,
                environment="isolated",
                risk_level=AgentRiskLevel.LOW,
                metadata={
                    "schema_version": ROUND28_SCHEMA_VERSION,
                    "pattern_key": pattern.pattern_key,
                    "feature_key": feature.feature_key,
                    "strategy_key": strategy.strategy_key,
                    "formula_hash": pattern.formula_hash,
                },
            )
        except AgentRequestConflictError:
            existing = self.agent_repository.get_request(key)
            if existing.payload != payload or existing.status != AgentRequestStatus.SUBMITTED:
                raise
            return existing
        return self.agent_service.submit(
            request.request_key,
            actor_role=AgentRole.RESEARCH,
            actor_id=requested_by,
            environment="isolated",
        )

    def compare_null(
        self,
        *,
        signature: APSignature,
        draws: Iterable[DrawRecord],
    ) -> dict[str, float]:
        return ArithmeticProgressionExtractor().compare_to_matched_nulls(signature, draws)

    def arithmetic(
        self,
        *,
        draws: Iterable[DrawRecord],
    ) -> tuple[PatternCandidate, ...]:
        return ArithmeticProgressionExtractor().extract_draw_patterns(draws)

    def list_patterns(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        self.repository.ensure_schema()
        return {"entity": "discovered_patterns", "items": self.repository.list_patterns(limit=limit, offset=offset)}

    def show_pattern(self, pattern_key_: str) -> dict[str, Any]:
        self.repository.ensure_schema()
        return {"entity": "discovered_pattern", "data": self.repository.get_pattern(pattern_key_)}

    def status(self) -> dict[str, Any]:
        self.repository.ensure_schema()
        return {
            "schema_version": ROUND28_SCHEMA_VERSION,
            "catalog_pattern_types": len(self.catalog.list_specs()),
            "catalog_minimum_coverage": self.catalog.validate_minimum_coverage(),
            "write_routes_enabled": False,
            "production_access": False,
            "repository": self.repository.summary(),
        }

    @staticmethod
    def _proposal_request_key(
        hypothesis_key: str,
        pattern: PatternCandidate,
        feature: SynthesizedFeature,
        strategy: SynthesizedStrategy,
    ) -> str:
        digest = sha256(
            f"{hypothesis_key}:{pattern.pattern_key}:{feature.feature_key}:{strategy.strategy_key}".encode("utf-8")
        ).hexdigest()[:16]
        return f"research-proposal-pattern-{digest}"
