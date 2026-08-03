from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from dehps.agents.repository import AgentRequestRepository
from dehps.config import ROOT_DIR
from dehps.prediction.v2.activation_binding import (
    CUTOVER_TASK_KEY,
    load_operator_completion,
    materialize_activation_binding_migration,
    persist_canonical_operator_completion,
)
from dehps.prediction.v2.mainline import CONTROL_PLANE_KEY
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import ResearchEvidenceSupervisor

SOURCE_MANIFEST = ROOT_DIR / "configs/prediction-v2/prediction-v2-shadow-mainline-v1.json"


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON object required: {path}")
    return value


def _verify_completed_operator_request(completion: dict) -> dict:
    request_key = str(completion["operator_request"])
    execution_id = int(completion["operator_execution_id"])
    repository = AgentRequestRepository()
    request = repository.get_request(request_key)
    executions = repository.list_executions(request_key)
    matches = [item for item in executions if item.id == execution_id]
    if request.status.value != "completed" or len(matches) != 1:
        raise RuntimeError("activation binding requires one completed typed Operator execution")
    execution = matches[0]
    if execution.status.value != "completed" or execution.executor_role.value != "operator":
        raise RuntimeError("activation binding Operator execution is not completed by Operator")
    return {
        "request_key": request_key,
        "request_status": request.status.value,
        "execution_id": execution_id,
        "execution_status": execution.status.value,
        "executor_role": execution.executor_role.value,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bind a completed Prediction v2 cutover into the isolated mainline."
    )
    parser.add_argument("--completion-artifact", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the canonical completion, import the allowlisted task revision, execute, and replay.",
    )
    args = parser.parse_args(argv)
    source_path = args.completion_artifact.resolve()
    completion, completion_digest = load_operator_completion(source_path)
    operator = _verify_completed_operator_request(completion)
    repository = PostgresResearchOSRepository()
    repository.ensure_schema()
    before = repository.export_manifest(control_plane_key=CONTROL_PLANE_KEY)
    source_manifest = _load(SOURCE_MANIFEST)
    if args.apply:
        canonical_path, canonical_completion, canonical_digest = (
            persist_canonical_operator_completion(
                root_dir=ROOT_DIR,
                source_path=source_path,
            )
        )
        if canonical_completion != completion or canonical_digest != completion_digest:
            raise RuntimeError("canonical Operator completion identity changed")
    else:
        canonical_path = ROOT_DIR / "runtime/prediction-v2/live-cutover-completion.json"
    migrated, migration = materialize_activation_binding_migration(
        root_dir=ROOT_DIR,
        base_manifest=before,
        source_manifest=source_manifest,
        completion_payload=completion,
    )
    if not args.apply:
        print(
            json.dumps(
                {
                    "status": "DRY_RUN_VERIFIED",
                    "operator": operator,
                    "completion_payload_digest": completion_digest,
                    "canonical_completion_path": str(canonical_path.relative_to(ROOT_DIR)),
                    "migration": migration,
                    "live_state_changed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    imported = repository.import_manifest(
        control_plane_key=CONTROL_PLANE_KEY,
        payload=migrated,
        source="prediction-v2-shadow-live-activation-binding",
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=CONTROL_PLANE_KEY,
    )
    execution = supervisor.run_once(task_key=CUTOVER_TASK_KEY)
    replay = supervisor.replay(task_key=CUTOVER_TASK_KEY)
    status = _load(ROOT_DIR / "runtime/logs/prediction-v2-shadow-status.json")
    print(
        json.dumps(
            {
                "status": "LIVE_ACTIVATION_REPLAY_VERIFIED",
                "operator": operator,
                "completion_payload_digest": completion_digest,
                "canonical_completion_path": str(canonical_path.relative_to(ROOT_DIR)),
                "migration": migration,
                "import": asdict(imported),
                "execution": execution,
                "replay": replay,
                "status_projection": status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
