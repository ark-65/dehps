from __future__ import annotations

import importlib.util
import math
import json
import subprocess

import pytest
from datetime import date, datetime

from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as successor,
)


def _history(count: int = 900) -> list[tuple[str, date, tuple[int, ...]]]:
    rows = []
    for index in range(count):
        start = index % 33
        red = tuple(sorted(((start + offset) % 33) + 1 for offset in range(6)))
        rows.append(
            (f"{2000 + index // 153:04d}{index % 153 + 1:03d}", date(2000, 1, 1), red)
        )
    return rows


def _frozen_preregistration() -> tuple[dict, dict]:
    source = successor.load_source_contract()
    preregistration, _ = successor.build_preregistration_artifacts(
        source_contract=source
    )
    return source, preregistration


def _settlements(*, count: int, gain: float, drift_at: int | None = None) -> list[dict]:
    return [
        successor._artifact(
            artifact_type=successor.SETTLEMENT_ARTIFACT_TYPE,
            body={
                "cohort_index": index,
                "target_issue": f"2099{index:03d}",
                "primary_endpoint_bits_per_issue": gain,
                "configuration_drift": index == drift_at,
            },
            parent_digests=("a" * 64,),
        )
        for index in range(1, count + 1)
    ]


def _builder():
    path = (
        ROOT_DIR
        / "apps/worker-python/scripts/build_m4_p3_forward_prequential_confirmatory_manifest.py"
    )
    spec = importlib.util.spec_from_file_location("successor_builder_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_contract_and_old_lineage_are_both_replay_verifiable(tmp_path, monkeypatch) -> None:
    source = successor.load_source_contract()
    assert source["frozen_contract"]["interim_looks"] == [20, 40, 60, 90, 120]
    assert source["frozen_contract"]["practical_effect"][
        "threshold_bits_per_issue"
    ] == 0.05
    assert source["frozen_contract"]["old_lineage"]["disposition"] == (
        "IMMUTABLE_HISTORY_NOT_CURRENT_ROUTE"
    )
    # The retired source is immutable history, not the current checkout.
    # Verify its original release bytes; do not reseal the historical contract
    # when unrelated, current repository code evolves.
    historical = successor.historical_bounded
    release = "f330f36e42c9e506860ac3634f86d28cced137d6"
    relative = historical.SOURCE_CONTRACT_PATH
    raw = subprocess.check_output(["git", "show", f"{release}:{relative}"], cwd=ROOT_DIR)
    assert raw == (ROOT_DIR / relative).read_bytes()
    contract = json.loads(raw)
    for entry in [*contract["source_entries"], {"path": relative}]:
        path = tmp_path / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(
            ["git", "show", f"{release}:{entry['path']}"], cwd=ROOT_DIR))
    monkeypatch.setattr(successor, "ROOT_DIR", tmp_path)
    verified = successor.old_source_digest_verification()
    assert verified["status"] == "VERIFIED"
    assert verified["artifact_digest"] == contract["artifact_digest"]
    assert verified["source_set_digest"] == contract["source_set_digest"]
    # Retain the fail-closed check: even one changed archived byte must fail.
    victim = tmp_path / contract["source_entries"][0]["path"]
    victim.write_bytes(victim.read_bytes() + b"\n")
    with pytest.raises(historical.M4V2BoundedOperationalForwardError,
                       match="bounded_forward_source_bytes_changed"):
        successor.old_source_digest_verification()


def test_refit_is_deterministic_and_reads_strictly_through_t_minus_one() -> None:
    source, preregistration = _frozen_preregistration()
    history = _history()
    history.extend(
        [
            ("2026097", date(2026, 8, 23), (1, 2, 3, 4, 5, 6)),
            ("2026098", date(2026, 8, 25), (7, 8, 9, 10, 11, 12)),
        ]
    )
    first = successor.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=history,
        target_issue="2026097",
    )
    second = successor.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=history,
        target_issue="2026097",
    )
    dataset, model = first
    assert first == second
    assert dataset["body"]["training_issue_count"] == 900
    assert dataset["body"]["training_end_issue"] < "2026097"
    assert all(row["issue"] < "2026097" for row in dataset["body"]["rows"])
    assert len(model["body"]["probabilities_q_1_to_33"]) == 33
    assert math.isclose(model["body"]["probability_sum"], 6.0, abs_tol=1e-12)
    assert model["body"]["hyperparameter_search"] == "NONE"
    assert model["body"]["model_selection"] == "NONE"


def test_predraw_seals_exact_100_plus_100_with_shared_blue_strategy() -> None:
    source, preregistration = _frozen_preregistration()
    _, model = successor.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=_history(),
        target_issue="2026097",
    )
    candidates, baseline, checkpoint, report = successor.generate_predraw_artifacts(
        preregistration=preregistration,
        model=model,
        target_draw_date=date(2026, 8, 23),
        sealed_at=datetime(2026, 8, 23, 12, tzinfo=successor.SHANGHAI),
    )
    assert candidates["body"]["candidate_count"] == 100
    assert baseline["body"]["candidate_count"] == 100
    assert len(candidates["body"]["tickets"]) == 100
    assert len(baseline["body"]["tickets"]) == 100
    assert [item["blue_number"] for item in candidates["body"]["tickets"]] == [
        item["blue_number"] for item in baseline["body"]["tickets"]
    ]
    assert checkpoint["body"]["status"] == "SEALED_BEFORE_DRAW"
    assert checkpoint["body"]["configuration_drift"] is False
    assert checkpoint["body"]["old_checkpoint_reused"] is False
    replay = successor.build_predraw_replay_artifact(
        model_candidates=candidates,
        random_baseline=baseline,
        checkpoint=checkpoint,
        report=report,
    )
    assert replay["body"]["registered_replay_status"] == (
        "REGISTERED_REPLAY_VERIFIED"
    )


def test_frozen_review_policy_emits_only_registered_decisions() -> None:
    source_digest = successor.load_source_contract()["artifact_digest"]
    cases = (
        (20, 0.20, None, "PASS_TO_P4"),
        (20, 0.06, None, "CONTINUE_TO_NEXT_LOOK"),
        (20, -0.20, None, "FAIL_NO_FORWARD_ADVANTAGE"),
        (20, 0.20, 1, "INVALID_FORWARD_EXECUTION"),
        (120, 0.01, None, "INCONCLUSIVE_AT_MAX_N"),
    )
    for look, gain, drift_at, expected in cases:
        artifact, decision = successor.build_review_artifact(
            look=look,
            settlements=_settlements(count=look, gain=gain, drift_at=drift_at),
            source_digest=source_digest,
        )
        assert decision == expected
        assert artifact["body"]["decision"] == expected
        assert artifact["body"]["formal_p4_ready"] is (expected == "PASS_TO_P4")


def test_p4_is_dormant_until_both_successor_pass_facts_exist() -> None:
    source_digest = successor.load_source_contract()["artifact_digest"]
    tasks = _builder().initial_tasks(
        source_digest=source_digest,
        target_issue="2026097",
        target_draw_date="2026-08-23",
    )
    p4 = next(
        item for item in tasks if item["task_key"] == successor.P4_TASK_KEY
    )
    dependencies = {
        item["target_key"] for item in p4["dependencies"] if item["dependency_type"] == "artifact"
    }
    assert dependencies == {
        successor.P4_PREREGISTRATION_FACT,
        successor.P3_COMPLETE_FACT,
        successor.PASS_TO_P4_FACT,
    }
    assert p4["requested_capability"] == successor.P4_CAPABILITY
    assert successor.P4_CAPABILITY not in successor.CAPABILITIES
