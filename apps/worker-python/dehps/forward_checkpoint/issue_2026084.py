from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from contextlib import nullcontext
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from psycopg import Connection
from psycopg.rows import dict_row

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.db import get_connection
from dehps.optimization.next_candidates import (
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
    STATIC_100_LINE_KEY,
)
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.scoring_kernel import candidate_store_from_matrix
from dehps.seven_red.domain import SIX_RED_UNIVERSE
from dehps.seven_red.inner_selection import (
    SevenRedInnerSelectionSnapshot,
    SevenRedStrategyKind,
)
from dehps.seven_red.portfolio import compile_six_red_top70_portfolio
from dehps.seven_red.random_control import compile_random_control_cohort
from dehps.seven_red.run_walk_forward import (
    EXPECTED_EXPERIMENT_KEY,
    EXPECTED_INNER_COUNT,
    RUNNER_VERSION,
    _build_strategy_bundles,
    _compile_score_vector,
    _load_checkpoint,
    _selected_bundle,
    build_frozen_run_plan,
)
from dehps.storage.postgres_store import (
    TOTAL_SSQ_RED_COMBINATIONS,
    load_history_until_with_dates,
)


TARGET_ISSUE = "2026084"
AS_OF_ISSUE = "2026083"
TARGET_DRAW_DATE = date(2026, 7, 23)
CHECKPOINT_PROTOCOL = "dehps-2026084-forward-checkpoint.v1"
SETTLEMENT_PROTOCOL = "dehps-2026084-forward-settlement.v1"
ARCHITECTURE_LABEL = (
    "old_architecture_frozen_forward_control_not_post_collapse_production"
)
REQUIRED_LINE_KEYS = (
    STATIC_100_LINE_KEY,
    DYNAMIC_KDJ_LINE_KEY,
    NEAR_DYNAMIC_KDJ_LINE_KEY,
)
SOURCE_RUN_DIR = (
    ROOT_DIR / "data/output/seven-red/seven-red-compound-top10-last60-v1"
)
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data/output/forward-checkpoints/2026084"
DEFAULT_CHECKPOINT_PATH = DEFAULT_OUTPUT_DIR / "checkpoint.json"
FORMAL_AUDIT_DIR = ROOT_DIR / "data/output/portfolio-audit/formal-208f1e8"


class ForwardCheckpointError(RuntimeError):
    """Raised when a forward checkpoint cannot be proven leakage-safe."""


def _fail(message: str) -> None:
    raise ForwardCheckpointError(message)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _encoded_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _write_immutable(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            _fail(f"immutable artifact content mismatch: {path}")
        return
    atomic_write_text(path, text)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean_source_commit() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        _fail("repository must be clean before sealing the pre-outcome checkpoint")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ForwardCheckpointError(f"cannot load required artifact: {path}") from exc
    if not isinstance(value, dict):
        _fail(f"required artifact is not a JSON object: {path}")
    return value


def _assert_pre_outcome(conn: Connection) -> list[tuple[str, date | None, tuple[int, ...]]]:
    outcome = conn.execute(
        "SELECT issue FROM ssq_history WHERE issue = %s",
        (TARGET_ISSUE,),
    ).fetchone()
    if outcome is not None:
        _fail("2026084 outcome already exists; a pre-outcome checkpoint may no longer be created")
    history = load_history_until_with_dates(conn, AS_OF_ISSUE)
    if not history or history[-1][0] != AS_OF_ISSUE:
        _fail("official history does not end at the required 2026083 cutoff")
    return history


def _load_frozen_prediction_runs(conn: Connection) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT prediction_run_key, line_key, line_label, line_kind, snapshot_key,
                   source_run_id, source_round_index, as_of_issue, target_issue,
                   train_mode, train_window, top_n, candidate_count, config_hash,
                   prediction_fingerprint, ranking_contract, config, metadata,
                   status, generated_at
              FROM forward_prediction_runs
             WHERE target_issue = %s
               AND line_key = ANY(%s)
             ORDER BY line_key
            """,
            (TARGET_ISSUE, list(REQUIRED_LINE_KEYS)),
        ).fetchall()
    normalized = [_json_safe(dict(row)) for row in rows]
    if len(normalized) != len(REQUIRED_LINE_KEYS):
        _fail("2026084 does not have exactly three frozen legacy prediction runs")
    if {row["line_key"] for row in normalized} != set(REQUIRED_LINE_KEYS):
        _fail("2026084 frozen legacy line set is incomplete")
    for row in normalized:
        if (
            row["as_of_issue"] != AS_OF_ISSUE
            or row["target_issue"] != TARGET_ISSUE
            or int(row["top_n"]) != 10_000
            or int(row["candidate_count"]) != 10_000
            or row["ranking_contract"] != "strict_v1"
            or row["status"] != "pending"
        ):
            _fail(f"legacy prediction run is not the required pending frozen run: {row['line_key']}")
    return normalized


def _load_top100(conn: Connection, prediction_run_key: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT rank, red_numbers, score
              FROM forward_prediction_candidates
             WHERE prediction_run_key = %s
               AND rank <= 100
             ORDER BY rank
            """,
            (prediction_run_key,),
        ).fetchall()
    result = [_json_safe(dict(row)) for row in rows]
    if [int(row["rank"]) for row in result] != list(range(1, 101)):
        _fail(f"frozen Top100 candidate rows are incomplete: {prediction_run_key}")
    for row in result:
        numbers = tuple(int(value) for value in row["red_numbers"])
        if len(numbers) != 6 or tuple(sorted(numbers)) != numbers:
            _fail(f"invalid frozen ticket in {prediction_run_key}")
        row["red_numbers"] = list(numbers)
    return result


def _load_formal_audit(line_key: str, prediction_run_key: str) -> dict[str, Any]:
    path = FORMAL_AUDIT_DIR / f"{line_key}-{TARGET_ISSUE}.json"
    payload = _load_json(path)
    source = payload.get("source") or {}
    if (
        source.get("source_key") != prediction_run_key
        or source.get("line_key") != line_key
        or source.get("target_issue") != TARGET_ISSUE
        or source.get("as_of_issue") != AS_OF_ISSUE
        or source.get("declared_candidate_count") != 10_000
        or source.get("loaded_candidate_pool_count") != 10_000
    ):
        _fail(f"formal portfolio audit does not bind prediction run: {line_key}")
    if payload.get("automatic_promotion_allowed") is True:
        _fail(f"formal portfolio audit unexpectedly permits promotion: {line_key}")
    return {
        "path": str(path.relative_to(ROOT_DIR)),
        "file_sha256": _sha256_file(path),
        "artifact_digest": payload.get("artifact_digest"),
        "content_digest": payload.get("content_digest"),
    }


def _verify_seven_red_source() -> tuple[Any, list[Any], list[Any], dict[str, Any]]:
    protocol = _load_json(SOURCE_RUN_DIR / "protocol.json")
    checkpoint_payload = _load_json(SOURCE_RUN_DIR / "checkpoint.json")
    manifest = _load_json(SOURCE_RUN_DIR / "run_manifest.json")
    walk = _load_json(SOURCE_RUN_DIR / "walk_forward_snapshot.json")
    statistics = _load_json(SOURCE_RUN_DIR / "statistical_snapshot.json")
    if (
        protocol.get("runner_version") != RUNNER_VERSION
        or manifest.get("source_commit") != protocol.get("source_commit")
        or checkpoint_payload.get("source_commit") != protocol.get("source_commit")
        or manifest.get("walk_forward_snapshot_digest") != walk.get("snapshot_digest")
        or manifest.get("statistical_snapshot_digest") != statistics.get("snapshot_digest")
        or statistics.get("source_walk_forward_snapshot_digest") != walk.get("snapshot_digest")
        or int(walk.get("trial_count") or 0) != 60
        or len(checkpoint_payload.get("completed_issues") or ()) != 80
        or len(checkpoint_payload.get("trials") or ()) != 60
    ):
        _fail("seven-red 60-period source artifacts do not form one verified chain")
    plan = build_frozen_run_plan(
        experiment_key=EXPECTED_EXPERIMENT_KEY,
        config_snapshot=protocol["experiment_config_snapshot"],
        issue_slice=checkpoint_payload["completed_issues"],
    )
    evaluations, trials = _load_checkpoint(
        SOURCE_RUN_DIR / "checkpoint.json",
        plan=plan,
        source_commit=str(manifest["source_commit"]),
    )
    if len(evaluations) != 320 or len(trials) != 60:
        _fail("seven-red source checkpoint does not replay the full 80-by-4 / 60 trial set")
    source = {
        "directory": str(SOURCE_RUN_DIR.relative_to(ROOT_DIR)),
        "source_commit": manifest["source_commit"],
        "plan_digest": plan.plan_digest,
        "walk_forward_snapshot_digest": walk["snapshot_digest"],
        "statistical_snapshot_digest": statistics["snapshot_digest"],
        "checkpoint_file_sha256": _sha256_file(SOURCE_RUN_DIR / "checkpoint.json"),
        "walk_forward_file_sha256": _sha256_file(
            SOURCE_RUN_DIR / "walk_forward_snapshot.json"
        ),
        "statistical_file_sha256": _sha256_file(
            SOURCE_RUN_DIR / "statistical_snapshot.json"
        ),
        "prior_outer_sample_count": 60,
    }
    return plan, evaluations, trials, source


def _legacy_snapshot(conn: Connection) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for run in _load_frozen_prediction_runs(conn):
        tickets = _load_top100(conn, str(run["prediction_run_key"]))
        result.append(
            {
                "run": run,
                "candidate_sequence_digest": canonical_digest(
                    tickets,
                    domain="dehps.2026084.legacy-top100-sequence.v1",
                ),
                "top100_tickets": tickets,
                "formal_portfolio_audit": _load_formal_audit(
                    str(run["line_key"]), str(run["prediction_run_key"])
                ),
            }
        )
    return result


def _build_seven_red_snapshot(
    *,
    history: list[tuple[str, date | None, tuple[int, ...]]],
    plan: Any,
    evaluations: Sequence[Any],
) -> dict[str, Any]:
    matrix = build_ranked_universe(include_hard_filter_exclusions=True)
    if len(matrix) != SIX_RED_UNIVERSE.cardinality:
        _fail("full legal six-red matrix cardinality mismatch")
    candidate_store = candidate_store_from_matrix(matrix)
    target = (TARGET_ISSUE, TARGET_DRAW_DATE, ())
    source_vector = _compile_score_vector(
        candidate_store=candidate_store,
        history=history,
        target=target,
    )
    if source_vector.source_history_latest_issue != AS_OF_ISSUE:
        _fail("2026084 score vector does not bind the 2026083 history cutoff")
    bundles = _build_strategy_bundles(
        plan=plan,
        source_vector=source_vector,
        target_issue=TARGET_ISSUE,
    )
    inner_issues = plan.issue_slice[-EXPECTED_INNER_COUNT:]
    evaluation_by_cell = {
        (row.parameter.parameter_digest, row.target_issue): row for row in evaluations
    }
    inner_rows = [
        evaluation_by_cell[(parameter.parameter_digest, inner_issue)]
        for parameter in plan.parameter_grid.parameters
        for inner_issue in inner_issues
    ]
    selection = SevenRedInnerSelectionSnapshot.build(
        outer_target_issue=TARGET_ISSUE,
        parameter_grid=plan.parameter_grid,
        protocol=plan.inner_protocol,
        inner_issues=inner_issues,
        evaluations=inner_rows,
    )
    selected = {
        kind: _selected_bundle(selection, bundles, kind)
        for kind in (SevenRedStrategyKind.RAW, SevenRedStrategyKind.DIVERSIFIED)
    }
    arms: dict[str, Any] = {}
    for kind, bundle in selected.items():
        cohort = compile_random_control_cohort(
            score_pool=bundle.score_pool,
            seed_policy=plan.seed_policy,
        )
        arms[kind.value] = {
            "selected_parameter_digest": bundle.parameter.parameter_digest,
            "score_pool_snapshot_digest": bundle.score_pool.snapshot_digest,
            "strategy_artifact_digest": (
                bundle.strategy.snapshot_digest
                if hasattr(bundle.strategy, "snapshot_digest")
                else bundle.strategy.artifact_digest
            ),
            "portfolio": bundle.portfolio.as_dict(),
            "random_control_cohort": cohort.as_dict(),
        }
    six_top70 = compile_six_red_top70_portfolio(
        source_vector=source_vector,
        target_issue=TARGET_ISSUE,
    )
    return {
        "source_vector": source_vector.as_dict(),
        "inner_selection": selection.as_dict(),
        "arms": arms,
        "six_red_top70": six_top70.as_dict(),
    }


def seal_2026084_checkpoint(
    *,
    conn: Connection | None = None,
    checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH,
) -> dict[str, Any]:
    """Create the sole pre-outcome 084 checkpoint; refuse any post-outcome creation."""
    if checkpoint_path.exists():
        existing = _verified_checkpoint(checkpoint_path)
        return {
            "status": "already_sealed",
            "issue": TARGET_ISSUE,
            "checkpoint_digest": existing["checkpoint_digest"],
            "checkpoint_path": str(checkpoint_path),
        }
    source_commit = _clean_source_commit()
    connection_context = get_connection() if conn is None else nullcontext(conn)
    with connection_context as active_conn:
        history = _assert_pre_outcome(active_conn)
        legacy = _legacy_snapshot(active_conn)
        plan, evaluations, _trials, seven_red_source = _verify_seven_red_source()
        seven_red = _build_seven_red_snapshot(
            history=history,
            plan=plan,
            evaluations=evaluations,
        )
        if active_conn.execute(
            "SELECT 1 FROM ssq_history WHERE issue = %s",
            (TARGET_ISSUE,),
        ).fetchone() is not None:
            _fail("2026084 outcome arrived while checkpoint compilation was in progress")
    payload = {
        "protocol": CHECKPOINT_PROTOCOL,
        "target_issue": TARGET_ISSUE,
        "target_draw_date": TARGET_DRAW_DATE.isoformat(),
        "as_of_issue": AS_OF_ISSUE,
        "sealed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_code_commit": source_commit,
        "architecture_label": ARCHITECTURE_LABEL,
        "database_cutoff": AS_OF_ISSUE,
        "outcome": None,
        "outer_sample_ordinal_if_settled": 61,
        "legacy_lines": legacy,
        "seven_red_source": seven_red_source,
        "seven_red_forward": seven_red,
        "guardrails": {
            "promotion_gate_opened": False,
            "automatic_promotion_allowed": False,
            "single_issue_upgrade_allowed": False,
            "production_action": "none",
        },
    }
    digest = canonical_digest(payload, domain="dehps.2026084.forward-checkpoint.v1")
    artifact = {**payload, "checkpoint_digest": digest}
    _write_immutable(checkpoint_path, _encoded_json(artifact))
    return {
        "status": "sealed",
        "issue": TARGET_ISSUE,
        "checkpoint_digest": digest,
        "checkpoint_path": str(checkpoint_path),
    }


def _verified_checkpoint(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    digest = payload.pop("checkpoint_digest", None)
    expected = canonical_digest(payload, domain="dehps.2026084.forward-checkpoint.v1")
    payload["checkpoint_digest"] = digest
    if (
        digest != expected
        or payload.get("protocol") != CHECKPOINT_PROTOCOL
        or payload.get("target_issue") != TARGET_ISSUE
        or payload.get("as_of_issue") != AS_OF_ISSUE
        or payload.get("outcome") is not None
        or payload.get("architecture_label") != ARCHITECTURE_LABEL
    ):
        _fail("pre-outcome checkpoint identity or chronology guard is invalid")
    return payload


def _ticket_numbers(portfolio: Mapping[str, Any]) -> list[tuple[int, ...]]:
    result = []
    for slot in portfolio.get("slots") or ():
        numbers = tuple(int(value) for value in slot["six_red"]["sorted_red_numbers"])
        if len(numbers) != 6 or tuple(sorted(numbers)) != numbers:
            _fail("checkpoint portfolio contains an invalid ticket")
        result.append(numbers)
    return result


def _settle_tickets(
    tickets: Iterable[Sequence[int]],
    actual: Sequence[int],
) -> dict[str, Any]:
    normalized = [tuple(int(value) for value in ticket) for ticket in tickets]
    actual_set = set(int(value) for value in actual)
    counts = [len(set(ticket) & actual_set) for ticket in normalized]
    unique_tickets = list(dict.fromkeys(normalized))
    unique_counts = [len(set(ticket) & actual_set) for ticket in unique_tickets]
    histogram = Counter(counts)
    unique_histogram = Counter(unique_counts)
    return {
        "paid_ticket_count": len(normalized),
        "unique_ticket_count": len(unique_tickets),
        "duplicate_ticket_count": len(normalized) - len(unique_tickets),
        "best_matched_red_count": max(counts, default=0),
        "slot_hit_histogram": [histogram[index] for index in range(7)],
        "unique_ticket_hit_histogram": [
            unique_histogram[index] for index in range(7)
        ],
        "red3_plus_ticket_count": sum(value >= 3 for value in counts),
        "red4_plus_ticket_count": sum(value >= 4 for value in counts),
        "red5_plus_ticket_count": sum(value >= 5 for value in counts),
        "red6_ticket_count": sum(value == 6 for value in counts),
    }


def _load_evaluations(conn: Connection) -> dict[str, dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT e.*, p.status AS prediction_status,
                   er.status AS evaluation_run_status
              FROM training_prediction_evaluations e
              JOIN forward_prediction_runs p
                ON p.prediction_run_key = e.prediction_run_key
              JOIN forward_evaluation_runs er
                ON er.evaluation_run_key = e.evaluation_run_key
             WHERE e.predicted_issue = %s
               AND e.line_key = ANY(%s)
             ORDER BY e.line_key
            """,
            (TARGET_ISSUE, list(REQUIRED_LINE_KEYS)),
        ).fetchall()
    result = {str(row["line_key"]): _json_safe(dict(row)) for row in rows}
    if set(result) != set(REQUIRED_LINE_KEYS) or len(rows) != len(REQUIRED_LINE_KEYS):
        _fail("2026084 does not have exactly three evaluated legacy lines")
    return result


def _verify_current_legacy_identity(
    conn: Connection,
    checkpoint: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    current = {
        row["line_key"]: row for row in _load_frozen_prediction_runs_after_outcome(conn)
    }
    for frozen in checkpoint["legacy_lines"]:
        run = frozen["run"]
        line_key = run["line_key"]
        now = current.get(line_key)
        if now is None or now["prediction_run_key"] != run["prediction_run_key"]:
            _fail(f"legacy run identity changed after checkpoint: {line_key}")
        tickets = _load_top100(conn, run["prediction_run_key"])
        digest = canonical_digest(
            tickets,
            domain="dehps.2026084.legacy-top100-sequence.v1",
        )
        if digest != frozen["candidate_sequence_digest"]:
            _fail(f"legacy Top100 ticket sequence changed after checkpoint: {line_key}")
    return current


def _load_frozen_prediction_runs_after_outcome(conn: Connection) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT prediction_run_key, line_key, line_label, line_kind, snapshot_key,
                   source_run_id, source_round_index, as_of_issue, target_issue,
                   train_mode, train_window, top_n, candidate_count, config_hash,
                   prediction_fingerprint, ranking_contract, config, metadata,
                   status, generated_at
              FROM forward_prediction_runs
             WHERE target_issue = %s
               AND line_key = ANY(%s)
             ORDER BY line_key
            """,
            (TARGET_ISSUE, list(REQUIRED_LINE_KEYS)),
        ).fetchall()
    result = [_json_safe(dict(row)) for row in rows]
    if len(result) != len(REQUIRED_LINE_KEYS):
        _fail("2026084 legacy run set changed after checkpoint")
    return result


def _legacy_settlement(
    checkpoint: Mapping[str, Any],
    evaluations: Mapping[str, Mapping[str, Any]],
    actual: Sequence[int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lines = []
    all_tickets: list[tuple[int, ...]] = []
    for frozen in checkpoint["legacy_lines"]:
        run = frozen["run"]
        line_key = run["line_key"]
        evaluation = evaluations[line_key]
        summary = evaluation.get("summary") or {}
        audit = summary.get("ranking_audit") or {}
        if (
            evaluation.get("status") != "evaluated"
            or evaluation.get("prediction_status") != "evaluated"
            or evaluation.get("evaluation_run_status") != "completed"
            or evaluation.get("prediction_run_key") != run["prediction_run_key"]
            or tuple(int(value) for value in evaluation.get("actual_red_numbers") or ())
            != tuple(actual)
        ):
            _fail(f"legacy evaluation is not a verified forward settlement: {line_key}")
        model_rank = int(audit.get("model_score_rank") or 0)
        if not 1 <= model_rank <= TOTAL_SSQ_RED_COMBINATIONS:
            _fail(f"legacy full-space rank is invalid: {line_key}")
        tickets = [
            tuple(int(value) for value in row["red_numbers"])
            for row in frozen["top100_tickets"]
        ]
        all_tickets.extend(tickets)
        line_settlement = _settle_tickets(tickets, actual)
        lines.append(
            {
                "line_key": line_key,
                "prediction_run_key": run["prediction_run_key"],
                "full_space_rank": model_rank,
                "hit_top100": bool(evaluation.get("hit_top_100")),
                "hit_top10000": bool(evaluation.get("hit_top_10000")),
                "top100_ticket_settlement": line_settlement,
            }
        )
    return lines, _settle_tickets(all_tickets, actual)


def _seven_red_settlement(
    checkpoint: Mapping[str, Any],
    actual: Sequence[int],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    forward = checkpoint["seven_red_forward"]
    arms: dict[str, Any] = {}
    controls: list[dict[str, Any]] = []
    for kind, arm in forward["arms"].items():
        arms[kind] = _settle_tickets(_ticket_numbers(arm["portfolio"]), actual)
        arms[kind]["portfolio_digest"] = arm["portfolio"]["portfolio_digest"]
        for row in arm["random_control_cohort"]["portfolios"]:
            settlement = _settle_tickets(_ticket_numbers(row), actual)
            controls.append(
                {
                    "strategy_family": kind,
                    "control_kind": row["control_kind"],
                    "seed_digest": row["seed_digest"],
                    "portfolio_digest": row["portfolio_digest"],
                    **settlement,
                }
            )
    arms["six_red_top70"] = _settle_tickets(
        _ticket_numbers(forward["six_red_top70"]),
        actual,
    )
    arms["six_red_top70"]["portfolio_digest"] = forward["six_red_top70"][
        "portfolio_digest"
    ]
    return arms, controls


def _control_aggregates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        groups.setdefault(
            (str(row["strategy_family"]), str(row["control_kind"])), []
        ).append(row)
    return [
        {
            "strategy_family": family,
            "control_kind": control_kind,
            "portfolio_count": len(group),
            "mean_best_matched_red_count": sum(
                int(row["best_matched_red_count"]) for row in group
            )
            / len(group),
            "mean_red3_plus_ticket_count": sum(
                int(row["red3_plus_ticket_count"]) for row in group
            )
            / len(group),
            "mean_red4_plus_ticket_count": sum(
                int(row["red4_plus_ticket_count"]) for row in group
            )
            / len(group),
            "mean_red5_plus_ticket_count": sum(
                int(row["red5_plus_ticket_count"]) for row in group
            )
            / len(group),
        }
        for (family, control_kind), group in sorted(groups.items())
    ]


def _render_settlement(payload: Mapping[str, Any]) -> str:
    actual = " ".join(f"{int(value):02d}" for value in payload["actual_red_numbers"])
    lines = [
        f"# DEHPS {TARGET_ISSUE} frozen forward checkpoint settlement",
        "",
        f"- actual red balls: `{actual}`",
        f"- architecture label: `{ARCHITECTURE_LABEL}`",
        f"- pre-outcome checkpoint: `{payload['checkpoint_digest']}`",
        f"- outer sample ordinal: `{payload['outer_sample_ordinal']}`",
        "- Promotion Gate: **closed**",
        "- production action: `none`",
        "",
        "## Legacy frozen lines",
        "",
        "| line | full-space rank | Top100 | Top10K | Top100 best red |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in payload["legacy_lines"]:
        lines.append(
            f"| {row['line_key']} | {row['full_space_rank']} | "
            f"{row['hit_top100']} | {row['hit_top10000']} | "
            f"{row['top100_ticket_settlement']['best_matched_red_count']} |"
        )
    lines.extend(
        [
            "",
            "## Equal-cost forward arms",
            "",
            "| arm | paid | unique | best red | red3+ | red4+ | red5+ | red6 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["seven_red_arms"].items():
        lines.append(
            f"| {name} | {row['paid_ticket_count']} | {row['unique_ticket_count']} | "
            f"{row['best_matched_red_count']} | {row['red3_plus_ticket_count']} | "
            f"{row['red4_plus_ticket_count']} | {row['red5_plus_ticket_count']} | "
            f"{row['red6_ticket_count']} |"
        )
    lines.extend(
        [
            "",
            "This single issue is the 61st strict outer observation. It cannot open the "
            "Promotion Gate or support a production upgrade by itself.",
            "",
        ]
    )
    return "\n".join(lines)


def settle_forward_checkpoint_if_available(
    issue: str,
    *,
    conn: Connection | None = None,
    checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Settle 084 from its pre-outcome checkpoint; other issues are not applicable."""
    if issue != TARGET_ISSUE:
        return {"status": "not_applicable", "issue": issue}
    if not checkpoint_path.exists():
        _fail("2026084 pre-outcome checkpoint is missing")
    checkpoint = _verified_checkpoint(checkpoint_path)
    connection_context = get_connection() if conn is None else nullcontext(conn)
    with connection_context as active_conn:
        row = active_conn.execute(
            """
            SELECT draw_date, red_numbers, blue_number
              FROM ssq_history
             WHERE issue = %s
            """,
            (TARGET_ISSUE,),
        ).fetchone()
        if row is None:
            return {"status": "awaiting_outcome", "issue": issue}
        actual_date, actual_red, actual_blue = row
        actual = tuple(int(value) for value in actual_red)
        _verify_current_legacy_identity(active_conn, checkpoint)
        evaluations = _load_evaluations(active_conn)
        legacy_lines, nominal_300 = _legacy_settlement(
            checkpoint,
            evaluations,
            actual,
        )
    seven_arms, control_rows = _seven_red_settlement(checkpoint, actual)
    payload = {
        "protocol": SETTLEMENT_PROTOCOL,
        "issue": TARGET_ISSUE,
        "actual_draw_date": actual_date.isoformat(),
        "actual_red_numbers": list(actual),
        "actual_blue_number": int(actual_blue),
        "checkpoint_digest": checkpoint["checkpoint_digest"],
        "checkpoint_source_code_commit": checkpoint["source_code_commit"],
        "architecture_label": ARCHITECTURE_LABEL,
        "database_cutoff": checkpoint["database_cutoff"],
        "source_artifact_digests": {
            "seven_red_walk_forward": checkpoint["seven_red_source"][
                "walk_forward_snapshot_digest"
            ],
            "seven_red_statistical": checkpoint["seven_red_source"][
                "statistical_snapshot_digest"
            ],
            "legacy_formal_audits": {
                row["run"]["line_key"]: row["formal_portfolio_audit"]
                for row in checkpoint["legacy_lines"]
            },
        },
        "outer_sample_ordinal": 61,
        "legacy_lines": legacy_lines,
        "legacy_nominal_300": nominal_300,
        "seven_red_arms": seven_arms,
        "random_control_rows": control_rows,
        "random_control_aggregates": _control_aggregates(control_rows),
        "promotion_gate_opened": False,
        "automatic_promotion_allowed": False,
        "single_issue_upgrade_allowed": False,
        "production_action": "none",
    }
    digest = canonical_digest(payload, domain="dehps.2026084.forward-settlement.v1")
    artifact = {**payload, "settlement_digest": digest}
    stem = f"settlement-{digest}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    _write_immutable(json_path, _encoded_json(artifact))
    _write_immutable(markdown_path, _render_settlement(artifact))
    return {
        "status": "settled",
        "issue": issue,
        "checkpoint_digest": checkpoint["checkpoint_digest"],
        "settlement_digest": digest,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "promotion_gate_opened": False,
    }


__all__ = [
    "ARCHITECTURE_LABEL",
    "AS_OF_ISSUE",
    "CHECKPOINT_PROTOCOL",
    "DEFAULT_CHECKPOINT_PATH",
    "ForwardCheckpointError",
    "TARGET_ISSUE",
    "seal_2026084_checkpoint",
    "settle_forward_checkpoint_if_available",
]
