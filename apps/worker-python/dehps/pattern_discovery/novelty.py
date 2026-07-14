from __future__ import annotations

from typing import Iterable, Protocol

from dehps.pattern_discovery.models import PatternCandidate, PatternNoveltyReport


class ExistingPattern(Protocol):
    pattern_key: str
    pattern_family: str
    formula_hash: str
    parameters: dict
    lifecycle_status: str


class PatternNoveltyDetector:
    def evaluate(
        self,
        candidate: PatternCandidate,
        existing: Iterable[ExistingPattern | PatternCandidate | dict],
        *,
        rejected_family_keys: Iterable[str] = (),
    ) -> PatternNoveltyReport:
        duplicate_keys: list[str] = []
        renamed: list[str] = []
        near_retries: list[str] = []
        rejected_families = set(rejected_family_keys)
        for item in existing:
            key = self._field(item, "pattern_key")
            if key == candidate.pattern_key:
                continue
            formula_hash = self._field(item, "formula_hash")
            family = self._field(item, "pattern_family")
            parameters = self._field(item, "parameters") or {}
            status = str(self._field(item, "lifecycle_status") or "")
            if formula_hash == candidate.formula_hash:
                duplicate_keys.append(str(key))
            elif family == candidate.pattern_family and parameters == candidate.parameters:
                renamed.append(str(key))
            if family in rejected_families or status in {"frozen_rejected", "forward_rejected"}:
                if family == candidate.pattern_family:
                    near_retries.append(str(key))
        reasons: list[str] = []
        if duplicate_keys:
            reasons.append("formula_hash_duplicate")
        if renamed:
            reasons.append("renamed_or_reparameterized_duplicate")
        if near_retries:
            reasons.append("rejected_family_near_retry")
        score = max(0.0, 1.0 - 0.5 * bool(duplicate_keys) - 0.3 * bool(renamed) - 0.2 * bool(near_retries))
        return PatternNoveltyReport(
            pattern_key=candidate.pattern_key,
            is_novel=not reasons,
            novelty_score=score,
            duplicate_pattern_keys=tuple(sorted(set(duplicate_keys))),
            renamed_duplicate_keys=tuple(sorted(set(renamed))),
            rejected_family_near_retries=tuple(sorted(set(near_retries))),
            parent_pattern_key=None if not duplicate_keys else sorted(duplicate_keys)[0],
            reasons=tuple(reasons),
        )

    @staticmethod
    def _field(value: object, name: str):
        if isinstance(value, dict):
            if name == "formula_hash" and "formula_hash" not in value and "formula" in value:
                return value.get("formula_hash")
            return value.get(name)
        attr = getattr(value, name, None)
        if name == "formula_hash" and attr is None and hasattr(value, "formula_hash"):
            return getattr(value, "formula_hash")
        return attr
