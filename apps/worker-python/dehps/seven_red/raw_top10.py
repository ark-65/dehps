from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from math import isfinite
from numbers import Real
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.seven_red.domain import (
    LINE_KEY,
    RESEARCH_ONLY,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SevenRedCandidate,
)


PRE_SCORED_CANDIDATE_LIST_VERSION = "pre_scored_seven_red_candidate_list.v1"
RAW_TOP10_SNAPSHOT_VERSION = "seven_red_raw_top10_snapshot.v1"
RAW_TOP10_RANKING_CONTRACT = "seven_red_raw_top10.normalized_round8_desc_lex_id_asc.v1"
RAW_TOP10_SIZE = 10
SCORE_ROUND_DIGITS = 8

SEVEN_RED_RAW_TOP10_NORMATIVE_DEFINITION = {
    "contract": "seven-red-raw-top10.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "seven_red_domain": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
    },
    "pre_scored_candidate": {
        "candidate": "canonical_SevenRedCandidate_under_seven-red-domain.v1.0.0",
        "scores": "finite_float64_compatible_raw_and_normalized_values",
        "stored_score_type": "python_float_binary64",
        "ranking_score": "normalized_score_rounded_to_8_decimal_places",
        "provenance": ["source_model", "feature_digest", "source_run_id"],
        "identity": "full_domain_separated_sha256_over_candidate_scores_and_provenance",
    },
    "candidate_list": {
        "canonical_order": "candidate_full_universe_lex_id_ascending",
        "input_order": "not_part_of_identity",
        "duplicates": "forbidden_by_candidate_id",
        "identity": "full_domain_separated_sha256_over_canonical_rows",
        "seed": "absent",
    },
    "raw_top10": {
        "size": RAW_TOP10_SIZE,
        "ranking_contract": RAW_TOP10_RANKING_CONTRACT,
        "primary_order": "ranking_score_descending",
        "tie_break": "candidate_full_universe_lex_id_ascending",
        "score_mutation": "forbidden",
        "diversity_intervention": "forbidden",
        "insufficient_input": "fail_closed",
        "identity": "source_artifact_digest_plus_ranked_selected_rows",
    },
    "non_goals": [
        "no_candidate_generation",
        "no_score_normalization_algorithm",
        "no_diversified_top10",
        "no_cross_candidate_expansion_audit",
        "no_model_or_production_integration",
        "no_research_conclusion",
    ],
}

SEVEN_RED_RAW_TOP10_GOLDEN_SUITE = {
    "suite": "seven_red_raw_top10_golden.v1",
    "source_candidates": [
        {"extra_red": 7, "normalized_score": 0.80},
        {"extra_red": 8, "normalized_score": 0.900000001},
        {"extra_red": 9, "normalized_score": 0.900000004},
        {"extra_red": 10, "normalized_score": 0.95},
        {"extra_red": 11, "normalized_score": 0.70},
        {"extra_red": 12, "normalized_score": 0.99},
        {"extra_red": 13, "normalized_score": 0.50},
        {"extra_red": 14, "normalized_score": 0.60},
        {"extra_red": 15, "normalized_score": 0.55},
        {"extra_red": 16, "normalized_score": 0.65},
        {"extra_red": 17, "normalized_score": 0.75},
        {"extra_red": 18, "normalized_score": 0.85},
    ],
    "expected_top10_extra_reds": [12, 10, 8, 9, 18, 7, 17, 11, 16, 14],
    "expected_top10_ranking_scores": [0.99, 0.95, 0.9, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6],
    "expected_candidate_list_digest": "11e808c38f8cfa64081e8986345b74b3fc7f29691d47e7ab514113bc79b24ca5",
    "expected_snapshot_digest": "c9a9710816090a22be10e78cfcd061384f70c83fcf71816d163cbb164e04f922",
    "expected_size": RAW_TOP10_SIZE,
    "stochastic": False,
}

SEVEN_RED_RAW_TOP10_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-raw-top10",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-raw-top10.schema.v1",
    normative_definition=SEVEN_RED_RAW_TOP10_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_RAW_TOP10_GOLDEN_SUITE,
)


class SevenRedRawTop10Violation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedRawTop10Violation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "seven_red_raw_top10_digest_invalid",
            f"{field_name} must be a full lowercase sha256 digest",
            field=field_name,
        )
    return value


def _require_canonical_text(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(character in "\r\n\x00" for character in value)
    ):
        _reject(
            "seven_red_scored_candidate_metadata_invalid",
            f"{field_name} must be non-empty canonical single-line text",
            field=field_name,
        )
    return value


def _coerce_score(value: object, *, field_name: str) -> float:
    if (
        not isinstance(value, (Real, Decimal))
        or isinstance(value, bool)
    ):
        _reject(
            "seven_red_scored_candidate_score_invalid",
            f"{field_name} must be a finite real number",
            field=field_name,
        )
    try:
        converted = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise SevenRedRawTop10Violation(
            "seven_red_scored_candidate_score_invalid",
            f"{field_name} must be a finite real number",
            field=field_name,
        ) from exc
    if not isfinite(converted):
        _reject(
            "seven_red_scored_candidate_score_invalid",
            f"{field_name} must be a finite real number",
            field=field_name,
        )
    return converted


def _ranking_score(normalized_score: float) -> float:
    rounded = round(normalized_score, SCORE_ROUND_DIGITS)
    return 0.0 if rounded == 0.0 else rounded


@dataclass(frozen=True)
class ScoredSevenRedCandidate:
    candidate: SevenRedCandidate
    raw_score: float
    normalized_score: float
    source_model: str
    feature_digest: str
    source_run_id: str
    row_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, SevenRedCandidate):
            _reject(
                "seven_red_scored_candidate_type_invalid",
                "candidate must be a canonical SevenRedCandidate",
            )
        for field_name, value in (
            ("raw_score", self.raw_score),
            ("normalized_score", self.normalized_score),
        ):
            if type(value) is not float or not isfinite(value):
                _reject(
                    "seven_red_scored_candidate_stored_score_invalid",
                    f"stored {field_name} must use the canonical finite float representation",
                    field=field_name,
                )
        _require_canonical_text(self.source_model, field_name="source_model")
        _require_digest(self.feature_digest, field_name="feature_digest")
        _require_canonical_text(self.source_run_id, field_name="source_run_id")
        object.__setattr__(
            self,
            "row_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.pre-scored-candidate-row.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        *,
        candidate: SevenRedCandidate,
        raw_score: object,
        normalized_score: object,
        source_model: object,
        feature_digest: object,
        source_run_id: object,
    ) -> ScoredSevenRedCandidate:
        if not isinstance(candidate, SevenRedCandidate):
            _reject(
                "seven_red_scored_candidate_type_invalid",
                "candidate must be a canonical SevenRedCandidate",
            )
        return cls(
            candidate=candidate,
            raw_score=_coerce_score(raw_score, field_name="raw_score"),
            normalized_score=_coerce_score(
                normalized_score,
                field_name="normalized_score",
            ),
            source_model=_require_canonical_text(
                source_model,
                field_name="source_model",
            ),
            feature_digest=_require_digest(
                feature_digest,
                field_name="feature_digest",
            ),
            source_run_id=_require_canonical_text(
                source_run_id,
                field_name="source_run_id",
            ),
        )

    @property
    def ranking_score(self) -> float:
        return _ranking_score(self.normalized_score)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.identity_payload(),
            "raw_score": self.raw_score,
            "normalized_score": self.normalized_score,
            "ranking_score": self.ranking_score,
            "source_model": self.source_model,
            "feature_digest": self.feature_digest,
            "source_run_id": self.source_run_id,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "row_digest": self.row_digest}


@dataclass(frozen=True)
class PreScoredSevenRedCandidateList:
    rows: tuple[ScoredSevenRedCandidate, ...]
    artifact_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.rows, tuple) or not self.rows:
            _reject(
                "seven_red_candidate_list_invalid",
                "candidate list must be a non-empty immutable tuple",
            )
        if any(not isinstance(row, ScoredSevenRedCandidate) for row in self.rows):
            _reject(
                "seven_red_candidate_list_row_type_invalid",
                "candidate list must contain ScoredSevenRedCandidate rows",
            )
        canonical = tuple(sorted(self.rows, key=lambda row: row.candidate.lex_id))
        if self.rows != canonical:
            _reject(
                "seven_red_candidate_list_order_noncanonical",
                "stored candidate-list rows must use candidate lex_id ascending order",
            )
        candidate_ids = tuple(row.candidate.candidate_id for row in self.rows)
        if len(set(candidate_ids)) != len(candidate_ids):
            _reject(
                "seven_red_candidate_list_duplicate",
                "candidate list contains duplicate seven-red candidate identities",
            )
        object.__setattr__(
            self,
            "artifact_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.pre-scored-candidate-list.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        rows: Sequence[ScoredSevenRedCandidate],
    ) -> PreScoredSevenRedCandidateList:
        frozen = tuple(rows)
        if any(not isinstance(row, ScoredSevenRedCandidate) for row in frozen):
            _reject(
                "seven_red_candidate_list_row_type_invalid",
                "candidate list must contain ScoredSevenRedCandidate rows",
            )
        return cls(rows=tuple(sorted(frozen, key=lambda row: row.candidate.lex_id)))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": PRE_SCORED_CANDIDATE_LIST_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity(),
            "seven_red_domain_contract": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
            "row_count": len(self.rows),
            "rows": [row.as_dict() for row in self.rows],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "artifact_digest": self.artifact_digest}


@dataclass(frozen=True)
class RawSevenRedTop10Entry:
    raw_rank: int
    scored_candidate: ScoredSevenRedCandidate

    def __post_init__(self) -> None:
        if (
            not isinstance(self.raw_rank, int)
            or isinstance(self.raw_rank, bool)
            or not 1 <= self.raw_rank <= RAW_TOP10_SIZE
        ):
            _reject(
                "seven_red_raw_top10_rank_invalid",
                "raw rank must be an integer in [1,10]",
                raw_rank=self.raw_rank,
            )
        if not isinstance(self.scored_candidate, ScoredSevenRedCandidate):
            _reject(
                "seven_red_raw_top10_entry_type_invalid",
                "raw Top10 entry must contain a ScoredSevenRedCandidate",
            )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "raw_rank": self.raw_rank,
            "row_digest": self.scored_candidate.row_digest,
            "candidate_id": self.scored_candidate.candidate.candidate_id,
            "sorted_red_numbers": list(
                self.scored_candidate.candidate.sorted_red_numbers
            ),
            "red_mask": self.scored_candidate.candidate.red_mask,
            "lex_id": self.scored_candidate.candidate.lex_id,
            "raw_score": self.scored_candidate.raw_score,
            "normalized_score": self.scored_candidate.normalized_score,
            "ranking_score": self.scored_candidate.ranking_score,
            "source_model": self.scored_candidate.source_model,
            "feature_digest": self.scored_candidate.feature_digest,
            "source_run_id": self.scored_candidate.source_run_id,
        }

    def as_dict(self) -> dict[str, Any]:
        return self.identity_payload()


def _ranked_rows(
    source: PreScoredSevenRedCandidateList,
) -> tuple[ScoredSevenRedCandidate, ...]:
    return tuple(
        sorted(
            source.rows,
            key=lambda row: (-row.ranking_score, row.candidate.lex_id),
        )
    )


@dataclass(frozen=True)
class RawSevenRedTop10Snapshot:
    source: PreScoredSevenRedCandidateList
    entries: tuple[RawSevenRedTop10Entry, ...]
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, PreScoredSevenRedCandidateList):
            _reject(
                "seven_red_raw_top10_source_invalid",
                "Raw Top10 source must be a PreScoredSevenRedCandidateList",
            )
        if len(self.source.rows) < RAW_TOP10_SIZE:
            _reject(
                "seven_red_raw_top10_insufficient_candidates",
                "Raw Top10 requires at least ten unique pre-scored candidates",
                actual=len(self.source.rows),
                required=RAW_TOP10_SIZE,
            )
        if not isinstance(self.entries, tuple) or len(self.entries) != RAW_TOP10_SIZE:
            _reject(
                "seven_red_raw_top10_entries_invalid",
                "Raw Top10 snapshot must contain exactly ten immutable entries",
            )
        expected = tuple(
            RawSevenRedTop10Entry(raw_rank=index, scored_candidate=row)
            for index, row in enumerate(_ranked_rows(self.source)[:RAW_TOP10_SIZE], start=1)
        )
        if self.entries != expected:
            _reject(
                "seven_red_raw_top10_order_mismatch",
                "Raw Top10 entries do not match the frozen score and lex-id ranking contract",
            )
        candidate_ids = tuple(
            entry.scored_candidate.candidate.candidate_id for entry in self.entries
        )
        if len(set(candidate_ids)) != RAW_TOP10_SIZE:
            _reject(
                "seven_red_raw_top10_duplicate_candidate",
                "Raw Top10 output must contain ten distinct candidates",
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.raw-top10-snapshot.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        source: PreScoredSevenRedCandidateList,
    ) -> RawSevenRedTop10Snapshot:
        if not isinstance(source, PreScoredSevenRedCandidateList):
            _reject(
                "seven_red_raw_top10_source_invalid",
                "Raw Top10 source must be a PreScoredSevenRedCandidateList",
            )
        entries = tuple(
            RawSevenRedTop10Entry(raw_rank=index, scored_candidate=row)
            for index, row in enumerate(_ranked_rows(source)[:RAW_TOP10_SIZE], start=1)
        )
        return cls(source=source, entries=entries)

    @property
    def source_candidate_list_digest(self) -> str:
        return self.source.artifact_digest

    @property
    def source_candidate_count(self) -> int:
        return len(self.source.rows)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": RAW_TOP10_SNAPSHOT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity(),
            "seven_red_domain_contract": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
            "ranking_contract": RAW_TOP10_RANKING_CONTRACT,
            "score_round_digits": SCORE_ROUND_DIGITS,
            "deterministic": True,
            "seed_policy": None,
            "source_candidate_list_digest": self.source_candidate_list_digest,
            "source_candidate_count": self.source_candidate_count,
            "candidate_count": len(self.entries),
            "entries": [entry.as_dict() for entry in self.entries],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}
