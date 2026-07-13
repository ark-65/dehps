from __future__ import annotations


RANK_HOMOGENEITY_STAGNATION_THRESHOLD = 16
RANK_HOMOGENEITY_WINDOW = 12
RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES = 4
EARLY_RANK_HOMOGENEITY_STAGNATION_THRESHOLD = 4
EARLY_RANK_HOMOGENEITY_WINDOW = 4
EARLY_RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES = 1


def rank_homogeneity_guardrail(
    rounds: list[dict],
    *,
    stagnation_rounds: int,
    window: int = RANK_HOMOGENEITY_WINDOW,
    max_unique_signatures: int = RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES,
) -> dict:
    signatures = _recent_signatures(rounds, window)
    unique_signatures = sorted(set(signatures))
    early_signatures = _recent_signatures(rounds, EARLY_RANK_HOMOGENEITY_WINDOW)
    early_unique_signatures = sorted(set(early_signatures))
    early_active = (
        stagnation_rounds >= EARLY_RANK_HOMOGENEITY_STAGNATION_THRESHOLD
        and len(early_signatures) >= EARLY_RANK_HOMOGENEITY_WINDOW
        and len(early_unique_signatures) <= EARLY_RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES
    )
    fallback_active = (
        stagnation_rounds >= RANK_HOMOGENEITY_STAGNATION_THRESHOLD
        and len(signatures) >= window
        and len(unique_signatures) <= max_unique_signatures
    )
    active = early_active or fallback_active
    if active:
        reason = "stale_rank_signature_cycle"
    elif stagnation_rounds < EARLY_RANK_HOMOGENEITY_STAGNATION_THRESHOLD:
        reason = "below_stagnation_threshold"
    elif len(early_signatures) < EARLY_RANK_HOMOGENEITY_WINDOW:
        reason = "insufficient_signature_window"
    else:
        reason = "rank_signatures_still_diverse"
    if fallback_active and not early_active:
        threshold, effective_window = RANK_HOMOGENEITY_STAGNATION_THRESHOLD, window
        observed, effective_signatures = len(signatures), unique_signatures
        effective_max = max_unique_signatures
    else:
        threshold, effective_window = EARLY_RANK_HOMOGENEITY_STAGNATION_THRESHOLD, EARLY_RANK_HOMOGENEITY_WINDOW
        observed, effective_signatures = len(early_signatures), early_unique_signatures
        effective_max = EARLY_RANK_HOMOGENEITY_MAX_UNIQUE_SIGNATURES
    return {
        "active": active,
        "reason": reason,
        "trigger_mode": "exact_repeat" if early_active else "low_diversity_cycle" if fallback_active else "",
        "stagnation_rounds": stagnation_rounds,
        "stagnation_threshold": threshold,
        "window": effective_window,
        "observed": observed,
        "unique_signature_count": len(effective_signatures),
        "max_unique_signatures": effective_max,
        "fallback_stagnation_threshold": RANK_HOMOGENEITY_STAGNATION_THRESHOLD,
        "fallback_window": window,
        "fallback_observed": len(signatures),
        "fallback_unique_signature_count": len(unique_signatures),
        "fallback_max_unique_signatures": max_unique_signatures,
        "signatures": effective_signatures[:8],
    }


def _recent_signatures(rounds: list[dict], window: int) -> list[str]:
    signatures: list[str] = []
    for round_info in rounds[-max(0, window):]:
        prefilter = round_info.get("prefilter") if isinstance(round_info.get("prefilter"), dict) else {}
        signature = prefilter.get("round_best_rank_signature_hash")
        if isinstance(signature, str) and signature:
            signatures.append(signature)
    return signatures
