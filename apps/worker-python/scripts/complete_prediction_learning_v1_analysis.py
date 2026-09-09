#!/usr/bin/env python3
"""Finish the same frozen round with traced Zhcw field normalization; no training."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"

FROZEN_ROOT = Path("/home/ark/workspace/dehps-prediction-learning-v1")
sys.path.insert(0, str(FROZEN_ROOT / "apps/worker-python"))

from dehps.crawler.ssq_client import ZhcwSsqDataSource, _normalize_remote_record
from dehps.prediction import learning_v1 as core, learning_v1_runtime as runtime, learning_v1_mainline as ml
from dehps.research_os.information_theory.measurement_system_v2.migration import build_additive_task_manifest
from dehps.research_os.supervisor import AtomicArtifactPayload, AtomicCapabilityResult, _load_single_completed_execution

ORIGINAL = FROZEN_ROOT / "runtime/prediction-learning-v1/20260905-first-round"
OUTPUT = ORIGINAL / "analysis-field-normalization-v1"
KEY = ml.CONTROL + "-analysis-field-normalization-v1"
CAPABILITY = "prediction_learning_analysis_field_normalization_v1"
EXPECTED_CONTRACT = "8e9ec9f83dc7da1587389ec7952c2ff037514daf5400dc8546b4a5bc1e04a033"


def normalize(record, row):
    """The original raw record stays intact; derived aliases have explicit provenance."""
    normalized = _normalize_remote_record(record, "zhcw")
    assert str(normalized["issue"]) == row["issue"]
    reds = sorted(map(int, normalized["red_numbers"]))
    blue = int(normalized["blue_number"])
    assert reds == row["red"] and blue == row["blue"], "payout labels differ from frozen snapshot"
    aliases = {"issue": row["issue"], "red": reds, "blue": blue}
    # Reject conflicting aliases instead of silently replacing populated fields.
    for key, expected in aliases.items():
        if key in record and record[key] not in (None, ""):
            value = record[key]
            if key == "red":
                value = sorted(map(int, value.replace(",", " ").split() if isinstance(value, str) else value))
            elif key == "blue":
                value = int(value)
            else:
                value = str(value)
            assert value == expected
    return {**record, **aliases}


def prepare_inputs():
    contract = core.read(ORIGINAL / "contract.json")
    assert contract["artifact_digest"] == EXPECTED_CONTRACT
    assert contract["body"]["source"] == runtime.source_identity(FROZEN_ROOT), "frozen code changed"
    assert time.time() - core.read(ORIGINAL / "start.json")["body"]["epoch"] < 86400
    for name in ("snapshot.json", "contract.json", "training.json", "checkpoint.json"):
        core.immutable(OUTPUT / name, core.read(ORIGINAL / name))
    snapshot = core.read(ORIGINAL / "snapshot.json")
    by_issue = {r["issue"]: r for r in snapshot["body"]["rows"]}
    training = core.read(ORIGINAL / "training.json")
    required = []
    for item in training["body"]["issues"]:
        issue = core.read(FROZEN_ROOT / item["path"])
        assert issue["artifact_digest"] == item["artifact_digest"]
        body = issue["body"]
        tickets = list(body["arms"].values()) + [r for repeats in body["random"].values() for r in repeats]
        if any(r["tier_counts_0_to_6"][1] or r["tier_counts_0_to_6"][2] for r in tickets):
            required.append(body["issue"])
    records = []
    for issue in required:
        raw_path = OUTPUT / "raw-payouts" / (issue + ".json")
        if raw_path.exists():
            raw = core.read(raw_path)
        else:
            original_path = ORIGINAL / "payouts" / (issue + ".json")
            if original_path.exists():
                previous = core.read(original_path)
                record = previous["body"]["record"]
                parent = previous["artifact_digest"]
            else:
                record = ZhcwSsqDataSource().fetch_issue_with_prizes(issue)
                parent = core.digest(record)
            assert record is not None, f"missing payout: {issue}"
            raw = core.seal("PredictionLearningRawPayout", {"issue": issue, "record": record,
                "original_record_digest": parent, "source": "https://jc.zhcw.com/port/client_json.php"})
            core.immutable(raw_path, raw)
        canonical = core.seal("PredictionLearningPayout", {"issue": issue,
            "record": normalize(raw["body"]["record"], by_issue[issue]),
            "raw_artifact_digest": raw["artifact_digest"], "normalization": "derived red/blue aliases; original raw preserved"})
        core.immutable(OUTPUT / "payouts" / (issue + ".json"), canonical)
        records.append({"issue": issue, "raw_digest": raw["artifact_digest"], "normalized_digest": canonical["artifact_digest"]})
    attestation = core.seal("PredictionLearningPayoutNormalization", {
        "contract_digest": contract["artifact_digest"], "training_digest": training["artifact_digest"],
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "records": records, "model_refit": False, "search_count_reset": False,
        "original_failed_analysis_preserved": True, "metrics_and_selection_unchanged": True})
    core.immutable(OUTPUT / "normalization.json", attestation)
    return attestation


class Completion:
    def __init__(self, repository):
        self.repository = repository

    def execute(self, *, control_plane_key, task, execution_id, git_commit):
        assert control_plane_key == ml.CONTROL and task.task_key == KEY
        definition = json.loads(task.metric_contract)
        assert definition["normalizer_source_sha256"] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        _load_single_completed_execution(repository=self.repository, root_dir=FROZEN_ROOT,
            control_plane_key=ml.CONTROL, task_key=ml.task_key("train-evaluate"))
        attestation = prepare_inputs()
        analysis = runtime.analyze(FROZEN_ROOT, OUTPUT)
        prediction = runtime.experimental_prediction(OUTPUT)
        return AtomicCapabilityResult(artifacts=tuple(AtomicArtifactPayload(f"analysis-{i}", f"analysis-{i}.json", value)
            for i, value in enumerate((attestation, analysis, prediction))),
            completion_facts=(KEY + ":COMPLETE",),
            execution_metadata=(("research_only", True), ("model_refit", False), ("formal_prediction_changed", False)))


def add_task(repository):
    current = repository.export_manifest(control_plane_key=ml.CONTROL)
    if any(t["task_key"] == KEY for t in current["tasks"]):
        return
    original_task = next(t for t in current["tasks"] if t["task_key"] == ml.task_key("analysis"))
    assert original_task["status"] == "failed", "original analysis is not the expected failed task"
    contract = core.read(ORIGINAL / "contract.json")
    training = core.read(ORIGINAL / "training.json")
    _, _, registered = _load_single_completed_execution(repository=repository, root_dir=FROZEN_ROOT,
        control_plane_key=ml.CONTROL, task_key=ml.task_key("train-evaluate"))
    assert training["artifact_digest"] in {r["artifact_digest"] for r in registered}
    task = {"task_key": KEY, "goal_key": ml.CONTROL, "task_type": CAPABILITY, "requested_capability": CAPABILITY,
        "lane": "research", "priority": 90, "status": "draft", "completion_classification": "INTEGRATION_PENDING",
        "input_artifact_digests": [contract["artifact_digest"], training["artifact_digest"]],
        "dependencies": [{"dependency_type": "task", "target_key": ml.task_key("train-evaluate"), "required_status": "completed"}],
        "metric_contract": {"normalizer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "contract_digest": contract["artifact_digest"], "replaces_failed_analysis_operationally": original_task["task_key"],
            "mainline_integration": {"goal": ml.CONTROL, "ready_condition": "frozen training completed; failed analysis retained",
                "runner": "existing ResearchEvidenceSupervisor with field normalization capability",
                "upstream_artifacts": [contract["artifact_digest"], training["artifact_digest"]],
                "downstream_artifacts": ["raw-to-normalized payout attestation", "unchanged frozen analysis", "RESEARCH_ONLY prediction"],
                "status_projection": "analysis-field-normalization-v1/learning-status.json",
                "downstream_consumer": "deterministic replay and final research report",
                "evidence_progress_rule": "exploratory only, no new configurations or training",
                "decision_consumer": "same frozen decision, no Formal P3 credit"}}}
    incoming = build_additive_task_manifest(live_payload=current, new_tasks=(task,))[0]
    repository.import_manifest(control_plane_key=ml.CONTROL, payload=incoming, source="analysis-field-normalization")


def main():
    from dotenv import load_dotenv
    load_dotenv("/home/ark/workspace/dehps/.env")
    source_root = Path(__file__).resolve().parents[3]
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=source_root).strip()
    spec = importlib.util.spec_from_file_location("frozen_learning_runner", FROZEN_ROOT / "apps/worker-python/scripts/run_prediction_learning_v1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = module.isolated_repository()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_root, text=True).strip()
    supervisor = ml.LearningSupervisor(repository=repo, root_dir=FROZEN_ROOT, output=OUTPUT, git_commit=commit)
    supervisor.capabilities[CAPABILITY] = Completion(repo)
    add_task(repo)
    state = repo.resolve_persisted(control_plane_key=ml.CONTROL)
    if next(t.status.value for t in state.resolutions if t.task_key == KEY) != "completed":
        supervisor.run_once(task_key=KEY)
    semantic = runtime.semantic_replay(FROZEN_ROOT, OUTPUT)
    core.immutable(OUTPUT / "semantic-replay.json", semantic)
    replays = [supervisor.replay(task_key=ml.task_key(p)) for p in ("freeze", "train-evaluate")]
    replays.append(supervisor.replay(task_key=KEY))
    core.immutable(OUTPUT / "replay.json", core.seal("PredictionLearningReplay", {"phases": replays,
        "semantic_digest": semantic["artifact_digest"], "normalization_digest": core.read(OUTPUT / "normalization.json")["artifact_digest"]}))
    runtime.render_report(OUTPUT, "YES — validated by unified mainline execution and replay in the isolated research lane. Original failed analysis is retained; field-normalization completion has its own execution identity.")
    print(json.dumps({"status": "REPLAY_VERIFIED", "report": str(OUTPUT / "report.md"), "replays": replays}))


if __name__ == "__main__":
    main()
