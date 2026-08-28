from __future__ import annotations

import hashlib
import importlib.util
import itertools
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from dehps.config import ROOT_DIR
from dehps.notifications import p3_top100 as notification
from dehps.notifications.mail import MailDeliveryReceipt, QqMailConfig
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as p3,
)
from dehps.research_os.models import ControlPlaneManifest, Task
from pydantic import SecretStr

ISSUE = "2026100"
RECIPIENT = "reader@example.com"
RECIPIENT_DIGEST = notification._recipient_digest(RECIPIENT)
SOURCE_DIGEST = "f" * 64


def _builder():
    path = (
        ROOT_DIR
        / "apps/worker-python/scripts/build_m4_p3_top100_notification_manifest.py"
    )
    spec = importlib.util.spec_from_file_location("p3_top100_builder_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runner():
    path = ROOT_DIR / "apps/worker-python/scripts/run_m4_p3_top100_notification.py"
    spec = importlib.util.spec_from_file_location("p3_top100_runner_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _predraw_bundle() -> notification.PredrawBundle:
    rows = list(itertools.islice(itertools.combinations(range(1, 34), 6), 100))
    candidates = p3._artifact(
        artifact_type=p3.MODEL_CANDIDATE_ARTIFACT_TYPE,
        body={
            "mode": "SHADOW_ONLY",
            "target_issue": ISSUE,
            "candidate_count": 100,
            "tickets": [
                {
                    "rank": rank,
                    "lex_id": rank,
                    "red_numbers": list(row),
                    "blue_number": 1 + ((rank - 1) % 16),
                    "model_log2_score": -float(rank),
                }
                for rank, row in enumerate(rows, start=1)
            ],
        },
        parent_digests=("1" * 64,),
    )
    baseline = p3._artifact(
        artifact_type=p3.RANDOM_BASELINE_ARTIFACT_TYPE,
        body={"mode": "SHADOW_ONLY", "target_issue": ISSUE, "candidate_count": 100},
        parent_digests=("2" * 64,),
    )
    checkpoint = p3._artifact(
        artifact_type=p3.CHECKPOINT_ARTIFACT_TYPE,
        body={
            "status": "SEALED_BEFORE_DRAW",
            "lineage_id": p3.LINEAGE_ID,
            "target_issue": ISSUE,
            "model_candidate_digest": candidates["artifact_digest"],
            "configuration_drift": False,
            "sealed_at": "2026-08-25T16:30:00+08:00",
            "official_draw_time": "2026-08-25T21:15:00+08:00",
        },
        parent_digests=(candidates["artifact_digest"],),
    )
    report = p3._artifact(
        artifact_type=p3.PREDRAW_REPORT_ARTIFACT_TYPE,
        body={"status": "PUBLISHED", "target_issue": ISSUE},
        parent_digests=(checkpoint["artifact_digest"],),
    )
    replay = p3._artifact(
        artifact_type=p3.PREDRAW_REPLAY_ARTIFACT_TYPE,
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "target_issue": ISSUE,
            "configuration_drift": False,
        },
        parent_digests=(
            candidates["artifact_digest"],
            baseline["artifact_digest"],
            checkpoint["artifact_digest"],
            report["artifact_digest"],
        ),
    )
    return notification.PredrawBundle(
        ISSUE, candidates, baseline, checkpoint, report, replay
    )


def _postdraw_bundle() -> notification.PostdrawBundle:
    predraw = _predraw_bundle()
    settlement = p3._artifact(
        artifact_type=p3.SETTLEMENT_ARTIFACT_TYPE,
        body={
            "status": "SETTLED",
            "lineage_id": p3.LINEAGE_ID,
            "target_issue": ISSUE,
            "actual_red_numbers": [1, 2, 3, 4, 5, 6],
            "actual_blue_number": 7,
            "configuration_drift": False,
            "ticket_support_decision_credit": False,
        },
        parent_digests=(predraw.model_candidates["artifact_digest"],),
    )
    replay = p3._artifact(
        artifact_type=p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE,
        body={
            "status": "REPLAY_VERIFIED",
            "registered_replay_status": "REGISTERED_REPLAY_VERIFIED",
            "target_issue": ISSUE,
        },
        parent_digests=(
            settlement["artifact_digest"],
            predraw.checkpoint["artifact_digest"],
        ),
    )
    return notification.PostdrawBundle(predraw, settlement, replay)


def _raw_payout(*, tier_one: str = "10000000", tier_two: str = "264245"):
    amounts = (tier_one, tier_two, "3000", "200", "10", "5")
    return {
        "issue": ISSUE,
        "frontWinningNum": "01 02 03 04 05 06",
        "backWinningNum": "07",
        "winnerDetails": [
            {
                "awardEtc": tier,
                "baseBetWinner": {"awardMoney": amount, "awardNum": tier * 10},
            }
            for tier, amount in enumerate(amounts, start=1)
        ],
    }


def test_pre_envelope_has_exact_100_red_blue_tickets_and_200_cny() -> None:
    envelope = notification.build_pre_envelope(
        bundle=_predraw_bundle(), recipient_digest=RECIPIENT_DIGEST
    )

    assert envelope["body"]["candidate_count"] == 100
    assert envelope["body"]["unit_cost_cny"] == "2.00"
    assert envelope["body"]["hypothetical_total_cost_cny"] == "200.00"
    assert envelope["body"]["text"].count("单注 ¥2.00") == 100
    assert "蓝球" in envelope["body"]["text"]
    assert "税前中奖总额：待开奖" in envelope["body"]["text"]
    expected = notification.build_pre_envelope(
        bundle=_predraw_bundle(), recipient_digest=RECIPIENT_DIGEST
    )
    replay = notification.build_pre_replay(envelope=envelope, expected=expected)
    assert replay["body"] == {
        "status": "REPLAY_VERIFIED",
        "issue": ISSUE,
        "same_registered_content": True,
        "smtp_connected": False,
        "delivery_eligible": True,
    }


@pytest.mark.parametrize(
    ("red_hits", "blue_hit", "tier"),
    (
        (6, True, 1),
        (6, False, 2),
        (5, True, 3),
        (5, False, 4),
        (4, True, 4),
        (4, False, 5),
        (3, True, 5),
        (2, True, 6),
        (0, True, 6),
        (3, False, 0),
    ),
)
def test_exact_ssq_prize_tiers(red_hits: int, blue_hit: bool, tier: int) -> None:
    assert notification.prize_tier(red_hits=red_hits, blue_hit=blue_hit) == tier


def test_tax_is_free_through_10000_and_full_gross_taxed_above() -> None:
    assert notification.calculate_return(Decimal("10000.00")) == {
        "hypothetical_cost_cny": "200.00",
        "gross_prize_cny": "10000.00",
        "estimated_tax_cny": "0.00",
        "after_tax_receipt_cny": "10000.00",
        "net_profit_cny": "9800.00",
        "roi_percent": "4900.00",
    }
    assert notification.calculate_return(Decimal("10000.01")) == {
        "hypothetical_cost_cny": "200.00",
        "gross_prize_cny": "10000.01",
        "estimated_tax_cny": "2000.00",
        "after_tax_receipt_cny": "8000.01",
        "net_profit_cny": "7800.01",
        "roi_percent": "3900.01",
    }


def test_post_report_uses_exact_issue_payout_and_exposes_all_money_labels() -> None:
    bundle = _postdraw_bundle()
    payout = notification.normalize_payout_record(record=_raw_payout(), bundle=bundle)
    report = notification.build_post_report(
        bundle=bundle, payout=payout, recipient_digest=RECIPIENT_DIGEST
    )

    assert [item["single_ticket_gross_cny"] for item in payout["body"]["tiers"]] == [
        "10000000.00",
        "264245.00",
        "3000.00",
        "200.00",
        "10.00",
        "5.00",
    ]
    assert (
        sum(report["body"]["tier_counts"].values()) + report["body"]["losing_count"]
        == 100
    )
    for label in (
        "模拟投入",
        "税前中奖总额",
        "预计应纳税额",
        "预计税后到账",
        "扣除200元后的净收益",
        "回报率",
    ):
        assert label in report["body"]["text"]
    assert "¥10,000.00" in report["body"]["text"]
    assert report["body"]["p3_decision_credit"] is False
    expected = notification.build_post_report(
        bundle=bundle, payout=payout, recipient_digest=RECIPIENT_DIGEST
    )
    assert (
        notification.build_post_replay(report=report, expected=expected)["body"][
            "delivery_eligible"
        ]
        is True
    )


def test_payout_rejects_fixed_tier_or_draw_drift() -> None:
    bundle = _postdraw_bundle()
    wrong_fixed = _raw_payout()
    wrong_fixed["winnerDetails"][4]["baseBetWinner"]["awardMoney"] = "11"
    with pytest.raises(notification.P3Top100NotificationError, match="fixed_prize"):
        notification.normalize_payout_record(record=wrong_fixed, bundle=bundle)

    wrong_issue = _raw_payout()
    wrong_issue["issue"] = "2026101"
    with pytest.raises(notification.P3Top100NotificationError, match="draw_identity"):
        notification.normalize_payout_record(record=wrong_issue, bundle=bundle)


def test_pre_window_is_exact_draw_day_17_to_2115() -> None:
    official = "2026-08-25T21:15:00+08:00"
    assert (
        notification.require_pre_draw_window(
            datetime.fromisoformat("2026-08-25T17:00:00+08:00"),
            official_draw_time=official,
        ).hour
        == 17
    )
    for value in (
        "2026-08-25T16:59:59+08:00",
        "2026-08-25T21:15:00+08:00",
        "2026-08-24T17:00:00+08:00",
    ):
        with pytest.raises(
            notification.P3Top100NotificationError, match="window_closed"
        ):
            notification.require_pre_draw_window(
                datetime.fromisoformat(value), official_draw_time=official
            )


def test_builder_projects_goal_ready_queue_then_replay_dependency_wait() -> None:
    build = _builder()
    initial = build.build_initial_manifest(
        minimum_issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
    )
    envelope = notification.build_pre_envelope(
        bundle=_predraw_bundle(), recipient_digest=RECIPIENT_DIGEST
    )
    payload, dry_run = build.add_pre_tasks(
        initial,
        issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
        predraw_input_digests=_predraw_bundle().input_digests,
        envelope_digest=envelope["artifact_digest"],
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    statuses = {item.task_key: item.status.value for item in snapshot.resolutions}
    keys = notification.issue_task_keys(ISSUE)

    assert dry_run["new_task_keys"] == sorted([keys["pre"], keys["pre_replay"]])
    assert statuses[keys["pre"]] == "ready"
    assert statuses[keys["pre_replay"]] == "dependency_wait"
    assert [item.task_key for item in snapshot.ready_queue] == [keys["pre"]]


def test_notification_runtime_uses_only_additive_v3_control_identities() -> None:
    assert notification.CONTROL_PLANE_KEY == "m4-p3-top100-notification-v3"
    assert notification.GOAL_KEY == "M4_P3_TOP100_REPLAY_BOUND_MAIL_AND_RETURN_V3"
    assert notification.SOURCE_CONTRACT_PATH.endswith(
        "m4-p3-top100-notification-source-v3.json"
    )
    assert notification.MINIMUM_ISSUE == "2026100"
    assert set(notification.CAPABILITIES) == {
        "p3_top100_pre_mail_envelope_v3",
        "p3_top100_pre_mail_replay_v3",
        "p3_top100_post_return_report_v3",
        "p3_top100_post_return_replay_v3",
    }
    assert all(
        "notification-v3-" in key
        for key in notification.issue_task_keys(ISSUE).values()
    )


def test_v3_source_contract_is_exact_and_p3_science_is_unmodified() -> None:
    source = notification.load_source_contract(root_dir=ROOT_DIR)
    assert source["artifact_digest"] == (
        "9831490a024664a5023c88d660d8d7c4be2e06be5db3456834ff65abf86d2b82"
    )
    assert source["source_set_digest"] == (
        "cde3c689057e7c5110f8e9fa3f5dbb75c00229cc24d2d9d69c8a9100531db7d0"
    )
    assert source["governance_bindings"] == {
        "research_request_id": 675,
        "research_approval_decision_id": 2852,
        "research_payload_sha256": (
            "31776e8dcf25177dd66505a2a9a4b1c7c092c37d50e3f8623644eb650b54f0c3"
        ),
        "engineering_request_id": 800,
        "engineering_approval_decision_id": 3404,
        "engineering_execution_id": 642,
        "engineering_payload_sha256": (
            "7989380318cda6afb9b44950ae79a295a15e790a99b6731e43cd38ca6071660a"
        ),
        "p3_lineage_id": "M4_P3_FORWARD_PREQUENTIAL_CONFIRMATORY_SUCCESSOR_V1",
        "p3_scientific_lineage_modified": False,
        "production_authorized": False,
    }


def test_v1_and_v2_source_contracts_remain_immutable_history() -> None:
    expected = {
        "configs/research-os/m4-p3-top100-notification-source-v1.json": (
            "c58be56d50f2041d17ccdf00480538b8749a6a28840f11224aa5d7834bd1e509"
        ),
        "configs/research-os/m4-p3-top100-notification-source-v2.json": (
            "f3633801ed8686ceb7dbe1d8ffca616b92cde296122bdfff03d733601d20ec9b"
        ),
    }
    for relative, digest in expected.items():
        path = ROOT_DIR / relative
        assert path.is_file() and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_runner_installs_only_v3_from_issue_2026100_without_delivery(
    monkeypatch,
) -> None:
    runner = _runner()
    imported: dict = {}

    class _MissingManifest(Exception):
        pass

    class _Repository:
        def ensure_schema(self):
            return None

        def load_manifest(self, *, control_plane_key):
            assert control_plane_key == notification.CONTROL_PLANE_KEY
            raise _MissingManifest

        def import_manifest(self, *, control_plane_key, payload, source):
            assert control_plane_key == "m4-p3-top100-notification-v3"
            assert payload["goals"][0]["goal_key"] == notification.GOAL_KEY
            assert payload["tasks"] == []
            assert "v3-install" in source
            imported.update(
                {"control_plane_key": control_plane_key, "payload": payload}
            )
            return "IMPORTED"

    monkeypatch.setattr(runner, "ResearchOSValidationError", _MissingManifest)
    monkeypatch.setattr(runner, "AgentRequestRepository", lambda: object())
    monkeypatch.setattr(runner.notification, "verify_governance", lambda _repo: None)
    output = runner.install(
        apply=True,
        repository=_Repository(),
        config=_mail_config(),
    )

    assert output["status"] == "INSTALLED"
    assert output["minimum_issue"] == "2026100"
    assert output["dispatch_performed"] is False
    assert output["external_delivery"] is False
    assert imported["control_plane_key"] == notification.CONTROL_PLANE_KEY
    assert "notification-v1" not in repr(imported)
    assert "notification-v2" not in repr(imported)


def test_v3_builder_rejects_noncanonical_or_historical_activation_issue() -> None:
    build = _builder()
    for minimum_issue in ("2026099", "2026101"):
        with pytest.raises(
            (notification.P3Top100NotificationError, build.P3Top100ManifestError)
        ):
            build.build_initial_manifest(
                minimum_issue=minimum_issue,
                recipient_digest=RECIPIENT_DIGEST,
                source_digest=SOURCE_DIGEST,
            )


def test_v3_additive_builder_and_runner_reject_tampered_live_minimum() -> None:
    build = _builder()
    runner = _runner()
    initial = ControlPlaneManifest.from_dict(
        build.build_initial_manifest(
            minimum_issue=notification.MINIMUM_ISSUE,
            recipient_digest=RECIPIENT_DIGEST,
            source_digest=SOURCE_DIGEST,
        )
    ).to_dict(include_digest=False)
    target = dict(initial["goals"][0]["target_metric_manifest"])
    target["minimum_issue"] = "2026099"
    initial["goals"][0]["target_metric_manifest"] = target

    with pytest.raises(build.P3Top100ManifestError, match="goal_binding_changed"):
        build._assert_goal_identity(
            initial,
            recipient_digest=RECIPIENT_DIGEST,
            source_digest=SOURCE_DIGEST,
        )

    class _Repository:
        def load_manifest(self, *, control_plane_key):
            assert control_plane_key == notification.CONTROL_PLANE_KEY
            return ControlPlaneManifest.from_dict(initial)

    with pytest.raises(runner.P3Top100RunnerError, match="goal target changed"):
        runner._goal_target(_Repository())


def test_v3_capability_and_registered_delivery_reject_historical_issue(
    monkeypatch,
) -> None:
    build = _builder()
    bundle = _predraw_bundle()
    envelope = notification.build_pre_envelope(
        bundle=bundle, recipient_digest=RECIPIENT_DIGEST
    )
    initial = build.build_initial_manifest(
        minimum_issue=notification.MINIMUM_ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
    )
    payload, _ = build.add_pre_tasks(
        initial,
        issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
        predraw_input_digests=bundle.input_digests,
        envelope_digest=envelope["artifact_digest"],
    )
    task = next(
        item
        for item in ControlPlaneManifest.from_dict(payload).tasks
        if item.task_key == notification.issue_task_keys(ISSUE)["pre"]
    )
    historical_payload = task.to_dict()
    historical_payload["task_key"] = "m4-p3-top100-notification-v3-2026099-pre-envelope"
    historical_payload["metric_contract"]["issue"] = "2026099"
    historical = Task.from_dict(
        historical_payload, goal_digest=historical_payload["goal_digest"]
    )
    monkeypatch.setattr(
        notification,
        "load_source_contract",
        lambda **_kwargs: {"artifact_digest": SOURCE_DIGEST},
    )
    monkeypatch.setattr(notification, "verify_governance", lambda _repo: None)

    with pytest.raises(
        notification.P3Top100NotificationError,
        match="precedes_v3_activation",
    ):
        notification.P3Top100NotificationCapability(repository=object()).execute(
            control_plane_key=notification.CONTROL_PLANE_KEY,
            task=historical,
            execution_id="e" * 64,
            git_commit="a" * 40,
        )
    with pytest.raises(
        notification.P3Top100NotificationError,
        match="precedes_v3_activation",
    ):
        notification.registered_delivery_email(
            object(),
            issue="2026099",
            kind="post",
            recipient=RECIPIENT,
        )


def test_v3_runner_never_dispatches_live_shaped_v1_or_v2_tasks(monkeypatch) -> None:
    runner = _runner()
    calls: list[str] = []

    class _Supervisor:
        def __init__(self, *, repository):
            assert repository is not None

        def run_once(self, *, task_key):
            calls.append(task_key)
            raise AssertionError("legacy task must not dispatch")

        def replay(self, *, task_key):
            calls.append(task_key)
            raise AssertionError("legacy task must not replay")

    class _Repository:
        control_plane = None

        def __init__(self):
            self.control_plane = self

        def load_manifest(self, *, control_plane_key):
            assert control_plane_key == notification.CONTROL_PLANE_KEY
            return object()

        def resolve(self, manifest):
            assert manifest is not None
            return SimpleNamespace(
                resolutions=[
                    SimpleNamespace(
                        task_key=f"m4-p3-top100-notification-v{version}-2026099-post-return-report",
                        status=SimpleNamespace(value="ready"),
                    )
                    for version in (1, 2)
                ]
            )

    monkeypatch.setattr(
        runner.notification, "P3Top100NotificationSupervisor", _Supervisor
    )
    with pytest.raises(runner.P3Top100RunnerError, match="not Ready"):
        runner._run_exact_tasks(
            _Repository(),
            task_keys=tuple(notification.issue_task_keys(ISSUE).values())[:2],
        )
    assert calls == []


def test_capability_compiles_only_exact_pre_task(monkeypatch) -> None:
    build = _builder()
    bundle = _predraw_bundle()
    envelope = notification.build_pre_envelope(
        bundle=bundle, recipient_digest=RECIPIENT_DIGEST
    )
    initial = build.build_initial_manifest(
        minimum_issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
    )
    payload, _ = build.add_pre_tasks(
        initial,
        issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
        predraw_input_digests=bundle.input_digests,
        envelope_digest=envelope["artifact_digest"],
    )
    task = next(
        item
        for item in ControlPlaneManifest.from_dict(payload).tasks
        if item.task_key == notification.issue_task_keys(ISSUE)["pre"]
    )
    monkeypatch.setattr(
        notification, "load_predraw_bundle", lambda *args, **kwargs: bundle
    )
    monkeypatch.setattr(
        notification,
        "load_source_contract",
        lambda **kwargs: {"artifact_digest": SOURCE_DIGEST},
    )
    monkeypatch.setattr(notification, "verify_governance", lambda repository: None)
    result = notification.P3Top100NotificationCapability(repository=object()).execute(
        control_plane_key=notification.CONTROL_PLANE_KEY,
        task=task,
        execution_id="e" * 64,
        git_commit="a" * 40,
    )
    assert len(result.artifacts) == 1
    assert result.artifacts[0].payload == envelope
    assert result.completion_facts == (notification.issue_facts(ISSUE)["pre"],)
    assert dict(result.execution_metadata)["external_delivery"] is False


def test_notification_supervisor_has_only_exact_capabilities_and_own_status(
    tmp_path,
) -> None:
    manifest = ControlPlaneManifest.from_dict(
        _builder().build_initial_manifest(
            minimum_issue=ISSUE,
            recipient_digest=RECIPIENT_DIGEST,
            source_digest=SOURCE_DIGEST,
        )
    )
    snapshot = ResearchOSControlPlane().resolve(manifest)
    supervisor = notification.P3Top100NotificationSupervisor(
        repository=object(), root_dir=tmp_path, require_clean_tree=False
    )
    projected = supervisor._build_lane_status(
        manifest, snapshot=snapshot, dispatch_performed=False
    )

    assert tuple(supervisor.capabilities) == notification.CAPABILITIES
    assert projected["control_plane_key"] == notification.CONTROL_PLANE_KEY
    assert projected["ready_queue"] == []
    assert projected["next_ready_task"] is None
    assert projected["p3_dispatch_allowed"] is False
    assert projected["p4_dispatch_allowed"] is False
    assert projected["p5_dispatch_allowed"] is False
    assert projected["unkeyed_dispatch_allowed"] is False


def test_notification_status_projects_first_ready_task_and_partial_recovery(
    tmp_path,
) -> None:
    build = _builder()
    bundle = _predraw_bundle()
    envelope = notification.build_pre_envelope(
        bundle=bundle, recipient_digest=RECIPIENT_DIGEST
    )
    initial = build.build_initial_manifest(
        minimum_issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
    )
    payload, _ = build.add_pre_tasks(
        initial,
        issue=ISSUE,
        recipient_digest=RECIPIENT_DIGEST,
        source_digest=SOURCE_DIGEST,
        predraw_input_digests=bundle.input_digests,
        envelope_digest=envelope["artifact_digest"],
    )
    supervisor = notification.P3Top100NotificationSupervisor(
        repository=object(), root_dir=tmp_path, require_clean_tree=False
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    keys = notification.issue_task_keys(ISSUE)
    projected = supervisor._build_lane_status(
        manifest, snapshot=snapshot, dispatch_performed=False
    )

    assert projected["ready_queue"] == [keys["pre"]]
    assert projected["next_ready_task"] == keys["pre"]

    completed_payload = manifest.to_dict(include_digest=False)
    pre_task = next(
        item for item in completed_payload["tasks"] if item["task_key"] == keys["pre"]
    )
    pre_task["status"] = "completed"
    pre_task["completion_classification"] = "COMPLETE"
    completed_payload["facts"]["artifacts"].append(
        notification.issue_facts(ISSUE)["pre"]
    )
    completed_payload["facts"]["artifacts"].append(
        "mainline-execution:"
        f"{keys['pre']}:"
        f"{next(item for item in manifest.tasks if item.task_key == keys['pre']).artifact_digest}:"
        f"{'e' * 64}:completed"
    )
    completed_manifest = ControlPlaneManifest.from_dict(completed_payload)
    completed_snapshot = ResearchOSControlPlane().resolve(completed_manifest)
    recovered = supervisor._build_lane_status(
        completed_manifest,
        snapshot=completed_snapshot,
        dispatch_performed=False,
    )

    assert recovered["ready_queue"] == [keys["pre_replay"]]
    assert recovered["next_ready_task"] == keys["pre_replay"]


def test_runner_replays_completed_envelope_then_runs_ready_replay(monkeypatch) -> None:
    runner = _runner()
    keys = notification.issue_task_keys(ISSUE)

    class _Repository:
        def __init__(self) -> None:
            self.control_plane = self
            self.statuses = {keys["pre"]: "completed", keys["pre_replay"]: "ready"}

        def load_manifest(self, *, control_plane_key):
            assert control_plane_key == notification.CONTROL_PLANE_KEY
            return object()

        def resolve(self, manifest):
            assert manifest is not None
            return SimpleNamespace(
                resolutions=[
                    SimpleNamespace(
                        task_key=task_key,
                        status=SimpleNamespace(value=status),
                    )
                    for task_key, status in self.statuses.items()
                ]
            )

    repository = _Repository()
    calls = {"run": [], "replay": []}

    class _Supervisor:
        def __init__(self, *, repository):
            self.repository = repository

        def replay(self, *, task_key):
            calls["replay"].append(task_key)
            return {"status": "REPLAY_VERIFIED", "task_key": task_key}

        def run_once(self, *, task_key):
            calls["run"].append(task_key)
            self.repository.statuses[task_key] = "completed"
            return {
                "execution_id": "e" * 64,
                "execution_artifact_digest": "a" * 64,
            }

    monkeypatch.setattr(
        runner.notification, "P3Top100NotificationSupervisor", _Supervisor
    )
    output = runner._run_exact_tasks(
        repository, task_keys=(keys["pre"], keys["pre_replay"])
    )

    assert calls == {
        "run": [keys["pre_replay"]],
        "replay": [keys["pre"], keys["pre_replay"]],
    }
    assert [item["status"] for item in output] == [
        "ALREADY_COMPLETED",
        "REPLAY_VERIFIED",
    ]


class _RecordingMail:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def send(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("ambiguous smtp")
        return MailDeliveryReceipt("<id@example.com>", "sender@example.com", RECIPIENT)


def _email() -> notification.NotificationEmail:
    return notification.NotificationEmail(
        kind="pre",
        issue=ISSUE,
        artifact_digest="a" * 64,
        replay_digest="b" * 64,
        recipient_digest=RECIPIENT_DIGEST,
        subject="subject",
        text="text",
        html="<p>text</p>",
    )


def _mail_config() -> QqMailConfig:
    return QqMailConfig(
        address="sender@example.com",
        authorization_code=SecretStr("secret"),
        recipient=RECIPIENT,
    )


def test_delivery_ledger_is_idempotent_and_uncertainty_never_retries(tmp_path) -> None:
    ledger = notification.P3Top100DeliveryLedger(tmp_path / "ledger.json")
    mail = _RecordingMail()
    service = notification.P3Top100NotificationDeliveryService(
        _mail_config(), mail_service=mail, ledger=ledger
    )
    assert service.deliver(_email())["status"] == "SENT"
    assert service.deliver(_email())["status"] == "ALREADY_SENT"
    assert mail.calls == 1

    uncertain_ledger = notification.P3Top100DeliveryLedger(tmp_path / "uncertain.json")
    failing = _RecordingMail(fail=True)
    uncertain = notification.P3Top100NotificationDeliveryService(
        _mail_config(), mail_service=failing, ledger=uncertain_ledger
    )
    with pytest.raises(RuntimeError, match="ambiguous smtp"):
        uncertain.deliver(_email())
    with pytest.raises(notification.P3Top100DeliveryStateError, match="uncertain"):
        uncertain.deliver(_email())
    assert failing.calls == 1


def test_deployed_unit_sources_keep_exact_schedules_and_runner_boundaries() -> None:
    pre_timer = (
        ROOT_DIR / "deploy/systemd/dehps-p3-top100-pre-draw-mail.timer"
    ).read_text()
    post_timer = (
        ROOT_DIR / "deploy/systemd/dehps-p3-top100-post-draw-mail.timer"
    ).read_text()
    pre_service = (
        ROOT_DIR / "deploy/systemd/dehps-p3-top100-pre-draw-mail.service"
    ).read_text()
    post_service = (
        ROOT_DIR / "deploy/systemd/dehps-p3-top100-post-draw-mail.service"
    ).read_text()

    assert "OnCalendar=Tue,Thu,Sun *-*-* 17:00:00 Asia/Shanghai" in pre_timer
    assert "OnUnitActiveSec=15min" in post_timer
    assert " pre --apply --deliver" in pre_service
    assert " post --apply --deliver" in post_service
    assert "ReadWritePaths=/home/ark/workspace/dehps/runtime" in pre_service
    assert "ReadWritePaths=/home/ark/workspace/dehps/runtime" in post_service
    assert "static_100" not in pre_service + post_service


def test_source_contract_is_bound_and_excludes_frozen_p3_sources() -> None:
    source = notification.load_source_contract()
    paths = {item["path"] for item in source["source_entries"]}
    frozen = {
        "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/forward_prequential_confirmatory.py",
        "apps/worker-python/scripts/build_m4_p3_forward_prequential_confirmatory_manifest.py",
        "apps/worker-python/scripts/run_m4_p3_forward_prequential_confirmatory.py",
        "apps/worker-python/dehps/research_os/information_theory/measurement_system_v2/marginal_static_contract.py",
        "apps/worker-python/dehps/prediction/v2/generator.py",
        "deploy/systemd/dehps-forward-prequential-successor.service",
        "deploy/systemd/dehps-forward-prequential-successor.timer",
    }
    assert paths.isdisjoint(frozen)
    assert source["governance_bindings"]["research_request_id"] == 675
    assert source["governance_bindings"]["engineering_request_id"] == 800
    assert source["governance_bindings"]["engineering_approval_decision_id"] == 3404
    assert source["governance_bindings"]["engineering_execution_id"] == 642
