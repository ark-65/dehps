from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path

import numpy as np
import pytest

from dehps.prediction import learning_v1 as core
from dehps.prediction import learning_v1_mainline as mainline
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.models import ControlPlaneManifest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def synthetic():
    rng = np.random.default_rng(7722)
    rows = [{"issue": f"{i+2000001:07d}", "draw_date": (date(2000, 1, 1) + timedelta(days=i * 2)).isoformat(),
             "red": sorted(rng.choice(np.arange(1,34), 6, replace=False).tolist()), "blue": int(rng.integers(1,17))}
            for i in range(902)]
    source = json.loads((ROOT / core.formal.SOURCE_CONTRACT_PATH).read_text())
    prereg = core.formal.build_preregistration_artifacts(source_contract=source)[0]
    return {"rows": rows, "formal_source": source, "formal_preregistration": prereg}


def test_probability_constraint_and_target_leakage(synthetic):
    y = core.targets(synthetic["rows"])
    for config in core.CONFIGS:
        q, state = core.fit(y[:900], config)
        assert abs(q.sum() - 6) < 1e-12
        corrupted = y.copy()
        corrupted[900:] = 1 - corrupted[900:]
        assert np.array_equal(q, core.fit(corrupted[:900], config)[0])
        assert state["training_count"] == 900
    with pytest.raises(AssertionError):
        core.fit(y[:899], core.CONFIGS[0])


def test_full_space_rank_and_score_equivalence(synthetic):
    space = core.combinations()
    q = core.fit(core.targets(synthetic["rows"][:900]), core.CONFIGS[0])[0]
    for red in ([1,2,3,4,5,6], [5,10,12,18,26,33], [28,29,30,31,32,33]):
        index = core.lex_id(red)
        assert (space[index] + 1).tolist() == red
        assert abs(core.scores(q, space[index:index+1])[0] - core.formal._ticket_score(red, q)) < 1e-12


def test_exact_original_top100_and_deterministic_new_results(synthetic, tmp_path):
    core.immutable(tmp_path / "snapshot.json", core.seal("test", synthetic))
    core.immutable(tmp_path / "contract.json", core.seal("test", {"random_repetitions": 1}))
    core.init_worker(tmp_path / "snapshot.json", tmp_path / "contract.json")
    first = core.evaluate_issue(900)
    second = core.evaluate_issue(900)
    assert first == second
    row = synthetic["rows"][900]
    history = [(r["issue"], date.fromisoformat(r["draw_date"]), tuple(r["red"])) for r in synthetic["rows"][:900]]
    _, model = core.formal.fit_model_artifacts(source_contract=synthetic["formal_source"],
        preregistration=synthetic["formal_preregistration"], history_rows=history, target_issue=row["issue"])
    official, _, _, _ = core.formal.generate_predraw_artifacts(preregistration=synthetic["formal_preregistration"],
        model=model, target_draw_date=date.fromisoformat(row["draw_date"]),
        sealed_at=datetime.fromisoformat(row["draw_date"]).replace(tzinfo=core.formal.SHANGHAI))
    expected = official["body"]["tickets"]
    result = first["body"]["arms"]["old_original"]
    assert [tuple(core.combinations()[i] + 1) for i in result["ticket_ids"]] == [tuple(t["red_numbers"]) for t in expected]
    assert len(set(result["ticket_ids"])) == 100
    for arm in first["body"]["arms"].values():
        assert sum(arm["hit_counts_0_to_6"]) == 100
        assert sum(arm["number_counts"]) == 600
        assert arm["blue_by_rank"] == result["blue_by_rank"]


def test_no_overwrite_and_resolver_chain(tmp_path):
    path = tmp_path / "immutable.json"
    core.immutable(path, core.seal("test", {"v": 1}))
    with pytest.raises(AssertionError):
        core.immutable(path, core.seal("test", {"v": 2}))
    contract = core.seal("contract", {"snapshot_digest": "a" * 64})
    m = ControlPlaneManifest.from_dict(mainline.manifest(contract))
    snapshot = ResearchOSControlPlane().resolve(m)
    assert [t.task_key for t in snapshot.ready_queue] == [mainline.task_key("freeze")]
    assert len(m.tasks) == 3


def test_data_integrity_rejects_missing_blue_and_issue_gaps(synthetic):
    rows = [dict(r) for r in synthetic["rows"]]
    core.validate_rows(rows, today="2026-09-05")
    rows[100]["blue"] = None
    with pytest.raises(AssertionError):
        core.validate_rows(rows, today="2026-09-05")
    rows[100]["blue"] = 1
    rows[100]["issue"] = "1000000"
    with pytest.raises(AssertionError):
        core.validate_rows(rows, today="2026-09-05")


@pytest.mark.skipif(os.getenv("DEHPS_LEARNING_INTEGRATION") != "1", reason="explicit isolated database integration opt-in")
def test_real_supervisor_synthetic_chain(synthetic, monkeypatch):
    from uuid import uuid4
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from dotenv import load_dotenv
    from dehps.config import get_settings
    from dehps.prediction import learning_v1_runtime as runtime
    from dehps.research_os.repository import PostgresResearchOSRepository
    from dehps.crawler.ssq_client import ZhcwSsqDataSource
    def synthetic_prizes(self, issue):
        row = next(r for r in synthetic["rows"] if r["issue"] == issue)
        return {"issue": issue, "red": row["red"], "blue": row["blue"],
            "winnerDetails": [{"awardEtc": k, "baseBetWinner": {"awardMoney": v, "awardNum": 1}}
                              for k, v in {1:5000000, 2:100000, 3:3000, 4:200, 5:10, 6:5}.items()]}
    monkeypatch.setattr(ZhcwSsqDataSource, "fetch_issue_with_prizes", synthetic_prizes)
    load_dotenv("/home/ark/workspace/dehps/.env")
    output = ROOT / "runtime" / ("synthetic-learning-test-" + uuid4().hex)
    core.immutable(output / "snapshot.json", core.seal("PredictionLearningSnapshot", synthetic))
    contract = runtime.freeze(ROOT, output)
    params = conninfo_to_dict(get_settings().database_url)
    database = "dehps_learning_test_" + uuid4().hex
    admin = make_conninfo(**{**params, "dbname": "postgres"})
    with psycopg.connect(admin, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        repo = PostgresResearchOSRepository(connection_factory=lambda: psycopg.connect(make_conninfo(**{**params, "dbname": database})))
        repo.ensure_schema()
        repo.import_manifest(control_plane_key=mainline.CONTROL, payload=mainline.manifest(contract))
        sup = mainline.LearningSupervisor(repository=repo, root_dir=ROOT, output=output, require_clean_tree=False)
        for phase in mainline.PHASES:
            sup.run_once(task_key=mainline.task_key(phase))
            assert sup.replay(task_key=mainline.task_key(phase))["status"] == "REPLAY_VERIFIED"
        assert core.read(output / "checkpoint.json")["body"]["training_count"] == len(synthetic["rows"])
        assert runtime.semantic_replay(ROOT, output)["body"]["analysis_recomputed"]
    finally:
        with psycopg.connect(admin, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
