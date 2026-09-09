"""Additive observation tasks. Never dispatch Formal P3, settlement or delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.notifications import p3_top100 as notification
from dehps.prediction import error_learning as learning
from dehps.prediction.error_learning_io import ScopedReader, load_frozen, load_opened
from dehps.research_os.information_theory.measurement_system_v2.migration import build_additive_task_manifest
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import AtomicArtifactPayload, AtomicCapabilityResult, MainlineSupervisorError, ResearchEvidenceSupervisor, integration_contract

CONTROL_PLANE_KEY = "prediction-error-learning-observation-v1"
GOAL_KEY = learning.GOAL
CAPABILITIES = {p: f"prediction_error_observation_{p}_v1" for p in ("record", "report")}
DOMAIN = "dehps.prediction-error-observation-mainline.v1"
SOURCE_PATHS = (
    "apps/worker-python/dehps/prediction/error_learning.py",
    "apps/worker-python/dehps/prediction/error_learning_io.py",
    "apps/worker-python/dehps/prediction/error_learning_mainline.py",
    "apps/worker-python/scripts/run_prediction_error_observations.py",
)


def source_digest(root: Path = ROOT_DIR) -> str:
    return canonical_digest({p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                             for p in SOURCE_PATHS}, domain=DOMAIN + ".source")


def task_key(issue: str, phase: str) -> str:
    learning._require(phase in CAPABILITIES, "observation_phase_changed")
    return f"prediction-error-observation-v1-{notification._issue(issue)}-{phase}"


def wrap(phase: str, payload: dict, parents: tuple[str, ...] = ()) -> dict:
    result = {"schema_version": "prediction-error-observation.v1",
              "artifact_type": f"PredictionErrorObservation{phase.title()}",
              "phase": phase, "body": payload, "parent_digests": list(parents)}
    result["artifact_digest"] = canonical_digest(result, domain=DOMAIN)
    return result


def validate(value: Mapping) -> dict:
    result = dict(value)
    digest = result.pop("artifact_digest", None)
    learning._require(result.get("phase") in CAPABILITIES and
                      wrap(result["phase"], result["body"], tuple(result["parent_digests"])) == dict(value),
                      "observation_artifact_changed")
    learning._require(canonical_digest(result, domain=DOMAIN) == digest,
                      "observation_digest_changed")
    return dict(value)


def initial_manifest(*, minimum_issue: str, source: str) -> dict:
    notification._issue(minimum_issue)
    return ControlPlaneManifest.from_dict({
        "schema_version": "research-os-control-plane-v1",
        "goals": [{"goal_key": GOAL_KEY, "semantic_version": "1.0.0",
                   "objective_class": "runtime_capability", "owner_lane": "maintenance",
                   "question": "Can actual frozen decisions produce reproducible observations and complete labels?",
                   "success_evidence": ["registered decision and report with deterministic replay"],
                   "baseline_metric_manifest": {"observation_integration": False},
                   "target_metric_manifest": {"minimum_issue": minimum_issue, "source_digest": source},
                   "guardrails": ["no_formal_prediction_change", "opened_issue_only", "no_delivery", "no_promotion"],
                   "status": "active"}], "tasks": [],
        "facts": {"artifacts": [], "evidence": [], "external_events": [], "authorities": []},
    }).to_dict(include_digest=True)


class ObservationCapability:
    def __init__(self, repository, root_dir: Path, code_root: Path = ROOT_DIR):
        self.repository, self.root_dir, self.code_root = repository, root_dir, code_root
        self._frozen_cache, self._opened_cache = {}, {}

    def frozen(self, issue: str):
        if issue not in self._frozen_cache:
            reader = ScopedReader(self.repository, issue=issue, post=False)
            self._frozen_cache[issue] = load_frozen(reader, issue=issue, source_root=self.root_dir, code_root=self.code_root)
        return self._frozen_cache[issue]

    def opened(self, issue: str):
        if issue not in self._opened_cache:
            self._opened_cache[issue] = load_opened(ScopedReader(self.repository, issue=issue, post=True),
                                                   issue=issue, source_root=self.root_dir)
        return self._opened_cache[issue]

    def stored(self, issue: str, phase: str):
        kind = f"PredictionErrorObservation{phase.title()}"
        return notification._completed_children(
            self.repository, root_dir=self.root_dir, control_plane_key=CONTROL_PLANE_KEY,
            task_key=task_key(issue, phase), expected_types={kind}, validator=validate)[kind]

    def inputs(self, issue: str, phase: str) -> tuple[str, ...]:
        frozen = self.frozen(issue)
        digests = (frozen.dataset["artifact_digest"], frozen.model["artifact_digest"],
                   *frozen.predraw.input_digests)
        if phase == "report":
            opened = self.opened(issue)
            digests += (self.stored(issue, "record")["artifact_digest"],
                        *opened[0].input_digests, opened[1]["artifact_digest"],
                        opened[3]["artifact_digest"])
        return (*dict.fromkeys(digests), source_digest(self.code_root))

    def check_task(self, task) -> tuple[str, str]:
        integration_contract(task)
        contract = json.loads(task.metric_contract)
        issue, phase = contract["issue"], contract["phase"]
        learning._require(task.task_key == task_key(issue, phase) and
                          task.requested_capability == CAPABILITIES[phase], "observation_task_changed")
        learning._require(task.input_artifact_digests == self.inputs(issue, phase),
                          "observation_inputs_changed")
        return issue, phase

    def report(self, issue: str) -> dict:
        record = self.stored(issue, "record")["body"]
        frozen = learning.restore_decision(record, code_root=self.code_root)
        learning._require(frozen == self.frozen(issue), "registered_decision_parents_changed")
        bundle, payout, available_at, _ = self.opened(issue)
        result = learning.build_preview(record, bundle, payout, code_root=self.code_root,
                                        available_at=available_at)
        result["integration"] = "INTEGRATED"
        result["execution_path"] = "ResearchEvidenceSupervisor"
        return result

    def execute(self, *, control_plane_key, task, execution_id, git_commit):
        learning._require(control_plane_key == CONTROL_PLANE_KEY, "observation_control_plane_changed")
        issue, phase = self.check_task(task)
        payload = (learning.capture_decision(self.frozen(issue), code_root=self.code_root)
                   if phase == "record" else self.report(issue))
        value = wrap(phase, payload, task.input_artifact_digests)
        return AtomicCapabilityResult(
            artifacts=(AtomicArtifactPayload("prediction-error-observation", "observation.json", value),),
            completion_facts=(task.task_key + ":COMPLETE",),
            execution_metadata=(("issue", issue), ("phase", phase),
                                ("formal_prediction_changed", False), ("scientific_credit", False)),
        )

    def verify(self, task) -> dict:
        issue, phase = self.check_task(task)
        stored = self.stored(issue, phase)
        if phase == "record":
            restored = learning.restore_decision(stored["body"], code_root=self.code_root)
            learning._require(restored == self.frozen(issue), "observation_record_replay_changed")
        else:
            learning._require(stored == wrap(phase, self.report(issue), task.input_artifact_digests), "observation_report_replay_changed")
        return stored


class ObservationSupervisor(ResearchEvidenceSupervisor):
    def __init__(self, *, code_root: Path = ROOT_DIR, **kwargs):
        from dehps.research_os import supervisor as base
        registered = base._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE.get(CONTROL_PLANE_KEY)
        if registered not in (None, "mainline"):
            raise MainlineSupervisorError("observation artifact namespace changed")
        base._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE[CONTROL_PLANE_KEY] = "mainline"
        super().__init__(control_plane_key=CONTROL_PLANE_KEY, **kwargs)
        self.observer = ObservationCapability(self.repository, self.root_dir, code_root)
        self.capabilities = {name: self.observer for name in CAPABILITIES.values()}

    @property
    def state_path(self):
        return self.root_dir / "runtime/logs/prediction-error-observation-state.json"

    def _write_state(self, payload):
        atomic_write_text(self.state_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _build_lane_status(self, manifest, *, snapshot, dispatch_performed, **kwargs):
        ready = [x.task_key for x in snapshot.ready_queue]
        return {"schema_version": "prediction-error-observation-status.v1",
                "control_plane_key": CONTROL_PLANE_KEY, "goal": GOAL_KEY,
                "manifest_digest": manifest.artifact_digest, "snapshot_digest": snapshot.snapshot_digest,
                "ready_queue": ready, "next_ready_task": ready[0] if ready else None,
                "dispatch_performed": dispatch_performed, "formal_prediction_changed": False,
                "scientific_credit": False, "model_replacement": False}

    def replay(self, *, task_key: str, execution_id: str | None = None):
        manifest = self.repository.load_manifest(control_plane_key=CONTROL_PLANE_KEY)
        tasks = [t for t in manifest.tasks if t.task_key == task_key]
        learning._require(len(tasks) == 1, "observation_replay_task_missing")
        events = self.repository.list_mainline_execution_events(
            control_plane_key=CONTROL_PLANE_KEY, task_key=task_key, execution_id=execution_id)
        completed = [e for e in events if e["event_type"] == "completed"]
        learning._require(len(completed) == 1, "observation_completion_changed")
        # Replay rereads registered immutable parents instead of trusting a computation cache.
        self.observer._frozen_cache.clear()
        self.observer._opened_cache.clear()
        value = self.observer.verify(tasks[0])
        return {"status": "REPLAY_VERIFIED", "task_key": task_key,
                "execution_id": completed[0]["execution_id"], "artifact_digest": value["artifact_digest"],
                "same_execution_identity": True, "same_artifact_identity": True,
                "durable_state_changed": False, "dispatch_performed": False}


def add_task(live: dict, *, issue: str, phase: str, inputs: tuple[str, ...]) -> dict:
    key = task_key(issue, phase)
    next_consumer = (task_key(issue, "report") if phase == "record" else
                     "registered report replay and subsequent authorized offline learner")
    task = {"task_key": key, "goal_key": GOAL_KEY, "task_type": CAPABILITIES[phase],
            "requested_capability": CAPABILITIES[phase], "lane": "maintenance", "priority": 90,
            "input_artifact_digests": list(inputs), "status": "draft",
            "completion_classification": "INTEGRATION_PENDING",
            "dependencies": ([] if phase == "record" else [{"dependency_type": "task",
                              "target_key": task_key(issue, "record"), "required_status": "completed"}]),
            "metric_contract": {"issue": issue, "phase": phase, "scientific_credit": False,
                "mainline_integration": {"goal": GOAL_KEY,
                    "ready_condition": "exact registered parents verified; report additionally needs opened labels and decision",
                    "runner": "ObservationSupervisor via ResearchEvidenceSupervisor",
                    "upstream_artifacts": list(inputs), "downstream_artifacts": [phase],
                    "status_projection": "prediction-error-observation-state.json",
                    "downstream_consumer": next_consumer, "evidence_progress_rule": "zero scientific credit",
                    "decision_consumer": "engineering acceptance; Formal P3 gate unchanged"}}}
    return build_additive_task_manifest(live_payload=live, new_tasks=(task,))[0]
