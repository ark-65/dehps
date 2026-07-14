from __future__ import annotations

from collections import Counter
from typing import Iterable

from dehps.domain.combination import normalize_red_numbers
from dehps.pattern_discovery.models import (
    DEFAULT_PATTERN_GENERATOR_VERSION,
    LEGAL_UNIVERSE_FINGERPRINT,
    PatternCandidate,
    history_fingerprint,
    pattern_key,
)


DrawRecord = tuple[str, tuple[int, ...]]


class ModularPatternExtractor:
    def __init__(self, *, generator_version: str = DEFAULT_PATTERN_GENERATOR_VERSION) -> None:
        self.generator_version = generator_version

    def extract_draw_patterns(self, draws: Iterable[DrawRecord], *, max_patterns: int = 20) -> tuple[PatternCandidate, ...]:
        normalized = tuple((str(issue), normalize_red_numbers(numbers)) for issue, numbers in draws)
        candidates: list[PatternCandidate] = []
        for modulus in (3, 5, 7, 10):
            counts: Counter[tuple[int, ...]] = Counter()
            for _, numbers in normalized:
                counts[tuple(sum(1 for n in numbers if n % modulus == residue) for residue in range(modulus))] += 1
            for profile, count in counts.most_common(max(1, max_patterns // 4)):
                candidates.append(self._candidate(modulus, profile, count, normalized))
        return tuple(candidates[:max_patterns])

    def _candidate(self, modulus: int, profile: tuple[int, ...], observed_count: int, draws: tuple[DrawRecord, ...]) -> PatternCandidate:
        kind = "tail_digit_histogram" if modulus == 10 else f"mod_{modulus}_residue"
        expected = len(draws) / max(1, modulus ** 2)
        payload = {"kind": kind, "profile": profile, "history": history_fingerprint(draws), "generator": self.generator_version}
        return PatternCandidate(
            pattern_key=pattern_key("pattern-mod", payload),
            pattern_family="tail_mod",
            pattern_type=kind,
            description=f"Residue profile modulo {modulus}: {profile}.",
            input_boundary={"domain": "ssq_red_ball", "red_count": 6, "modulus": modulus},
            formula={"operator": "residue_profile", "modulus": modulus, "profile": profile},
            parameters={"modulus": modulus, "profile": profile},
            observed_support=float(observed_count),
            expected_support=float(expected),
            effect_size=(observed_count - expected) / max(1, len(draws)),
            stability_score=0.5,
            novelty_score=1.0,
            complexity_score=min(1.0, 0.2 + modulus / 50),
            search_issue_range={"start": draws[0][0], "end": draws[-1][0]} if draws else {},
            history_fingerprint=history_fingerprint(draws),
            legal_universe_fingerprint=LEGAL_UNIVERSE_FINGERPRINT,
            null_definition={"primary": "legal_universe", "matched": {"legal_universe": expected / max(1, len(draws))}},
            failure_condition={"frozen": "family_adjusted_p_value >= 0.05"},
            leakage_risks=("post_hoc_modulus_selection",),
            source_artifacts=tuple(issue for issue, numbers in draws if tuple(sum(1 for n in numbers if n % modulus == residue) for residue in range(modulus)) == profile),
            multiplicity_family=kind,
            generator_version=self.generator_version,
            metadata={"sample_count": len(draws)},
        )
