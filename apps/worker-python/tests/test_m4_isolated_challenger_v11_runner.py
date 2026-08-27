from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
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


def _context():
    return contract.render_context(
        source_max_issue="2026100", source_max_draw_date="2026-08-30"
    )


def test_manifest_dry_run_has_exact_tasks_and_preregistration_ready() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = _context()
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
        context=_context(),
        source_digest="a" * 64,
        operator_configuration_authorized=False,
    )
    assert result["status"] == "DRY_RUN"
    assert result["import_performed"] is False
    assert result["smtp_calls"] == 0
    assert result["formal_p3_mutated"] is False


def test_install_apply_returns_imported_manifest_digest(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    manifest_digest = "b" * 64
    payload = {"manifest_digest": manifest_digest}
    monkeypatch.setattr(
        runner.builder,
        "build_bootstrap_manifest",
        lambda **_kwargs: (payload, {"status": "DRY_RUN"}),
    )

    class _Repository:
        def __init__(self, **_kwargs):
            self.imported = None

        def ensure_schema(self):
            return None

        def import_bootstrap_manifest(self, manifest):
            kwargs = {"payload": manifest}
            self.imported = kwargs
            return "imported", manifest["manifest_digest"]

    monkeypatch.setattr(runner, "IsolatedChallengerRepository", _Repository)
    monkeypatch.setattr(
        runner,
        "_attest_database_schema",
        lambda **_kwargs: {
            "schema_version": contract.DATABASE_SCHEMA_VERSION,
            "contract_digest": contract.CONTRACT_DIGEST,
            "installed_git_commit": "c" * 40,
        },
    )
    monkeypatch.setattr(
        runner.artifacts,
        "load_source_contract",
        lambda **_kwargs: {"artifact_digest": "a" * 64},
    )
    monkeypatch.setattr(
        runner.mainline,
        "build_registered_input",
        lambda **_kwargs: {"artifact_digest": "d" * 64},
    )
    registered = iter(({"artifact_digest": "a" * 64}, {"artifact_digest": "d" * 64}))
    monkeypatch.setattr(
        runner.mainline,
        "register_input_artifact",
        lambda **_kwargs: next(registered),
    )

    result = runner.install(
        apply=True,
        context=_context(),
        source_digest="a" * 64,
        operator_configuration_authorized=True,
        git_commit="c" * 40,
    )

    assert result["status"] == "IMPORTED"
    assert result["manifest_digest"] == manifest_digest
    assert result["import_result"] == "imported"
    assert result["smtp_calls"] == 0
    assert result["workloads"] == 0
    assert result["formal_p3_mutated"] is False


def _bootstrap_rebind_fixture(runner):
    current_context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        projection_time="2026-08-30T16:00:00+08:00",
    )
    incoming_context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        projection_time="2026-08-30T16:30:00+08:00",
    )
    predecessor_payload, _ = runner.builder.build_bootstrap_manifest(
        context=current_context,
        source_digest=runner.PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST,
        operator_configuration_authorized=True,
    )
    incoming_payload, _ = runner.builder.build_bootstrap_manifest(
        context=incoming_context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    return (
        current_context,
        incoming_context,
        ControlPlaneManifest.from_dict(predecessor_payload),
        incoming_payload,
    )


def _bootstrap_rebind_repository(runner, *, current, context, events=()):
    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            if "SELECT current_manifest_digest" in statement:
                self.result = {"current_manifest_digest": current.artifact_digest}
            elif "SELECT manifest_json" in statement:
                self.result = {
                    "manifest_json": current.to_dict(include_digest=True)
                }
            else:
                raise AssertionError(statement)
            return self

        def fetchone(self):
            return self.result

    class _Repository(runner.IsolatedChallengerRepository):
        def __init__(self):
            self.context = dict(context)
            self.source_digest = "f" * 64
            self._fact_gate = None
            self._definition_gate = None
            self._bootstrap_rebind_gate = None
            self.current = current

        def load_manifest(self, *, control_plane_key):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            return self.current

        def list_mainline_execution_event_metadata(self, **_kwargs):
            return tuple(events)

        def import_manifest(self, *, control_plane_key, payload, source="native"):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            assert source in {
                "native",
                "m4-isolated-24h-challenger-v11-operator-install",
                "m4-isolated-24h-challenger-v11-exact-bootstrap-rebind",
            }
            incoming = ControlPlaneManifest.from_dict(payload)
            self._verify_exact_transition(incoming)
            self._verify_mainline_completion_records(
                _Cursor(),
                control_plane_key=control_plane_key,
                manifest=incoming,
            )
            self.current = incoming
            return "imported"

    return _Repository()


def test_repository_rebinds_only_exact_unexecuted_predecessor_bootstrap() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(
        runner
    )
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )

    result, digest = repository.import_bootstrap_manifest(incoming_payload)

    assert result == "imported"
    assert digest == repository.current.artifact_digest
    assert digest != ControlPlaneManifest.from_dict(incoming_payload).artifact_digest
    assert repository._bootstrap_rebind_gate is None
    assert all(
        state.declared_status is TaskStatus.DRAFT
        for state in repository.current.task_states
    )


@pytest.mark.parametrize("corruption", ["state", "fact", "event", "source"])
def test_repository_bootstrap_rebind_rejects_nonpristine_predecessor(
    corruption: str,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    current_context, incoming_context, current, incoming_payload = (
        _bootstrap_rebind_fixture(runner)
    )
    events = ()
    if corruption == "state":
        states = list(current.task_states)
        states[0] = replace(states[0], declared_status=TaskStatus.RUNNING)
        current = replace(current, task_states=tuple(states))
    elif corruption == "fact":
        current = replace(
            current,
            facts=replace(
                current.facts,
                artifacts=frozenset({"forged-bootstrap:COMPLETE"}),
            ),
        )
    elif corruption == "event":
        events = ({"event_type": "started"},)
    else:
        wrong_payload, _ = runner.builder.build_bootstrap_manifest(
            context=current_context,
            source_digest="e" * 64,
            operator_configuration_authorized=True,
        )
        current = ControlPlaneManifest.from_dict(wrong_payload)
    repository = _bootstrap_rebind_repository(
        runner,
        current=current,
        context=incoming_context,
        events=events,
    )

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_precondition_changed",
    ):
        repository.import_bootstrap_manifest(incoming_payload)
    assert repository._bootstrap_rebind_gate is None


def test_repository_bootstrap_rebind_rejects_target_change_and_direct_import() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(
        runner
    )
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )
    changed_context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        batch_seq=1,
        projection_time="2026-08-30T16:30:00+08:00",
    )
    changed_payload, _ = runner.builder.build_bootstrap_manifest(
        context=changed_context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_target_changed",
    ):
        repository.import_bootstrap_manifest(changed_payload)

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="goal_transition_changed",
    ):
        repository.import_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            payload=incoming_payload,
        )


def test_repository_bootstrap_rebind_gate_is_nonreentrant() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(
        runner
    )
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )
    repository._bootstrap_rebind_gate = {"consumed": False}
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_gate_reentrant",
    ):
        repository.import_bootstrap_manifest(incoming_payload)


def test_roll_forward_before_preregistration_never_loads_completed_health(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        projection_time="2026-08-30T16:00:00+08:00",
    )
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    extensions = []

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params=None):
            self.statement = statement
            return self

        def fetchone(self):
            if "multiplicity_head" in self.statement:
                return (0, 0)
            assert "registration_batches" in self.statement
            return (0,)

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

        @staticmethod
        def export_manifest(**_kwargs):
            return payload

        @staticmethod
        def import_extension(value):
            extensions.append(value)

    monkeypatch.setattr(
        runner,
        "_latest_registered_health_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("pre-preregistration health load")
        ),
    )

    runner._roll_forward(
        repository=_Repository(),
        context=context,
        source_digest="f" * 64,
        now=datetime(2026, 8, 28, 0, 47, tzinfo=contract.TIMEZONE),
    )

    assert len(extensions) == 1
    extended = ControlPlaneManifest.from_dict(extensions[0])
    assert len(extended.tasks) == 15
    assert contract.FREEZE_FACT not in extended.facts.artifacts


def test_fact_builder_rejects_formal_route_or_promotion() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = _context()
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
    context = _context()
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
    context = _context()
    schedule = contract.schedule_for_issue(
        context["target_issue"], target_draw_date=context["target_draw_date"]
    )
    predraw_key = contract.task_template_by_name("predraw_delivery").key(context)
    start = schedule["predraw_send"]
    stop = datetime.combine(
        contract.require_draw_date(
            context["target_draw_date"], field="target_draw_date"
        ),
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


def test_resource_probe_reads_exact_user_manager_formal_p3_unit(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    observed: list[list[str]] = []

    def fake_run(command, **kwargs):
        observed.append(list(command))
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 2,
        }
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "LoadState=loaded\n"
                "ActiveState=inactive\n"
                "SubState=dead\n"
                "MainPID=0\n"
                "ControlPID=0\n"
            ),
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    observation = runner._resource_observation()
    assert observed == [
        [
            "systemctl",
            "--user",
            "show",
            contract.FORMAL_P3_UNIT,
            "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
            "--no-pager",
        ]
    ]
    assert contract.formal_p3_activity_state(observation) == "QUIESCENT"


def test_completed_activation_recovery_replays_without_workload(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
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
    assert (
        "EnvironmentFile=/home/ark/.config/dehps/"
        "m4-isolated-24h-challenger-v11.env"
    ) in service
    assert "/etc/dehps/" not in service
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


def test_repository_helper_does_not_shadow_base_task_validator() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    namespace = runner.IsolatedChallengerRepository.__dict__
    assert "_verify_task_definition" not in namespace
    assert "_verify_isolated_task_definition" in namespace


@pytest.mark.parametrize("row_count", [1, 2])
def test_latest_history_identity_requires_one_exact_issue_date(
    monkeypatch, row_count: int
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    rows = [("2026099", date(2026, 8, 27))] * row_count

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            assert "WHERE issue=(SELECT MAX(issue) FROM ssq_history)" in statement
            return self

        def fetchall(self):
            return rows

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

    monkeypatch.setattr(runner, "PostgresResearchOSRepository", _Repository)
    if row_count == 1:
        assert runner._latest_history_identity() == ("2026099", "2026-08-27")
    else:
        with pytest.raises(
            runner.IsolatedRunnerError, match="latest_identity_changed"
        ):
            runner._latest_history_identity()


@pytest.mark.parametrize("returncode", [0, 1])
def test_database_schema_attestation_accepts_only_ancestor_repair(
    monkeypatch, returncode: int
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    installed = "a" * 40
    current = "b" * 40
    expected_insert = (
        contract.DATABASE_SCHEMA_VERSION,
        contract.CONTRACT_DIGEST,
        current,
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params=None):
            if statement.startswith("INSERT"):
                assert params == expected_insert
            else:
                assert statement.startswith("SELECT")
                assert params is None
            return self

        @staticmethod
        def fetchone():
            return (
                contract.DATABASE_SCHEMA_VERSION,
                contract.CONTRACT_DIGEST,
                installed,
            )

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

    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        assert kwargs == {
            "cwd": runner.ROOT_DIR,
            "check": False,
            "capture_output": True,
            "text": True,
        }
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    if returncode == 0:
        assert runner._attest_database_schema(
            repository=_Repository(), git_commit=current
        )["installed_git_commit"] == installed
    else:
        with pytest.raises(runner.IsolatedRunnerError, match="not_ancestor"):
            runner._attest_database_schema(
                repository=_Repository(), git_commit=current
            )
    assert commands == [
        ["git", "merge-base", "--is-ancestor", installed, current]
    ]
