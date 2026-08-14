from __future__ import annotations

import copy
from pathlib import Path

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    prediction_v2_structural_baseline_comparison_execution as execution_module,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_structural_baseline_comparison_execution import (
    BASELINE_CLASSES,
    CANDIDATE_STATS,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_CAPABILITY,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_COMPLETION_FACT,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_SOURCE_CONTRACT_PATH,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY,
    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY,
    REPETITION_SCAN,
    ExecutionSettings,
    build_candidate_stream,
    execute_structural_baseline_comparison_program,
    load_prediction_v2_structural_baseline_comparison_execution_source_contract,
    replay_structural_baseline_comparison_artifacts,
    run_reference_preflight,
    verify_prediction_v2_structural_baseline_comparison_execution_source_bytes,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import ResearchEvidenceSupervisor

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
SOURCE_FACT_PREFIX = "prediction-v2-structural-baseline-comparison-execution-source:"
PREREGISTRATION_TASK_KEY = (
    "prediction-v2-structural-baseline-comparison-preregistration"
)
PREREGISTRATION_COMPLETION_FACT = (
    "prediction-v2-structural-baseline-comparison-preregistration:COMPLETE"
)

CANDIDATE_RANKS = [
    98,
    2781,
    16937,
    23505,
    26835,
    31424,
    37855,
    38854,
    47819,
    58284,
    59235,
    60561,
    63707,
    65499,
    74478,
    76430,
    85594,
    89784,
    91885,
    108770,
    115028,
    117341,
    120298,
    130783,
    132230,
    140163,
    162280,
    179348,
    180198,
    188877,
    191715,
    199416,
    218171,
    238881,
    252442,
    253611,
    257333,
    265460,
    266679,
    270504,
    279800,
    284433,
    286226,
    293247,
    294780,
    300055,
    301409,
    308478,
    313861,
    325202,
    328200,
    332596,
    335626,
    337888,
    340099,
    348232,
    363069,
    367802,
    372032,
    372946,
    377201,
    383133,
    385277,
    405009,
    416624,
    417960,
    427359,
    438826,
    439912,
    456892,
    457174,
    464322,
    466187,
    466414,
    471181,
    477464,
    482905,
    483478,
    487968,
    490957,
    500799,
    505546,
    509134,
    518440,
    523775,
    533183,
    539112,
    543977,
    545675,
    546673,
    548567,
    557456,
    577920,
    582146,
    596441,
    613091,
    615022,
    619070,
    619749,
    630750,
    634943,
    641114,
    648074,
    651388,
    670088,
    676303,
    678578,
    679553,
    681195,
    683696,
    684674,
    686639,
    691677,
    712948,
    720499,
    731154,
    747979,
    751491,
    761568,
    796426,
    797620,
    798782,
    804511,
    807099,
    810463,
    812158,
    812245,
    814903,
    817555,
    828045,
    830983,
    846928,
    854729,
    857636,
    857740,
    863863,
    869712,
    872608,
    874838,
    896018,
    897376,
    897956,
    898240,
    919495,
    925114,
    928242,
    933770,
    935042,
    935338,
    941507,
    957886,
    971532,
    981464,
    984678,
    990044,
    992183,
    998703,
    999033,
    999441,
    1000645,
    1011332,
    1014100,
    1023756,
    1024043,
    1026499,
    1033386,
    1044364,
    1046252,
    1052131,
    1053621,
    1057427,
    1064961,
    1084324,
    1086963,
    1089651,
    1100355,
]


def _artifact(body: dict, *, domain: str) -> dict:
    payload = {"artifact_digest": "", **body}
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload


def _parents() -> dict[str, dict]:
    preregistration = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-preregistration.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_preregistration"
            ),
            "status": "COMPLETE",
            "program": {
                "baseline_classes": [
                    {"class_id": class_id} for class_id in BASELINE_CLASSES
                ],
                "portfolio_budget": 176,
                "replicates_per_class": 128,
                "candidate_chunk_size_per_step": 256,
                "total_candidate_considerations": 17_301_504,
                "master_seed_hex": execution_module.MASTER_SEED_HEX,
                "candidate_stream_domain": execution_module.CANDIDATE_STREAM_DOMAIN,
                "construction_invariant": execution_module.CONSTRUCTION_INVARIANT,
            },
            "comparison_contract": {
                "strict_dominance": execution_module.STRICT_DOMINANCE,
                "required_candidate_dominated_replicates_per_class": 122,
                "maximum_baseline_replicates_dominating_candidate_per_class": 0,
            },
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-preregistration.v1"
        ),
    )
    handoff = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-"
                "execution-handoff.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_execution_handoff"
            ),
            "status": "COMPLETE",
            "preregistration_digest": preregistration["artifact_digest"],
            "comparison_execution_authorized": True,
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-execution-handoff.v1"
        ),
    )
    completion = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-baseline-comparison-"
                "preregistration-completion.v1"
            ),
            "artifact_type": (
                "prediction_v2_structural_baseline_comparison_"
                "preregistration_completion"
            ),
            "status": "COMPLETE",
            "preregistration_digest": preregistration["artifact_digest"],
            "execution_handoff_digest": handoff["artifact_digest"],
        },
        domain=(
            "dehps.prediction-v2.structural-baseline-comparison-"
            "preregistration-completion.v1"
        ),
    )
    preregistration_execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "completion_fact": PREREGISTRATION_COMPLETION_FACT,
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    portfolio = _artifact(
        {
            "schema_version": "dehps-prediction-v2-canonical-structural-portfolio.v1",
            "artifact_type": "prediction_v2_canonical_b176_structural_portfolio",
            "status": "COMPLETE",
            "candidate_budget": 176,
            "selected_ranks": CANDIDATE_RANKS,
            "exact_stats": dict(CANDIDATE_STATS),
        },
        domain="dehps.prediction-v2.canonical-structural-portfolio.v1",
    )
    evaluation_execution = _artifact(
        {
            "schema_version": "dehps-research-os-mainline-execution.v1",
            "artifact_type": "research_os_mainline_execution",
            "completion_classification": "VALIDATED_IN_MAINLINE",
        },
        domain="dehps.research-os.mainline-execution.v1",
    )
    evaluation_decision = _artifact(
        {
            "schema_version": (
                "dehps-prediction-v2-structural-portfolio-evaluation-decision.v1"
            ),
            "artifact_type": ("prediction_v2_structural_portfolio_evaluation_decision"),
            "status": "COMPLETE",
            "selected_stats": dict(CANDIDATE_STATS),
            "decision_usefulness_claim": False,
            "prediction_probability_claim": False,
        },
        domain=("dehps.prediction-v2.structural-portfolio-evaluation-decision.v1"),
    )
    return {
        "preregistration_execution": preregistration_execution,
        "preregistration": preregistration,
        "execution_handoff": handoff,
        "preregistration_completion": completion,
        "candidate_portfolio": portfolio,
        "candidate_evaluation_execution": evaluation_execution,
        "candidate_evaluation_decision": evaluation_decision,
    }


def _source(*, test_mode: bool = False) -> dict:
    source = load_prediction_v2_structural_baseline_comparison_execution_source_contract(
        ROOT_DIR
        / PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_SOURCE_CONTRACT_PATH
    )
    if test_mode:
        source = copy.deepcopy(source)
        source["test_mode_allowed"] = True
    return source


def test_source_contract_and_compiled_reference_preflight() -> None:
    source = _source()
    verify_prediction_v2_structural_baseline_comparison_execution_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    preflight = run_reference_preflight()
    assert preflight["status"] == "PASS"
    assert preflight["integer_exact"] is True
    assert preflight["repetition_scan"] == REPETITION_SCAN


def test_candidate_stream_snapshot_resumes_exact_sequence() -> None:
    uninterrupted = build_candidate_stream(BASELINE_CLASSES[0], 7)
    prefix = uninterrupted.draw_chunk(31).tolist()
    snapshot = uninterrupted.snapshot()
    suffix = uninterrupted.draw_chunk(29).tolist()
    resumed = build_candidate_stream(BASELINE_CLASSES[0], 7, snapshot=snapshot)
    assert resumed.draw_chunk(29).tolist() == suffix
    assert prefix[:4] == [569354, 335530, 1046883, 497340]


def test_small_parallel_execution_reuses_committed_replicate_results(
    tmp_path: Path,
) -> None:
    settings = ExecutionSettings(
        replicates_per_class=1,
        portfolio_budget=8,
        candidate_chunk_size=16,
        checkpoint_every_steps=4,
        parallel_workers=3,
        wall_clock_limit_seconds=120,
        resident_memory_limit_bytes=4_294_967_296,
    )
    arguments = {
        "source_contract": _source(test_mode=True),
        "checkpoint_dir": tmp_path,
        "settings": settings,
        "require_registered_identities": False,
        **_parents(),
    }
    first = execute_structural_baseline_comparison_program(**arguments)
    second = execute_structural_baseline_comparison_program(**arguments)
    assert first.artifacts == second.artifacts
    assert len(first.result_index["ordered_replicates"]) == 3
    assert first.result_index["total_candidate_considerations"] == 384
    assert all(
        row["repetition_scan"] == REPETITION_SCAN
        for row in first.result_index["ordered_replicates"]
    )


def test_partial_checkpoint_resumes_from_last_16_step_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = ExecutionSettings(
        replicates_per_class=1,
        portfolio_budget=20,
        candidate_chunk_size=16,
        checkpoint_every_steps=16,
        parallel_workers=1,
        wall_clock_limit_seconds=120,
        resident_memory_limit_bytes=4_294_967_296,
    )
    execution_module._WORKER_TABLES = execution_module.build_universe_tables()
    identity = "c" * 64
    arguments = (BASELINE_CLASSES[1], 0, str(tmp_path), identity, settings)
    original_write = execution_module._write_json

    def stop_after_checkpoint(path: Path, payload: dict) -> None:
        original_write(path, payload)
        if path.name == "partial.json":
            raise RuntimeError("simulated_process_stop")

    with monkeypatch.context() as context:
        context.setattr(execution_module, "_write_json", stop_after_checkpoint)
        with pytest.raises(RuntimeError, match="simulated_process_stop"):
            execution_module._run_replicate_child(arguments)

    partial = tmp_path / "replicates" / BASELINE_CLASSES[1] / "000/partial.json"
    assert (
        execution_module.json.loads(partial.read_text())["state"]["completed_steps"]
        == 16
    )
    resumed = execution_module._run_replicate_child(arguments)
    fresh_dir = tmp_path / "fresh"
    fresh_arguments = (BASELINE_CLASSES[1], 0, str(fresh_dir), identity, settings)
    fresh = execution_module._run_replicate_child(fresh_arguments)
    assert resumed == fresh
    assert not partial.exists()


def test_registered_output_replay_recomputes_gate_without_workload() -> None:
    parents = _parents()
    source = _source()
    rows = []
    for class_id in BASELINE_CLASSES:
        for replicate_index in range(128):
            row = {
                "schema_version": (
                    "dehps-prediction-v2-structural-baseline-replicate-result.v1"
                ),
                "checkpoint_identity": "a" * 64,
                "checkpoint_digest": "",
                "class_id": class_id,
                "replicate_index": replicate_index,
                "seed_digest": execution_module._replicate_seed(
                    class_id, replicate_index
                ).hex(),
                "candidate_considerations": 45_056,
                "selected_ranks": [0] * 176,
                "stats": {
                    "singleton_square_sum": 34_000,
                    "pair_square_sum": 14_300,
                    "minimum_replacement_distance": 2,
                    "sum_pairwise_replacement_distance": 75_000,
                },
                "construction_invariant": execution_module.CONSTRUCTION_INVARIANT,
                "repetition_scan": REPETITION_SCAN,
            }
            row["checkpoint_digest"] = execution_module._checkpoint_digest(
                row,
                domain=(
                    "dehps.prediction-v2.structural-baseline-"
                    "replicate-result-checkpoint.v1"
                ),
            )
            rows.append(row)
    run = execution_module._build_result_artifacts(
        source_contract=source,
        settings=execution_module.PRODUCTION_SETTINGS,
        preflight=run_reference_preflight(),
        rows=rows,
        **parents,
    )
    replay = replay_structural_baseline_comparison_artifacts(
        result_index=run.result_index,
        gate_outcome=run.gate_outcome,
        completion=run.completion,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["candidate_considerations_replayed"] == 0
    assert replay["repetition_scan"] == REPETITION_SCAN


def test_additive_migration_revises_execution_and_adds_only_route() -> None:
    source = load_m4_manifest(MANIFEST_PATH).to_dict(include_digest=False)
    live = copy.deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"]
        != PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    ]
    current = next(
        item
        for item in live["tasks"]
        if item["task_key"]
        == PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    )
    current["requested_capability"] = None
    current["input_artifact_digests"] = []
    current["metric_contract"]["engineering_complete"] = False
    current["metric_contract"]["engineering_increment_percent"] = 0
    fact = SOURCE_FACT_PREFIX + _source()["artifact_digest"]
    live["facts"]["artifacts"].remove(fact)
    _, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY,
        ),
        allowlisted_revised_task_keys=(
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY,
        ),
        add_artifact_facts=(fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION_TASK_KEY
    ]
    assert dry_run["revised_task_keys"] == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0


def test_status_projects_completed_execution_and_ready_route() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    tasks = {item.task_key: item for item in manifest.tasks}
    for item in payload["tasks"]:
        if item["task_key"] in {
            PREREGISTRATION_TASK_KEY,
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY,
        }:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            PREREGISTRATION_COMPLETION_FACT,
            PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_COMPLETION_FACT,
            mainline_completion_fact(
                task=tasks[PREREGISTRATION_TASK_KEY], execution_id="c" * 64
            ),
            mainline_completion_fact(
                task=tasks[
                    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
                ],
                execution_id="d" * 64,
            ),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (
                PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
            ),
            "decision": "SUPPORTED_BEYOND_FROZEN_TRANSPARENT_BASELINES",
            "candidate_stats": dict(CANDIDATE_STATS),
            "class_summaries": [],
            "baseline_replicates_executed": 384,
            "total_candidate_considerations": 17_301_504,
            "construction_invariant": execution_module.CONSTRUCTION_INVARIANT,
            "repetition_scan": REPETITION_SCAN,
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_ROUTE_DECISION"
    )
    execution = projection["prediction_v2_structural_baseline_comparison_execution"]
    assert execution["execution_complete"] is True
    assert execution["baseline_replicates_executed"] == 384
    assert execution["total_candidate_considerations"] == 17_301_504
    assert execution["repetition_scan"] == REPETITION_SCAN
    assert execution["next_consumer_resolver_status"] == "ready"


def test_manifest_and_index_bind_the_singular_execution_capability() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key
        == PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    )
    source = _source()
    assert task.requested_capability == (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_CAPABILITY
    )
    assert task.input_artifact_digests[0] == source["artifact_digest"]
    assert len(task.input_artifact_digests) == 8
    index = execution_module.json.loads(
        (
            ROOT_DIR
            / "configs/research-os/m4-information-theory-artifact-index-v1.json"
        ).read_text(encoding="utf-8")
    )
    assert index["artifacts"][source["artifact_digest"]]["path"] == str(
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_SOURCE_CONTRACT_PATH
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert (
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_CAPABILITY
        in supervisor.capabilities
    )


def test_latest_summary_prefers_completed_baseline_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolutions = [
        type(
            "Resolution",
            (),
            {
                "task_key": (
                    PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
                ),
                "status": TaskStatus.COMPLETED,
            },
        )()
    ]
    requested: list[str] = []

    def load_execution(**kwargs: object) -> tuple[dict, dict, tuple]:
        requested.append(str(kwargs["task_key"]))
        return (
            {"payload": [["registered_artifact_count", 4]]},
            {
                "artifact_digest": "1" * 64,
                "decision": "SUPPORTED_BEYOND_FROZEN_TRANSPARENT_BASELINES",
                "baseline_replicates_executed": 384,
            },
            (),
        )

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    summary = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )._latest_completed_v2_summary(type("Snapshot", (), {"resolutions": resolutions})())
    assert requested == [
        PREDICTION_V2_STRUCTURAL_BASELINE_COMPARISON_EXECUTION_TASK_KEY
    ]
    assert summary is not None
    assert summary["baseline_replicates_executed"] == 384
