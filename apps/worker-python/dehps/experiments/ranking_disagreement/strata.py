from __future__ import annotations

import numpy as np

from dehps.experiments.ranking_disagreement.models import STRATA_KEYS, FeatureFrame, StrataThresholds


def fit_strata_thresholds(frames: list[FeatureFrame], *, source_stage: str = "historical_search") -> StrataThresholds:
    if source_stage != "historical_search":
        raise ValueError("Round 24 strata thresholds may only be fit in historical_search")
    if not frames:
        raise ValueError("cannot fit disagreement strata without search-window features")
    values = np.concatenate([frame.disagreement_score for frame in frames])
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("strata fit received missing or non-finite disagreement scores")
    low, medium, high = np.quantile(values, [0.25, 0.50, 0.75], method="linear")
    if not (low <= medium <= high):
        raise ValueError("strata thresholds are not monotonic")
    return StrataThresholds(
        low_max=float(low),
        medium_max=float(medium),
        high_max=float(high),
        source_stage=source_stage,
        source_issue_count=len(frames),
    ).finalized()


def assign_strata(frame: FeatureFrame, thresholds: StrataThresholds) -> np.ndarray:
    frozen = thresholds.finalized() if not thresholds.fingerprint else thresholds
    scores = frame.disagreement_score
    labels = np.full(scores.shape[0], "extreme_disagreement", dtype=object)
    labels[scores <= frozen.high_max] = "high_disagreement"
    labels[scores <= frozen.medium_max] = "medium_disagreement"
    labels[scores <= frozen.low_max] = "low_disagreement"
    unique = set(str(label) for label in np.unique(labels))
    if not unique.issubset(set(STRATA_KEYS)):
        raise ValueError(f"unknown strata produced: {sorted(unique)}")
    if labels.shape[0] != frame.combination_ids.shape[0]:
        raise ValueError("strata assignment count must match legal universe")
    return labels


def strata_counts(labels: np.ndarray) -> dict[str, int]:
    return {key: int(np.sum(labels == key)) for key in STRATA_KEYS}


def thresholds_from_json(payload: dict[str, object]) -> StrataThresholds:
    return StrataThresholds(
        low_max=float(payload["low_max"]),
        medium_max=float(payload["medium_max"]),
        high_max=float(payload["high_max"]),
        source_stage=str(payload["source_stage"]),
        source_issue_count=int(payload["source_issue_count"]),
        version=str(payload.get("version", "ranking-disagreement-strata-v1")),
        fingerprint=str(payload.get("fingerprint", "")),
    ).finalized()
