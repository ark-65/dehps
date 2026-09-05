#!/usr/bin/env python3
"""Explicit offline first round; never changes the production database or services."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dehps.prediction import learning_v1 as core
from dehps.prediction import learning_v1_runtime as runtime

ROOT = Path(__file__).resolve().parents[3]


def isolated_repository():
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from dehps.config import get_settings
    from dehps.research_os.repository import PostgresResearchOSRepository
    production = conninfo_to_dict(get_settings().database_url)
    database = "dehps_prediction_learning_v1_20260905"
    assert production.get("dbname") != database
    with psycopg.connect(make_conninfo(**{**production, "dbname": "postgres"}), autocommit=True) as admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone()
        if not exists:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    local = make_conninfo(**{**production, "dbname": database})
    def connect():
        connection = psycopg.connect(local)
        assert connection.info.dbname == database
        return connection
    return PostgresResearchOSRepository(connection_factory=connect)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "run", "replay", "status"))
    parser.add_argument("--production-root", type=Path, default=Path("/home/ark/workspace/dehps"))
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(args.production_root / ".env")
    output = ROOT / "runtime/prediction-learning-v1/20260905-first-round"
    output.mkdir(parents=True, exist_ok=True)
    if args.mode == "prepare":
        snap = runtime.snapshot(args.production_root, output)
        contract = runtime.freeze(ROOT, output)
        print(json.dumps({"status": "FROZEN_BEFORE_RESULTS", "snapshot_digest": snap["artifact_digest"],
            "contract_digest": contract["artifact_digest"], "issues": len(contract["body"]["outer_issues"]),
            "workers": contract["body"]["workers"], "estimated_seconds": contract["body"]["estimated_seconds_conservative"]}))
        return
    from dehps.prediction import learning_v1_mainline as mainline
    repo = isolated_repository()
    repo.ensure_schema()
    supervisor = mainline.LearningSupervisor(repository=repo, root_dir=ROOT, output=output)
    if args.mode == "run":
        contract = core.read(output / "contract.json")
        with repo.connection_factory() as connection:
            exists = connection.execute("SELECT 1 FROM research_os_control_planes WHERE control_plane_key=%s", (mainline.CONTROL,)).fetchone()
        if not exists:
            repo.import_manifest(control_plane_key=mainline.CONTROL, payload=mainline.manifest(contract))
        for phase in mainline.PHASES:
            key = mainline.task_key(phase)
            snapshot = repo.resolve_persisted(control_plane_key=mainline.CONTROL)
            status = next(t.status.value for t in snapshot.resolutions if t.task_key == key)
            if status != "completed":
                supervisor.run_once(task_key=key)
            print(json.dumps(supervisor.replay(task_key=key)), flush=True)
    elif args.mode == "replay":
        semantic = runtime.semantic_replay(ROOT, output)
        core.immutable(output / "semantic-replay.json", semantic)
        results = []
        for phase in mainline.PHASES:
            results.append(supervisor.replay(task_key=mainline.task_key(phase)))
        core.immutable(output / "replay.json", core.seal("PredictionLearningReplay", {"phases": results, "semantic_digest": semantic["artifact_digest"]}))
        runtime.render_report(output, "YES — validated by unified mainline execution and replay (isolated offline research lane; production unchanged).")
        print(json.dumps({"status": "REPLAY_VERIFIED", "phases": results, "report": str(output / "report.md")}), flush=True)
    else:
        print(json.dumps(supervisor.status(), default=str))


if __name__ == "__main__":
    main()
