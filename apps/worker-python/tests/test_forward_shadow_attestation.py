from __future__ import annotations

from dataclasses import replace

import numpy as np

from dehps.forward_runtime.shadow_attestation import ForwardShadowAttestationService
from dehps.ranking_contract import STRICT_RANKING_CONTRACT
from dehps.scoring_kernel import (
    KernelResult,
    ShadowOperationalEvidence,
    build_shadow_operational_receipt,
    compare_kernel_results,
    link_post_draw_attestation,
    seal_shadow_watch_cycle,
)


class ConnectionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def kernel_result(backend: str) -> KernelResult:
    identity = {
        "ranking_contract": STRICT_RANKING_CONTRACT,
        "candidate_contract": "candidate.v1.0.0",
        "candidate_abi": "candidate_abi.v1",
        "candidate_digest": "a" * 64,
        "candidate_layout_digest": "b" * 64,
        "candidate_package_digest": "c" * 64,
        "candidate_abi_verification_id": "verified_candidate.v1-fixture",
    }
    return KernelResult(
        backend=backend,
        contract_version="dehps-scoring-strict-v1",
        target_scores=np.ascontiguousarray([0.5], dtype=np.float64),
        exact_ranks=np.ascontiguousarray([2], dtype=np.int64),
        top_candidate_ids=np.ascontiguousarray([[1]], dtype=np.int64),
        top_scores=np.ascontiguousarray([[0.9]], dtype=np.float64),
        red5_candidate_ids=np.ascontiguousarray([1], dtype=np.int64),
        red5_scores=np.ascontiguousarray([0.9], dtype=np.float64),
        red5_ranks=np.ascontiguousarray([1], dtype=np.int64),
        telemetry=identity,
    )


def operational(issue: str, line: str, *, pending: bool) -> ShadowOperationalEvidence:
    return ShadowOperationalEvidence(
        prediction_run_key=f"{line}:{issue}:fixture",
        source_code_commit="a" * 40,
        replay_code_commit="a" * 40,
        official_candidate_artifact_status="matched",
        evaluation_status="pending" if pending else "passed",
        restart_recovery_result="pending" if pending else "passed",
        watchdog_result="pending" if pending else "passed",
    )


def comparison(issue: str, line: str, evidence: ShadowOperationalEvidence) -> dict:
    return compare_kernel_results(
        target_issue=issue,
        line_key=line,
        config_fingerprint="config-fixture",
        candidate_store_version="candidate-store.v1",
        official=kernel_result("numpy_reference"),
        shadow=kernel_result("numba_cpu"),
        operational=evidence,
    )


def watch_cycle(issue: str, *, commit: str = "a" * 40) -> dict:
    return seal_shadow_watch_cycle(
        watch_code_commit=commit,
        watch_started_at="2026-07-18T00:00:00+00:00",
        observed_at="2026-07-18T01:00:00+00:00",
        sync_status="new_issue",
        sync_audit_passed=True,
        current_latest_issue=issue,
        evaluation_batch_status="ok",
        evaluation_failed_count=0,
    )


def source_capture(issue: str, line: str) -> dict:
    return comparison(issue, line, operational(issue, line, pending=True))


def attestation(issue: str, line: str, cycle: dict) -> dict:
    capture = source_capture(issue, line)
    reconstruction = comparison(issue, line, operational(issue, line, pending=False))
    receipt = build_shadow_operational_receipt(
        scoring_capture=capture,
        reconstruction=reconstruction,
        watch_cycle=cycle,
    )
    final = comparison(
        issue,
        line,
        replace(
            operational(issue, line, pending=False),
            restart_recovery_result=receipt["restart_recovery_result"],
            watchdog_result=receipt["watchdog_result"],
            operational_receipt=receipt,
        ),
    )
    return link_post_draw_attestation(
        scoring_capture=capture,
        post_draw_comparison=final,
    )


def run(issue: str, line: str, *, capture: bool = True, evaluated: bool = True) -> dict:
    return {
        "prediction_run_key": f"{line}:{issue}:fixture",
        "target_issue": issue,
        "line_key": line,
        "prediction_status": "evaluated" if evaluated else "pending",
        "forward_evaluation_status": "completed" if evaluated else None,
        "metadata": {"shadow_scoring_evidence": source_capture(issue, line)} if capture else {},
    }


def service(tmp_path, runs, builder) -> ForwardShadowAttestationService:
    return ForwardShadowAttestationService(
        connection_factory=ConnectionContext,
        output_dir=tmp_path,
        worker_count=2,
        run_loader=lambda conn, target_issue: list(runs),
        candidate_store_factory=lambda: object(),  # type: ignore[return-value]
        evidence_builder=builder,
    )


def test_closure_keeps_missing_draw_and_evaluation_pending(tmp_path) -> None:
    calls = []
    rows = [run("2026083", "static_100", evaluated=False)]
    closer = service(tmp_path, rows, lambda *args, **kwargs: calls.append(kwargs))

    no_issue = closer.close_cycle(
        seal_shadow_watch_cycle(
            watch_code_commit="a" * 40,
            watch_started_at="start",
            observed_at="now",
            sync_status="deferred_until_update_window",
            sync_audit_passed=False,
            current_latest_issue=None,
            evaluation_batch_status="ok",
            evaluation_failed_count=0,
        )
    )
    pending = closer.close_cycle(watch_cycle("2026083"))

    assert no_issue["status"] == "pending_no_current_issue"
    assert pending["pending_count"] == 1
    assert pending["runs"][0]["status"] == "pending_evaluation"
    assert calls == []


def test_closure_is_content_addressed_and_idempotent(tmp_path) -> None:
    issue = "2026083"
    rows = [run(issue, "static_100")]
    calls = []

    def build(conn, *, run, store, worker_count, watch_cycle):
        calls.append(run["prediction_run_key"])
        return attestation(issue, "static_100", watch_cycle)

    closer = service(tmp_path, rows, build)
    first = closer.close_cycle(watch_cycle(issue))
    second = closer.close_cycle(watch_cycle(issue))

    assert first["attested_count"] == 1
    assert second["already_attested_count"] == 1
    assert calls == ["static_100:2026083:fixture"]
    assert len(list(tmp_path.glob("shadow-*.json"))) == 1
    assert first["automatic_promotion_allowed"] is False


def test_closure_does_not_write_failed_watchdog_evidence(tmp_path) -> None:
    issue = "2026083"
    rows = [run(issue, "static_100")]

    def build(conn, *, run, store, worker_count, watch_cycle):
        return attestation(issue, "static_100", watch_cycle)

    closer = service(tmp_path, rows, build)
    result = closer.close_cycle(watch_cycle(issue, commit="b" * 40))

    assert result["status"] == "failed"
    assert result["failed_count"] == 1
    assert result["runs"][0]["status"] == "failed_operational_evidence"
    assert list(tmp_path.glob("shadow-*.json")) == []


def test_closure_isolates_one_line_failure_and_never_qualifies_legacy(tmp_path) -> None:
    issue = "2026083"
    rows = [
        run(issue, "static_100"),
        run(issue, "dynamic_kdj"),
        run(issue, "dynamic_kdj_near", capture=False),
    ]

    def build(conn, *, run, store, worker_count, watch_cycle):
        if run["line_key"] == "dynamic_kdj":
            raise RuntimeError("replay failed")
        return attestation(issue, run["line_key"], watch_cycle)

    result = service(tmp_path, rows, build).close_cycle(watch_cycle(issue))

    assert result["status"] == "failed"
    assert result["attested_count"] == 1
    assert result["failed_count"] == 1
    assert result["ineligible_count"] == 1
    assert {row["status"] for row in result["runs"]} == {
        "attested",
        "failed",
        "ineligible_no_simultaneous_capture",
    }
    assert result["automatic_promotion_allowed"] is False
