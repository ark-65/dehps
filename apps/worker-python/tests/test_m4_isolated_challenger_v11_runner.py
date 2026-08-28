from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    MainlineExecutionEvent,
    TaskStatus,
)

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
    assert len(contract.TASK_TEMPLATES) == 43
    assert len(contract.ARTIFACT_TYPES) == 45
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
    assert len(manifest.tasks) == 43
    assert dry_run["task_count"] == 43
    assert dry_run["import_performed"] is False
    assert [item.task_key for item in resolved.ready_queue] == [
        "m4-isolated-24h-challenger-v11-preregistration"
    ]


def test_incident_resolution_manifest_requires_sent_incident_and_daily_mail() -> None:
    builder = _load_script("build_m4_isolated_24h_challenger_v11_manifest")
    context = _context()
    assert "incident_resolution" not in builder.INCIDENT_TEMPLATE_NAMES
    payload, _ = builder.build_manifest(
        context=context,
        source_digest="a" * 64,
        operator_configuration_authorized=False,
        simulation_events=False,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    resolution = next(
        task
        for task in manifest.tasks
        if json.loads(task.metric_contract)["task_template"] == "incident_resolution"
    )
    incident_key = contract.task_template_by_name("incident_open").key(context)
    incident_delivery_key = contract.task_template_by_name("incident_delivery").key(
        context
    )
    daily_replay_key = contract.task_template_by_name("daily_summary_replay").key(
        context
    )
    daily_delivery_key = contract.task_template_by_name("daily_delivery").key(context)
    assert resolution.requested_capability == (
        "M4IsolatedIncidentResolutionCapabilityV11"
    )
    assert [
        (item.dependency_type.value, item.target_key)
        for item in resolution.dependencies
    ] == [
        ("artifact", f"{incident_key}:OPEN"),
        ("artifact", f"{incident_delivery_key}:SENT"),
        ("artifact", f"{daily_replay_key}:REGISTERED_REPLAY_VERIFIED"),
        ("artifact", f"{daily_delivery_key}:SENT"),
    ]


def test_daily_recovery_command_is_an_explicit_operator_surface() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    args = runner.parse_args(["recover-daily-mail", "--apply"])
    assert args.command == "recover-daily-mail"
    assert args.apply is True
    assert runner.DAILY_RECOVERY_OPERATIONS == (
        "disable-isolated-timer-and-wait-quiescent",
        "register-new-source-and-runtime-migration-input",
        "recover-daily-summary-sequence2-and-generic-replay",
        "rebind-all-unexecuted-old-source-tasks",
        "complete-daily-mail-chain-with-one-data250",
        "resolve-current-incident-and-advance-ledger",
        "prove-duplicate-cycle-zero-smtp",
        "reenable-isolated-timer-and-verify-status",
    )


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


def test_repository_allows_only_completed_attested_predecessor_tasks_in_mixed_source() -> (
    None
):
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    old_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    old = ControlPlaneManifest.from_dict(old_payload)
    old_task = old.tasks[0]
    task = replace(old_task, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST)
    state = replace(
        old.task_state_by_digest[old_task.artifact_digest],
        task_digest=task.artifact_digest,
        declared_status=TaskStatus.COMPLETED,
        completion_classification=CompletionClassification.COMPLETE,
    )
    fact = (
        f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
        f"{'1' * 64}:completed"
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.source_digest = "f" * 64
    repository._verify_isolated_task_definition(
        task,
        state=state,
        artifact_facts=frozenset({fact}),
        partial_live_rebind=True,
    )
    intermediate_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=next(
            item
            for item in runner.LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS
            if item != runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST
        ),
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    intermediate = ControlPlaneManifest.from_dict(intermediate_payload).tasks[0]
    intermediate = replace(
        intermediate, goal_digest=runner.LIVE_PARTIAL_FROZEN_GOAL_DIGEST
    )
    intermediate_state = replace(state, task_digest=intermediate.artifact_digest)
    intermediate_fact = (
        f"mainline-execution:{intermediate.task_key}:"
        f"{intermediate.artifact_digest}:{'3' * 64}:completed"
    )
    repository._verify_isolated_task_definition(
        intermediate,
        state=intermediate_state,
        artifact_facts=frozenset({intermediate_fact}),
        partial_live_rebind=True,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            task,
            state=replace(
                state,
                declared_status=TaskStatus.DRAFT,
                completion_classification=CompletionClassification.INTEGRATION_PENDING,
            ),
            artifact_facts=frozenset({fact}),
            partial_live_rebind=True,
        )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            task,
            state=state,
            artifact_facts=frozenset(),
            partial_live_rebind=True,
        )
    arbitrary_payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest="e" * 64,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    arbitrary = ControlPlaneManifest.from_dict(arbitrary_payload).tasks[0]
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="historical_task_source_changed",
    ):
        repository._verify_isolated_task_definition(
            arbitrary,
            state=replace(state, task_digest=arbitrary.artifact_digest),
            artifact_facts=frozenset(
                {
                    (
                        f"mainline-execution:{arbitrary.task_key}:"
                        f"{arbitrary.artifact_digest}:{'2' * 64}:completed"
                    )
                }
            ),
            partial_live_rebind=True,
        )


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
                self.result = {"manifest_json": current.to_dict(include_digest=True)}
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
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(runner)
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


def test_repository_rebind_preserves_exact_unexecuted_multicontext_task_set() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    current_context, incoming_context, current, incoming_payload = (
        _bootstrap_rebind_fixture(runner)
    )
    extra_context = {
        **current_context,
        "epoch_date": "20260828",
        "minute": "202608280052",
    }
    extended_payload = runner.builder.extend_manifest(
        current.to_dict(include_digest=True),
        context=extra_context,
        source_digest=runner.PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST,
        template_names=frozenset({"runtime_health"}),
    )
    extended = ControlPlaneManifest.from_dict(extended_payload)
    assert len(extended.tasks) == 15
    preserved_keys = tuple(task.task_key for task in extended.tasks)
    repository = _bootstrap_rebind_repository(
        runner,
        current=extended,
        context=incoming_context,
    )

    result, digest = repository.import_bootstrap_manifest(incoming_payload)

    assert result == "imported"
    assert digest == repository.current.artifact_digest
    assert len(repository.current.tasks) == 15
    assert tuple(task.task_key for task in repository.current.tasks) == preserved_keys
    assert any(
        task.task_key.endswith("runtime-health-202608280052")
        for task in repository.current.tasks
    )
    assert repository._bootstrap_rebind_gate is None


def test_extension_inherits_the_single_frozen_live_goal_digest() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest=runner.LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST,
        operator_configuration_authorized=True,
    )
    current = ControlPlaneManifest.from_dict(payload)
    extension_context = {
        **context,
        "epoch_date": "20260828",
        "minute": "202608280216",
    }
    extended = ControlPlaneManifest.from_dict(
        runner.builder.extend_manifest(
            current.to_dict(include_digest=True),
            context=extension_context,
            source_digest="f" * 64,
            template_names=frozenset({"runtime_health"}),
        )
    )
    added = [
        item
        for item in extended.tasks
        if item.task_key not in {task.task_key for task in current.tasks}
    ]
    assert len(added) == 1
    assert added[0].goal_digest == current.goals[0].artifact_digest
    assert (
        __import__("json").loads(added[0].metric_contract)["source_contract_digest"]
        == "f" * 64
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
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(runner)
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )
    changed_context = contract.render_context(
        source_max_issue="2026101",
        source_max_draw_date="2026-09-01",
        projection_time="2026-09-01T16:30:00+08:00",
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
    _, incoming_context, current, incoming_payload = _bootstrap_rebind_fixture(runner)
    repository = _bootstrap_rebind_repository(
        runner, current=current, context=incoming_context
    )
    repository._bootstrap_rebind_gate = {"consumed": False}
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="bootstrap_rebind_gate_reentrant",
    ):
        repository.import_bootstrap_manifest(incoming_payload)


def test_daily_recovery_rebind_preserves_completed_and_rejects_event_bearing(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        epoch_date="20260828",
        minute="202608280900",
        projection_time="2026-08-28T09:00:21.441271+08:00",
    )
    payload, _ = runner.builder.build_manifest(
        context=context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        operator_configuration_authorized=True,
        simulation_events=False,
    )
    base = ControlPlaneManifest.from_dict(payload)
    daily = next(
        item for item in base.tasks if item.task_key == contract.DAILY_RECOVERY_TASK_KEY
    )
    states = list(base.task_states)
    index = next(
        index
        for index, state in enumerate(states)
        if state.task_digest == daily.artifact_digest
    )
    states[index] = replace(
        states[index],
        declared_status=TaskStatus.COMPLETED,
        completion_classification=CompletionClassification.COMPLETE,
    )
    current = replace(base, task_states=tuple(states))
    monkeypatch.setattr(
        runner.contract, "DAILY_RECOVERY_TASK_DIGEST", daily.artifact_digest
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params):
            assert "research_os_mainline_artifacts" in statement
            return self

        @staticmethod
        def fetchone():
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
        source_digest = "f" * 64

        def __init__(self, *, events=()):
            self._evolving_source_rebind_gate = None
            self.events = tuple(events)
            self.imported = None

        @staticmethod
        def load_manifest(**_kwargs):
            return current

        def list_mainline_execution_event_metadata(self, **_kwargs):
            return self.events

        @staticmethod
        def connection_factory():
            return _Connection()

        def import_manifest(self, *, control_plane_key, payload, source):
            assert control_plane_key == contract.CONTROL_PLANE_KEY
            assert source == "m4-isolated-v11-exact-unexecuted-old-source-rebind"
            incoming = ControlPlaneManifest.from_dict(payload)
            assert (
                incoming.artifact_digest
                == self._evolving_source_rebind_gate["incoming_manifest_digest"]
            )
            self._evolving_source_rebind_gate["consumed"] = True
            self.imported = incoming

    repository = _Repository()
    result = (
        runner.IsolatedChallengerRepository.rebind_unexecuted_daily_recovery_source(
            repository
        )
    )
    assert result["task_count"] == len(base.tasks) - 1
    assert repository._evolving_source_rebind_gate is None
    rebound_daily = next(
        item
        for item in repository.imported.tasks
        if item.task_key == contract.DAILY_RECOVERY_TASK_KEY
    )
    assert rebound_daily.artifact_digest == daily.artifact_digest
    for task in repository.imported.tasks:
        source = json.loads(task.metric_contract)["source_contract_digest"]
        assert source == (
            contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
            if task.task_key == contract.DAILY_RECOVERY_TASK_KEY
            else "f" * 64
        )

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="rebind_candidate_has_execution_event",
    ):
        runner.IsolatedChallengerRepository.rebind_unexecuted_daily_recovery_source(
            _Repository(events=({"event_type": "started"},))
        )


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


@pytest.mark.parametrize(
    ("before", "after", "with_completion_fact"),
    [
        (TaskStatus.DRAFT, TaskStatus.RUNNING, False),
        (TaskStatus.RUNNING, TaskStatus.FAILED, False),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED, True),
    ],
)
def test_completion_verifier_accepts_only_exact_lifecycle_transition_shape(
    monkeypatch, before: TaskStatus, after: TaskStatus, with_completion_fact: bool
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    base = ControlPlaneManifest.from_dict(payload)
    states = list(base.task_states)
    states[0] = replace(states[0], declared_status=before)
    current = replace(base, task_states=tuple(states))
    states[0] = replace(states[0], declared_status=after)
    incoming = replace(base, task_states=tuple(states))
    if with_completion_fact:
        fact = (
            f"mainline-execution:{base.tasks[0].task_key}:"
            f"{'a' * 64}:{'b' * 64}:completed"
        )
        incoming = replace(
            incoming,
            facts=replace(incoming.facts, artifacts=frozenset({fact})),
        )

    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            if "SELECT current_manifest_digest" in statement:
                self.result = {"current_manifest_digest": current.artifact_digest}
            elif "SELECT manifest_json" in statement:
                self.result = {"manifest_json": current.to_dict(include_digest=True)}
            else:
                raise AssertionError(statement)
            return self

        def fetchone(self):
            return self.result

    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._bootstrap_rebind_gate = None
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )

    repository._verify_mainline_completion_records(
        _Cursor(),
        control_plane_key=contract.CONTROL_PLANE_KEY,
        manifest=incoming,
    )


@pytest.mark.parametrize(
    ("before", "after", "with_fact"),
    [
        (TaskStatus.DRAFT, TaskStatus.RUNNING, True),
        (TaskStatus.RUNNING, TaskStatus.FAILED, True),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED, False),
        (TaskStatus.DRAFT, TaskStatus.COMPLETED, True),
    ],
)
def test_completion_verifier_rejects_wrong_fact_or_transition(
    monkeypatch, before: TaskStatus, after: TaskStatus, with_fact: bool
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=_context(),
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    base = ControlPlaneManifest.from_dict(payload)
    current_states = list(base.task_states)
    current_states[0] = replace(current_states[0], declared_status=before)
    current = replace(base, task_states=tuple(current_states))
    incoming_states = list(current.task_states)
    incoming_states[0] = replace(incoming_states[0], declared_status=after)
    incoming = replace(current, task_states=tuple(incoming_states))
    if with_fact:
        fact = (
            f"mainline-execution:{base.tasks[0].task_key}:"
            f"{'a' * 64}:{'b' * 64}:completed"
        )
        incoming = replace(
            incoming,
            facts=replace(incoming.facts, artifacts=frozenset({fact})),
        )

    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            self.result = (
                {"current_manifest_digest": current.artifact_digest}
                if "SELECT current_manifest_digest" in statement
                else {"manifest_json": current.to_dict(include_digest=True)}
            )
            return self

        def fetchone(self):
            return self.result

    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._bootstrap_rebind_gate = None
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(
        runner.ResearchOSValidationError,
        match="atomic_completion_transition_changed",
    ):
        repository._verify_mainline_completion_records(
            _Cursor(),
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest=incoming,
        )


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


def test_incident_resolution_activation_advances_terminal_ledger(monkeypatch) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    template = contract.task_template_by_name("incident_resolution")
    task_key = template.key(context)
    incident_id = context["incident_id"]
    monkeypatch.setattr(
        runner.mainline,
        "load_completed_task_artifacts",
        lambda **_kwargs: (
            {
                "artifact_type": "M4IsolatedIncidentResolutionV11",
                "artifact_digest": "1" * 64,
                "body": {"status": "RESOLVED", "incident_id": incident_id},
            },
            {
                "artifact_type": "M4IsolatedIncidentLedgerHeadV11",
                "artifact_digest": "2" * 64,
                "body": {
                    "transition_seq": 7,
                    "transition_kind": "RESOLVED",
                    "incident_id": incident_id,
                },
            },
        ),
    )
    assert runner._activation_facts(
        task_key=task_key,
        template=template,
        context=context,
        repository=object(),
    ) == (
        f"{task_key}:RESOLVED",
        "m4-isolated-24h-challenger-v11-incident-ledger-head-7:ADVANCED",
    )


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


def test_user_scope_recovery_governance_is_exact_and_keeps_mail_mandatory(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    repaired_source = "d" * 64
    repaired_commit = "e" * 40
    source_contract = {
        "artifact_digest": repaired_source,
        "governance_bindings": {
            "failed_state_recovery_gate_base_merged_commit": (
                runner.USER_SCOPE_FAILED_STATE_RECOVERY_BASE_COMMIT
            ),
            "failed_state_recovery_gate_engineering_approval_decision_id": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_DECISION_ID
            ),
            "failed_state_recovery_gate_engineering_execution_id": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_EXECUTION_ID
            ),
            "failed_state_recovery_gate_engineering_request_id": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_ID
            ),
            "failed_state_recovery_gate_engineering_request_key": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_KEY
            ),
            "failed_state_recovery_gate_engineering_request_payload_sha256": (
                runner.USER_SCOPE_FAILED_STATE_ENGINEERING_PAYLOAD_SHA256
            ),
            "sequence2_completion_gate_base_merged_commit": (
                runner.USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT
            ),
            "sequence2_completion_gate_engineering_approval_decision_id": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_DECISION_ID
            ),
            "sequence2_completion_gate_engineering_execution_id": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_EXECUTION_ID
            ),
            "sequence2_completion_gate_engineering_request_id": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_ID
            ),
            "sequence2_completion_gate_engineering_request_key": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_KEY
            ),
            "sequence2_completion_gate_engineering_request_payload_sha256": (
                runner.USER_SCOPE_SEQUENCE2_ENGINEERING_PAYLOAD_SHA256
            ),
            "sequence3_guard_recovery_base_merged_commit": (
                runner.USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT
            ),
            "sequence3_guard_recovery_engineering_approval_decision_id": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_DECISION_ID
            ),
            "sequence3_guard_recovery_engineering_execution_id": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_EXECUTION_ID
            ),
            "sequence3_guard_recovery_engineering_request_id": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_ID
            ),
            "sequence3_guard_recovery_engineering_request_key": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_KEY
            ),
            "sequence3_guard_recovery_engineering_request_payload_sha256": (
                runner.USER_SCOPE_SEQUENCE3_ENGINEERING_PAYLOAD_SHA256
            ),
            "second_terminal_guard_repair_base_merged_commit": (
                runner.USER_SCOPE_SECOND_GUARD_REPAIR_BASE_COMMIT
            ),
            "second_terminal_guard_repair_engineering_approval_decision_id": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_DECISION_ID
            ),
            "second_terminal_guard_repair_engineering_execution_id": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_EXECUTION_ID
            ),
            "second_terminal_guard_repair_engineering_request_id": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_ID
            ),
            "second_terminal_guard_repair_engineering_request_key": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_KEY
            ),
            "second_terminal_guard_repair_engineering_request_payload_sha256": (
                runner.USER_SCOPE_SECOND_GUARD_ENGINEERING_PAYLOAD_SHA256
            ),
            "running_projection_resume_repair_base_merged_commit": (
                runner.USER_SCOPE_RUNNING_RESUME_REPAIR_BASE_COMMIT
            ),
            "running_projection_resume_repair_engineering_approval_decision_id": (
                runner.USER_SCOPE_ENGINEERING_DECISION_ID
            ),
            "running_projection_resume_repair_engineering_execution_id": (
                runner.USER_SCOPE_ENGINEERING_EXECUTION_ID
            ),
            "running_projection_resume_repair_engineering_request_id": (
                runner.USER_SCOPE_ENGINEERING_REQUEST_ID
            ),
            "running_projection_resume_repair_engineering_request_key": (
                runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
            ),
            "running_projection_resume_repair_engineering_request_payload_sha256": (
                runner.USER_SCOPE_ENGINEERING_PAYLOAD_SHA256
            ),
        },
    }
    engineering = SimpleNamespace(
        id=runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        request_type=runner.AgentRequestType.ENGINEERING_RUNTIME_FIX,
        status=runner.AgentRequestStatus.COMPLETED,
        metadata={"payload_sha256": runner.USER_SCOPE_ENGINEERING_PAYLOAD_SHA256},
    )
    engineering_approval = SimpleNamespace(
        id=runner.USER_SCOPE_ENGINEERING_DECISION_ID,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=runner.AgentRole.REVIEWER,
    )
    engineering_execution = SimpleNamespace(
        id=runner.USER_SCOPE_ENGINEERING_EXECUTION_ID,
        status=runner.AgentExecutionStatus.COMPLETED,
        environment="development",
        executor_role=runner.AgentRole.ENGINEERING,
    )
    recovery = {
        "candidate_result_count": 0,
        "current_manifest_digest": runner.USER_SCOPE_FAILED_MANIFEST_DIGEST,
        "engineering_approval_decision_id": (runner.USER_SCOPE_ENGINEERING_DECISION_ID),
        "engineering_execution_id": runner.USER_SCOPE_ENGINEERING_EXECUTION_ID,
        "engineering_request_id": runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        "execution_attempt_count": contract.ATTEMPTS_PER_BATCH,
        "origin_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "origin_source_contract_digest": (
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
        ),
        "registered_candidate_count": contract.ATTEMPTS_PER_BATCH,
        "repaired_source_contract_digest": repaired_source,
        "running_execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "running_task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "running_task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": runner.USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        "prior_failed_event_digest": runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "next_completion_sequence": 3,
        "predecessor_attestation_digest": (
            runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
        ),
    }
    payload = {
        "version": "m4-isolated-v11-sequence3-guard-recovery-v4",
        "commit": repaired_commit,
        "checks": {"user_systemd_running_batch_recovery": recovery},
        "mail_contract": {
            "mandatory_kinds": list(runner.USER_SCOPE_MANDATORY_MAIL_KINDS),
            "sent": (
                "Only SMTP final DATA250 plus append-only exactly-once "
                "receipt/artifact/replay projects SENT"
            ),
        },
        "resource_contract": {
            "continuous_24h": True,
            "p3_mutation": False,
            "p3_preempts": True,
            "p4_p5_p6_or_promotion": False,
            "workers_max": contract.WORKER_COUNT,
        },
        "ordered_operations": [
            "resume-p3-user-scope-running-batch",
            "recover-user-systemd-post-batch",
        ],
    }
    payload_sha = hashlib.sha256(
        contract.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    operator = SimpleNamespace(
        id=746,
        parent_request_id=runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        request_type=runner.AgentRequestType.OPERATOR_RELEASE,
        status=runner.AgentRequestStatus.EXECUTING,
        payload=payload,
        metadata={"payload_sha256": payload_sha},
    )
    operator_approval = SimpleNamespace(
        id=3160,
        decision_code="request_approved",
        previous_status="under_review",
        new_status="approved",
        decided_by_role=runner.AgentRole.REVIEWER,
    )
    operator_execution = SimpleNamespace(
        id=601,
        status=runner.AgentExecutionStatus.RUNNING,
        environment="production",
        executor_role=runner.AgentRole.OPERATOR,
    )

    class _Repository:
        def get_request(self, key):
            return (
                engineering
                if key == runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
                else operator
            )

        def list_decisions(self, key):
            return (
                [engineering_approval]
                if key == runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
                else [operator_approval]
            )

        def list_execution_metadata(self, key):
            return (
                [engineering_execution]
                if key == runner.USER_SCOPE_ENGINEERING_REQUEST_KEY
                else [operator_execution]
            )

    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "operator")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "3160")
    monkeypatch.setenv("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "601")
    result = runner.validate_user_scope_recovery_governance(
        repository=_Repository(),
        source_contract=source_contract,
        repaired_source_digest=repaired_source,
        git_commit=repaired_commit,
        phase="resume",
    )
    assert result["operator_payload_sha256"] == payload_sha
    operator.payload = {
        **payload,
        "mail_contract": {
            **payload["mail_contract"],
            "mandatory_kinds": ["PREDRAW_TOP100"],
        },
    }
    with pytest.raises(runner.IsolatedRunnerError, match="operator_scope"):
        runner.validate_user_scope_recovery_governance(
            repository=_Repository(),
            source_contract=source_contract,
            repaired_source_digest=repaired_source,
            git_commit=repaired_commit,
            phase="resume",
        )


def test_user_scope_resume_surface_is_single_task_and_attestation_is_deterministic() -> (
    None
):
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    source = inspect.getsource(runner.resume_p3_user_scope_running_batch)
    tree = ast.parse(source)
    run_once_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run_once"
    ]
    assert len(run_once_calls) == 1
    assert "cycle(" not in source
    assert "_roll_forward(" not in source
    assert "send_external_once" not in source
    governance = {
        "phase": "resume",
        "engineering_request_id": runner.USER_SCOPE_ENGINEERING_REQUEST_ID,
        "engineering_decision_id": runner.USER_SCOPE_ENGINEERING_DECISION_ID,
        "engineering_execution_id": runner.USER_SCOPE_ENGINEERING_EXECUTION_ID,
        "operator_request_id": 746,
        "operator_decision_id": 3160,
        "operator_execution_id": 601,
        "operator_payload_sha256": "f" * 64,
    }
    first_path, first = runner._user_scope_runtime_attestation(
        repaired_source_digest="d" * 64,
        repaired_git_commit="e" * 40,
        governance=governance,
        predecessor_attestation_digest=(
            runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
        ),
    )
    second_path, second = runner._user_scope_runtime_attestation(
        repaired_source_digest="d" * 64,
        repaired_git_commit="e" * 40,
        governance=governance,
        predecessor_attestation_digest=(
            runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
        ),
    )
    assert first_path == second_path
    assert first == second
    assert first["scientific_contract_changed"] is False
    assert first["formal_p3_mutated"] is False
    assert first["p4_p5_p6_or_promotion_triggered"] is False
    assert first["parent_digests"][-1] == "f" * 64
    assert (
        first["parent_digests"][-2] == runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST
    )


def test_user_scope_predecessor_attestation_is_exact_and_immutable(
    monkeypatch, tmp_path
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    foundation = {
        "schema_version": "dehps-m4-isolated-v11-user-systemd-runtime-migration.v1",
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": runner.USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "origin_git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": "dea22d7ca1cc876d278b1d18e4e68801a41291fd",
        "origin_source_contract_digest": runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "f6d043e22862c1ffd850dc5932a7be3c6f2dbaab4e9cf1d57db8a3f8158157ef"
        ),
        "repair": "SYSTEMD_SYSTEM_MANAGER_TO_EXACT_USER_MANAGER_QUERY",
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 745,
            "engineering_decision_id": 3157,
            "engineering_execution_id": 600,
            "operator_request_id": 746,
            "operator_decision_id": 3162,
            "operator_execution_id": 601,
            "operator_payload_sha256": (
                "019bfa1769bd0359bc94b4b4d023c13ec3d02ce9a7a93c91a9bca86b5b2d876d"
            ),
        },
        "parent_digests": [
            runner.USER_SCOPE_RESUME_TASK_DIGEST,
            runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "f6d043e22862c1ffd850dc5932a7be3c6f2dbaab4e9cf1d57db8a3f8158157ef",
            "019bfa1769bd0359bc94b4b4d023c13ec3d02ce9a7a93c91a9bca86b5b2d876d",
        ],
    }
    latest = {
        "schema_version": (
            "dehps-m4-isolated-v11-same-key-event-isolation-runtime-migration.v2"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": runner.USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "origin_git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": runner.USER_SCOPE_EVENT_ISOLATION_RUNTIME_COMMIT,
        "origin_source_contract_digest": runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed"
        ),
        "repair": "EXACT_SAME_KEY_EVENT_VIEW_AFTER_USER_SYSTEMD_GUARD_REPAIR",
        "predecessor_attestation_digest": (
            runner.USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST
        ),
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 747,
            "engineering_decision_id": 3167,
            "engineering_execution_id": 602,
            "operator_request_id": 748,
            "operator_decision_id": 3172,
            "operator_execution_id": 603,
            "operator_payload_sha256": (
                "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f"
            ),
        },
        "parent_digests": [
            runner.USER_SCOPE_RESUME_TASK_DIGEST,
            runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed",
            runner.USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
            "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f",
        ],
    }
    guard = {
        "schema_version": (
            "dehps-m4-isolated-v11-utc-registration-failed-event-runtime-migration.v3"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": runner.USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": runner.USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": runner.USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "origin_git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": "c30db93efb428198b4d7c0c0548feefbd315ba59",
        "origin_source_contract_digest": runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780"
        ),
        "repair": "UTC_REGISTRATION_RESUME_AND_EXACT_FAILED_EVENT_RECOVERY",
        "predecessor_attestation_digest": runner.USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 750,
            "engineering_decision_id": 3182,
            "engineering_execution_id": 605,
            "operator_request_id": 751,
            "operator_decision_id": 3187,
            "operator_execution_id": 606,
            "operator_payload_sha256": (
                "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5"
            ),
        },
        "parent_digests": [
            runner.USER_SCOPE_RESUME_TASK_DIGEST,
            runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
            runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780",
            runner.USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
            "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5",
        ],
    }
    for payload in (foundation, latest, guard):
        path = (
            tmp_path
            / "runtime/research-os/mainline/tasks"
            / runner.USER_SCOPE_RESUME_TASK_KEY
            / runner.USER_SCOPE_RESUME_EXECUTION_ID
            / "runtime-migrations"
            / payload["artifact_digest"]
            / "user-systemd-runtime-migration.json"
        )
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(runner, "ROOT_DIR", tmp_path)
    assert runner._load_user_scope_predecessor_attestation() == guard
    guard["governance"]["operator_execution_id"] = 999
    path.write_text(json.dumps(guard), encoding="utf-8")
    with pytest.raises(runner.IsolatedRunnerError, match="attestation_changed"):
        runner._load_user_scope_predecessor_attestation()


def _user_scope_event_dict(record: MainlineExecutionEvent) -> dict[str, object]:
    return {
        "event_digest": record.artifact_digest,
        "execution_id": record.execution_id,
        "control_plane_key": record.control_plane_key,
        "manifest_digest": record.manifest_digest,
        "task_key": record.task_key,
        "task_digest": record.task_digest,
        "capability": record.capability,
        "event_type": record.event_type,
        "sequence": record.sequence,
        "recorded_at": record.recorded_at,
        "payload": list(record.payload),
    }


def _user_scope_events(runner, *, completed: bool) -> tuple[dict[str, object], ...]:
    shared = {
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "task_key": runner.USER_SCOPE_RESUME_TASK_KEY,
        "capability": runner.USER_SCOPE_RESUME_CAPABILITY,
    }
    records = [
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_HISTORICAL_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_HISTORICAL_TASK_DIGEST,
            event_type="started",
            sequence=0,
            recorded_at=runner.USER_SCOPE_HISTORICAL_STARTED_AT,
            payload=(
                (
                    "input_artifact_digests",
                    [runner.USER_SCOPE_HISTORICAL_SOURCE_DIGEST],
                ),
                ("git_commit", runner.USER_SCOPE_HISTORICAL_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_HISTORICAL_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_HISTORICAL_TASK_DIGEST,
            event_type="failed",
            sequence=1,
            recorded_at=runner.USER_SCOPE_HISTORICAL_FAILED_AT,
            payload=(
                ("error", "atomic_registration_artifact_content_changed"),
                ("git_commit", runner.USER_SCOPE_HISTORICAL_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="started",
            sequence=0,
            recorded_at=runner.USER_SCOPE_RESUME_STARTED_AT,
            payload=(
                (
                    "input_artifact_digests",
                    [runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST],
                ),
                ("git_commit", runner.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="failed",
            sequence=1,
            recorded_at=runner.USER_SCOPE_RESUME_FAILED_AT,
            payload=(
                ("error", "atomic_registration_resume_changed"),
                ("git_commit", runner.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
            event_type="failed",
            sequence=2,
            recorded_at=runner.USER_SCOPE_GUARD_FAILED_AT,
            payload=(
                (
                    "error",
                    "M4-v2 atomic successor does not permit failed-execution recovery",
                ),
                ("git_commit", runner.USER_SCOPE_RESUME_ORIGIN_COMMIT),
            ),
        ),
    ]
    assert (
        records[0].artifact_digest == runner.USER_SCOPE_HISTORICAL_STARTED_EVENT_DIGEST
    )
    assert (
        records[1].artifact_digest == runner.USER_SCOPE_HISTORICAL_FAILED_EVENT_DIGEST
    )
    assert records[2].artifact_digest == runner.USER_SCOPE_RESUME_STARTED_EVENT_DIGEST
    assert records[3].artifact_digest == runner.USER_SCOPE_RESUME_FAILED_EVENT_DIGEST
    assert records[4].artifact_digest == runner.USER_SCOPE_GUARD_FAILED_EVENT_DIGEST
    if completed:
        records.append(
            MainlineExecutionEvent(
                **shared,
                execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
                manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
                task_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
                event_type="completed",
                sequence=3,
                recorded_at="2026-08-28T05:00:00+08:00",
                payload=tuple(
                    sorted(
                        {
                            "execution_artifact_digest": "a" * 64,
                            "execution_artifact_path": "runtime/execution.json",
                            "registered_artifact_count": 19,
                            "publication_batch_digest": "b" * 64,
                            "git_commit": runner.USER_SCOPE_RESUME_ORIGIN_COMMIT,
                        }.items()
                    )
                ),
            )
        )
    return tuple(_user_scope_event_dict(record) for record in records)


@pytest.mark.parametrize(
    ("counts", "expected"),
    (
        (
            {
                "candidates": contract.ATTEMPTS_PER_BATCH,
                "terminal": contract.ATTEMPTS_PER_BATCH,
                "results": contract.ATTEMPTS_PER_BATCH,
                "attempts": contract.ATTEMPTS_PER_BATCH,
                "committed_attempts": contract.ATTEMPTS_PER_BATCH,
            },
            True,
        ),
        (
            {
                "candidates": contract.ATTEMPTS_PER_BATCH,
                "terminal": contract.ATTEMPTS_PER_BATCH,
                "results": contract.ATTEMPTS_PER_BATCH - 1,
                "attempts": contract.ATTEMPTS_PER_BATCH,
                "committed_attempts": contract.ATTEMPTS_PER_BATCH,
            },
            False,
        ),
        (None, False),
    ),
)
def test_search_batch_mirror_complete_decodes_exact_dict_row(counts, expected) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")

    class _Cursor:
        statement = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            self.statement = statement
            if "SELECT registration_seq" in statement:
                assert params == (0,)
            else:
                assert params == (7,) * 5
                for alias in (
                    "AS candidates",
                    "AS terminal",
                    "AS results",
                    "AS attempts",
                    "AS committed_attempts",
                ):
                    assert alias in statement
            return self

        def fetchone(self):
            if "SELECT registration_seq" in self.statement:
                return {"registration_seq": 7}
            return counts

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor(*, row_factory):
            assert row_factory is runner.dict_row
            return _Cursor()

    repository = SimpleNamespace(connection_factory=lambda: _Connection())
    assert (
        runner._search_batch_mirror_complete(
            repository=repository,
            context={"batch_seq": "000000000000"},
        )
        is expected
    )


@pytest.mark.parametrize(
    ("counts", "error"),
    (
        ({"count": contract.ATTEMPTS_PER_BATCH}, "count_row_changed"),
        (
            {
                "candidates": "count",
                "terminal": contract.ATTEMPTS_PER_BATCH,
                "results": contract.ATTEMPTS_PER_BATCH,
                "attempts": contract.ATTEMPTS_PER_BATCH,
                "committed_attempts": contract.ATTEMPTS_PER_BATCH,
            },
            "count_value_changed",
        ),
    ),
)
def test_search_batch_mirror_complete_fails_closed_on_dict_row_drift(
    counts, error
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")

    class _Cursor:
        statement = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params):
            self.statement = statement
            return self

        def fetchone(self):
            if "SELECT registration_seq" in self.statement:
                return {"registration_seq": 7}
            return counts

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor(*, row_factory):
            assert row_factory is runner.dict_row
            return _Cursor()

    repository = SimpleNamespace(connection_factory=lambda: _Connection())
    with pytest.raises(runner.IsolatedRunnerError, match=error):
        runner._search_batch_mirror_complete(
            repository=repository,
            context={"batch_seq": "000000000000"},
        )


@pytest.mark.parametrize(
    ("manifest_digest", "target_status"),
    (
        ("FAILED", TaskStatus.FAILED),
        ("RUNNING", TaskStatus.RUNNING),
    ),
)
def test_user_scope_live_preflight_distinguishes_failed_and_running_manifests(
    monkeypatch, manifest_digest, target_status
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    manifest_digest = {
        "FAILED": runner.USER_SCOPE_FAILED_MANIFEST_DIGEST,
        "RUNNING": runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
    }[manifest_digest]
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
    )
    target = SimpleNamespace(
        task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        artifact_digest=runner.USER_SCOPE_RESUME_TASK_DIGEST,
        requested_capability=runner.USER_SCOPE_RESUME_CAPABILITY,
        metric_contract=json.dumps(
            {
                "render_context": context,
                "source_contract_digest": (
                    runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
                ),
            }
        ),
    )
    completed_states = [
        SimpleNamespace(declared_status=TaskStatus.COMPLETED) for _ in range(22)
    ]
    draft_states = [SimpleNamespace(declared_status=TaskStatus.DRAFT) for _ in range(4)]
    target_state = SimpleNamespace(
        declared_status=target_status,
        completion_classification=CompletionClassification.INTEGRATED,
        superseded_by_task_digest=None,
    )
    manifest = SimpleNamespace(
        artifact_digest=manifest_digest,
        tasks=[target]
        + [
            SimpleNamespace(task_key=f"other-{index}", artifact_digest=f"{index:064x}")
            for index in range(26)
        ],
        task_states=(*completed_states, *draft_states, target_state),
        task_state_by_digest={target.artifact_digest: target_state},
        facts=SimpleNamespace(artifacts=frozenset()),
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement):
            self.statement = statement
            return self

        def fetchall(self):
            if "registration_batches" in self.statement:
                return [
                    (
                        0,
                        0,
                        "2026100",
                        runner.USER_SCOPE_RESUME_EXECUTION_ID,
                        0,
                        contract.ATTEMPTS_PER_BATCH,
                        contract.ATTEMPTS_PER_BATCH,
                    )
                ]
            return [
                (
                    0,
                    "TERMINAL",
                    runner.USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
                    contract.ATTEMPTS_PER_BATCH,
                )
            ]

        def fetchone(self):
            if "multiplicity_head" in self.statement:
                return (0, contract.ATTEMPTS_PER_BATCH)
            if "worker_started_at IS NOT NULL" in self.statement:
                return (
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    contract.ATTEMPTS_PER_BATCH,
                    0,
                    0,
                )
            if "execution_attempts" in self.statement:
                return (contract.ATTEMPTS_PER_BATCH,)
            return (0,)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    repository = SimpleNamespace(
        load_manifest=lambda **_kwargs: manifest,
        list_mainline_execution_events=lambda **_kwargs: _user_scope_events(
            runner, completed=False
        ),
        list_mainline_artifacts=lambda **_kwargs: (),
        connection_factory=lambda: _Connection(),
    )
    monkeypatch.setattr(runner, "_p3_source_identity", lambda: ("p3", "unchanged"))

    verified_manifest, verified_context = runner._validate_user_scope_resume_live_state(
        repository=repository
    )

    assert verified_manifest is manifest
    assert verified_context == context
    assert runner.USER_SCOPE_FAILED_MANIFEST_DIGEST != (
        runner.USER_SCOPE_RESUME_MANIFEST_DIGEST
    )
    manifest.artifact_digest = "0" * 64
    with pytest.raises(runner.IsolatedRunnerError, match="manifest_changed"):
        runner._validate_user_scope_resume_live_state(repository=repository)


def test_user_scope_event_view_is_exact_filtered_non_reentrant_and_closes(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    events = _user_scope_events(runner, completed=True)
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "list_mainline_execution_events",
        lambda _self, **_kwargs: events,
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._user_scope_resume_event_gate = False
    assert (
        repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        )
        == events
    )
    with repository.user_scope_resume_event_view():
        current = repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            execution_id=runner.USER_SCOPE_RESUME_EXECUTION_ID,
        )
        assert [item["event_type"] for item in current] == [
            "started",
            "failed",
            "failed",
            "completed",
        ]
        assert all(
            item["task_digest"] == runner.USER_SCOPE_RESUME_TASK_DIGEST
            for item in current
        )
        with (
            pytest.raises(runner.IsolatedRunnerError, match="reentrant"),
            repository.user_scope_resume_event_view(),
        ):
            pass
    assert repository._user_scope_resume_event_gate is False
    assert (
        repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        )
        == events
    )


def test_failed_to_running_transition_requires_exact_two_phase_user_scope_gate(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    context = _context()
    payload, _ = runner.builder.build_bootstrap_manifest(
        context=context,
        source_digest="f" * 64,
        operator_configuration_authorized=True,
    )
    base = ControlPlaneManifest.from_dict(payload)
    task = base.tasks[0]
    current_states = list(base.task_states)
    current_states[0] = replace(
        current_states[0],
        declared_status=TaskStatus.FAILED,
        completion_classification=CompletionClassification.INTEGRATED,
    )
    current = replace(base, task_states=tuple(current_states))
    incoming_states = list(current.task_states)
    incoming_states[0] = replace(
        incoming_states[0],
        declared_status=TaskStatus.RUNNING,
        completion_classification=CompletionClassification.INTEGRATED,
    )
    incoming = replace(current, task_states=tuple(incoming_states))

    class _Cursor:
        def __init__(self):
            self.result = None

        def execute(self, statement, _params=None):
            self.result = (
                {"current_manifest_digest": current.artifact_digest}
                if "SELECT current_manifest_digest" in statement
                else {"manifest_json": current.to_dict(include_digest=True)}
            )
            return self

        def fetchone(self):
            return self.result

    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository.context = dict(context)
    repository.source_digest = "f" * 64
    repository._fact_gate = None
    repository._definition_gate = None
    repository._bootstrap_rebind_gate = None
    repository._user_scope_resume_event_gate = False
    repository._user_scope_failed_transition_gate = None
    repository.load_manifest = lambda **_kwargs: current
    monkeypatch.setattr(
        runner, "USER_SCOPE_FAILED_MANIFEST_DIGEST", current.artifact_digest
    )
    monkeypatch.setattr(
        runner, "USER_SCOPE_RESUME_MANIFEST_DIGEST", incoming.artifact_digest
    )
    monkeypatch.setattr(runner, "USER_SCOPE_RESUME_TASK_KEY", task.task_key)
    monkeypatch.setattr(runner, "USER_SCOPE_RESUME_TASK_DIGEST", task.artifact_digest)
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "_verify_mainline_completion_records",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(
        runner.ResearchOSValidationError,
        match="failed_recovery_transition_gate_changed",
    ):
        repository._verify_exact_transition(incoming)
    with repository.user_scope_resume_event_view():
        repository._verify_exact_transition(incoming)
        assert repository._user_scope_failed_transition_gate == {
            "router_consumed": True,
            "completion_consumed": False,
        }
        repository._verify_mainline_completion_records(
            _Cursor(),
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest=incoming,
        )
        assert repository._user_scope_failed_transition_gate == {
            "router_consumed": True,
            "completion_consumed": True,
        }
        with pytest.raises(
            runner.ResearchOSValidationError,
            match="failed_recovery_transition_gate_changed",
        ):
            repository._verify_exact_transition(incoming)
    assert repository._user_scope_resume_event_gate is False
    assert repository._user_scope_failed_transition_gate is None


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "changed", "extra"))
def test_user_scope_event_view_rejects_any_raw_event_set_drift_and_closes(
    monkeypatch, mutation
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    raw = list(_user_scope_events(runner, completed=False))
    if mutation == "missing":
        raw.pop(0)
    elif mutation == "duplicate":
        raw.append(dict(raw[0]))
    elif mutation == "changed":
        raw[0] = {**raw[0], "recorded_at": "2026-08-27T19:42:00+00:00"}
    else:
        extra = MainlineExecutionEvent(
            execution_id="c" * 64,
            control_plane_key=contract.CONTROL_PLANE_KEY,
            manifest_digest=runner.USER_SCOPE_RESUME_MANIFEST_DIGEST,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
            task_digest="d" * 64,
            capability=runner.USER_SCOPE_RESUME_CAPABILITY,
            event_type="started",
            sequence=0,
            recorded_at="2026-08-28T05:00:00+08:00",
            payload=(),
        )
        raw.append(_user_scope_event_dict(extra))
    events = tuple(raw)
    monkeypatch.setattr(
        runner.PostgresResearchOSRepository,
        "list_mainline_execution_events",
        lambda _self, **_kwargs: events,
    )
    repository = object.__new__(runner.IsolatedChallengerRepository)
    repository._user_scope_resume_event_gate = False
    with (
        pytest.raises((runner.IsolatedRunnerError, ValueError)),
        repository.user_scope_resume_event_view(),
    ):
        repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=runner.USER_SCOPE_RESUME_TASK_KEY,
        )
    assert repository._user_scope_resume_event_gate is False


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
    single_bundle = runner._parallel_equivalence_bundle(single, target_issue="2026101")
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
        "EnvironmentFile=/home/ark/.config/dehps/m4-isolated-24h-challenger-v11.env"
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
        with pytest.raises(runner.IsolatedRunnerError, match="latest_identity_changed"):
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
        assert (
            runner._attest_database_schema(
                repository=_Repository(), git_commit=current
            )["installed_git_commit"]
            == installed
        )
    else:
        with pytest.raises(runner.IsolatedRunnerError, match="not_ancestor"):
            runner._attest_database_schema(repository=_Repository(), git_commit=current)
    assert commands == [["git", "merge-base", "--is-ancestor", installed, current]]


def test_committed_recovery_replays_and_mirrors_without_run_once_or_smtp(
    monkeypatch,
) -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    manifest = SimpleNamespace(
        artifact_digest=runner.USER_SCOPE_COMMITTED_MANIFEST_DIGEST
    )
    ledger = {"state": "PRE_MIRROR"}
    replay = {
        "status": "REPLAY_VERIFIED",
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "same_artifact_content": True,
        "all_registrations_and_parent_chains_exact": True,
        "manual_input_assembly": False,
        "dispatch_performed": False,
    }

    class _Supervisor:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def run_once(**_kwargs):
            raise AssertionError("committed recovery must not run workload")

        @staticmethod
        def replay(**_kwargs):
            return replay

    monkeypatch.setattr(
        runner,
        "validate_user_scope_committed_recovery_governance",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        runner.artifacts,
        "load_source_contract",
        lambda **_kwargs: {"artifact_digest": "a" * 64},
    )
    monkeypatch.setattr(
        runner,
        "_validate_user_scope_committed_live_state",
        lambda **_kwargs: (manifest, _context(), ledger["state"]),
    )
    monkeypatch.setattr(runner, "_p3_source_identity", lambda: ("p3", "unchanged"))
    monkeypatch.setattr(runner.mainline, "IsolatedChallengerSupervisor", _Supervisor)
    monkeypatch.setattr(
        runner,
        "_user_scope_committed_ledger_state",
        lambda **_kwargs: ledger["state"],
    )

    def mirror(**_kwargs):
        ledger["state"] = "MIRRORED"

    monkeypatch.setattr(runner, "_mirror_search_batch_ledger", mirror)
    result = runner.recover_p3_user_scope_committed_batch(
        apply=True,
        repository=object(),
        repaired_source_digest="a" * 64,
        repaired_git_commit="b" * 40,
    )
    assert result["status"] == "BATCH_COMPLETE_AND_REPLAY_VERIFIED"
    assert result["ledger_state_before"] == "PRE_MIRROR"
    assert result["ledger_state_after"] == "MIRRORED"
    assert result["scientific_workloads_executed"] == 0
    assert result["run_once_calls"] == 0
    assert result["smtp_calls"] == 0
    assert result["mandatory_mail_kinds"] == list(
        runner.USER_SCOPE_MANDATORY_MAIL_KINDS
    )
    assert result["mail_integration"] == (
        "PENDING_REAL_SCHEDULED_DATA250_RECEIPT_REPLAY"
    )


def test_committed_recovery_surface_contains_no_workload_dispatch() -> None:
    runner = _load_script("run_m4_isolated_24h_challenger_v11")
    source = inspect.getsource(runner.recover_p3_user_scope_committed_batch)
    tree = ast.parse(source)
    run_once_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run_once"
    ]
    assert run_once_calls == []
    assert "send_external_once" not in source
    assert "_mirror_search_batch_ledger" in source
    assert "USER_SCOPE_MANDATORY_MAIL_KINDS" in source
