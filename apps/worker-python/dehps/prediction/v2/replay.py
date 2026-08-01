from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from dehps.input_contracts.history_window import HistorySnapshotArtifact
from dehps.prediction.v2.contracts import seal_artifact, verify_artifact
from dehps.prediction.v2.generator import generate_shadow_pool
from dehps.prediction.v2.reports import build_post_draw_report, build_pre_draw_report
from dehps.prediction.v2.state import encode_state


def replay_pre_draw(
    *,
    contract: Mapping[str, Any],
    history: HistorySnapshotArtifact,
    expected_state: Mapping[str, Any],
    expected_pool: Mapping[str, Any],
    expected_top100: Mapping[str, Any],
    expected_report: Mapping[str, Any],
) -> dict[str, Any]:
    report = verify_artifact(expected_report, domain="dehps.prediction-v2.pre-draw-report.v1")
    verified_state = verify_artifact(
        expected_state,
        domain="dehps.prediction-v2.state-artifact.v1",
    )
    verified_pool = verify_artifact(
        expected_pool,
        domain="dehps.prediction-v2.shadow-pool-artifact.v1",
    )
    verified_top100 = verify_artifact(
        expected_top100,
        domain="dehps.prediction-v2.shadow-top100-artifact.v1",
    )
    reconstructed_state = encode_state(
        history,
        as_of_issue=str(report["as_of_issue"]),
        target_issue=str(report["target_issue"]),
    )
    reconstructed_pool, reconstructed_top100 = generate_shadow_pool(
        contract=contract,
        state=reconstructed_state,
    )
    reconstructed_report = build_pre_draw_report(
        contract=contract,
        state=reconstructed_state,
        pool=reconstructed_pool,
        top100=reconstructed_top100,
    )
    expected = {
        "state": verified_state["artifact_digest"],
        "pool": verified_pool["artifact_digest"],
        "top100": verified_top100["artifact_digest"],
        "report": report["artifact_digest"],
    }
    actual = {
        "state": reconstructed_state["artifact_digest"],
        "pool": reconstructed_pool["artifact_digest"],
        "top100": reconstructed_top100["artifact_digest"],
        "report": reconstructed_report["artifact_digest"],
    }
    if expected != actual:
        raise ValueError("Prediction v2 pre-draw physical replay changed")
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-replay-artifact.v1",
            "artifact_type": "PredictionV2ReplayArtifact.v1",
            "replay_kind": "PRE_DRAW",
            "status": "REPLAY_VERIFIED",
            "same_contract_identity": True,
            "same_history_identity": True,
            "same_state_identity": True,
            "same_pool_identity": True,
            "same_top100_identity": True,
            "same_report_identity": True,
            "manual_input_assembly": False,
            "historical_evidence": "NOT_RUN",
            "promotion_gate_opened": False,
            "parent_digests": list(actual.values()),
        },
        domain="dehps.prediction-v2.replay-artifact.v1",
    )


def replay_post_draw(
    *,
    pre_draw_report: Mapping[str, Any],
    actual_issue: str,
    actual_red_numbers: Sequence[object],
    expected_report: Mapping[str, Any],
) -> dict[str, Any]:
    reconstructed = build_post_draw_report(
        pre_draw_report=pre_draw_report,
        actual_issue=actual_issue,
        actual_red_numbers=actual_red_numbers,
    )
    if reconstructed["artifact_digest"] != expected_report.get("artifact_digest"):
        raise ValueError("Prediction v2 post-draw physical replay changed")
    return seal_artifact(
        {
            "schema_version": "dehps-prediction-v2-replay-artifact.v1",
            "artifact_type": "PredictionV2ReplayArtifact.v1",
            "replay_kind": "POST_DRAW",
            "status": "REPLAY_VERIFIED",
            "same_pre_draw_identity": True,
            "same_actual_draw_identity": True,
            "same_report_identity": True,
            "manual_input_assembly": False,
            "historical_evidence": "NOT_RUN",
            "promotion_gate_opened": False,
            "parent_digests": [
                str(pre_draw_report["artifact_digest"]),
                str(expected_report["artifact_digest"]),
            ],
        },
        domain="dehps.prediction-v2.replay-artifact.v1",
    )
