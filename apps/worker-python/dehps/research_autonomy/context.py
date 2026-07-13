from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from typing import Any

from dehps.evaluation.objective_policy import DEFAULT_OBJECTIVE_POLICY
from dehps.research_autonomy.evidence_reader import FormalEvidenceReader
from dehps.research_autonomy.feature_catalog import FeatureCatalog, FeatureDescriptor
from dehps.research_autonomy.mechanism_catalog import MechanismCatalog
from dehps.research_autonomy.repository import ResearchContextRepository


@dataclass(frozen=True)
class HypothesisSummary:
    hypothesis_key: str
    family_key: str
    title: str
    mechanism: str
    status: str
    input_fields: tuple[str, ...]
    feature_keys: tuple[str, ...]
    model_keys: tuple[str, ...]
    validation_protocol: str
    rejection_scope: str
    rejection_reason: str | None
    reopen_condition: str | None


@dataclass(frozen=True)
class HypothesisFamilySummary:
    family_key: str
    title: str
    mechanism: str
    status: str
    rejection_scope: str
    rejection_reason: str | None
    reopen_condition: str | None


@dataclass(frozen=True)
class ExperimentSummary:
    experiment_key: str
    hypothesis_key: str
    experiment_type: str
    status: str
    run_id: str | None
    report_path: str | None
    config_snapshot: dict[str, Any]


@dataclass(frozen=True)
class EvidenceSummary:
    evidence_id: int
    hypothesis_key: str
    experiment_key: str | None
    evidence_type: str
    direction: str
    summary: str
    metrics: dict[str, Any]


@dataclass(frozen=True)
class TrainingFailureSummary:
    key: str
    status: str
    cause: str
    recovery: str
    run_id: str | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class CandidateSourcePerformance:
    source_key: str
    state: str
    generated: int
    prefilter_selected: int
    full_eval_top5: int
    round_best_rounds: int
    frozen_frontier_rounds: int
    search_navigation_rounds: int


@dataclass(frozen=True)
class ObjectivePolicySummary:
    version: str
    policy_hash: str
    metric_keys: tuple[str, ...]


@dataclass(frozen=True)
class ModelDescriptor:
    key: str
    kind: str
    implementation_path: str
    input_feature_keys: tuple[str, ...]
    current_status: str


@dataclass(frozen=True)
class ForwardEvidenceStatus:
    status: str
    protocol: str
    paired_issue_count: int
    min_paired_issues: int
    review_ready: bool
    promotion_eligible: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class DataBoundarySummary:
    protocol: str
    status: str
    training_fields: tuple[str, ...]
    excluded_fields: tuple[str, ...]
    future_information_allowed: bool
    ticket_distribution_observed: bool


@dataclass(frozen=True)
class ResearchContext:
    active_hypotheses: tuple[HypothesisSummary, ...]
    rejected_hypotheses: tuple[HypothesisSummary, ...]
    rejected_families: tuple[HypothesisFamilySummary, ...]
    recent_experiments: tuple[ExperimentSummary, ...]
    recent_evidence: tuple[EvidenceSummary, ...]
    training_failures: tuple[TrainingFailureSummary, ...]
    candidate_source_performance: tuple[CandidateSourcePerformance, ...]
    current_objective_policy: ObjectivePolicySummary
    available_features: tuple[FeatureDescriptor, ...]
    available_models: tuple[ModelDescriptor, ...]
    forward_evidence_status: ForwardEvidenceStatus
    data_boundary: DataBoundarySummary
    sequential_null_status: dict[str, Any]
    frozen_validation_status: dict[str, Any]
    source_training_run_ids: tuple[str, ...]
    formal_source_paths: tuple[str, ...]

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ResearchContextBuilder:
    def __init__(
        self,
        repository: ResearchContextRepository | None = None,
        evidence_reader: FormalEvidenceReader | None = None,
        feature_catalog: FeatureCatalog | None = None,
        mechanism_catalog: MechanismCatalog | None = None,
    ) -> None:
        self.repository = repository or ResearchContextRepository()
        self.evidence_reader = evidence_reader or FormalEvidenceReader()
        self.feature_catalog = feature_catalog or FeatureCatalog()
        self.mechanism_catalog = mechanism_catalog or MechanismCatalog()

    def build(self) -> ResearchContext:
        registry = self.repository.read_registry()
        training_rounds = self.repository.read_training_rounds()
        evidence = self.evidence_reader.read()
        active = tuple(
            self._hypothesis(item) for item in registry["hypotheses"] if item["status"] != "rejected"
        )
        rejected = tuple(
            self._hypothesis(item) for item in registry["hypotheses"] if item["status"] == "rejected"
        )
        rejected_families = tuple(
            HypothesisFamilySummary(**item)
            for item in registry["families"]
            if item["status"] in {"rejected", "partially_rejected", "exhausted"}
        )
        mechanisms = self.mechanism_catalog.build(rejected, rejected_families)
        features = self.feature_catalog.build(rejected, rejected_families)
        # Catalog association is evaluated during context construction so a rejected
        # mechanism cannot silently lose its Registry link.
        associated_families = {
            family_key for mechanism in mechanisms for family_key in mechanism.known_hypothesis_families
        }
        missing_families = {
            item.family_key for item in rejected_families
        } - associated_families
        if missing_families:
            raise ValueError(
                "rejected Registry families are not associated with the mechanism catalog: "
                + ", ".join(sorted(missing_families))
            )
        context = ResearchContext(
            active_hypotheses=active,
            rejected_hypotheses=rejected,
            rejected_families=rejected_families,
            recent_experiments=tuple(ExperimentSummary(**item) for item in registry["experiments"]),
            recent_evidence=tuple(EvidenceSummary(**item) for item in registry["evidence"]),
            training_failures=tuple(
                TrainingFailureSummary(**item)
                for item in (*evidence.training_failures, *self._round_failures(training_rounds))
            ),
            candidate_source_performance=tuple(
                CandidateSourcePerformance(**item) for item in evidence.candidate_sources
            ),
            current_objective_policy=ObjectivePolicySummary(
                version=DEFAULT_OBJECTIVE_POLICY.version,
                policy_hash=DEFAULT_OBJECTIVE_POLICY.policy_hash,
                metric_keys=("top_100", "top_1000", "top_10000", "median_rank", "worst_rank", "rank_tail"),
            ),
            available_features=features,
            available_models=self._models(evidence.model_paths),
            forward_evidence_status=ForwardEvidenceStatus(**evidence.forward_evidence),
            data_boundary=DataBoundarySummary(**evidence.data_boundary),
            sequential_null_status=evidence.sequential_null,
            frozen_validation_status=evidence.frozen_validation,
            source_training_run_ids=tuple(
                sorted({*evidence.training_run_ids, *(str(row["run_id"]) for row in training_rounds)})
            ),
            formal_source_paths=tuple(evidence.source_paths),
        )
        return replace(context)

    @staticmethod
    def _hypothesis(item: dict[str, Any]) -> HypothesisSummary:
        return HypothesisSummary(**item)

    @staticmethod
    def _models(paths: tuple[str, ...]) -> tuple[ModelDescriptor, ...]:
        descriptors: list[ModelDescriptor] = []
        for path in sorted(paths):
            name = path.rsplit("/", 1)[-1].removesuffix(".py")
            if name.startswith("__") or name in {"protocol", "prediction_input_boundary"}:
                continue
            kind = "advisor" if "/advisors/" in path else "ranker"
            descriptors.append(
                ModelDescriptor(
                    key=name,
                    kind=kind,
                    implementation_path=path,
                    input_feature_keys=(),
                    current_status="implemented",
                )
            )
        return tuple(descriptors)

    @staticmethod
    def _round_failures(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "key": f"training_round:{row['run_id']}:{row['round_index']}",
                "status": "not_improved",
                "cause": "persisted training round did not improve the incumbent",
                "recovery": "do not repeat the same-history configuration without a new preregistered mechanism",
                "run_id": str(row["run_id"]),
                "evidence": {
                    "as_of_issue": row["as_of_issue"],
                    "objective_score": (
                        None if row["objective_score"] is None else float(row["objective_score"])
                    ),
                    "top_100_hits": row["top_100_hits"],
                    "top_1000_hits": row["top_1000_hits"],
                    "top_10000_hits": row["top_10000_hits"],
                    "best_rank": row["best_rank"],
                    "worst_rank": row["worst_rank"],
                },
            }
            for row in rows
            if not row["improved"]
        )
