from types import SimpleNamespace

from dehps.agents.errors import AgentRequestConflictError
from dehps.agents.requests import AgentRequestStatus, AgentRequestType
from dehps.pattern_discovery.models import ROUND28_SCHEMA_VERSION, PatternSearchBudget
from dehps.pattern_discovery.service import PatternDiscoveryService

from pattern_fixtures import ap_candidate


class AgentRepository:
    def __init__(self, existing) -> None:
        self.existing = existing

    def ensure_schema(self) -> None:
        return None

    def get_request(self, request_key: str):
        assert request_key == self.existing.request_key
        return self.existing


class ConflictAgentService:
    def __init__(self, existing) -> None:
        self.existing = existing

    def create_draft(self, **kwargs):
        raise AgentRequestConflictError("request key already exists")

    def submit(self, request_key: str, **kwargs):
        return self.existing


def test_pattern_hypothesis_submit_reuses_existing_matching_request() -> None:
    pattern = ap_candidate(length=3, start=1, difference=1)
    service = PatternDiscoveryService()
    feature = service.feature_synthesizer.synthesize(pattern)
    strategy = service.strategy_synthesizer.synthesize(feature, pattern)
    significance = service.significance_reviewer.review(
        pattern,
        multiplicity_count=1,
        multiplicity_complete=True,
    )
    request_key = service._proposal_request_key(  # noqa: SLF001
        "hypothesis-key",
        pattern,
        feature,
        strategy,
    )
    existing = SimpleNamespace(
        request_key=request_key,
        request_type=AgentRequestType.RESEARCH_HYPOTHESIS_PROPOSAL,
        status=AgentRequestStatus.SUBMITTED,
        metadata={
            "schema_version": ROUND28_SCHEMA_VERSION,
            "pattern_key": pattern.pattern_key,
            "feature_key": feature.feature_key,
            "strategy_key": strategy.strategy_key,
            "formula_hash": pattern.formula_hash,
        },
    )
    service = PatternDiscoveryService(
        agent_repository=AgentRepository(existing),  # type: ignore[arg-type]
        agent_service=ConflictAgentService(existing),  # type: ignore[arg-type]
    )

    result = service.submit_pattern_hypothesis(
        pattern=pattern,
        feature=feature,
        strategy=strategy,
        significance=significance,
        budget=PatternSearchBudget(),
        requested_by="research:test",
        request_key=request_key,
    )

    assert result is existing
