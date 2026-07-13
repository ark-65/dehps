from dehps.research_autonomy.context import ResearchContextBuilder
from dehps.research_autonomy.evidence_reader import FormalEvidenceBundle


class Repository:
    def read_registry(self):
        return {"families": [], "hypotheses": [], "experiments": [], "evidence": []}

    def read_training_rounds(self):
        return [{
            "run_id": "run-1", "round_index": 1, "as_of_issue": "2026079", "improved": False,
            "objective_score": 1, "top_100_hits": 0, "top_1000_hits": 0,
            "top_10000_hits": 0, "best_rank": 100, "worst_rank": 1000000,
        }]


class Reader:
    def read(self):
        return FormalEvidenceBundle(
            training_failures=(), candidate_sources=(),
            forward_evidence={"status": "accumulating", "protocol": "p", "paired_issue_count": 1,
                              "min_paired_issues": 20, "review_ready": False,
                              "promotion_eligible": False, "blockers": ("insufficient",)},
            data_boundary={"protocol": "b", "status": "passed",
                           "training_fields": ("issue", "draw_date", "red_numbers"),
                           "excluded_fields": (), "future_information_allowed": False,
                           "ticket_distribution_observed": False},
            sequential_null={"status": "noise_risk"},
            frozen_validation={"selection_uses_frozen_validation": False},
            training_run_ids=("run-1",),
            model_paths=("apps/worker-python/dehps/models/frequency_ranker.py",),
            source_paths=("formal.json",),
        )


def test_context_builder_uses_formal_sources_and_stable_fingerprint() -> None:
    builder = ResearchContextBuilder(repository=Repository(), evidence_reader=Reader())
    first = builder.build()
    second = builder.build()
    assert first == second
    assert first.fingerprint == second.fingerprint
    assert len(first.fingerprint) == 64
    assert first.training_failures[0].key == "training_round:run-1:1"
    assert first.data_boundary.status == "passed"
