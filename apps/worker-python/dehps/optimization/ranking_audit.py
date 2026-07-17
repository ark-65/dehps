from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import Connection

from dehps.features.red_ball_features import calculate_red_ball_features
from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.regime import select_history
from dehps.optimization.walk_forward import (
    RankedUniverseMatrix,
    build_ranked_universe,
    fingerprint_history,
    rank_target,
    rank_target_structural,
)
from dehps.ranking_contract import normalize_ranking_contract
from dehps.storage.postgres_store import (
    TOTAL_SSQ_RED_COMBINATIONS,
    load_history_until_with_dates,
)


LEGACY_CURRENT_REGIME_YEARS = 10


class PredictionHistoryReplayError(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class PredictionHistoryReplay:
    history: list
    base_history: list
    resolution: str
    stored_fingerprint: str
    replay_fingerprint: str


def resolve_training_history_for_prediction_run(
    conn: Connection,
    run: dict[str, Any],
    *,
    apply_train_window: bool = True,
) -> PredictionHistoryReplay:
    """Reconstruct the exact history identity before applying a rolling window.

    Legacy forward runs did not persist their current-regime fields. They may use
    the historical 10-year production default only when its digest exactly matches
    the immutable fingerprint stored with the run. No heuristic fallback is allowed.
    """

    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    as_of_issue = str(run.get("as_of_issue") or metadata.get("as_of_issue") or "")
    scope = str(metadata.get("history_scope") or "")
    regime_years = int(metadata.get("regime_years") or 0)
    stored_fingerprint = str(metadata.get("history_fingerprint") or "")

    if scope in {"full_history_audit", "current_regime_default"} and regime_years >= 1:
        base_history = select_history(
            conn,
            scope=scope,  # type: ignore[arg-type]
            as_of_issue=as_of_issue,
            regime_years=regime_years,
        ).dated_history
        resolution = f"explicit:{scope}:{regime_years}y"
    else:
        base_history = load_history_until_with_dates(conn, as_of_issue)
        resolution = "legacy:full_history"

    replay_fingerprint = fingerprint_history(base_history)
    if stored_fingerprint and replay_fingerprint != stored_fingerprint and not scope:
        legacy_selection = select_history(
            conn,
            scope="current_regime_default",
            as_of_issue=as_of_issue,
            regime_years=LEGACY_CURRENT_REGIME_YEARS,
        )
        legacy_fingerprint = fingerprint_history(legacy_selection.dated_history)
        if legacy_fingerprint == stored_fingerprint:
            base_history = legacy_selection.dated_history
            replay_fingerprint = legacy_fingerprint
            resolution = "legacy:current_regime_default:10y:exact_digest"

    if stored_fingerprint and replay_fingerprint != stored_fingerprint:
        raise PredictionHistoryReplayError(
            "prediction_history_fingerprint_mismatch",
            "the prediction history snapshot cannot be reconstructed exactly",
            prediction_run_key=run.get("prediction_run_key"),
            as_of_issue=as_of_issue,
            resolution=resolution,
            stored=stored_fingerprint,
            replay=replay_fingerprint,
        )

    history = base_history
    if apply_train_window and str(run.get("train_mode") or metadata.get("train_mode")) == "rolling":
        train_window = int(run.get("train_window") or metadata.get("train_window") or 0)
        if train_window > 0:
            history = history[-train_window:]
    return PredictionHistoryReplay(
        history=history,
        base_history=base_history,
        resolution=resolution,
        stored_fingerprint=stored_fingerprint,
        replay_fingerprint=replay_fingerprint,
    )


def legal_red_combination(numbers: tuple[int, ...]) -> bool:
    return (
        len(numbers) == 6
        and tuple(sorted(numbers)) == numbers
        and len(set(numbers)) == 6
        and all(1 <= number <= 33 for number in numbers)
    )


def hard_filter_reason(numbers: tuple[int, ...]) -> str | None:
    features = calculate_red_ball_features(numbers)
    if int(features["max_consecutive_run"]) >= 5:
        return "max_consecutive_run_at_least_5"
    for key in ("zone_1_count", "zone_2_count", "zone_3_count"):
        if int(features[key]) == 6:
            return f"all_numbers_in_{key.removesuffix('_count')}"
    return None


def training_history_for_prediction_run(
    conn: Connection,
    run: dict[str, Any],
    *,
    apply_train_window: bool = True,
) -> list:
    return resolve_training_history_for_prediction_run(
        conn,
        run,
        apply_train_window=apply_train_window,
    ).history


def build_actual_ranking_audit(
    conn: Connection,
    *,
    prediction_run: dict[str, Any],
    actual_draw: dict[str, Any],
    candidates: list[dict[str, Any]],
    ranked_universe: RankedUniverseMatrix | None = None,
) -> dict[str, Any]:
    actual = tuple(int(value) for value in actual_draw.get("red_numbers") or ())
    issue = str(actual_draw.get("issue") or prediction_run.get("target_issue") or "")
    generated = legal_red_combination(actual)
    reason = hard_filter_reason(actual) if generated else "invalid_legal_combination"
    passed_hard_filters = generated and reason is None
    audit: dict[str, Any] = {
        "protocol": "forward-actual-ranking-path-v1",
        "issue": issue,
        "line_key": prediction_run.get("line_key"),
        "prediction_run_key": prediction_run.get("prediction_run_key"),
        "snapshot_key": prediction_run.get("snapshot_key"),
        "ranking_contract": normalize_ranking_contract(
            prediction_run.get("ranking_contract")
        ),
        "actual_reds": list(actual),
        "legal_sample_space": TOTAL_SSQ_RED_COMBINATIONS,
        "generated": generated,
        "passed_hard_filters": passed_hard_filters,
        "hard_filter_reason": reason if generated else None,
        "initial_score_rank": None,
        "model_score_rank": None,
        "rerank_applied": False,
        "rerank_rank": None,
        "final_export_rank": None,
        "eliminated_stage": None,
        "elimination_reason": None,
    }
    if not generated:
        audit.update(eliminated_stage="generation", elimination_reason="invalid_legal_combination")
        return audit
    if not passed_hard_filters:
        audit.update(eliminated_stage="hard_filter", elimination_reason=reason)
        return audit

    matrix = ranked_universe or build_ranked_universe()
    history = training_history_for_prediction_run(conn, prediction_run)
    config_values = prediction_run.get("config") if isinstance(prediction_run.get("config"), dict) else {}
    config = FrequencyRankerConfig(
        **{key: float(value) for key, value in config_values.items() if isinstance(value, int | float)}
    )
    initial_rank, initial_score = rank_target_structural(
        target_numbers=actual,
        ranked_universe=matrix,
    )
    model_rank, model_score = rank_target(
        target_numbers=actual,
        train_history=history,
        config=config,
        target_draw_date=actual_draw.get("draw_date"),
        ranked_universe=matrix,
    )
    export_row = next(
        (
            row
            for row in candidates
            if tuple(int(value) for value in row.get("red_numbers") or ()) == actual
        ),
        None,
    )
    final_export_rank = int(export_row["rank"]) if export_row is not None else None
    top_n = int(prediction_run.get("top_n") or len(candidates))
    audit.update(
        initial_score_rank=initial_rank,
        initial_score=initial_score,
        model_score_rank=model_rank,
        model_score=model_score,
        # There is currently no separate post-model reranker. Record the identity
        # transition explicitly so a future reranker cannot be confused with export.
        rerank_rank=model_rank,
        final_export_rank=final_export_rank,
    )
    if model_rank > top_n:
        audit.update(
            eliminated_stage="model_score",
            elimination_reason="model_score_rank_below_export_cutoff",
        )
    elif final_export_rank is None:
        audit.update(
            eliminated_stage="final_export",
            elimination_reason="expected_candidate_missing_from_export",
        )
    elif final_export_rank != model_rank:
        audit.update(
            eliminated_stage="final_export",
            elimination_reason="export_rank_mismatch",
        )
    return audit
