from __future__ import annotations

import ast
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_mainline as mainline,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def _context():
    return contract.render_context(
        source_max_issue="2026100", source_max_draw_date="2026-08-30"
    )


def test_simulated_chain_covers_all_tasks_and_never_creates_sent() -> None:
    result = mainline.simulate_artifact_chain(
        context=_context(), git_commit="a" * 40, source_digest="b" * 64
    )
    assert result["status"] == "SIMULATION_REPLAY_VERIFIED"
    assert result["task_count"] == 42
    assert result["external_sent_count"] == 0
    assert result["smtp_calls"] == 0
    assert result["all_parents_registered"] is True
    assert set(result["delivery_states"]) == {"SIMULATED"}
    assert len(result["delivery_states"]) == 4
    assert set(result["delivery_mail_kinds"]) == {
        "PREDRAW_TOP100",
        "POSTDRAW_SETTLEMENT",
        "DAILY_24H_RESEARCH_SUMMARY",
        "IMMEDIATE_FAIL_CLOSED_INCIDENT",
    }
    assert result["formal_p3_mutated"] is False


def test_external_mail_acceptance_requires_issue_cycle_daily_and_no_incident() -> None:
    facts = {
        "m4-isolated-24h-challenger-v11-2026101-predraw-delivery:SENT",
        "m4-isolated-24h-challenger-v11-2026101-post-delivery:SENT",
        "m4-isolated-24h-challenger-v11-daily-20260827-delivery:SENT",
        "m4-isolated-24h-challenger-v11-incident-fixture-delivery:SENT",
    }
    evidence = mainline._external_delivery_evidence(facts)
    assert evidence["real_mail_acceptance"] is True
    assert evidence["complete_external_issue_cycles"] == ["2026101"]
    assert evidence["daily_sent_epochs"] == ["20260827"]
    assert evidence["incident_sent_ids"] == ["fixture"]
    blocked = mainline._external_delivery_evidence(
        facts | {"m4-isolated-24h-challenger-v11-incident-bad-open:OPEN"}
    )
    assert blocked["real_mail_acceptance"] is False


def test_search_batch_emits_exact_atomic_cardinalities() -> None:
    context = _context()
    template = contract.task_template_by_name("search_batch")
    output = mainline.build_task_artifacts(
        template=template,
        task_key=template.key(context),
        target_issue=context["target_issue"],
        git_commit="a" * 40,
        source_digest="b" * 64,
        parent_digests=("c" * 64,),
        execution_id="d" * 64,
        simulation=True,
        created_at="2026-08-27T00:00:00+00:00",
    )
    types = [item["artifact_type"] for item in output]
    assert types.count("M4IsolatedCandidateRegistrationV11") == 18
    assert types.count("M4IsolatedExecutionAttemptV11") == 18
    assert types.count("M4IsolatedCandidateResultV11") == 18
    assert types.count("M4IsolatedSeedCohortV11") == 6
    assert types.count("M4IsolatedDuplicateSuppressionV11") == 0


def test_artifact_replay_rejects_content_or_parent_corruption() -> None:
    context = _context()
    template = contract.task_template_by_name("history_snapshot")
    value = mainline.build_task_artifacts(
        template=template,
        task_key=template.key(context),
        target_issue=context["target_issue"],
        git_commit="a" * 40,
        source_digest="b" * 64,
        parent_digests=("c" * 64,),
        execution_id="d" * 64,
        simulation=True,
        created_at="2026-08-27T00:00:00+00:00",
    )[0]
    assert artifacts.replay_artifact(value)["status"] == "REPLAY_VERIFIED"
    corrupted = deepcopy(value)
    corrupted["body"]["simulation"] = False
    with pytest.raises(artifacts.IsolatedArtifactError, match="digest"):
        artifacts.replay_artifact(corrupted)


def test_parent_closure_allows_prior_atomic_artifact_and_rejects_raw_digest() -> None:
    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement, _params):
            return self

        @staticmethod
        def fetchall():
            return []

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

    first = artifacts.build_artifact(
        artifact_type="M4IsolatedPreregistrationV11",
        task_key="m4-isolated-24h-challenger-v11-preregistration",
        target_issue=None,
        git_commit="a" * 40,
        source_contract_digest="b" * 64,
        config_digest="c" * 64,
        parent_digests=(),
        type_body={"fixture": "registered-root"},
    )
    second = artifacts.build_artifact(
        artifact_type="M4IsolatedHistorySnapshotV11",
        task_key="m4-isolated-24h-challenger-v11-2026101-history-snapshot",
        target_issue="2026101",
        git_commit="a" * 40,
        source_contract_digest="b" * 64,
        config_digest="c" * 64,
        parent_digests=(first["artifact_digest"],),
        type_body={"fixture": "atomic-child"},
    )
    mainline.verify_registered_parent_closure(
        repository=_Repository(), payloads=(first, second)
    )
    raw_parent = deepcopy(second)
    raw_parent["parent_digests"] = ["d" * 64]
    raw_parent["body"]["input_digest"] = contract.domain_digest(
        raw_parent["parent_digests"],
        domain="dehps.m4.isolated-24h-challenger.input-set.v11",
    )
    type_body = {
        key: value
        for key, value in raw_parent["body"].items()
        if key not in artifacts.COMMON_BODY_KEYS
    }
    raw_parent["body"]["output_digest"] = contract.domain_digest(
        type_body,
        domain="dehps.m4.isolated-24h-challenger.output."
        "M4IsolatedHistorySnapshotV11.v11",
    )
    envelope = dict(raw_parent)
    envelope.pop("artifact_digest")
    raw_parent["artifact_digest"] = contract.domain_digest(
        envelope, domain=contract.ARTIFACT_DOMAIN
    )
    with pytest.raises(mainline.IsolatedMainlineError, match="not_registered"):
        mainline.verify_registered_parent_closure(
            repository=_Repository(), payloads=(raw_parent,)
        )


def test_registered_input_identities_are_exact_and_source_bound() -> None:
    source = "1" * 64
    schema = "2" * 64
    query = "3" * 64
    schedule = "4" * 64
    content = "5" * 64
    projection = "6" * 64
    commit = "a" * 40
    database = mainline.build_registered_input(
        artifact_type="M4IsolatedDatabaseSchemaIdentityV11",
        body={
            "schema_version": contract.DATABASE_SCHEMA_VERSION,
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_contract_digest": source,
            "installed_git_commit": commit,
        },
        parent_digests=(source,),
    )
    history_schema = mainline.build_registered_input(
        artifact_type="M4IsolatedHistorySchemaInputV11",
        body={
            "schema_digest": schema,
            "history_query_digest": query,
            "source_contract_digest": source,
        },
        parent_digests=(source,),
    )
    history_content = mainline.build_registered_input(
        artifact_type="M4IsolatedHistoryContentInputV11",
        body={
            "source_max_issue": "2026100",
            "source_max_draw_date": "2026-08-27",
            "target_issue": "2026101",
            "target_draw_date": "2026-08-30",
            "deadline": "2026-08-30T17:00:00+08:00",
            "official_draw_time": "2026-08-30T21:15:00+08:00",
            "projection_time": "2026-08-27T12:00:00+08:00",
            "history_query_digest": query,
            "history_content_digest": content,
            "schema_digest": schema,
            "schedule_contract_digest": schedule,
            "source_contract_digest": source,
        },
        parent_digests=(source, history_schema["artifact_digest"]),
    )
    draw_body = {
        "issue": "2026101",
        "draw_date": "2026-08-30",
        "red_numbers": [1, 2, 3, 4, 5, 6],
        "blue_number": 7,
        "history_source": "fixture",
        "payout_source": "zhcw",
        "payout_source_url": "https://jc.zhcw.com/port/client_json.php",
        "raw_record_sha256": "7" * 64,
        "tier_amounts_cny": {str(index): "0.00" for index in range(1, 7)},
    }
    draw_digest = contract.domain_digest(
        draw_body,
        domain="dehps.m4.isolated-24h-challenger.audited-draw.v11",
    )
    draw = mainline.build_registered_input(
        artifact_type="M4IsolatedAuditedDrawInputV11",
        artifact_digest=draw_digest,
        body=draw_body,
        parent_digests=(source, projection),
    )
    for value in (database, history_schema, history_content, draw):
        assert mainline.validate_registered_input_payload(value) == value
    corrupted = deepcopy(history_content)
    corrupted["body"]["source_contract_digest"] = "8" * 64
    with pytest.raises(mainline.IsolatedMainlineError, match="identity_changed"):
        mainline.validate_registered_input_payload(corrupted)


def test_history_registered_inputs_are_source_qualified_and_parent_bound(
    monkeypatch,
) -> None:
    raw_schema = "2" * 64
    raw_content = "5" * 64
    query = "3" * 64
    schedule = "4" * 64

    def values(source: str):
        schema = mainline.build_registered_input(
            artifact_type="M4IsolatedHistorySchemaInputV11",
            body={
                "schema_digest": raw_schema,
                "history_query_digest": query,
                "source_contract_digest": source,
            },
            parent_digests=(source,),
        )
        content = mainline.build_registered_input(
            artifact_type="M4IsolatedHistoryContentInputV11",
            body={
                "source_max_issue": "2026099",
                "source_max_draw_date": "2026-08-27",
                "target_issue": "2026100",
                "target_draw_date": "2026-08-30",
                "deadline": "2026-08-30T17:00:00+08:00",
                "official_draw_time": "2026-08-30T21:15:00+08:00",
                "projection_time": "2026-08-28T00:27:06.982677+08:00",
                "history_query_digest": query,
                "history_content_digest": raw_content,
                "schema_digest": raw_schema,
                "schedule_contract_digest": schedule,
                "source_contract_digest": source,
            },
            parent_digests=(source, schema["artifact_digest"]),
        )
        return schema, content

    first_schema, first_content = values("1" * 64)
    second_schema, second_content = values("6" * 64)
    assert first_schema["body"]["schema_digest"] == raw_schema
    assert second_schema["body"]["schema_digest"] == raw_schema
    assert first_content["body"]["history_content_digest"] == raw_content
    assert second_content["body"]["history_content_digest"] == raw_content
    assert first_schema["artifact_digest"] != second_schema["artifact_digest"]
    assert first_content["artifact_digest"] != second_content["artifact_digest"]

    monkeypatch.setattr(
        mainline,
        "load_registered_input",
        lambda **_kwargs: first_schema,
    )
    mainline._validate_history_content_parent_binding(
        repository=object(), payload=first_content
    )
    corrupted_schema = deepcopy(first_schema)
    corrupted_schema["body"]["schema_digest"] = "7" * 64
    monkeypatch.setattr(
        mainline,
        "load_registered_input",
        lambda **_kwargs: corrupted_schema,
    )
    with pytest.raises(mainline.IsolatedMainlineError, match="schema_parent_changed"):
        mainline._validate_history_content_parent_binding(
            repository=object(), payload=first_content
        )


def test_production_target_projection_uses_target_issue_only_as_common_field(
    monkeypatch,
) -> None:
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        projection_time="2026-08-28T00:27:06.982677+08:00",
    )
    source_digest = "1" * 64
    projection = {
        "source_max_issue": context["source_max_issue"],
        "source_max_draw_date": context["source_max_draw_date"],
        "target_issue": context["target_issue"],
        "target_draw_date": context["target_draw_date"],
        "deadline": "2026-08-30T17:00:00+08:00",
        "official_draw_time": "2026-08-30T21:15:00+08:00",
        "projection_time": context["projection_time"],
        "history_query_digest": "2" * 64,
        "history_content_digest": "3" * 64,
        "schema_digest": "4" * 64,
        "schedule_contract_digest": "5" * 64,
    }
    capability = mainline.IsolatedV11Capability(
        capability_name="M4IsolatedTargetIssueProjectionCapabilityV11",
        context=context,
        source_digest=source_digest,
        simulation=False,
        repository=SimpleNamespace(connection_factory=lambda: None),
        root_dir=Path.cwd(),
    )
    capability._upstream = lambda _name: (
        {
            "artifact_type": "M4IsolatedPreregistrationV11",
            "artifact_digest": "6" * 64,
        },
    )
    monkeypatch.setattr(
        mainline.search,
        "load_target_issue_projection",
        lambda *_args, **_kwargs: dict(projection),
    )
    monkeypatch.setattr(mainline, "load_registered_input", lambda **_kwargs: {})
    monkeypatch.setattr(
        mainline,
        "register_input_artifact",
        lambda *, payload, **_kwargs: payload,
    )
    artifact = capability._target_projection(
        task_key=contract.task_template_by_name("target_issue_projection").key(context),
        git_commit="a" * 40,
    )[0]
    assert artifact["body"]["target_issue"] == "2026100"
    type_body = {
        key: value
        for key, value in artifact["body"].items()
        if key not in artifacts.COMMON_BODY_KEYS
    }
    assert "target_issue" not in type_body
    assert type_body == {
        key: value for key, value in projection.items() if key != "target_issue"
    }
    assert artifacts.validate_artifact(artifact) == artifact


def test_production_history_snapshot_uses_target_issue_only_as_common_field(
    monkeypatch,
) -> None:
    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
        projection_time="2026-08-28T00:27:06.982677+08:00",
    )
    source_digest = "1" * 64
    projection = {
        "artifact_type": "M4IsolatedTargetIssueProjectionV11",
        "artifact_digest": "2" * 64,
        "body": {
            "source_max_issue": "2026099",
            "source_max_draw_date": "2026-08-27",
            "target_issue": "2026100",
            "target_draw_date": "2026-08-30",
            "history_query_digest": contract.domain_digest(
                mainline.search.TARGET_PROJECTION_SQL,
                domain="dehps.m4.isolated-24h-challenger.schema-query.v11",
            ),
        },
    }
    preregistration = {
        "artifact_type": "M4IsolatedPreregistrationV11",
        "artifact_digest": "3" * 64,
    }
    history = (
        mainline.search.HistoryRow(
            issue="2026099",
            draw_date=datetime(2026, 8, 27, tzinfo=UTC).date(),
            red_numbers=(1, 2, 3, 4, 5, 6),
            blue_number=7,
            source="fixture",
        ),
    )
    capability = mainline.IsolatedV11Capability(
        capability_name="M4IsolatedHistorySnapshotCapabilityV11",
        context=context,
        source_digest=source_digest,
        simulation=False,
        repository=SimpleNamespace(connection_factory=lambda: None),
        root_dir=Path.cwd(),
    )
    capability._upstream = lambda name: (
        preregistration if name == "preregistration" else projection,
    )
    monkeypatch.setattr(
        mainline.search,
        "load_history",
        lambda *_args, **_kwargs: history,
    )
    artifact = capability._history_snapshot(
        task_key=contract.task_template_by_name("history_snapshot").key(context),
        git_commit="a" * 40,
    )[0]
    assert artifact["body"]["target_issue"] == "2026100"
    type_body = {
        key: value
        for key, value in artifact["body"].items()
        if key not in artifacts.COMMON_BODY_KEYS
    }
    assert "target_issue" not in type_body
    assert type_body["target_draw_date"] == "2026-08-30"
    assert type_body[
        "history_snapshot_digest"
    ] == mainline.search.history_snapshot_digest(
        history,
        target_issue="2026100",
        target_draw_date="2026-08-30",
    )
    assert artifacts.validate_artifact(artifact) == artifact


def test_production_genesis_uses_target_issue_only_as_common_field() -> None:
    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params=None):
            self.statement = statement
            return self

        def fetchone(self):
            assert "multiplicity_head" in self.statement
            return (-1, 0, None)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def cursor():
            return _Cursor()

    context = contract.render_context(
        source_max_issue="2026099",
        source_max_draw_date="2026-08-27",
        target_issue="2026100",
        target_draw_date="2026-08-30",
    )
    capability = mainline.IsolatedV11Capability(
        capability_name="M4IsolatedSearchGenesisCapabilityV11",
        context=context,
        source_digest="1" * 64,
        simulation=False,
        repository=SimpleNamespace(connection_factory=lambda: _Connection()),
        root_dir=Path.cwd(),
    )
    capability._active_created_at = "2026-08-28T00:00:00+08:00"
    parents = {
        "preregistration": {
            "artifact_type": "M4IsolatedPreregistrationV11",
            "artifact_digest": "2" * 64,
        },
        "history_snapshot": {
            "artifact_type": "M4IsolatedHistorySnapshotV11",
            "artifact_digest": "3" * 64,
        },
    }
    capability._upstream = lambda name: (parents[name],)
    values = capability._genesis(
        task_key=contract.task_template_by_name("genesis").key(context),
        git_commit="a" * 40,
    )
    assert {item["artifact_type"] for item in values} == {
        "M4IsolatedEmptyMultiplicityHeadV11",
        "M4IsolatedSearchCheckpointV11",
    }
    for item in values:
        assert item["body"]["target_issue"] == "2026100"
        type_body = {
            key: value
            for key, value in item["body"].items()
            if key not in artifacts.COMMON_BODY_KEYS
        }
        assert "target_issue" not in type_body
        assert artifacts.validate_artifact(item) == item


def test_literal_production_type_bodies_never_repeat_common_envelope_fields() -> None:
    tree = ast.parse(Path(mainline.__file__).read_text(encoding="utf-8"))
    overlaps: list[tuple[int, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not (
            isinstance(node.func, ast.Attribute) and node.func.attr == "_build"
        ):
            continue
        keyword = next(
            (item for item in node.keywords if item.arg == "type_body"), None
        )
        if keyword is None or not isinstance(keyword.value, ast.Dict):
            continue
        keys = {
            item.value
            for item in keyword.value.keys
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
        overlap = sorted(keys & artifacts.COMMON_BODY_KEYS)
        if overlap:
            overlaps.append((node.lineno, overlap))
    assert overlaps == []


def test_atomic_registration_timestamp_compares_aware_instants() -> None:
    expected = "2026-08-27T19:41:59.920157+00:00"
    same_instant = datetime.fromisoformat("2026-08-28T03:41:59.920157+08:00")
    assert mainline._same_aware_timestamp_instant(same_instant, expected) is True
    assert (
        mainline._same_aware_timestamp_instant(
            datetime.fromisoformat("2026-08-28T03:41:59.920158+08:00"), expected
        )
        is False
    )
    assert (
        mainline._same_aware_timestamp_instant(
            datetime.fromisoformat("2026-08-28T03:41:59.920157"), expected
        )
        is False
    )


def test_registered_input_persistence_is_exact_and_idempotent() -> None:
    source = "1" * 64
    commit = "a" * 40
    value = mainline.build_registered_input(
        artifact_type="M4IsolatedDatabaseSchemaIdentityV11",
        body={
            "schema_version": contract.DATABASE_SCHEMA_VERSION,
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_contract_digest": source,
            "installed_git_commit": commit,
        },
        parent_digests=(source,),
    )
    stored: dict[str, tuple[object, ...]] = {}

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            if statement.startswith("INSERT"):
                assert params is not None
                stored.setdefault(
                    str(params[0]),
                    (
                        params[1],
                        json.loads(str(params[2])),
                        json.loads(str(params[3])),
                        params[4],
                        params[5],
                        params[6],
                    ),
                )
            else:
                self.selected = str(params[0])
            return self

        def fetchone(self):
            return stored.get(self.selected)

        def fetchall(self):
            row = stored.get(self.selected)
            return [] if row is None else [row]

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

    repository = _Repository()
    first = mainline.register_input_artifact(
        repository=repository,
        payload=value,
        git_commit=commit,
    )
    second = mainline.register_input_artifact(
        repository=repository,
        payload=value,
        git_commit=commit,
    )
    assert first == second == value
    assert (
        mainline.load_registered_input(
            repository=repository,
            artifact_digest=value["artifact_digest"],
            expected_artifact_type="M4IsolatedDatabaseSchemaIdentityV11",
        )
        == value
    )
    row = stored[value["artifact_digest"]]
    stored[value["artifact_digest"]] = (*row[:-1], "f" * 64)
    with pytest.raises(mainline.IsolatedMainlineError, match="registration_changed"):
        mainline.load_registered_input(
            repository=repository,
            artifact_digest=value["artifact_digest"],
        )


def test_operator_attestation_corruption_is_rejected() -> None:
    valid = {
        "operator_request_id": 704,
        "approval_decision_id": 2955,
        "execution_id": 562,
        "payload_sha256": "a" * 64,
        "environment": "production",
        "scope_digest": "b" * 64,
        "secret_values_serialized": False,
    }
    artifacts.validate_operator_attestation_body(valid)
    corrupted = {**valid, "secret_values_serialized": True}
    with pytest.raises(artifacts.IsolatedArtifactError, match="secret_boundary"):
        artifacts.validate_operator_attestation_body(corrupted)


def test_thermal_guard_requires_exact_pause_and_resume_intervals(
    monkeypatch, tmp_path: Path
) -> None:
    start = datetime(2026, 8, 27, tzinfo=UTC)
    observations = iter(
        (
            (92.0, start),
            (92.0, start + timedelta(seconds=10)),
            (79.0, start + timedelta(seconds=20)),
            (79.0, start + timedelta(seconds=320)),
            (100.0, start + timedelta(seconds=330)),
        )
    )

    def observation():
        temperature, observed_at = next(observations)
        return {
            "query_ok": True,
            "source": "fixture",
            "max_cpu_celsius": temperature,
            "sample_count": 1,
            "observed_at": observed_at.isoformat(),
            "observed_monotonic_ns": int(observed_at.timestamp() * 1_000_000_000),
        }

    monkeypatch.setattr(mainline, "thermal_observation", observation)
    guard = mainline.ThermalGuard(root_dir=tmp_path)
    guard.sample(force=True)
    assert guard.paused is False
    guard.sample(force=True)
    assert guard.paused is True
    guard.sample(force=True)
    assert guard.paused is True
    guard.sample(force=True)
    assert guard.paused is False
    guard.sample(force=True)
    assert guard.paused is True
    assert guard.hard_stop_seen is True


def test_incident_open_advances_registered_head_chain(
    monkeypatch, tmp_path: Path
) -> None:
    offending = "e" * 64
    context = contract.render_context(
        source_max_issue="2026100",
        source_max_draw_date="2026-08-30",
        incident_reason_code="REPLAY_FAILED",
        incident_offending_digest=offending,
    )

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            assert "research_os_mainline_artifacts" in statement
            assert params == (offending,)
            return self

        @staticmethod
        def fetchone():
            return (1,)

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

    previous = {
        "artifact_digest": "f" * 64,
        "body": {"incident_seq": 6, "open_count": 7},
    }
    capability = mainline.IsolatedV11Capability(
        capability_name="M4IsolatedIncidentOpenCapabilityV11",
        context=context,
        source_digest="b" * 64,
        simulation=False,
        repository=_Repository(),
        root_dir=tmp_path,
    )
    capability._active_created_at = "2026-08-27T00:00:00+00:00"
    monkeypatch.setattr(capability, "_latest_incident_head", lambda: previous)
    incident, head = capability._incident_open(
        task_key=contract.task_template_by_name("incident_open").key(context),
        git_commit="a" * 40,
    )
    assert incident["parent_digests"] == [offending]
    assert incident["body"]["reason_code"] == "REPLAY_FAILED"
    assert head["parent_digests"] == [
        previous["artifact_digest"],
        incident["artifact_digest"],
    ]
    assert head["body"]["incident_seq"] == 7
    assert head["body"]["open_count"] == 8


@pytest.mark.parametrize(
    ("mode", "expected_reason"),
    [
        ("missing", "P3_ISSUE_TASK_MISSING"),
        ("not_complete", "P3_ISSUE_TASK_NOT_COMPLETE"),
        ("registration", "P3_REGISTRATION_COUNT_MISMATCH"),
        ("artifact", "P3_ARTIFACT_IDENTITY_MISMATCH"),
        ("generic", "P3_GENERIC_REPLAY_NOT_VERIFIED"),
        ("identity", "P3_ARTIFACT_IDENTITY_MISMATCH"),
    ],
)
def test_formal_p3_comparison_pending_reason_is_explicit(
    monkeypatch, tmp_path: Path, mode: str, expected_reason: str
) -> None:
    context = _context()
    issue = context["target_issue"]
    keys = mainline.formal_p3.issue_task_keys(issue)
    required_keys = {
        mainline.formal_p3.PREREGISTRATION_TASK_KEY,
        keys["refit"],
        keys["predraw"],
        keys["predraw_replay"],
        keys["settlement"],
        keys["settlement_replay"],
    }

    class _Repository:
        @staticmethod
        def load_manifest(*, control_plane_key):
            assert control_plane_key == "m4-information-theory-mainline"
            task_keys = set() if mode == "missing" else required_keys
            return SimpleNamespace(
                tasks=[SimpleNamespace(task_key=item) for item in task_keys]
            )

    capability = mainline.IsolatedV11Capability(
        capability_name="M4IsolatedFormalP3ComparisonInputCapabilityV11",
        context=context,
        source_digest="b" * 64,
        simulation=False,
        repository=_Repository(),
        root_dir=tmp_path,
    )
    settlement = {
        "artifact_type": "M4IsolatedSettlementV11",
        "artifact_digest": "c" * 64,
    }
    preregistration = {
        "artifact_type": "M4IsolatedPreregistrationV11",
        "artifact_digest": "d" * 64,
    }
    capability._upstream = lambda name: (  # type: ignore[method-assign]
        settlement if name == "settlement" else preregistration,
    )

    p3 = mainline.formal_p3
    p3_prereg = {
        "artifact_type": p3.PREREGISTRATION_ARTIFACT_TYPE,
        "artifact_digest": "1" * 64,
    }
    p4_prereg = {
        "artifact_type": p3.P4_PREREGISTRATION_ARTIFACT_TYPE,
        "artifact_digest": "2" * 64,
    }
    dataset = {
        "artifact_type": p3.DATASET_ARTIFACT_TYPE,
        "artifact_digest": "3" * 64,
        "body": {"target_issue": "1900001", "future_rows_read": False},
        "parent_digests": [
            p3_prereg["artifact_digest"],
            contract.FORMAL_P3_SOURCE_DIGEST,
        ],
    }
    model = {
        "artifact_type": p3.MODEL_ARTIFACT_TYPE,
        "artifact_digest": "4" * 64,
        "body": {
            "target_issue": issue,
            "lineage_id": contract.FORMAL_P3_LINEAGE,
            "source_digest": contract.FORMAL_P3_SOURCE_DIGEST,
            "future_rows_read": False,
        },
        "parent_digests": [
            dataset["artifact_digest"],
            p3_prereg["artifact_digest"],
            contract.FORMAL_P3_SOURCE_DIGEST,
        ],
    }
    candidates = {
        "artifact_type": p3.MODEL_CANDIDATE_ARTIFACT_TYPE,
        "artifact_digest": "5" * 64,
    }
    baseline = {
        "artifact_type": p3.RANDOM_BASELINE_ARTIFACT_TYPE,
        "artifact_digest": "6" * 64,
    }
    checkpoint = {
        "artifact_type": p3.CHECKPOINT_ARTIFACT_TYPE,
        "artifact_digest": "7" * 64,
        "body": {
            "target_issue": issue,
            "lineage_id": contract.FORMAL_P3_LINEAGE,
            "source_digest": contract.FORMAL_P3_SOURCE_DIGEST,
            "status": "SEALED_BEFORE_DRAW",
            "configuration_drift": False,
        },
        "parent_digests": [
            model["artifact_digest"],
            candidates["artifact_digest"],
            baseline["artifact_digest"],
            p3_prereg["artifact_digest"],
        ],
    }
    report = {
        "artifact_type": p3.PREDRAW_REPORT_ARTIFACT_TYPE,
        "artifact_digest": "8" * 64,
    }
    predraw_replay = {
        "artifact_type": p3.PREDRAW_REPLAY_ARTIFACT_TYPE,
        "artifact_digest": "9" * 64,
        "body": {"target_issue": issue, "status": "REPLAY_VERIFIED"},
        "parent_digests": [
            candidates["artifact_digest"],
            baseline["artifact_digest"],
            checkpoint["artifact_digest"],
            report["artifact_digest"],
        ],
    }
    p3_settlement = {
        "artifact_type": p3.SETTLEMENT_ARTIFACT_TYPE,
        "artifact_digest": "a" * 64,
        "body": {
            "target_issue": issue,
            "lineage_id": contract.FORMAL_P3_LINEAGE,
            "configuration_drift": False,
        },
        "parent_digests": [
            model["artifact_digest"],
            candidates["artifact_digest"],
            baseline["artifact_digest"],
            checkpoint["artifact_digest"],
        ],
    }
    settlement_replay = {
        "artifact_type": p3.SETTLEMENT_REPLAY_ARTIFACT_TYPE,
        "artifact_digest": "e" * 64,
        "body": {"target_issue": issue, "status": "REPLAY_VERIFIED"},
        "parent_digests": [
            p3_settlement["artifact_digest"],
            checkpoint["artifact_digest"],
        ],
    }
    by_type = {
        item["artifact_type"]: item
        for item in (
            p3_prereg,
            p4_prereg,
            dataset,
            model,
            candidates,
            baseline,
            checkpoint,
            report,
            predraw_replay,
            p3_settlement,
            settlement_replay,
        )
    }

    def fake_load(**kwargs):
        if mode == "not_complete":
            raise mainline.IsolatedMainlineError("formal_p3_task_not_complete")
        if mode == "registration":
            raise mainline.IsolatedMainlineError("registration_count_changed")
        if mode == "artifact":
            raise mainline.IsolatedMainlineError("artifact_identity_changed")
        return "f" * 64, tuple(
            by_type[item] for item in kwargs["expected_artifact_types"]
        )

    monkeypatch.setattr(mainline, "load_formal_p3_completed_task_artifacts", fake_load)
    if mode == "generic":
        monkeypatch.setattr(
            mainline,
            "verify_formal_p3_generic_replay",
            lambda **_kwargs: (_ for _ in ()).throw(
                mainline.IsolatedMainlineError("generic_replay_failed")
            ),
        )
    else:
        monkeypatch.setattr(
            mainline, "verify_formal_p3_generic_replay", lambda **_kwargs: {}
        )
    output = capability._formal_p3_comparison_input(
        task_key=contract.task_template_by_name("formal_p3_comparison_input").key(
            context
        ),
        git_commit="a" * 40,
    )
    assert output[0]["artifact_type"] == "M4IsolatedFormalP3PendingMarkerV11"
    assert output[0]["body"]["reason_codes"] == [expected_reason]


def test_supervisor_registers_every_frozen_capability_without_unkeyed_dispatch() -> (
    None
):
    source = "b" * 64
    supervisor = mainline.IsolatedChallengerSupervisor(
        repository=PostgresResearchOSRepository(),
        context=_context(),
        source_digest=source,
        git_commit="a" * 40,
        require_clean_tree=False,
        simulation=True,
    )
    expected = {item.capability for item in contract.TASK_TEMPLATES}
    assert expected.issubset(supervisor.capabilities)
    assert set(supervisor.isolated_capability_names) == expected
