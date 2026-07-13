from __future__ import annotations

from dataclasses import dataclass

from dehps.search.fields import PHASE_SEARCH_FIELDS


EARLY_BROAD_ROUNDS = 24
MID_SEARCH_ROUNDS = 72
PHASES = (("large", 0.20), ("large", 0.15), ("medium", 0.10), ("large", 0.12))
MID_PHASES = (("medium", 0.08), ("medium", 0.06), ("small", 0.04))
LATE_PHASES = (("small", 0.03), ("micro", 0.015), ("micro", 0.01), ("small", 0.02))
EARLY_SEARCH_BASE_MIN_DISTANCE = 0.08
MID_SEARCH_BASE_MIN_DISTANCE = 0.04
LATE_SEARCH_BASE_MIN_DISTANCE = 0.015
STAGNATION_THRESHOLD = 16


@dataclass(frozen=True)
class SearchState:
    round_index: int
    stagnation_rounds: int = 0


@dataclass(frozen=True)
class SearchPhase:
    name: str
    distance: float
    fields: tuple[str, ...]
    stage: str


def select_search_phase(state: SearchState) -> SearchPhase:
    if state.stagnation_rounds >= STAGNATION_THRESHOLD:
        _name, distance = PHASES[state.round_index % len(PHASES)]
        name, stage = "large", "stagnation_broad"
        distance = max(distance, 0.15)
    elif state.round_index < EARLY_BROAD_ROUNDS:
        name, distance = PHASES[state.round_index % len(PHASES)]
        stage = "early_broad"
    elif state.round_index < MID_SEARCH_ROUNDS:
        name, distance = MID_PHASES[(state.round_index - EARLY_BROAD_ROUNDS) % len(MID_PHASES)]
        stage = "mid_search"
    else:
        name, distance = LATE_PHASES[(state.round_index - MID_SEARCH_ROUNDS) % len(LATE_PHASES)]
        stage = "late_refine"
    return SearchPhase(name=name, distance=distance, fields=PHASE_SEARCH_FIELDS[name], stage=stage)


def search_base_min_distance_for_stage(stage: str) -> float:
    if stage in {"early_broad", "stagnation_broad"}:
        return EARLY_SEARCH_BASE_MIN_DISTANCE
    if stage == "mid_search":
        return MID_SEARCH_BASE_MIN_DISTANCE
    return LATE_SEARCH_BASE_MIN_DISTANCE
