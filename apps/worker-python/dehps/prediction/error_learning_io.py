"""Exact-issue, read-only adapter to existing registered P3/report artifacts.

No discovery of results by filesystem glob, no aggregate reads, no dispatch,
schema initialization, training, settlement, SMTP or database writes.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dehps.db import get_connection
from dehps.notifications import p3_top100 as notification
from dehps.prediction.error_learning import DecisionIntegrityError, FrozenInputs, _require, _time
from dehps.research_os.information_theory.measurement_system_v2 import forward_prequential_confirmatory as p3
from dehps.research_os.repository import PostgresResearchOSRepository


class MissingFrozenInputError(ValueError):
    """Historical refit was never registered; cannot manufacture it now."""


@contextmanager
def read_only_connection():
    with get_connection() as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '15s'")
        yield connection


class ScopedReader:
    """Restrict existing loaders to named tasks and result-blind event metadata."""

    def __init__(self, repository: PostgresResearchOSRepository, *, issue: str, post: bool):
        issue = notification._issue(issue)
        self.repository = repository
        keys = p3.issue_task_keys(issue)
        self.allowed = {(notification.P3_CONTROL_PLANE_KEY, p3.PREREGISTRATION_TASK_KEY)}
        self.allowed.update((notification.P3_CONTROL_PLANE_KEY, keys[k])
                            for k in ("refit", "predraw", "predraw_replay"))
        if post:
            self.allowed.update((notification.P3_CONTROL_PLANE_KEY, keys[k])
                                for k in ("settlement", "settlement_replay"))
            nk = notification.issue_task_keys(issue)
            self.allowed.update((notification.CONTROL_PLANE_KEY, nk[k])
                                for k in ("post", "post_replay"))
        self.executions: set[tuple[str, str]] = set()
        self.audit: list[dict[str, Any]] = []
        self.registrations: list[dict[str, Any]] = []

    def load_manifest(self, *, control_plane_key: str):
        _require(any(cp == control_plane_key for cp, _ in self.allowed), "control_plane_outside_scope")
        return self.repository.load_manifest(control_plane_key=control_plane_key)

    def list_mainline_execution_events(self, *, control_plane_key: str, task_key: str):
        _require((control_plane_key, task_key) in self.allowed, "task_outside_opened_scope")
        events = self.repository.list_mainline_execution_event_metadata(
            control_plane_key=control_plane_key, task_keys=(task_key,))
        for event in events:
            if event["event_type"] == "completed":
                self.executions.add((control_plane_key, event["execution_id"]))
        self.audit.append({"task_key": task_key, "events": events})
        return events

    def list_mainline_artifacts(self, *, control_plane_key: str, execution_id: str):
        _require((control_plane_key, execution_id) in self.executions, "execution_outside_scope")
        records = self.repository.list_mainline_artifacts(control_plane_key=control_plane_key,
                                                          execution_id=execution_id)
        self.registrations.extend(records)
        return records


def load_frozen(reader: ScopedReader, *, issue: str, source_root: Path, code_root: Path) -> FrozenInputs:
    predraw = notification.load_predraw_bundle(reader, issue=issue, root_dir=source_root)
    refit_events = reader.list_mainline_execution_events(
        control_plane_key=notification.P3_CONTROL_PLANE_KEY, task_key=p3.issue_task_keys(issue)["refit"])
    if not refit_events:
        raise MissingFrozenInputError("registered_refit_dataset_and_model")
    refit = notification._completed_children(
        reader, root_dir=source_root, control_plane_key=notification.P3_CONTROL_PLANE_KEY,
        task_key=p3.issue_task_keys(issue)["refit"],
        expected_types={p3.DATASET_ARTIFACT_TYPE, p3.MODEL_ARTIFACT_TYPE},
        validator=p3.validate_artifact)
    prereg = notification._completed_children(
        reader, root_dir=source_root, control_plane_key=notification.P3_CONTROL_PLANE_KEY,
        task_key=p3.PREREGISTRATION_TASK_KEY,
        expected_types={p3.PREREGISTRATION_ARTIFACT_TYPE, p3.P4_PREREGISTRATION_ARTIFACT_TYPE},
        validator=p3.validate_artifact)
    # The actual registration time, not just a self-reported sealed_at field,
    # must precede the draw. Read neither interim review nor cumulative metrics.
    official = _time(predraw.checkpoint["body"]["official_draw_time"])
    for item in reader.audit:
        if item["task_key"] in {p3.issue_task_keys(issue)[k] for k in ("refit", "predraw", "predraw_replay")}:
            completed = [e for e in item["events"] if e["event_type"] == "completed"]
            _require(len(completed) == 1 and _time(completed[0]["recorded_at"]) < official,
                     "registration_not_before_draw")
    pre_tasks = {p3.PREREGISTRATION_TASK_KEY, *(p3.issue_task_keys(issue)[k]
                 for k in ("refit", "predraw", "predraw_replay"))}
    proof = [e for item in reader.audit if item["task_key"] in pre_tasks
             for e in item["events"] if e["event_type"] == "completed"]
    proof += [r for r in reader.registrations if r["task_key"] in pre_tasks]
    return FrozenInputs(p3.load_source_contract(root_dir=code_root),
                        prereg[p3.PREREGISTRATION_ARTIFACT_TYPE],
                        refit[p3.DATASET_ARTIFACT_TYPE], refit[p3.MODEL_ARTIFACT_TYPE], predraw, proof)


def load_opened(reader: ScopedReader, *, issue: str, source_root: Path):
    # Establish the already-open per-issue reporting artifact before loading the
    # settlement. This never runs the old report/recovery path.
    keys = notification.issue_task_keys(issue)
    reports = notification._completed_children(
        reader, root_dir=source_root, control_plane_key=notification.CONTROL_PLANE_KEY,
        task_key=keys["post"],
        expected_types={notification.POST_REPORT_ARTIFACT_TYPE, notification.PAYOUT_SOURCE_ARTIFACT_TYPE},
        validator=notification.validate_notification_artifact)
    replay = notification._completed_children(
        reader, root_dir=source_root, control_plane_key=notification.CONTROL_PLANE_KEY,
        task_key=keys["post_replay"], expected_types={notification.POST_REPLAY_ARTIFACT_TYPE},
        validator=notification.validate_notification_artifact)[notification.POST_REPLAY_ARTIFACT_TYPE]
    report, payout = reports[notification.POST_REPORT_ARTIFACT_TYPE], reports[notification.PAYOUT_SOURCE_ARTIFACT_TYPE]
    bundle = notification.load_postdraw_bundle(reader, issue=issue, root_dir=source_root)
    expected_report = notification.build_post_report(bundle=bundle, payout=payout,
                                                      recipient_digest=report["body"]["recipient_digest"])
    _require(report == expected_report, "opened_base_report_changed")
    expected_replay = notification.build_post_replay(report=report, expected=expected_report)
    _require(replay == expected_replay, "opened_report_replay_changed")
    completed = [e for item in reader.audit if item["task_key"] == p3.issue_task_keys(issue)["settlement"]
                 for e in item["events"] if e["event_type"] == "completed"]
    _require(bool(completed), "opened_report_completion_missing")
    # Availability is the audited settlement's durable completion. Access to the
    # label was separately gated above by the already-open report and replay.
    available_at = max(e["recorded_at"] for e in completed)
    _require(_time(available_at) <= datetime.now(timezone.utc), "opened_report_in_future")
    return bundle, payout, available_at, report
