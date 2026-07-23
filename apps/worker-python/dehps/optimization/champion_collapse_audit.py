from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest
from dehps.models.frequency_ranker import FrequencyRankerConfig, HistoryDraw
from dehps.optimization.signal_diagnostics import (
    DEFAULT_RANDOM_SEEDS,
    RANKING_TIE_POLICY,
    _rank_order,
    _rank_positions,
    ranking_similarity,
)
from dehps.optimization.walk_forward import (
    CONFIG_WEIGHT_FIELDS,
    RankedUniverseMatrix,
    compile_score_config_grid_artifact,
    fingerprint_history,
)
from dehps.seven_red.domain import SIX_RED_UNIVERSE


CHAMPION_COLLAPSE_PROTOCOL = "dehps-champion-path-collapse-audit.v1"
GUARDRAIL = (
    "Diagnostic only. Candidate ranking diversity, family concentration, objective "
    "margins, and counterfactual component selectors do not authorize a new "
    "objective, weight, candidate, search restart, production mutation, or promotion."
)


class ChampionCollapseAuditError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise ChampionCollapseAuditError(message)


def _finite_number(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ChampionCollapseAuditError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        _fail(f"{label} must be finite")
    return result


def validate_candidate_state(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    state = source.get("research_candidate_state")
    if not isinstance(state, Mapping):
        _fail("source is missing research_candidate_state")
    candidates = state.get("candidates")
    evaluated = state.get("evaluated_config_hashes")
    declared_count = state.get("candidate_count")
    if not isinstance(candidates, list) or not isinstance(evaluated, list):
        _fail("candidate state must contain candidates and evaluated_config_hashes")
    hashes = [str(row.get("config_hash") or "") for row in candidates]
    evaluated_hashes = [str(value) for value in evaluated]
    if (
        int(declared_count or -1) != len(candidates)
        or len(candidates) != len(evaluated_hashes)
        or len(set(hashes)) != len(hashes)
        or set(hashes) != set(evaluated_hashes)
        or not all(hashes)
    ):
        _fail("candidate state is incomplete, duplicated, or hash-inconsistent")
    champion = source.get("research_learning", {}).get("champion", {})
    champion_hash = str(champion.get("config_hash") or "")
    if not candidates or hashes[0] != champion_hash:
        _fail("persisted candidate row 1 must match the research champion")
    for row in candidates:
        config = row.get("config")
        if not isinstance(config, Mapping):
            _fail("candidate config must be an object")
        missing = set(CONFIG_WEIGHT_FIELDS) - set(config)
        if missing:
            _fail("candidate config is missing scoring weights")
        for field in CONFIG_WEIGHT_FIELDS:
            _finite_number(config[field], label=f"config.{field}")
    return [dict(row) for row in candidates]


def _source_family(row: Mapping[str, Any]) -> str:
    candidate_source = row.get("candidate_source")
    if isinstance(candidate_source, Mapping) and candidate_source.get("key"):
        return str(candidate_source["key"])
    return str(row.get("source_key") or "unknown")


def _primary_signature(row: Mapping[str, Any]) -> tuple[int, int, int]:
    return (
        int(row.get("top_100_hits") or 0),
        int(row.get("top_1000_hits") or 0),
        int(row.get("top_10000_hits") or 0),
    )


def _objective_score(row: Mapping[str, Any]) -> float:
    reward = row.get("reward")
    return _finite_number(
        reward.get("objectiveScore") if isinstance(reward, Mapping) else None,
        label="reward.objectiveScore",
    )


def _frozen_objective_score(row: Mapping[str, Any]) -> float:
    frozen = row.get("frozen_validation")
    reward = frozen.get("reward") if isinstance(frozen, Mapping) else None
    return _finite_number(
        reward.get("objectiveScore") if isinstance(reward, Mapping) else None,
        label="frozen_validation.reward.objectiveScore",
    )


def _selector_winner(
    candidates: Sequence[Mapping[str, Any]],
    *,
    key,
    maximize: bool,
) -> dict[str, Any]:
    index, row = (
        max(enumerate(candidates), key=lambda pair: key(pair[1]))
        if maximize
        else min(enumerate(candidates), key=lambda pair: key(pair[1]))
    )
    return {
        "config_hash": str(row["config_hash"]),
        "source_family": _source_family(row),
        "persisted_candidate_rank": index + 1,
        "value": key(row),
    }


def persisted_boundary_summary(
    source: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(candidates) < 2:
        _fail("decision-boundary audit requires at least two candidates")
    family_counts = Counter(_source_family(row) for row in candidates)
    top_family_counts = {
        f"top_{cutoff}": dict(
            sorted(Counter(_source_family(row) for row in candidates[:cutoff]).items())
        )
        for cutoff in (1, 5, 10, 20)
        if len(candidates) >= cutoff
    }
    signatures = [_primary_signature(row) for row in candidates]
    signature_counts = Counter(signatures)
    champion = candidates[0]
    runner_up = candidates[1]
    champion_objective = _objective_score(champion)
    runner_objective = _objective_score(runner_up)
    objective_margin = champion_objective - runner_objective
    selectors = {
        "persisted_candidate_order": {
            "config_hash": str(champion["config_hash"]),
            "source_family": _source_family(champion),
            "persisted_candidate_rank": 1,
            "value": None,
        },
        "recorded_search_objective_max": _selector_winner(
            candidates,
            key=_objective_score,
            maximize=True,
        ),
        "recorded_frozen_objective_max": _selector_winner(
            candidates,
            key=_frozen_objective_score,
            maximize=True,
        ),
        "recorded_median_rank_min": _selector_winner(
            candidates,
            key=lambda row: _finite_number(row.get("median_rank"), label="median_rank"),
            maximize=False,
        ),
        "recorded_worst_rank_min": _selector_winner(
            candidates,
            key=lambda row: _finite_number(row.get("worst_rank"), label="worst_rank"),
            maximize=False,
        ),
    }
    winner_hashes = {str(row["config_hash"]) for row in selectors.values()}
    round_summary = source.get("round_summary")
    learning = source.get("research_learning")
    champion_state = learning.get("champion") if isinstance(learning, Mapping) else {}
    return {
        "round_count": int(
            round_summary.get("round_count") if isinstance(round_summary, Mapping) else 0
        ),
        "last_improved_round": int(
            round_summary.get("last_improved_round")
            if isinstance(round_summary, Mapping)
            else 0
        ),
        "stagnation_rounds": int(
            round_summary.get("stagnation_rounds")
            if isinstance(round_summary, Mapping)
            else 0
        ),
        "persisted_champion": {
            "config_hash": str(champion["config_hash"]),
            "source_family": _source_family(champion),
            "champion_round": int(
                champion_state.get("round")
                if isinstance(champion_state, Mapping)
                else 0
            ),
            "primary_signature": list(_primary_signature(champion)),
            "objective_score": champion_objective,
            "frozen_objective_score": _frozen_objective_score(champion),
        },
        "runner_up": {
            "config_hash": str(runner_up["config_hash"]),
            "source_family": _source_family(runner_up),
            "primary_signature": list(_primary_signature(runner_up)),
            "primary_signature_tied": _primary_signature(champion)
            == _primary_signature(runner_up),
            "objective_score": runner_objective,
        },
        "objective_boundary": {
            "champion_minus_runner_up_objective_score": objective_margin,
            "relative_margin": objective_margin / max(abs(champion_objective), 1e-12),
            "primary_signature_tied": _primary_signature(champion)
            == _primary_signature(runner_up),
            "diagnostic_component_selectors": selectors,
            "distinct_selector_winner_count": len(winner_hashes),
            "selector_count": len(selectors),
            "all_selectors_choose_persisted_champion": len(winner_hashes) == 1,
        },
        "source_families": {
            "candidate_count": len(candidates),
            "family_count": len(family_counts),
            "overall_counts": dict(sorted(family_counts.items())),
            "top_counts": top_family_counts,
        },
        "primary_signatures": {
            "unique_count": len(signature_counts),
            "champion_signature_candidate_count": signature_counts[
                _primary_signature(champion)
            ],
            "champion_signature_share": signature_counts[
                _primary_signature(champion)
            ]
            / len(candidates),
        },
    }


def topk_sequence_digest(order: np.ndarray, cutoff: int) -> str:
    if order.ndim != 1 or cutoff < 1 or len(order) < cutoff:
        _fail("TopK sequence digest requires a valid order and cutoff")
    values = np.ascontiguousarray(order[:cutoff], dtype="<i8")
    return hashlib.sha256(values.tobytes()).hexdigest()


def _weight_distance(
    left: FrequencyRankerConfig,
    right: FrequencyRankerConfig,
) -> dict[str, float]:
    delta = np.array(
        [
            float(getattr(left, field)) - float(getattr(right, field))
            for field in CONFIG_WEIGHT_FIELDS
        ],
        dtype=np.float64,
    )
    return {
        "l2": float(np.linalg.norm(delta)),
        "max_abs": float(np.max(np.abs(delta))),
    }


def run_champion_collapse_audit(
    *,
    source: Mapping[str, Any],
    source_path: str,
    source_sha256: str,
    history: list[HistoryDraw],
    ranked_universe: RankedUniverseMatrix,
    target_issue: str,
    target_draw_date: date | None,
    seed_digest: str = DEFAULT_RANDOM_SEEDS[0],
) -> dict[str, Any]:
    candidates = validate_candidate_state(source)
    if len(ranked_universe) != SIX_RED_UNIVERSE.cardinality:
        _fail("champion collapse audit requires the full legal six-red universe")
    configs = tuple(FrequencyRankerConfig(**row["config"]) for row in candidates)
    score_artifact = compile_score_config_grid_artifact(
        train_history=history,
        configs=configs,
        ranked_universe=ranked_universe,
        target_draw_date=target_draw_date,
        target_issue=target_issue,
    )
    champion_scores = score_artifact.scores[:, 0]
    champion_order = _rank_order(champion_scores)
    champion_positions = _rank_positions(champion_order)
    champion_config = configs[0]
    rows = []
    for index, (candidate, config) in enumerate(
        zip(candidates, configs, strict=True)
    ):
        scores = score_artifact.scores[:, index]
        order = _rank_order(scores)
        positions = _rank_positions(order)
        rows.append(
            {
                "persisted_candidate_rank": index + 1,
                "config_hash": str(candidate["config_hash"]),
                "source_family": _source_family(candidate),
                "config": dict(candidate["config"]),
                "recorded_search_metrics": {
                    "primary_signature": list(_primary_signature(candidate)),
                    "median_rank": candidate.get("median_rank"),
                    "worst_rank": candidate.get("worst_rank"),
                    "objective_score": _objective_score(candidate),
                    "frozen_objective_score": _frozen_objective_score(candidate),
                },
                "weight_distance_vs_champion": _weight_distance(
                    champion_config,
                    config,
                ),
                "ranking_similarity_vs_champion": (
                    {
                        "spearman_full_universe": 1.0,
                        "kendall_tau_pair_sample": 1.0,
                        "kendall_pair_count": 50_000,
                        "topk_jaccard": {
                            "top_10": 1.0,
                            "top_100": 1.0,
                            "top_10000": 1.0,
                        },
                    }
                    if index == 0
                    else ranking_similarity(
                        reference_positions=champion_positions,
                        candidate_positions=positions,
                        seed_digest=seed_digest,
                        target_issue=target_issue,
                        comparison_label=str(candidate["config_hash"]),
                    )
                ),
                "topk_sequence_digests": {
                    f"top_{cutoff}": topk_sequence_digest(order, cutoff)
                    for cutoff in (10, 100, 10_000)
                },
            }
        )
    boundary = persisted_boundary_summary(source, candidates)
    geometry_summary: dict[str, Any] = {
        "candidate_count": len(rows),
        "unique_topk_sequence_digests": {
            f"top_{cutoff}": len(
                {row["topk_sequence_digests"][f"top_{cutoff}"] for row in rows}
            )
            for cutoff in (10, 100, 10_000)
        },
    }
    for metric in (
        "spearman_full_universe",
        "kendall_tau_pair_sample",
    ):
        values = [
            float(row["ranking_similarity_vs_champion"][metric]) for row in rows
        ]
        geometry_summary[metric] = {
            "min": min(values),
            "median": float(np.median(values)),
            "max": max(values),
            "mean": float(np.mean(values)),
        }
    for cutoff in (10, 100, 10_000):
        values = [
            float(
                row["ranking_similarity_vs_champion"]["topk_jaccard"][
                    f"top_{cutoff}"
                ]
            )
            for row in rows
        ]
        geometry_summary[f"top_{cutoff}_jaccard"] = {
            "min": min(values),
            "median": float(np.median(values)),
            "max": max(values),
            "mean": float(np.mean(values)),
        }
    payload = {
        "protocol": {
            "name": CHAMPION_COLLAPSE_PROTOCOL,
            "status": "diagnostic_only",
            "promotion_allowed": False,
            "target_issue": target_issue,
            "target_draw_date": (
                target_draw_date.isoformat() if target_draw_date else None
            ),
            "outcome_accessed": False,
            "history_latest_issue": history[-1][0],
            "history_fingerprint": fingerprint_history(history),
            "universe_size": len(ranked_universe),
            "universe_contract": "full_legal_six_red",
            "ranking_tie_policy": RANKING_TIE_POLICY,
            "seed_digest": seed_digest,
            "guardrail": GUARDRAIL,
        },
        "source": {
            "path": source_path,
            "file_sha256": source_sha256,
            "run_id": source.get("run_id"),
            "status": source.get("status"),
            "candidate_count": len(candidates),
            "evaluated_config_hash_count": len(
                source["research_candidate_state"]["evaluated_config_hashes"]
            ),
        },
        "score_artifact_digest": score_artifact.artifact_digest,
        "decision_path": boundary,
        "ranking_geometry": geometry_summary,
        "candidates": rows,
        "winner": None,
        "research_decision": None,
        "production_action": "none",
    }
    digest = canonical_digest(
        payload,
        domain="dehps.champion-collapse-audit.snapshot.v1",
    )
    return {**payload, "snapshot_digest": digest}


def render_champion_collapse_report(payload: Mapping[str, Any]) -> str:
    protocol = payload["protocol"]
    decision = payload["decision_path"]
    geometry = payload["ranking_geometry"]
    champion = decision["persisted_champion"]
    runner = decision["runner_up"]
    boundary = decision["objective_boundary"]
    return "\n".join(
        (
            "# DEHPS champion-path collapse audit",
            "",
            f"- snapshot: `{payload['snapshot_digest']}`",
            f"- source run: `{payload['source']['run_id']}`",
            f"- source rounds: `{decision['round_count']}`",
            f"- last improved round: `{decision['last_improved_round']}`",
            f"- stagnation rounds: `{decision['stagnation_rounds']}`",
            f"- retained candidates: `{geometry['candidate_count']}`",
            f"- pre-outcome target: `{protocol['target_issue']}`",
            f"- outcome accessed: `{str(protocol['outcome_accessed']).lower()}`",
            f"- promotion allowed: `{str(protocol['promotion_allowed']).lower()}`",
            "",
            "## Candidate ranking geometry",
            "",
            f"- unique Top10 sequences: `{geometry['unique_topk_sequence_digests']['top_10']}`",
            f"- unique Top100 sequences: `{geometry['unique_topk_sequence_digests']['top_100']}`",
            f"- unique Top10000 sequences: `{geometry['unique_topk_sequence_digests']['top_10000']}`",
            f"- Spearman vs champion: min `{geometry['spearman_full_universe']['min']:.6f}`, median `{geometry['spearman_full_universe']['median']:.6f}`",
            f"- Top10000 Jaccard vs champion: min `{geometry['top_10000_jaccard']['min']:.6f}`, median `{geometry['top_10000_jaccard']['median']:.6f}`",
            "",
            "## Persisted champion path",
            "",
            f"- champion: `{champion['config_hash']}` from `{champion['source_family']}` at round `{champion['champion_round']}`",
            f"- runner-up: `{runner['config_hash']}` from `{runner['source_family']}`",
            f"- primary signature tied: `{str(boundary['primary_signature_tied']).lower()}`",
            f"- objective margin: `{boundary['champion_minus_runner_up_objective_score']:.12f}`",
            f"- relative objective margin: `{boundary['relative_margin']:.12f}`",
            f"- distinct diagnostic component winners: `{boundary['distinct_selector_winner_count']}/{boundary['selector_count']}`",
            "",
            "Candidate-set diversity and champion-path diversity are separate "
            "endpoints. No winner or research decision is produced.",
            "",
            GUARDRAIL,
            "",
        )
    )


def write_champion_collapse_artifacts(
    payload: Mapping[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    digest = str(payload["snapshot_digest"])
    body = {key: value for key, value in payload.items() if key != "snapshot_digest"}
    expected = canonical_digest(
        body,
        domain="dehps.champion-collapse-audit.snapshot.v1",
    )
    if digest != expected:
        _fail("champion collapse snapshot digest does not cover the payload")
    json_path = output_dir / f"champion-collapse-audit-{digest}.json"
    report_path = output_dir / f"champion-collapse-audit-{digest}.md"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    report = render_champion_collapse_report(payload)
    for path, content in ((json_path, encoded), (report_path, report)):
        if path.exists() and path.read_text(encoding="utf-8") != content:
            _fail(f"digest-addressed artifact content mismatch: {path}")
        if not path.exists():
            atomic_write_text(path, content)
    return json_path, report_path


__all__ = [
    "CHAMPION_COLLAPSE_PROTOCOL",
    "ChampionCollapseAuditError",
    "GUARDRAIL",
    "persisted_boundary_summary",
    "render_champion_collapse_report",
    "run_champion_collapse_audit",
    "topk_sequence_digest",
    "validate_candidate_state",
    "write_champion_collapse_artifacts",
]
