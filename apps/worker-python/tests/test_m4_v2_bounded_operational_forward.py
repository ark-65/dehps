from __future__ import annotations

import importlib.util
import math
from datetime import date, datetime

from dehps.config import ROOT_DIR
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    bounded_operational_forward as bounded,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import ResearchEvidenceSupervisor


def _source() -> dict:
    return {
        "artifact_digest": "a" * 64,
        "frozen_contract": {
            "branch": "MARGINAL_STATIC",
            "estimator_identity": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "feature_identity": (
                "NO_FEATURES_33_EXPANDING_RED_NUMBER_EVENT_COUNTS_ONLY"
            ),
            "target_valid_forward_issues": 120,
            "model_ticket_count": 100,
            "random_baseline_ticket_count": 100,
            "proposal_pool_size": 10_000,
            "data_reuse_policy": "STAGED_INDEPENDENT_SAMPLES",
            "issue_20_review": "INTEGRITY_ONLY",
            "issue_60_review": "INTEGRITY_ONLY",
            "issue_120_review": "SOLE_OUTCOME_BEARING_REVIEW",
            "formal_p4": "DEPENDENCY_WAIT",
            "pass_to_p4": "NOT_EMITTED",
            "promotion": "NOT_TRIGGERED",
            "model_source_file_sha256": "b" * 64,
        },
    }


def _history(count: int = 900) -> list[tuple[str, date, tuple[int, ...]]]:
    rows = []
    for index in range(count):
        start = index % 33
        red = tuple(sorted(((start + offset) % 33) + 1 for offset in range(6)))
        rows.append(
            (f"{2000 + index // 153:04d}{index % 153 + 1:03d}", date(2000, 1, 1), red)
        )
    return rows


def test_frozen_model_refit_is_deterministic_and_strictly_prior() -> None:
    source = _source()
    preregistration, replay = bounded.build_preregistration_artifacts(
        source_contract=source
    )
    first = bounded.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=_history(),
        target_issue="2026097",
    )
    second = bounded.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=_history(),
        target_issue="2026097",
    )
    dataset, model = first
    assert first == second
    assert replay["body"]["registered_replay_status"] == ("REGISTERED_REPLAY_VERIFIED")
    assert dataset["body"]["future_rows_read"] is False
    assert model["body"]["status"] == "TRAINED"
    assert len(model["body"]["probabilities_q_1_to_33"]) == 33
    assert math.isclose(model["body"]["probability_sum"], 6.0, abs_tol=1e-12)
    assert model["body"]["hyperparameter_search"] == "NONE"
    assert model["body"]["model_selection"] == "NONE"


def test_predraw_has_exact_paired_budgets_shared_blue_and_registered_replay() -> None:
    source = _source()
    preregistration, _ = bounded.build_preregistration_artifacts(source_contract=source)
    _, model = bounded.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=_history(),
        target_issue="2026097",
    )
    artifacts = bounded.generate_predraw_artifacts(
        source_contract=source,
        preregistration=preregistration,
        model=model,
        target_draw_date=date(2026, 8, 23),
        sealed_at=datetime(2026, 8, 23, 12, tzinfo=bounded.SHANGHAI),
    )
    candidates, baseline, checkpoint, report = artifacts
    assert len(candidates["body"]["tickets"]) == 100
    assert len(baseline["body"]["tickets"]) == 100
    assert [item["blue_number"] for item in candidates["body"]["tickets"]] == [
        item["blue_number"] for item in baseline["body"]["tickets"]
    ]
    assert checkpoint["body"]["status"] == "SEALED_BEFORE_DRAW"
    assert checkpoint["body"]["configuration_drift"] is False
    assert report["body"]["status"] == "PUBLISHED"
    replay = bounded.build_predraw_replay_artifact(
        model_candidates=candidates,
        random_baseline=baseline,
        checkpoint=checkpoint,
        report=report,
    )
    assert replay["body"]["status"] == "REPLAY_VERIFIED"
    assert replay["body"]["registered_replay_status"] == ("REGISTERED_REPLAY_VERIFIED")


def test_settlement_keeps_primary_endpoint_and_aggregate_blind_boundary() -> None:
    source = _source()
    preregistration, _ = bounded.build_preregistration_artifacts(source_contract=source)
    _, model = bounded.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=_history(),
        target_issue="2026097",
    )
    candidates, baseline, checkpoint, _ = bounded.generate_predraw_artifacts(
        source_contract=source,
        preregistration=preregistration,
        model=model,
        target_draw_date=date(2026, 8, 23),
        sealed_at=datetime(2026, 8, 23, 12, tzinfo=bounded.SHANGHAI),
    )
    settlement = bounded.build_settlement_artifact(
        model=model,
        model_candidates=candidates,
        random_baseline=baseline,
        checkpoint=checkpoint,
        actual_red_numbers=(1, 4, 16, 22, 26, 31),
        actual_blue_number=12,
        durable_event_key="draw-sync:2026097",
        history_fingerprint="c" * 64,
    )
    replay = bounded.build_settlement_replay_artifact(
        settlement=settlement,
        checkpoint=checkpoint,
    )
    assert settlement["body"]["status"] == "SETTLED"
    assert isinstance(settlement["body"]["primary_endpoint_bits_per_issue"], float)
    assert settlement["body"]["aggregate_outcome_exposed"] is False
    assert replay["body"]["registered_replay_status"] == ("REGISTERED_REPLAY_VERIFIED")


def test_target_selection_skips_a_missed_deadline_without_backfill() -> None:
    history = _history()
    history[-1] = ("2026096", date(2026, 8, 20), history[-1][2])
    issue, draw_date, _, _ = bounded.target_for_now(
        history,
        moment=datetime(2026, 8, 21, 12, tzinfo=bounded.SHANGHAI),
    )
    assert (issue, draw_date) == ("2026097", date(2026, 8, 23))
    skipped, skipped_date, _, _ = bounded.target_for_now(
        history,
        moment=datetime(2026, 8, 23, 18, tzinfo=bounded.SHANGHAI),
    )
    assert (skipped, skipped_date) == ("2026098", date(2026, 8, 25))


def test_manifest_keeps_formal_p4_waiting_and_registers_one_ready_preregistration() -> (
    None
):
    path = (
        ROOT_DIR
        / "apps/worker-python/scripts/build_m4_v2_bounded_operational_forward_manifest.py"
    )
    spec = importlib.util.spec_from_file_location("bounded_builder_test", path)
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    baseline = PostgresResearchOSRepository().load_manifest(
        control_plane_key=builder.CONTROL_PLANE_KEY
    )
    assert baseline.artifact_digest == builder.BASELINE_MANIFEST_DIGEST
    payload, dry_run = builder.build_manifest(
        baseline.to_dict(include_digest=True),
        source_contract_digest="d" * 64,
        target_issue="2026097",
        target_draw_date="2026-08-23",
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    statuses = {item.task_key: item.status.value for item in snapshot.resolutions}
    assert tuple(item.task_key for item in snapshot.ready_queue) == (
        bounded.PREREGISTRATION_TASK_KEY,
    )
    assert statuses[builder.FORMAL_P4_TASK_KEY] == "dependency_wait"
    assert "m4-p3-predictive-decision:PASS_TO_P4" not in manifest.facts.artifacts
    assert dry_run["pass_to_p4_emitted"] is False


def test_unified_supervisor_registers_only_the_frozen_bounded_capabilities() -> None:
    supervisor = ResearchEvidenceSupervisor(require_clean_tree=False)
    for capability in (
        bounded.PREREGISTRATION_CAPABILITY,
        bounded.REFIT_CAPABILITY,
        bounded.PREDRAW_CAPABILITY,
        bounded.PREDRAW_REPLAY_CAPABILITY,
        bounded.SETTLEMENT_CAPABILITY,
        bounded.SETTLEMENT_REPLAY_CAPABILITY,
    ):
        assert capability in supervisor.capabilities
