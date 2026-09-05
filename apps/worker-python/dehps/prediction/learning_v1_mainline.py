"""Use the existing Research Evidence Supervisor with an isolated experiment DB."""
from __future__ import annotations

import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.prediction import learning_v1 as core
from dehps.prediction import learning_v1_runtime as runtime
from dehps.research_os.information_theory.measurement_system_v2.migration import build_additive_task_manifest
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import AtomicArtifactPayload, AtomicCapabilityResult, ResearchEvidenceSupervisor

CONTROL = core.GOAL
PHASES = ("freeze", "train-evaluate", "analysis")


def task_key(phase):
    return f"{CONTROL}-{phase}"


def manifest(contract):
    value = ControlPlaneManifest.from_dict({"schema_version": "research-os-control-plane-v1",
        "goals": [{"goal_key": core.GOAL, "semantic_version": "1.0.0", "objective_class": "prediction_quality",
            "owner_lane": "research", "question": "Do predefined marginal learning and portfolio changes improve exploratory walk-forward results?",
            "success_evidence": ["actual trained checkpoint, all contrasts, honest frozen decision and replay"],
            "baseline_metric_manifest": {"old": "EXPANDING_LEGAL_MARGINAL_ALPHA_1", "uniform": "6/33"},
            "target_metric_manifest": {"contract_digest": contract["artifact_digest"]},
            "guardrails": ["research_only", "no_formal_change", "no_mail", "no_outer_tuning", "one_round"],
            "status": "active"}], "tasks": [],
        "facts": {"artifacts": [], "evidence": [], "external_events": [], "authorities": []}}).to_dict(include_digest=True)
    tasks = []
    for index, phase in enumerate(PHASES):
        next_consumer = task_key(PHASES[index + 1]) if index + 1 < len(PHASES) else "deterministic replay and research-only validation decision"
        tasks.append({"task_key": task_key(phase), "goal_key": core.GOAL,
            "task_type": f"prediction_learning_{phase}", "requested_capability": f"prediction_learning_{phase}",
            "lane": "research", "priority": 90, "input_artifact_digests": [contract["artifact_digest"], contract["body"]["snapshot_digest"]],
            "status": "draft", "completion_classification": "INTEGRATION_PENDING",
            "dependencies": [] if index == 0 else [{"dependency_type": "task", "target_key": task_key(PHASES[index - 1]), "required_status": "completed"}],
            "metric_contract": {"phase": phase, "contract_digest": contract["artifact_digest"],
                "mainline_integration": {"goal": core.GOAL,
                    "ready_condition": "verified frozen contract and predecessor completed",
                    "runner": "LearningSupervisor via ResearchEvidenceSupervisor",
                    "upstream_artifacts": [contract["artifact_digest"], contract["body"]["snapshot_digest"]],
                    "downstream_artifacts": [phase], "status_projection": "experiment-local learning-status.json",
                    "downstream_consumer": next_consumer, "evidence_progress_rule": "exploratory only; no formal evidence credit",
                    "decision_consumer": "frozen research comparison; no production promotion"}}})
    return build_additive_task_manifest(live_payload=value, new_tasks=tasks)[0]


class LearningCapability:
    def __init__(self, root, output, repository):
        self.root, self.output, self.repository = root, output, repository

    def execute(self, *, control_plane_key, task, execution_id, git_commit):
        assert control_plane_key == CONTROL
        definition = json.loads(task.metric_contract)
        contract = core.read(self.output / "contract.json")
        assert contract["artifact_digest"] == definition["contract_digest"]
        assert contract["body"]["source"] == runtime.source_identity(self.root)
        phase = definition["phase"]
        if phase != "freeze":
            from dehps.research_os import supervisor as base
            previous = PHASES[PHASES.index(phase) - 1]
            _, _, parents = base._load_single_completed_execution(repository=self.repository,
                root_dir=self.root, control_plane_key=CONTROL, task_key=task_key(previous))
            parent_digests = {v["artifact_digest"] for v in parents}
            required_files = ("contract.json", "snapshot.json") if phase == "train-evaluate" else ("training.json", "checkpoint.json")
            assert all(core.read(self.output / p)["artifact_digest"] in parent_digests for p in required_files)
        if phase == "freeze":
            values = (core.read(self.output / "snapshot.json"), contract)
        elif phase == "train-evaluate":
            values = runtime.run_training(self.root, self.output)
        else:
            assert phase == "analysis"
            values = (runtime.analyze(self.root, self.output),)
            if core.read(self.output / "snapshot.json")["body"].get("production_read_only"):
                values += (runtime.experimental_prediction(self.output),)
        return AtomicCapabilityResult(artifacts=tuple(
            AtomicArtifactPayload(f"learning-{i}", f"learning-{i}.json", value) for i, value in enumerate(values)),
            completion_facts=(task.task_key + ":COMPLETE",),
            execution_metadata=(("research_only", True), ("formal_prediction_changed", False), ("phase", phase)))


class LearningSupervisor(ResearchEvidenceSupervisor):
    def __init__(self, *, output: Path, **kwargs):
        from dehps.research_os import supervisor as base
        assert base._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE.get(CONTROL) in (None, "mainline")
        base._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE[CONTROL] = "mainline"
        super().__init__(control_plane_key=CONTROL, **kwargs)
        self.output = output
        capability = LearningCapability(self.root_dir, output, self.repository)
        self.capabilities = {f"prediction_learning_{p}": capability for p in PHASES}

    @property
    def state_path(self):
        return self.output / "supervisor-state.json"

    def _build_lane_status(self, manifest, *, snapshot, dispatch_performed, **kwargs):
        ready = [t.task_key for t in snapshot.ready_queue]
        return {"goal": CONTROL, "manifest_digest": manifest.artifact_digest,
            "snapshot_digest": snapshot.snapshot_digest, "ready_queue": ready,
            "next_ready_task": ready[0] if ready else None,
            "tasks": {t.task_key: t.status.value for t in snapshot.resolutions},
            "dispatch_performed": dispatch_performed, "research_only": True, "formal_prediction_changed": False}

    def _write_lane_status(self, payload):
        atomic_write_text(self.output / "learning-status.json", json.dumps(payload, indent=2) + "\n")

    def replay(self, *, task_key, execution_id=None):
        from dehps.research_os import supervisor as base
        # Existing canonical loader verifies execution/registration/fact/source-file identities.
        completed = base._load_single_completed_execution(repository=self.repository,
            root_dir=self.root_dir, control_plane_key=CONTROL, task_key=task_key)
        events = self.repository.list_mainline_execution_events(control_plane_key=CONTROL,
            task_key=task_key, execution_id=execution_id)
        completed_events = [e for e in events if e["event_type"] == "completed"]
        assert len(completed_events) == 1
        contract = core.read(self.output / "contract.json")
        assert contract["body"]["source"] == runtime.source_identity(self.root_dir)
        records = self.repository.list_mainline_artifacts(control_plane_key=CONTROL,
                    execution_id=completed_events[0]["execution_id"])
        for record in records:
            path = self.root_dir / record["artifact_path"]
            value = json.loads(path.read_text())
            if value.get("artifact_type", "").startswith("PredictionLearning"):
                core.verify(value)
                assert value["artifact_digest"] == record["artifact_digest"]
        return {"status": "REPLAY_VERIFIED", "task_key": task_key,
            "execution_id": completed_events[0]["execution_id"],
            "same_execution_identity": True, "same_artifact_identity": True, "dispatch_performed": False}
