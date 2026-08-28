from __future__ import annotations

import ast
import hashlib
import json
import os
from copy import deepcopy
from dataclasses import asdict, replace
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
from dehps.research_os.models import (
    MainlineArtifactRegistration,
    MainlineExecutionEvent,
)
from dehps.research_os.repository import PostgresResearchOSRepository


def _context():
    return contract.render_context(
        source_max_issue="2026100", source_max_draw_date="2026-08-30"
    )


def test_inner_resource_probe_reads_exact_user_manager_formal_p3_unit(
    monkeypatch,
) -> None:
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

    monkeypatch.setattr(mainline.subprocess, "run", fake_run)
    observation = mainline.formal_p3_resource_observation()
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


def test_inner_resource_probe_remains_fail_closed_for_active_or_missing_user_unit(
    monkeypatch,
) -> None:
    def observation(stdout: str, *, returncode: int = 0) -> str:
        monkeypatch.setattr(
            mainline.subprocess,
            "run",
            lambda *_args, **_kwargs: SimpleNamespace(
                returncode=returncode, stdout=stdout
            ),
        )
        return contract.formal_p3_activity_state(
            mainline.formal_p3_resource_observation()
        )

    assert (
        observation(
            "LoadState=loaded\nActiveState=active\nSubState=running\n"
            "MainPID=42\nControlPID=0\n"
        )
        == "PREEMPT"
    )
    assert (
        observation(
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\n"
            "MainPID=0\nControlPID=0\n",
            returncode=1,
        )
        == "PREEMPT"
    )


def test_simulated_chain_covers_all_tasks_and_never_creates_sent() -> None:
    result = mainline.simulate_artifact_chain(
        context=_context(), git_commit="a" * 40, source_digest="b" * 64
    )
    assert result["status"] == "SIMULATION_REPLAY_VERIFIED"
    assert result["task_count"] == 43
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


@pytest.mark.skipif(
    os.getenv("DEHPS_TEST_POSTGRES") != "1",
    reason="set DEHPS_TEST_POSTGRES=1 for live read-only health-cohort acceptance",
)
def test_live_runtime_health_complete_provenance_and_frozen_cohort_are_exact() -> None:
    repository = PostgresResearchOSRepository()
    root_dir = Path(__file__).resolve().parents[3]
    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    preregistration_task = next(
        item
        for item in manifest.tasks
        if item.requested_capability == "M4IsolatedPreregistrationCapabilityV11"
    )
    preregistration = mainline._unique_type(
        mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=root_dir,
            task_key=preregistration_task.task_key,
        ),
        "M4IsolatedPreregistrationV11",
    )
    history = mainline.validated_runtime_health_history(
        repository=repository,
        root_dir=root_dir,
        preregistration=preregistration,
        manifest=manifest,
    )
    assert len(history) >= mainline._RUNTIME_HEALTH_LEGACY_COUNT
    legacy = history[: mainline._RUNTIME_HEALTH_LEGACY_COUNT]
    assert {item["parent_digest"] for item in legacy} == {
        mainline._RUNTIME_HEALTH_LEGACY_ROOT_DIGEST
    }
    preimage = {
        "schema_version": mainline._RUNTIME_HEALTH_LEGACY_COHORT_SCHEMA,
        "field_order": list(mainline._RUNTIME_HEALTH_LEGACY_FIELD_ORDER),
        "records": [item["record"] for item in legacy],
    }
    assert (
        contract.domain_digest(
            preimage, domain=mainline._RUNTIME_HEALTH_LEGACY_COHORT_DOMAIN
        )
        == mainline._RUNTIME_HEALTH_LEGACY_COHORT_DIGEST
    )
    assert legacy[-1]["completed_at"].isoformat() == (
        mainline._RUNTIME_HEALTH_LEGACY_ANCHOR_RECORDED_AT
    )
    assert legacy[-1]["task_key"] == mainline._RUNTIME_HEALTH_LEGACY_ANCHOR_TASK_KEY
    assert legacy[-1]["artifact"]["artifact_digest"] == (
        mainline._RUNTIME_HEALTH_LEGACY_ANCHOR_ARTIFACT_DIGEST
    )
    assert any(item["minute"] == "202608300000" for item in legacy)
    assert legacy[-1]["minute"] != "202608300000"
    assert not any(
        fact.endswith(":HEALTH_RECORDED") for fact in manifest.facts.artifacts
    )
    assert all(item["record"][9] == f"{item['task_key']}:COMPLETE" for item in history)

    exact_execution = legacy[-1]["execution"]
    exact_summary = legacy[-1]["completed_summary"]
    mainline._validate_runtime_health_zero_operation_metadata(
        execution=exact_execution,
        completed_summary=exact_summary,
    )
    for key, expected in mainline._RUNTIME_HEALTH_EXECUTION_STATIC.items():
        corrupted_execution = deepcopy(exact_execution)
        corrupted_execution[key] = (
            not expected
            if isinstance(expected, bool)
            else ["changed"]
            if isinstance(expected, list)
            else expected + 1
            if isinstance(expected, int)
            else "changed"
        )
        with pytest.raises(
            mainline.IsolatedMainlineError,
            match="zero_operation_metadata_changed",
        ):
            mainline._validate_runtime_health_zero_operation_metadata(
                execution=corrupted_execution,
                completed_summary=exact_summary,
            )
    for key, expected in mainline._RUNTIME_HEALTH_COMPLETED_STATIC.items():
        corrupted_summary = deepcopy(exact_summary)
        corrupted_summary[key] = (
            not expected
            if isinstance(expected, bool)
            else ["changed"]
            if isinstance(expected, list)
            else expected + 1
            if isinstance(expected, int)
            else "changed"
        )
        with pytest.raises(
            mainline.IsolatedMainlineError,
            match="zero_operation_metadata_changed",
        ):
            mainline._validate_runtime_health_zero_operation_metadata(
                execution=exact_execution,
                completed_summary=corrupted_summary,
            )
    for target, key in (
        ("execution", "unexpected"),
        ("summary", "unexpected"),
        ("summary", "publication_batch_digest"),
    ):
        corrupted_execution = deepcopy(exact_execution)
        corrupted_summary = deepcopy(exact_summary)
        if target == "execution":
            corrupted_execution[key] = "changed"
        elif key == "publication_batch_digest":
            corrupted_summary[key] = "not-a-digest"
        else:
            corrupted_summary[key] = "changed"
        with pytest.raises(
            mainline.IsolatedMainlineError,
            match="zero_operation_metadata_changed",
        ):
            mainline._validate_runtime_health_zero_operation_metadata(
                execution=corrupted_execution,
                completed_summary=corrupted_summary,
            )

    with pytest.raises(
        mainline.IsolatedMainlineError, match="legacy_cohort_count_changed"
    ):
        mainline._validate_runtime_health_sequence(
            entries=legacy[:-1],
            preregistration_digest=mainline._RUNTIME_HEALTH_LEGACY_ROOT_DIGEST,
        )
    for field_index in range(len(mainline._RUNTIME_HEALTH_LEGACY_FIELD_ORDER)):
        changed = deepcopy(list(legacy))
        changed[0]["record"][field_index] = f"changed-{field_index}"
        with pytest.raises(
            mainline.IsolatedMainlineError, match="legacy_cohort_digest_changed"
        ):
            mainline._validate_runtime_health_sequence(
                entries=changed,
                preregistration_digest=mainline._RUNTIME_HEALTH_LEGACY_ROOT_DIGEST,
            )

    successor = deepcopy(legacy[-1])
    successor["completed_at"] = legacy[-1]["completed_at"] + timedelta(minutes=1)
    successor["task_key"] = "m4-isolated-24h-challenger-v11-runtime-health-successor"
    successor["minute"] = "202608280932"
    successor["completed_event_digest"] = "d" * 64
    successor["parent_digest"] = mainline._RUNTIME_HEALTH_LEGACY_ANCHOR_ARTIFACT_DIGEST
    successor["artifact"]["artifact_digest"] = "e" * 64
    accepted = mainline._validate_runtime_health_sequence(
        entries=(*legacy, successor),
        preregistration_digest=mainline._RUNTIME_HEALTH_LEGACY_ROOT_DIGEST,
    )
    assert accepted[-1]["artifact"]["artifact_digest"] == "e" * 64
    for mutation in ("parent", "retroactive", "duplicate_minute"):
        corrupted = deepcopy(successor)
        if mutation == "parent":
            corrupted["parent_digest"] = "0" * 64
        elif mutation == "retroactive":
            corrupted["completed_at"] = legacy[-1]["completed_at"]
        else:
            corrupted["minute"] = legacy[-1]["minute"]
        with pytest.raises(
            mainline.IsolatedMainlineError,
            match="successor_chain_changed|minute_not_unique",
        ):
            mainline._validate_runtime_health_sequence(
                entries=(*legacy, corrupted),
                preregistration_digest=mainline._RUNTIME_HEALTH_LEGACY_ROOT_DIGEST,
            )

    corrupted_manifest = replace(
        manifest,
        facts=replace(
            manifest.facts,
            artifacts=manifest.facts.artifacts
            | frozenset({f"{legacy[-1]['task_key']}:HEALTH_RECORDED"}),
        ),
    )
    with pytest.raises(
        mainline.IsolatedMainlineError,
        match="noncanonical_activation_fact",
    ):
        mainline.validated_runtime_health_history(
            repository=repository,
            root_dir=root_dir,
            preregistration=preregistration,
            manifest=corrupted_manifest,
        )

    missing_complete_manifest = replace(
        manifest,
        facts=replace(
            manifest.facts,
            artifacts=manifest.facts.artifacts
            - frozenset({f"{legacy[-1]['task_key']}:COMPLETE"}),
        ),
    )
    with pytest.raises(
        mainline.IsolatedMainlineError,
        match="completion_fact_changed",
    ):
        mainline.validated_runtime_health_history(
            repository=repository,
            root_dir=root_dir,
            preregistration=preregistration,
            manifest=missing_complete_manifest,
        )

    target_task_key = legacy[-1]["task_key"]

    class _CorruptingRepository:
        def __init__(self, mode: str):
            self.mode = mode

        def __getattr__(self, name):
            return getattr(repository, name)

        def list_mainline_execution_events(self, **kwargs):
            values = [
                dict(item)
                for item in repository.list_mainline_execution_events(**kwargs)
            ]
            if self.mode == "event" and kwargs.get("task_key") == target_task_key:
                values[0]["payload"] = [["git_commit", "0" * 40]]
            elif (
                self.mode == "completed_event"
                and kwargs.get("task_key") == target_task_key
            ):
                values[-1]["payload"] = [["simulation", True]]
            return tuple(values)

        def list_mainline_artifacts(self, **kwargs):
            values = [
                dict(item) for item in repository.list_mainline_artifacts(**kwargs)
            ]
            target_execution = legacy[-1]["record"][4]
            if kwargs.get("execution_id") != target_execution:
                return tuple(values)
            if self.mode == "missing_registration":
                values.pop()
            elif self.mode == "registration_identity":
                values[0]["task_digest"] = "0" * 64
            elif self.mode == "registration_path":
                values[0]["artifact_path"] = "runtime/wrong/artifact.json"
            elif self.mode == "registration_git":
                values[0]["git_commit"] = "0" * 40
            elif self.mode == "registration_parent":
                values[0]["parent_digests"] = ["0" * 64]
            return tuple(values)

    for mode in (
        "event",
        "completed_event",
        "missing_registration",
        "registration_identity",
        "registration_path",
        "registration_git",
        "registration_parent",
    ):
        with pytest.raises(
            (mainline.IsolatedMainlineError, mainline.MainlineSupervisorError)
        ):
            mainline.validated_runtime_health_history(
                repository=_CorruptingRepository(mode),
                root_dir=root_dir,
                preregistration=preregistration,
                manifest=manifest,
            )

    with pytest.raises(
        mainline.IsolatedMainlineError,
        match="source_registration_missing",
    ):
        mainline._validate_runtime_health_source_registrations(
            repository=repository,
            root_dir=root_dir,
            source_digests=("0" * 64,),
        )


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
    resolved = mainline._external_delivery_evidence(
        facts | {"m4-isolated-24h-challenger-v11-incident-bad-open:OPEN"},
        open_incident_ids=[],
    )
    assert resolved["real_mail_acceptance"] is True
    assert resolved["open_incident_count"] == 0


def test_runtime_migration_attestation_registered_input_identity_is_exact() -> None:
    value = mainline.build_runtime_migration_attestation_input(
        runtime_git_commit="a" * 40,
        runtime_source_contract_digest="b" * 64,
        operator_request_id=900,
        operator_approval_decision_id=901,
        operator_execution_id=902,
        operator_payload_sha256="c" * 64,
        operator_execution_started_at="2026-08-28T02:00:00+08:00",
    )
    assert mainline.validate_registered_input_payload(value) == value
    assert set(value) == {
        "schema_version",
        "artifact_type",
        "artifact_digest",
        "body",
        "parent_digests",
    }
    assert set(value["body"]) == (
        mainline._RUNTIME_MIGRATION_COMMON_KEYS | mainline._RUNTIME_MIGRATION_TYPE_KEYS
    )
    assert value["parent_digests"] == [
        contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        "b" * 64,
    ]
    assert value["body"]["created_at"] == "2026-08-27T18:00:00+00:00"
    corrupted = deepcopy(value)
    corrupted["body"]["task_key"] += "-alternate"
    identity = {
        key: item for key, item in corrupted.items() if key != "artifact_digest"
    }
    corrupted["artifact_digest"] = contract.domain_digest(
        identity, domain=contract.REGISTERED_INPUT_DOMAIN
    )
    with pytest.raises(mainline.IsolatedMainlineError, match="identity_changed"):
        mainline.validate_registered_input_payload(corrupted)


def test_runtime_migration_parent_sources_are_content_attested_from_git(
    monkeypatch,
) -> None:
    def source_payload(label: str) -> tuple[dict[str, object], bytes]:
        value: dict[str, object] = {
            "schema_version": contract.SOURCE_SCHEMA,
            "artifact_type": contract.SOURCE_ARTIFACT_TYPE,
            "source_set_digest": contract.domain_digest(
                [label, "source-set"], domain="fixture"
            ),
            "contract_key": contract.CONTRACT_KEY,
            "contract_digest": contract.CONTRACT_DIGEST,
            "governance_bindings": {"fixture": label},
            "runtime_versions": {"python": "fixture"},
            "source_entries": [
                {
                    "path": f"fixture/{label}.py",
                    "sha256": contract.domain_digest([label], domain="fixture"),
                    "bytes": 1,
                }
            ],
        }
        value["artifact_digest"] = contract.domain_digest(
            value, domain=contract.SOURCE_DOMAIN
        )
        content = json.dumps(
            value, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8")
        return value, content

    old_source, old_bytes = source_payload("old")
    new_source, new_bytes = source_payload("new")
    monkeypatch.setattr(
        mainline.contract,
        "DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST",
        old_source["artifact_digest"],
    )
    commits = ("a" * 40, "b" * 40)
    content_by_commit = {commits[0]: old_bytes, commits[1]: new_bytes}
    rows = [
        (
            source["artifact_digest"],
            contract.SOURCE_ARTIFACT_TYPE,
            source,
            [],
            commit,
            contract.SOURCE_CONTRACT_PATH,
            hashlib.sha256(content).hexdigest(),
        )
        for source, commit, content in (
            (old_source, commits[0], old_bytes),
            (new_source, commits[1], new_bytes),
        )
    ]

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            return self

        @staticmethod
        def fetchall():
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

    monkeypatch.setattr(
        mainline.subprocess,
        "run",
        lambda command, **_kwargs: SimpleNamespace(
            returncode=0, stdout=content_by_commit[command[2].split(":", 1)[0]]
        ),
    )
    attestation = {
        "artifact_type": contract.RUNTIME_MIGRATION_INPUT_TYPE,
        "parent_digests": [
            old_source["artifact_digest"],
            new_source["artifact_digest"],
        ],
        "body": {"runtime_source_contract_digest": new_source["artifact_digest"]},
    }
    mainline._validate_runtime_migration_source_parents(
        repository=_Repository(), payload=attestation
    )
    rows[0] = (*rows[0][:-1], "0" * 64)
    with pytest.raises(mainline.IsolatedMainlineError, match="parent_content_changed"):
        mainline._validate_runtime_migration_source_parents(
            repository=_Repository(), payload=attestation
        )


def test_registered_artifact_loader_reconstructs_digest_column(
    tmp_path: Path,
) -> None:
    payload = artifacts.build_artifact(
        artifact_type="M4IsolatedEmptyIncidentHeadV11",
        task_key="m4-isolated-24h-challenger-v11-incident-head-genesis",
        target_issue=None,
        git_commit="a" * 40,
        source_contract_digest="b" * 64,
        config_digest="c" * 64,
        parent_digests=("d" * 64,),
        type_body={
            "incident_seq": -1,
            "open_count": 0,
            "latest_incident_digest": None,
        },
        deterministic_seed=None,
        replay_status="NOT_APPLICABLE",
        created_at="2026-08-28T00:00:00+00:00",
    )
    relative = "runtime/isolated-24h-challenger-v11/artifacts/fixture/artifact.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    registration = MainlineArtifactRegistration(
        execution_id="e" * 64,
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=payload["body"]["task_key"],
        task_digest="f" * 64,
        artifact_digest=payload["artifact_digest"],
        artifact_type=payload["artifact_type"],
        schema_version=payload["schema_version"],
        artifact_path=relative,
        parent_digests=tuple(payload["parent_digests"]),
        git_commit="a" * 40,
    )
    rows = [
        {
            "registration_digest": registration.registration_digest,
            "registration_json": json.loads(
                json.dumps(asdict(registration), sort_keys=True)
            ),
        }
    ]

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            return self

        def fetchall(self):
            return rows

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def cursor(self, **_kwargs):
            return _Cursor()

    class _Repository:
        @staticmethod
        def connection_factory():
            return _Connection()

    loaded = mainline.load_registered_isolated_artifact(
        repository=_Repository(),
        root_dir=tmp_path,
        artifact_digest=payload["artifact_digest"],
    )
    assert loaded == payload
    rows[0]["registration_digest"] = "0" * 64
    with pytest.raises(mainline.MainlineSupervisorError):
        mainline.load_registered_isolated_artifact(
            repository=_Repository(),
            root_dir=tmp_path,
            artifact_digest=payload["artifact_digest"],
        )
    rows[0]["registration_digest"] = registration.registration_digest
    rows.clear()
    with pytest.raises(mainline.IsolatedMainlineError, match="identity_not_unique"):
        mainline.load_registered_isolated_artifact(
            repository=_Repository(),
            root_dir=tmp_path,
            artifact_digest=payload["artifact_digest"],
        )
    rows.append(
        {
            "registration_digest": registration.registration_digest,
            "registration_json": json.loads(
                json.dumps(asdict(registration), sort_keys=True)
            ),
        }
    )
    path.write_text(json.dumps({**payload, "artifact_digest": "0" * 64}))
    with pytest.raises(artifacts.IsolatedArtifactError, match="digest_mismatch"):
        mainline.load_registered_isolated_artifact(
            repository=_Repository(),
            root_dir=tmp_path,
            artifact_digest=payload["artifact_digest"],
        )


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


def test_registration_created_at_canonicalizes_aware_database_timestamp_to_utc() -> (
    None
):
    committed_at = datetime.fromisoformat("2026-08-28T03:56:35.300063+08:00")
    assert (
        mainline._canonical_registration_created_at(committed_at)
        == "2026-08-27T19:56:35.300063+00:00"
    )
    with pytest.raises(
        mainline.IsolatedMainlineError,
        match="registration_committed_at_timezone_changed",
    ):
        mainline._canonical_registration_created_at(
            datetime.fromisoformat("2026-08-28T03:56:35.300063")
        )


def test_exact_failed_event_recovery_hook_binds_event_and_attestation_chain(
    tmp_path: Path,
) -> None:
    shared = {
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "manifest_digest": mainline._EXACT_FAILED_RECOVERY_MANIFEST_DIGEST,
        "task_key": mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        "task_digest": mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
        "capability": "M4IsolatedSearchBatchCapabilityV11",
    }
    started = MainlineExecutionEvent(
        **shared,
        execution_id=mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        event_type="started",
        sequence=0,
        recorded_at="2026-08-27T19:56:35.300063+00:00",
        payload=(
            (
                "input_artifact_digests",
                [mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST],
            ),
            ("git_commit", mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT),
        ),
    )
    failed = MainlineExecutionEvent(
        **shared,
        execution_id=mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        event_type="failed",
        sequence=1,
        recorded_at="2026-08-27T20:59:52.863000+00:00",
        payload=(
            ("error", "atomic_registration_resume_changed"),
            ("git_commit", mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT),
        ),
    )

    def event_payload(event: MainlineExecutionEvent) -> dict[str, object]:
        return {
            "event_digest": event.artifact_digest,
            "execution_id": event.execution_id,
            "control_plane_key": event.control_plane_key,
            "manifest_digest": event.manifest_digest,
            "task_key": event.task_key,
            "task_digest": event.task_digest,
            "capability": event.capability,
            "event_type": event.event_type,
            "sequence": event.sequence,
            "recorded_at": event.recorded_at,
            "payload": list(event.payload),
        }

    assert (
        started.artifact_digest == mainline._EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST
    )
    assert failed.artifact_digest == mainline._EXACT_SEQUENCE2_FAILED_EVENT_DIGEST
    attestation = {
        "schema_version": (
            "dehps-m4-isolated-v11-same-key-event-isolation-runtime-migration.v2"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": mainline._EXACT_SEQUENCE2_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        "task_digest": mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
        "execution_id": mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        "started_event_digest": mainline._EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST,
        "origin_git_commit": mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT,
        "runtime_git_commit": "103aa7585257accf727020ea6454a3c1cc383267",
        "origin_source_contract_digest": (
            mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST
        ),
        "runtime_source_contract_digest": (
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed"
        ),
        "repair": "EXACT_SAME_KEY_EVENT_VIEW_AFTER_USER_SYSTEMD_GUARD_REPAIR",
        "predecessor_attestation_digest": (
            "4d2c037b172beaa525de05c855d0d0e1ad72e8978c271f3cdf68fb9d23aa6452"
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
            mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
            mainline._EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST,
            mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST,
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed",
            "4d2c037b172beaa525de05c855d0d0e1ad72e8978c271f3cdf68fb9d23aa6452",
            "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f",
        ],
    }
    identity = dict(attestation)
    identity.pop("artifact_digest")
    assert (
        contract.domain_digest(
            identity,
            domain=(
                "dehps.m4.isolated-24h-challenger."
                "same-key-event-isolation-runtime-migration.v11"
            ),
        )
        == mainline._EXACT_SEQUENCE2_ATTESTATION_DIGEST
    )
    path = (
        tmp_path
        / "runtime/research-os/mainline/tasks"
        / mainline._EXACT_FAILED_RECOVERY_TASK_KEY
        / mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID
        / "runtime-migrations"
        / mainline._EXACT_SEQUENCE2_ATTESTATION_DIGEST
        / "user-systemd-runtime-migration.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(attestation), encoding="utf-8")
    supervisor = object.__new__(mainline.IsolatedChallengerSupervisor)
    supervisor.root_dir = tmp_path
    supervisor.isolated_source_digest = (
        mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST
    )
    supervisor.failed_recovery_event_digest = (
        mainline._EXACT_SEQUENCE2_FAILED_EVENT_DIGEST
    )
    supervisor.failed_recovery_attestation_digest = (
        mainline._EXACT_SEQUENCE2_ATTESTATION_DIGEST
    )
    task = SimpleNamespace(
        task_key=mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        artifact_digest=mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
        input_artifact_digests=(mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST,),
    )
    events = (event_payload(started), event_payload(failed))

    class _Repository:
        @staticmethod
        def list_mainline_execution_events(**kwargs):
            assert kwargs == {
                "control_plane_key": contract.CONTROL_PLANE_KEY,
                "task_key": mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
                "execution_id": mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
            }
            return events

    supervisor.repository = _Repository()
    supervisor.control_plane_key = contract.CONTROL_PLANE_KEY
    assert (
        supervisor._validated_additional_failed_recovery_event(task=task, events=events)
        == events[1]
    )
    assert supervisor._has_validated_m4_p3_runtime_recovery(
        task=task,
        execution_id=mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        terminal_sequence=2,
    )
    assert supervisor._is_valid_atomic_terminal_event_set(
        task=task,
        events=events,
        terminal_sequence=2,
    )
    for changed in (
        {"execution_id": "f" * 64},
        {"terminal_sequence": 3},
        {
            "task": SimpleNamespace(
                task_key="changed",
                artifact_digest=mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
                input_artifact_digests=(
                    mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST,
                ),
            )
        },
    ):
        arguments = {
            "task": task,
            "execution_id": mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
            "terminal_sequence": 2,
            **changed,
        }
        with pytest.raises(
            mainline.MainlineSupervisorError,
            match="completion authorization changed",
        ):
            supervisor._has_validated_m4_p3_runtime_recovery(**arguments)
    path.write_text(json.dumps({**attestation, "repair": "changed"}), encoding="utf-8")
    with pytest.raises(
        mainline.MainlineSupervisorError,
        match="attestation changed",
    ):
        supervisor._validated_additional_failed_recovery_event(task=task, events=events)


def test_daily_recovery_hook_binds_exact_failed_prefix_and_registered_input(
    monkeypatch,
) -> None:
    runtime_git = "a" * 40
    runtime_source = "b" * 64
    attestation_digest = "c" * 64
    events = (
        {
            "event_digest": contract.DAILY_RECOVERY_STARTED_EVENT_DIGEST,
            "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
            "control_plane_key": contract.CONTROL_PLANE_KEY,
            "manifest_digest": contract.DAILY_RECOVERY_FAILED_MANIFEST_DIGEST,
            "task_key": contract.DAILY_RECOVERY_TASK_KEY,
            "task_digest": contract.DAILY_RECOVERY_TASK_DIGEST,
            "capability": "M4IsolatedDailySummaryCapabilityV11",
            "event_type": "started",
            "sequence": 0,
            "recorded_at": "2026-08-28T01:00:43.798450+00:00",
            "payload": [
                [
                    "input_artifact_digests",
                    [contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST],
                ],
                ["git_commit", contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT],
            ],
        },
        {
            "event_digest": contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST,
            "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
            "control_plane_key": contract.CONTROL_PLANE_KEY,
            "manifest_digest": contract.DAILY_RECOVERY_FAILED_MANIFEST_DIGEST,
            "task_key": contract.DAILY_RECOVERY_TASK_KEY,
            "task_digest": contract.DAILY_RECOVERY_TASK_DIGEST,
            "capability": "M4IsolatedDailySummaryCapabilityV11",
            "event_type": "failed",
            "sequence": 1,
            "recorded_at": "2026-08-28T01:00:44.641800+00:00",
            "payload": [
                ["error", "mainline artifact registration shape changed"],
                ["git_commit", contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT],
            ],
        },
    )
    task = SimpleNamespace(
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
        artifact_digest=contract.DAILY_RECOVERY_TASK_DIGEST,
        input_artifact_digests=(contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,),
    )

    class _Repository:
        @staticmethod
        def list_mainline_execution_events(**kwargs):
            assert kwargs == {
                "control_plane_key": contract.CONTROL_PLANE_KEY,
                "task_key": contract.DAILY_RECOVERY_TASK_KEY,
                "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
            }
            return events

    monkeypatch.setattr(
        mainline,
        "load_registered_input",
        lambda **kwargs: {
            "artifact_digest": kwargs["artifact_digest"],
            "body": {
                "runtime_git_commit": runtime_git,
                "runtime_source_contract_digest": runtime_source,
            },
        },
    )
    supervisor = object.__new__(mainline.IsolatedChallengerSupervisor)
    supervisor.repository = _Repository()
    supervisor.control_plane_key = contract.CONTROL_PLANE_KEY
    supervisor.isolated_source_digest = contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
    supervisor.failed_recovery_event_digest = (
        contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST
    )
    supervisor.failed_recovery_attestation_digest = attestation_digest
    supervisor.runtime_git_commit = runtime_git
    supervisor.runtime_source_contract_digest = runtime_source

    assert (
        supervisor._validated_additional_failed_recovery_event(task=task, events=events)
        == events[1]
    )
    assert supervisor._has_validated_m4_p3_runtime_recovery(
        task=task,
        execution_id=contract.DAILY_RECOVERY_EXECUTION_ID,
        terminal_sequence=2,
    )
    assert supervisor._is_valid_atomic_terminal_event_set(
        task=task, events=events, terminal_sequence=2
    )
    supervisor.runtime_source_contract_digest = "d" * 64
    with pytest.raises(
        mainline.MainlineSupervisorError, match="runtime identity changed"
    ):
        supervisor._validated_additional_failed_recovery_event(task=task, events=events)


def test_isolated_completion_hook_delegates_when_no_recovery_token(monkeypatch) -> None:
    supervisor = object.__new__(mainline.IsolatedChallengerSupervisor)
    supervisor.failed_recovery_event_digest = ""
    supervisor.failed_recovery_attestation_digest = ""
    task = SimpleNamespace(task_key="ordinary", artifact_digest="a" * 64)
    observed: list[tuple[object, str, int]] = []

    def delegated(self, *, task, execution_id, terminal_sequence=2):
        observed.append((task, execution_id, terminal_sequence))
        return True

    monkeypatch.setattr(
        mainline.supervisor_module.ResearchEvidenceSupervisor,
        "_has_validated_m4_p3_runtime_recovery",
        delegated,
    )
    assert supervisor._has_validated_m4_p3_runtime_recovery(
        task=task,
        execution_id="b" * 64,
        terminal_sequence=3,
    )
    assert observed == [(task, "b" * 64, 3)]

    terminal_observed: list[tuple[object, object, int]] = []

    def terminal_delegated(self, *, task, events, terminal_sequence):
        terminal_observed.append((task, events, terminal_sequence))
        return True

    monkeypatch.setattr(
        mainline.supervisor_module.ResearchEvidenceSupervisor,
        "_is_valid_atomic_terminal_event_set",
        terminal_delegated,
    )
    ordinary_events = ({"event_type": "started", "sequence": 0},)
    assert supervisor._is_valid_atomic_terminal_event_set(
        task=task,
        events=ordinary_events,
        terminal_sequence=1,
    )
    assert terminal_observed == [(task, ordinary_events, 1)]


def test_terminal_attempt_crash_resume_performs_zero_new_training() -> None:
    configurations = mainline.search.base_configurations(
        snapshot_digest="1" * 64,
        source_contract_digest="2" * 64,
    )
    jobs = mainline.search.plan_batch(configurations, cursor=0)
    initial_outcomes = {
        job.candidate_id: mainline.search.deterministic_candidate_result(job)
        for job in jobs
    }
    initial_attempts = tuple(
        mainline.search.CandidateAttemptOutcome(
            candidate_id=job.candidate_id,
            retry_ordinal=0,
            status=initial_outcomes[job.candidate_id].status,
            reason=initial_outcomes[job.candidate_id].error_code,
        )
        for job in jobs
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("terminal attempts must not be leased or executed again")

    outcomes, attempts = mainline.search.execute_history_jobs_with_retries(
        jobs,
        history=(),
        activity_probe=forbidden,
        quiescence_waiter=forbidden,
        initial_outcomes=initial_outcomes,
        initial_attempts=initial_attempts,
        on_lease=forbidden,
        on_started=forbidden,
        on_unstarted=forbidden,
        on_heartbeat=forbidden,
        on_attempt=forbidden,
        preemption_reason_probe=forbidden,
    )
    assert outcomes == tuple(initial_outcomes[job.candidate_id] for job in jobs)
    assert attempts == initial_attempts
    assert len(outcomes) == contract.ATTEMPTS_PER_BATCH


def test_exact_sequence3_guard_recovery_binds_three_events_and_attestation(
    tmp_path: Path,
) -> None:
    shared = {
        "control_plane_key": contract.CONTROL_PLANE_KEY,
        "manifest_digest": mainline._EXACT_FAILED_RECOVERY_MANIFEST_DIGEST,
        "task_key": mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        "task_digest": mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
        "capability": "M4IsolatedSearchBatchCapabilityV11",
        "execution_id": mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
    }
    records = (
        MainlineExecutionEvent(
            **shared,
            event_type="started",
            sequence=0,
            recorded_at="2026-08-27T19:56:35.300063+00:00",
            payload=(
                (
                    "input_artifact_digests",
                    [mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST],
                ),
                ("git_commit", mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            event_type="failed",
            sequence=1,
            recorded_at="2026-08-27T20:59:52.863000+00:00",
            payload=(
                ("error", "atomic_registration_resume_changed"),
                ("git_commit", mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT),
            ),
        ),
        MainlineExecutionEvent(
            **shared,
            event_type="failed",
            sequence=2,
            recorded_at="2026-08-27T21:48:34.466338+00:00",
            payload=(
                (
                    "error",
                    "M4-v2 atomic successor does not permit failed-execution recovery",
                ),
                ("git_commit", mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT),
            ),
        ),
    )

    def payload(event: MainlineExecutionEvent) -> dict[str, object]:
        return {
            "event_digest": event.artifact_digest,
            "execution_id": event.execution_id,
            "control_plane_key": event.control_plane_key,
            "manifest_digest": event.manifest_digest,
            "task_key": event.task_key,
            "task_digest": event.task_digest,
            "capability": event.capability,
            "event_type": event.event_type,
            "sequence": event.sequence,
            "recorded_at": event.recorded_at,
            "payload": list(event.payload),
        }

    events = tuple(payload(item) for item in records)
    assert records[2].artifact_digest == mainline._EXACT_SEQUENCE3_FAILED_EVENT_DIGEST
    attestation = {
        "schema_version": (
            "dehps-m4-isolated-v11-utc-registration-failed-event-runtime-migration.v3"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": mainline._EXACT_SEQUENCE3_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        "task_digest": mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
        "execution_id": mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        "started_event_digest": mainline._EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST,
        "failed_event_digest": mainline._EXACT_SEQUENCE2_FAILED_EVENT_DIGEST,
        "origin_git_commit": mainline._EXACT_FAILED_RECOVERY_ORIGIN_COMMIT,
        "runtime_git_commit": "c30db93efb428198b4d7c0c0548feefbd315ba59",
        "origin_source_contract_digest": (
            mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST
        ),
        "runtime_source_contract_digest": (
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780"
        ),
        "repair": "UTC_REGISTRATION_RESUME_AND_EXACT_FAILED_EVENT_RECOVERY",
        "predecessor_attestation_digest": (
            mainline._EXACT_SEQUENCE2_ATTESTATION_DIGEST
        ),
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
            mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
            mainline._EXACT_FAILED_RECOVERY_STARTED_EVENT_DIGEST,
            mainline._EXACT_SEQUENCE2_FAILED_EVENT_DIGEST,
            mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST,
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780",
            mainline._EXACT_SEQUENCE2_ATTESTATION_DIGEST,
            "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5",
        ],
    }
    identity = dict(attestation)
    identity.pop("artifact_digest")
    assert (
        contract.domain_digest(
            identity,
            domain=(
                "dehps.m4.isolated-24h-challenger."
                "utc-registration-failed-event-runtime-migration.v11"
            ),
        )
        == mainline._EXACT_SEQUENCE3_ATTESTATION_DIGEST
    )
    path = (
        tmp_path
        / "runtime/research-os/mainline/tasks"
        / mainline._EXACT_FAILED_RECOVERY_TASK_KEY
        / mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID
        / "runtime-migrations"
        / mainline._EXACT_SEQUENCE3_ATTESTATION_DIGEST
        / "user-systemd-runtime-migration.json"
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(attestation), encoding="utf-8")

    class _Repository:
        @staticmethod
        def list_mainline_execution_events(**_kwargs):
            return events

    supervisor = object.__new__(mainline.IsolatedChallengerSupervisor)
    supervisor.root_dir = tmp_path
    supervisor.repository = _Repository()
    supervisor.control_plane_key = contract.CONTROL_PLANE_KEY
    supervisor.isolated_source_digest = (
        mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST
    )
    supervisor.failed_recovery_event_digest = (
        mainline._EXACT_SEQUENCE3_FAILED_EVENT_DIGEST
    )
    supervisor.failed_recovery_attestation_digest = (
        mainline._EXACT_SEQUENCE3_ATTESTATION_DIGEST
    )
    task = SimpleNamespace(
        task_key=mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        artifact_digest=mainline._EXACT_FAILED_RECOVERY_TASK_DIGEST,
        input_artifact_digests=(mainline._EXACT_FAILED_RECOVERY_ORIGIN_SOURCE_DIGEST,),
    )
    assert supervisor._has_validated_m4_p3_runtime_recovery(
        task=task,
        execution_id=mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        terminal_sequence=3,
    )
    assert supervisor._is_valid_atomic_terminal_event_set(
        task=task,
        events=events,
        terminal_sequence=3,
    )
    assert not supervisor._is_valid_atomic_terminal_event_set(
        task=task,
        events=events,
        terminal_sequence=2,
    )
    corrupted = list(events)
    corrupted[2] = {**corrupted[2], "recorded_at": "2026-08-27T21:48:34+00:00"}
    with pytest.raises(
        mainline.MainlineSupervisorError,
        match="digest changed|guard event changed",
    ):
        supervisor._validated_additional_failed_recovery_event(
            task=task,
            events=tuple(corrupted),
        )
    with pytest.raises(
        mainline.MainlineSupervisorError,
        match="digest changed|guard event changed",
    ):
        supervisor._is_valid_atomic_terminal_event_set(
            task=task,
            events=tuple(corrupted),
            terminal_sequence=3,
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
        "body": {"transition_seq": 6, "open_count": 1},
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
    monkeypatch.setattr(
        capability,
        "_latest_incident_state",
        lambda: {
            "head": previous,
            "transition_seq": 6,
            "open_incident_ids": ["1" * 64],
            "open_count": 1,
            "resolved_incident_ids": [],
        },
    )
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
    assert head["body"]["transition_seq"] == 7
    assert head["body"]["transition_kind"] == "OPEN"
    assert head["body"]["open_count"] == 2
    assert head["body"]["open_incident_ids"] == sorted(
        ["1" * 64, context["incident_id"]]
    )


def test_incident_ledger_resolves_current_and_two_future_incidents(
    monkeypatch, tmp_path: Path
) -> None:
    context = _context()
    metric_contract = json.dumps(
        {"render_context": context}, sort_keys=True, separators=(",", ":")
    )
    source_digest = "b" * 64
    config_digest = "c" * 64
    git_commit = "a" * 40
    genesis_key = contract.task_template_by_name("incident_head_genesis").key(context)

    def build(
        artifact_type: str,
        task_key: str,
        parents: tuple[str, ...],
        type_body: dict[str, object],
        created_at: str,
    ) -> dict[str, object]:
        value = artifacts.build_artifact(
            artifact_type=artifact_type,
            task_key=task_key,
            target_issue=None,
            git_commit=git_commit,
            source_contract_digest=source_digest,
            config_digest=config_digest,
            parent_digests=parents,
            type_body=type_body,
            created_at=created_at,
        )
        return mainline.validate_v5_lifecycle_artifact(value)

    genesis = build(
        "M4IsolatedEmptyIncidentHeadV11",
        genesis_key,
        ("0" * 64,),
        {"incident_seq": -1, "open_count": 0, "latest_incident_digest": None},
        "2026-08-28T00:00:00+00:00",
    )
    tasks: list[SimpleNamespace] = []
    values_by_task: dict[str, tuple[dict[str, object], ...]] = {genesis_key: (genesis,)}
    facts: set[str] = set()
    previous = genesis
    resolved_ids: list[str] = []

    for ordinal, incident_id in enumerate(
        (contract.DAILY_RECOVERY_INCIDENT_ID, "2" * 64, "3" * 64)
    ):
        open_seq = ordinal * 2
        resolution_seq = open_seq + 1
        opened_at = f"2026-08-28T0{ordinal + 1}:00:00+00:00"
        resolved_at = f"2026-08-28T0{ordinal + 1}:30:00+00:00"
        open_key = f"m4-isolated-24h-challenger-v11-incident-{incident_id}-open"
        incident = build(
            "M4IsolatedIncidentV11",
            open_key,
            (f"{ordinal + 4:x}" * 64,),
            {
                "status": "OPEN",
                "incident_id": incident_id,
                "reason_code": "DEADLINE_OR_ABSENCE",
                "offending_artifact_digests": [f"{ordinal + 4:x}" * 64],
                "opened_at": opened_at,
            },
            opened_at,
        )
        if ordinal == 0:
            open_head = build(
                "M4IsolatedIncidentHeadV11",
                open_key,
                (previous["artifact_digest"], incident["artifact_digest"]),
                {
                    "incident_seq": 0,
                    "open_count": 1,
                    "latest_incident_digest": incident["artifact_digest"],
                    "opened_at": opened_at,
                },
                opened_at,
            )
        else:
            open_head = build(
                "M4IsolatedIncidentLedgerHeadV11",
                open_key,
                (previous["artifact_digest"], incident["artifact_digest"]),
                {
                    "transition_seq": open_seq,
                    "transition_kind": "OPEN",
                    "incident_id": incident_id,
                    "open_incident_ids": [incident_id],
                    "open_count": 1,
                    "previous_head_digest": previous["artifact_digest"],
                    "latest_incident_digest": incident["artifact_digest"],
                    "latest_resolution_digest": None,
                    "transition_at": opened_at,
                },
                opened_at,
            )
            facts.add(
                "m4-isolated-24h-challenger-v11-incident-ledger-head-"
                f"{open_seq}:ADVANCED"
            )
        values_by_task[open_key] = (incident, open_head)
        facts.add(f"{open_key}:OPEN")
        tasks.append(
            SimpleNamespace(
                task_key=open_key,
                requested_capability="M4IsolatedIncidentOpenCapabilityV11",
                metric_contract=metric_contract,
            )
        )
        resolution_key = (
            f"m4-isolated-24h-challenger-v11-incident-{incident_id}-resolution-v1"
        )
        incident_receipt = contract.domain_digest(
            [incident_id, "incident-receipt"], domain="fixture"
        )
        daily_replay = contract.domain_digest(
            [incident_id, "daily-replay"], domain="fixture"
        )
        daily_receipt = contract.domain_digest(
            [incident_id, "daily-receipt"], domain="fixture"
        )
        attestation = contract.domain_digest(
            [incident_id, "attestation"], domain="fixture"
        )
        completion = contract.domain_digest(
            [incident_id, "completed"], domain="fixture"
        )
        execution_id = contract.domain_digest(
            [incident_id, "execution"], domain="fixture"
        )
        resolution = build(
            "M4IsolatedIncidentResolutionV11",
            resolution_key,
            (
                incident["artifact_digest"],
                open_head["artifact_digest"],
                incident_receipt,
                daily_replay,
                daily_receipt,
                attestation,
            ),
            {
                "incident_id": incident_id,
                "reason_code": "DEADLINE_OR_ABSENCE",
                "resolution_kind": "RECOVERED_DAILY_MAIL_CHAIN_V1",
                "status": "RESOLVED",
                "open_fact": f"{open_key}:OPEN",
                "incident_artifact_digest": incident["artifact_digest"],
                "incident_receipt_digest": incident_receipt,
                "repair_proof_digest": daily_replay,
                "runtime_migration_attestation_digest": attestation,
                "recovered_task_key": contract.DAILY_RECOVERY_TASK_KEY,
                "recovered_execution_id": execution_id,
                "recovered_completion_event_digest": completion,
                "daily_summary_replay_digest": daily_replay,
                "daily_delivery_task_key": (
                    "m4-isolated-24h-challenger-v11-daily-20260828-delivery"
                ),
                "daily_receipt_digest": daily_receipt,
                "resolved_at": resolved_at,
            },
            resolved_at,
        )
        resolution_head = build(
            "M4IsolatedIncidentLedgerHeadV11",
            resolution_key,
            (open_head["artifact_digest"], resolution["artifact_digest"]),
            {
                "transition_seq": resolution_seq,
                "transition_kind": "RESOLVED",
                "incident_id": incident_id,
                "open_incident_ids": [],
                "open_count": 0,
                "previous_head_digest": open_head["artifact_digest"],
                "latest_incident_digest": incident["artifact_digest"],
                "latest_resolution_digest": resolution["artifact_digest"],
                "transition_at": resolved_at,
            },
            resolved_at,
        )
        values_by_task[resolution_key] = (resolution, resolution_head)
        facts.update(
            {
                f"{resolution_key}:RESOLVED",
                (
                    "m4-isolated-24h-challenger-v11-incident-ledger-head-"
                    f"{resolution_seq}:ADVANCED"
                ),
            }
        )
        tasks.append(
            SimpleNamespace(
                task_key=resolution_key,
                requested_capability=("M4IsolatedIncidentResolutionCapabilityV11"),
                metric_contract=metric_contract,
            )
        )
        previous = resolution_head
        resolved_ids.append(incident_id)

    manifest = SimpleNamespace(
        tasks=tuple(tasks), facts=SimpleNamespace(artifacts=frozenset(facts))
    )

    class _Repository:
        @staticmethod
        def load_manifest(**_kwargs):
            return manifest

        @staticmethod
        def list_mainline_execution_events(**_kwargs):
            return ({"event_type": "completed"},)

    monkeypatch.setattr(
        mainline,
        "load_completed_task_artifacts",
        lambda **kwargs: values_by_task[kwargs["task_key"]],
    )
    state = mainline.latest_incident_ledger_state(
        repository=_Repository(), root_dir=tmp_path
    )
    assert state["transition_seq"] == 5
    assert state["open_count"] == 0
    assert state["open_incident_ids"] == []
    assert state["resolved_incident_ids"] == sorted(resolved_ids)

    corrupted = deepcopy(values_by_task[tasks[-1].task_key][1])
    corrupted["body"]["transition_seq"] = 6
    values_by_task[tasks[-1].task_key] = (
        values_by_task[tasks[-1].task_key][0],
        corrupted,
    )
    with pytest.raises(mainline.IsolatedMainlineError, match="sequence_gap_or_branch"):
        mainline.latest_incident_ledger_state(
            repository=_Repository(), root_dir=tmp_path
        )


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


def test_exact_committed_replay_route_never_calls_shared_generic_loader(
    monkeypatch,
) -> None:
    context = _context()
    supervisor = object.__new__(mainline.IsolatedChallengerSupervisor)
    supervisor.isolated_context = context
    supervisor.repository = object()
    supervisor.root_dir = Path("/fixture")
    expected = {
        "status": "REPLAY_VERIFIED",
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "same_artifact_content": True,
        "all_registrations_and_parent_chains_exact": True,
        "manual_input_assembly": False,
        "dispatch_performed": False,
    }
    observed = []

    def exact(**kwargs):
        observed.append(kwargs)
        return expected

    monkeypatch.setattr(mainline, "replay_exact_sequence3_committed_execution", exact)
    monkeypatch.setattr(
        mainline.ResearchEvidenceSupervisor,
        "replay",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared generic loader must not run")
        ),
    )
    assert (
        supervisor.replay(
            task_key=mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
            execution_id=mainline._EXACT_FAILED_RECOVERY_EXECUTION_ID,
        )
        == expected
    )
    assert observed == [
        {"repository": supervisor.repository, "root_dir": Path("/fixture")}
    ]


def test_exact_committed_replay_route_requires_both_frozen_identities(
    monkeypatch,
) -> None:
    context = _context()
    supervisor = object.__new__(mainline.IsolatedChallengerSupervisor)
    supervisor.isolated_context = context
    supervisor.repository = object()
    supervisor.root_dir = Path("/fixture")
    monkeypatch.setattr(
        mainline, "replay_exact_sequence3_committed_execution", lambda **_kwargs: {}
    )
    delegated = {"status": "DELEGATED"}
    monkeypatch.setattr(
        mainline.ResearchEvidenceSupervisor,
        "replay",
        lambda *_args, **_kwargs: delegated,
    )
    monkeypatch.setattr(
        mainline, "load_completed_task_artifacts", lambda **_kwargs: ({},)
    )
    result = supervisor.replay(
        task_key=mainline._EXACT_FAILED_RECOVERY_TASK_KEY,
        execution_id="0" * 64,
    )
    assert result["status"] == "DELEGATED"
    assert result["same_artifact_content"] is True
