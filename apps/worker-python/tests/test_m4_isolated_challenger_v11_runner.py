from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.models import ControlPlaneManifest, TaskStatus

ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    path = ROOT / "apps/worker-python/scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_dry_run_has_exact_tasks_and_preregistration_ready() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = contract.render_context(source_max_issue="2026100")
    payload, dry_run = builder.build_manifest(
        context=context,
        source_digest="a" * 64,
        operator_configuration_authorized=False,
        simulation_events=False,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    snapshot = builder.ControlPlaneManifest.from_dict(payload)
    resolved = (
        __import__(
            "dehps.research_os.control_plane", fromlist=["ResearchOSControlPlane"]
        )
        .ResearchOSControlPlane()
        .resolve(snapshot)
    )
    assert len(manifest.tasks) == 42
    assert dry_run["task_count"] == 42
    assert dry_run["import_performed"] is False
    assert [item.task_key for item in resolved.ready_queue] == [
        "m4-isolated-24h-challenger-v11-preregistration"
    ]


def test_install_without_apply_is_non_mutating() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    result = runner.install(
        apply=False,
        context=contract.render_context(source_max_issue="2026100"),
        source_digest="a" * 64,
        operator_configuration_authorized=False,
    )
    assert result["status"] == "DRY_RUN"
    assert result["import_performed"] is False
    assert result["smtp_calls"] == 0
    assert result["formal_p3_mutated"] is False


def test_fact_builder_rejects_formal_route_or_promotion() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = contract.render_context(source_max_issue="2026100")
    payload, _ = builder.build_manifest(context=context, source_digest="a" * 64)
    for fact in (
        "m4-p3-illegal:COMPLETE",
        "successor:PASS_TO_P4",
        "successor:PASS_TO_P5",
        "PROMOTION:TRIGGERED",
    ):
        try:
            builder.manifest_with_facts(payload, add_artifact_facts=(fact,))
        except builder.IsolatedManifestError:
            pass
        else:
            raise AssertionError(f"forbidden fact accepted: {fact}")


def test_activation_compiles_delivery_only_from_registered_receipt(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(source_max_issue="2026100")
    delivery = contract.task_template_by_name("predraw_delivery")
    body = {
        "state": "SENT",
        "delivery_key": "1" * 64,
        "mail_kind": "PREDRAW_TOP100",
        "target_issue": context["target_issue"],
        "content_digest": "2" * 64,
        "recipient_set_digest": "3" * 64,
        "attempt_count": 1,
        "smtp_transaction_started_at": "2026-08-27T09:00:00+00:00",
        "smtp_data_accepted_at": "2026-08-27T09:00:01+00:00",
    }
    artifact_digest = "4" * 64
    monkeypatch.setattr(
        runner.mainline,
        "load_completed_task_artifacts",
        lambda **kwargs: (
            {
                "artifact_type": "M4IsolatedDeliveryReceiptV11",
                "artifact_digest": artifact_digest,
                "body": body,
            },
        ),
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params):
            self.statement = statement
            return self

        def fetchone(self):
            assert self.statement.startswith("SELECT")
            return (
                body["mail_kind"],
                body["content_digest"],
                body["recipient_set_digest"],
                body["state"],
                body["attempt_count"],
                artifact_digest,
            )

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self):
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    repository = _Repository()
    assert runner._activation_facts(
        task_key=delivery.key(context),
        template=delivery,
        context=context,
        repository=repository,
    ) == (f"{delivery.key(context)}:SENT",)
    prereg = contract.task_template_by_name("preregistration")
    assert runner._activation_facts(
        task_key=prereg.key(context),
        template=prereg,
        context=context,
        repository=repository,
    ) == (contract.FREEZE_FACT,)


def test_daily_and_predraw_absence_windows_are_fail_closed() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(source_max_issue="2026100")
    schedule = contract.schedule_for_issue(context["target_issue"])
    predraw_key = contract.task_template_by_name("predraw_delivery").key(context)
    start = schedule["predraw_send"]
    stop = datetime.combine(
        contract.issue_draw_date(context["target_issue"]),
        contract.OFFICIAL_DRAW_TIME,
        contract.TIMEZONE,
    )
    assert runner._delivery_absent(
        now=start + timedelta(minutes=1),
        scheduled=start,
        stop_at=stop,
        delivery_task_key=predraw_key,
        facts=set(),
    )
    assert not runner._delivery_absent(
        now=start + timedelta(minutes=1),
        scheduled=start,
        stop_at=stop,
        delivery_task_key=predraw_key,
        facts={f"{predraw_key}:SENT"},
    )
    assert not runner._delivery_absent(
        now=stop,
        scheduled=start,
        stop_at=stop,
        delivery_task_key=predraw_key,
        facts=set(),
    )

    daily = start.replace(hour=9, minute=0)
    daily_context = {**context, "epoch_date": daily.strftime("%Y%m%d")}
    daily_key = contract.task_template_by_name("daily_delivery").key(daily_context)
    assert not runner._delivery_absent(
        now=daily + timedelta(seconds=59),
        scheduled=daily,
        stop_at=daily + timedelta(days=1),
        delivery_task_key=daily_key,
        facts=set(),
    )
    assert runner._delivery_absent(
        now=daily + timedelta(minutes=1),
        scheduled=daily,
        stop_at=daily + timedelta(days=1),
        delivery_task_key=daily_key,
        facts=set(),
    )


def test_completed_activation_recovery_replays_without_workload(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(source_max_issue="2026100")
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest="a" * 64,
        operator_configuration_authorized=True,
        simulation_events=True,
    )
    original = ControlPlaneManifest.from_dict(payload)
    task = next(
        item
        for item in original.tasks
        if item.task_key
        == contract.task_template_by_name("preregistration").key(context)
    )
    manifest = type("Manifest", (), {})()
    manifest.tasks = [task]
    manifest.facts = type("Facts", (), {"artifacts": frozenset()})()
    manifest.task_state_by_digest = {
        task.artifact_digest: type(
            "State", (), {"declared_status": TaskStatus.COMPLETED}
        )()
    }

    imported: list[tuple[str, ...]] = []

    class _Repository:

        @staticmethod
        def load_manifest(*, control_plane_key):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            return manifest

        @staticmethod
        def list_mainline_execution_events(**_kwargs):
            return [{"event_type": "completed", "execution_id": "b" * 64}]

        def import_verified_facts(self, values):
            imported.append(tuple(values))

    calls: list[tuple[str, str]] = []
    class _Supervisor:
        def __init__(self, **_kwargs):
            pass

        def replay(self, *, task_key, execution_id):
            calls.append((task_key, execution_id))
            return {
                "status": "REPLAY_VERIFIED",
                "same_execution_identity": True,
                "same_artifact_identity": True,
                "same_artifact_content": True,
                "all_registrations_and_parent_chains_exact": True,
                "manual_input_assembly": False,
                "dispatch_performed": False,
            }

    repository = _Repository()
    monkeypatch.setattr(runner.mainline, "IsolatedChallengerSupervisor", _Supervisor)
    monkeypatch.setattr(runner, "_activation_present", lambda **_kwargs: False)
    monkeypatch.setattr(
        runner,
        "_activation_facts",
        lambda **_kwargs: (contract.FREEZE_FACT,),
    )
    recovered = runner._recover_completed_activations(
        repository=repository, source_digest="a" * 64
    )
    assert calls == [(task.task_key, "b" * 64)]
    assert imported == [(contract.FREEZE_FACT,)]
    assert recovered[0]["execution_id"] == "b" * 64


def test_single_and_18_worker_equivalence_binds_all_downstream_identities() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    configurations = runner.search.base_configurations(
        snapshot_digest="1" * 64,
        source_contract_digest="2" * 64,
    )
    jobs = runner.search.plan_batch(configurations, cursor=0)
    single = runner.search.execute_jobs(jobs, worker_count=1)
    parallel = runner.search.execute_jobs(jobs, worker_count=contract.WORKER_COUNT)
    single_bundle = runner._parallel_equivalence_bundle(
        single, target_issue="2026101"
    )
    parallel_bundle = runner._parallel_equivalence_bundle(
        parallel, target_issue="2026101"
    )
    assert single_bundle == parallel_bundle
    decoded = __import__("json").loads(single_bundle)
    assert len(decoded["candidate_results"]) == contract.ATTEMPTS_PER_BATCH
    assert len(decoded["candidate_order"]) == contract.ATTEMPTS_PER_BATCH
    assert len(decoded["top100"]) == contract.PORTFOLIO_SIZE
    assert all(
        len(decoded[field]) == 64
        for field in ("checkpoint_digest", "artifact_digest", "replay_digest")
    )


def test_service_outer_bound_keeps_mail_windows_recoverable() -> None:
    service = (
        ROOT / "infra/systemd/dehps-m4-isolated-24h-challenger-v11.service"
    ).read_text(encoding="utf-8")
    migration = (
        ROOT / "infra/postgres/migrations/003_m4_isolated_24h_challenger_v11.sql"
    ).read_text(encoding="utf-8")
    assert "TimeoutStartSec=1h45min" in service
    assert "CPUQuota=1800%" in service
    assert "MemoryMax=24G" in service
    assert "CREATE TRIGGER delivery_ledger_append_only" in migration
    assert "CREATE TRIGGER schema_identity_append_only" in migration
    assert "CREATE TRIGGER registered_inputs_append_only" in migration


def test_database_schema_attestation_is_exact_and_idempotent() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    commit = "a" * 40
    expected = (
        contract.DATABASE_SCHEMA_VERSION,
        contract.CONTRACT_DIGEST,
        commit,
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            if statement.startswith("INSERT"):
                assert params == expected
            else:
                assert statement.startswith("SELECT")
                assert params is None
            return self

        @staticmethod
        def fetchone():
            return expected

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    assert runner._attest_database_schema(
        repository=_Repository(), git_commit=commit
    ) == {
        "schema_version": contract.DATABASE_SCHEMA_VERSION,
        "contract_digest": contract.CONTRACT_DIGEST,
        "installed_git_commit": commit,
    }
