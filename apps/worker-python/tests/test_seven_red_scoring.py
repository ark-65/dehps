from __future__ import annotations

from dataclasses import replace
import inspect
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest

from dehps.seven_red import (
    SCORE_TICK_SCALE,
    SIX_RED_UNIVERSE,
    PreScoredSevenRedCandidateList,
    RawSevenRedTop10Snapshot,
    SevenRedScorePoolConfig,
    SevenRedScorePoolCompiler,
    SevenRedScorePoolVerifier,
    SevenRedScorePoolViolation,
    SixRedFullScoreVector,
    compile_seven_red_score_pool,
)
from dehps.seven_red.domain import SixRedCombination
from dehps.seven_red.scoring import (
    SEVEN_RED_SCORE_POOL_GOLDEN_SUITE,
    SEVEN_RED_SCORE_POOL_NORMATIVE_DEFINITION,
)
from dehps.scoring_kernel.full_score_artifact import FullScoreGridArtifactVerifierV1


_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64
_COMMIT = "c" * 40


def _vector(
    *,
    values: dict[int, int] | None = None,
    fill: int = 0,
    latest_issue: str = "2026001",
) -> SixRedFullScoreVector:
    ticks = np.full(SIX_RED_UNIVERSE.cardinality, fill, dtype=np.int64)
    for lex_id, value in (values or {}).items():
        ticks[lex_id] = value
    ticks.setflags(write=False)
    return SixRedFullScoreVector(
        score_ticks=ticks,
        source_full_score_artifact_digest=_DIGEST,
        source_full_score_payload_digest=_OTHER_DIGEST,
        source_full_score_scores_digest=_DIGEST,
        source_runtime_envelope_digest=_OTHER_DIGEST,
        source_candidate_package_digest=_DIGEST,
        source_history_snapshot_digest=_OTHER_DIGEST,
        source_history_latest_issue=latest_issue,
        source_window_artifact_digest=_DIGEST,
        source_window_spec_digest=_OTHER_DIGEST,
        source_weights_digest=_DIGEST,
        source_config_index=0,
        source_config_count=1,
        source_code_commit=_COMMIT,
    )


def _six_lex(numbers: tuple[int, ...]) -> int:
    return SixRedCombination(numbers).lex_id


def test_contract_freezes_research_only_top_m_exact_mean_boundary() -> None:
    definition = SEVEN_RED_SCORE_POOL_NORMATIVE_DEFINITION

    assert definition["research_only"] is True
    assert definition["six_red_score_vector"]["cardinality"] == 1_107_568
    assert definition["generation"]["supersets_per_seed"] == 27
    assert definition["scoring"]["aggregate"] == (
        "exact_arithmetic_mean_of_seven_int64_score_ticks"
    )
    assert definition["scoring"]["float_ranking"] == "forbidden"
    assert "no_production_topk_integration" in definition["non_goals"]


def test_configuration_has_no_defaults_and_rejects_invalid_M_or_P() -> None:
    signature = inspect.signature(SevenRedScorePoolConfig)
    assert signature.parameters["seed_top_n"].default is inspect.Parameter.empty
    assert signature.parameters["pool_top_n"].default is inspect.Parameter.empty

    for kwargs, code in (
        ({"seed_top_n": 0, "pool_top_n": 10}, "seven_red_score_pool_seed_top_n_invalid"),
        ({"seed_top_n": True, "pool_top_n": 10}, "seven_red_score_pool_seed_top_n_invalid"),
        ({"seed_top_n": 1, "pool_top_n": 9}, "seven_red_score_pool_pool_top_n_invalid"),
        ({"seed_top_n": 1, "pool_top_n": False}, "seven_red_score_pool_pool_top_n_invalid"),
    ):
        with pytest.raises(SevenRedScorePoolViolation) as error:
            SevenRedScorePoolConfig(**kwargs)
        assert error.value.code == code


def test_full_score_vector_requires_exact_full_read_only_int64_buffer() -> None:
    writable = np.zeros(SIX_RED_UNIVERSE.cardinality, dtype=np.int64)
    with pytest.raises(SevenRedScorePoolViolation) as error:
        replace(_vector(), score_ticks=writable)
    assert error.value.code == "six_red_score_vector_writable"

    wrong_shape = np.zeros(10, dtype=np.int64)
    wrong_shape.setflags(write=False)
    with pytest.raises(SevenRedScorePoolViolation) as error:
        replace(_vector(), score_ticks=wrong_shape)
    assert error.value.code == "six_red_score_vector_buffer_invalid"


def test_full_score_adapter_binds_one_verified_round8_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        FullScoreGridArtifactVerifierV1,
        "verify",
        lambda self, artifact, **kwargs: None,
    )
    scores = np.zeros((SIX_RED_UNIVERSE.cardinality, 2), dtype=np.float64)
    scores[0, 1] = 0.12345678
    scores.setflags(write=False)
    envelope = SimpleNamespace(
        envelope_digest=_DIGEST,
        candidate_package_digest=_OTHER_DIGEST,
        history_snapshot_digest=_DIGEST,
        history_latest_issue="2026001",
        window_artifact_digest=_OTHER_DIGEST,
        window_spec_digest=_DIGEST,
        code_commit=_COMMIT,
    )
    artifact = SimpleNamespace(
        header=SimpleNamespace(
            candidate_count=SIX_RED_UNIVERSE.cardinality,
            config_count=2,
            scores_digest=_DIGEST,
            weights_digest=_OTHER_DIGEST,
        ),
        scores=scores,
        runtime_envelope=envelope,
        artifact_digest=_DIGEST,
        payload_digest=_OTHER_DIGEST,
    )

    vector = SixRedFullScoreVector.from_full_score_grid(
        artifact,
        verified_runtime=object(),
        weights=object(),
        config_index=1,
    )

    assert vector.score_ticks[0] == 12_345_678
    assert vector.source_config_index == 1
    assert vector.source_config_count == 2
    assert vector.source_candidate_package_digest == _OTHER_DIGEST


def test_full_score_adapter_rejects_non_round8_source_even_after_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        FullScoreGridArtifactVerifierV1,
        "verify",
        lambda self, artifact, **kwargs: None,
    )
    scores = np.zeros((SIX_RED_UNIVERSE.cardinality, 1), dtype=np.float64)
    scores[0, 0] = 0.123456789
    scores.setflags(write=False)
    artifact = SimpleNamespace(
        header=SimpleNamespace(
            candidate_count=SIX_RED_UNIVERSE.cardinality,
            config_count=1,
            scores_digest=_DIGEST,
            weights_digest=_OTHER_DIGEST,
        ),
        scores=scores,
        runtime_envelope=SimpleNamespace(
            envelope_digest=_DIGEST,
            candidate_package_digest=_OTHER_DIGEST,
            history_snapshot_digest=_DIGEST,
            history_latest_issue="2026001",
            window_artifact_digest=_OTHER_DIGEST,
            window_spec_digest=_DIGEST,
            code_commit=_COMMIT,
        ),
        artifact_digest=_DIGEST,
        payload_digest=_OTHER_DIGEST,
    )

    with pytest.raises(SevenRedScorePoolViolation) as error:
        SixRedFullScoreVector.from_full_score_grid(
            artifact,
            verified_runtime=object(),
            weights=object(),
            config_index=0,
        )
    assert error.value.code == "six_red_score_vector_round8_mismatch"


def test_full_score_adapter_rejects_tick_overflow_after_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        FullScoreGridArtifactVerifierV1,
        "verify",
        lambda self, artifact, **kwargs: None,
    )
    scores = np.zeros((SIX_RED_UNIVERSE.cardinality, 1), dtype=np.float64)
    scores[0, 0] = np.finfo(np.float64).max
    scores.setflags(write=False)
    artifact = SimpleNamespace(
        header=SimpleNamespace(
            candidate_count=SIX_RED_UNIVERSE.cardinality,
            config_count=1,
            scores_digest=_DIGEST,
            weights_digest=_OTHER_DIGEST,
        ),
        scores=scores,
        runtime_envelope=SimpleNamespace(
            envelope_digest=_DIGEST,
            candidate_package_digest=_OTHER_DIGEST,
            history_snapshot_digest=_DIGEST,
            history_latest_issue="2026001",
            window_artifact_digest=_OTHER_DIGEST,
            window_spec_digest=_DIGEST,
            code_commit=_COMMIT,
        ),
        artifact_digest=_DIGEST,
        payload_digest=_OTHER_DIGEST,
    )

    with pytest.raises(SevenRedScorePoolViolation) as error:
        SixRedFullScoreVector.from_full_score_grid(
            artifact,
            verified_runtime=object(),
            weights=object(),
            config_index=0,
        )
    assert error.value.code == "six_red_score_vector_tick_overflow"


def test_source_provenance_fields_are_part_of_vector_identity() -> None:
    base = replace(_vector(), source_config_count=2)
    mutations = (
        {"source_full_score_artifact_digest": "d" * 64},
        {"source_runtime_envelope_digest": "d" * 64},
        {"source_history_snapshot_digest": "d" * 64},
        {"source_history_latest_issue": "2026000"},
        {"source_window_artifact_digest": "d" * 64},
        {"source_window_spec_digest": "d" * 64},
        {"source_weights_digest": "d" * 64},
        {"source_config_index": 1},
    )

    for mutation in mutations:
        assert replace(base, **mutation).vector_digest != base.vector_digest


def test_one_seed_generates_27_unique_supersets_and_existing_pool_abi() -> None:
    snapshot = compile_seven_red_score_pool(
        source_vector=_vector(),
        configuration=SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10),
        target_issue="2026002",
    )

    assert snapshot.seeds[0].six_red.lex_id == 0
    assert snapshot.generated_occurrence_count == 27
    assert snapshot.deduplicated_candidate_count == 27
    assert len(snapshot.ranked_pool) == 10
    assert isinstance(snapshot.candidate_pool, PreScoredSevenRedCandidateList)
    assert all(row.source_seed_ranks == (1,) for row in snapshot.ranked_pool)
    assert [row.scored_candidate.candidate.lex_id for row in snapshot.ranked_pool] == sorted(
        row.scored_candidate.candidate.lex_id for row in snapshot.ranked_pool
    )

    raw = RawSevenRedTop10Snapshot.build(snapshot.candidate_pool)
    assert [entry.scored_candidate.candidate.lex_id for entry in raw.entries] == [
        row.scored_candidate.candidate.lex_id for row in snapshot.ranked_pool
    ]


def test_two_overlapping_seeds_deduplicate_shared_seven_red_candidate() -> None:
    snapshot = compile_seven_red_score_pool(
        source_vector=_vector(),
        configuration=SevenRedScorePoolConfig(seed_top_n=2, pool_top_n=10),
        target_issue="2026002",
    )

    assert [seed.six_red.lex_id for seed in snapshot.seeds] == [0, 1]
    assert snapshot.generated_occurrence_count == 54
    assert snapshot.deduplicated_candidate_count == 53
    shared = next(
        row
        for row in snapshot.ranked_pool
        if row.scored_candidate.candidate.sorted_red_numbers == (1, 2, 3, 4, 5, 6, 7)
    )
    assert shared.source_seed_ranks == (1, 2)


def test_fixed_point_constituent_mean_controls_ranking_without_float_order() -> None:
    target = (1, 2, 3, 4, 5, 6, 7)
    constituent_ids = tuple(_six_lex(numbers) for numbers in combinations(target, 6))
    source = _vector(values={constituent_ids[0]: 10})

    snapshot = compile_seven_red_score_pool(
        source_vector=source,
        configuration=SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10),
        target_issue="2026002",
    )
    first = snapshot.ranked_pool[0]

    assert first.constituent_tick_sum == 10
    assert first.ranking_tick == 1
    assert first.scored_candidate.raw_score == 10 / (7 * SCORE_TICK_SCALE)
    assert first.scored_candidate.ranking_score == 1 / SCORE_TICK_SCALE
    assert first.scored_candidate.candidate.sorted_red_numbers == target


def test_negative_fixed_point_mean_uses_exact_symmetric_nearest_tick() -> None:
    target = (1, 2, 3, 4, 5, 6, 7)
    constituent_ids = tuple(_six_lex(numbers) for numbers in combinations(target, 6))
    values = {lex_id: -2 for lex_id in constituent_ids}
    values[constituent_ids[0]] = -1
    source = _vector(values=values, fill=-100)

    snapshot = compile_seven_red_score_pool(
        source_vector=source,
        configuration=SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10),
        target_issue="2026002",
    )
    first = snapshot.ranked_pool[0]

    assert first.constituent_tick_sum == -13
    assert first.ranking_tick == -2
    assert first.scored_candidate.ranking_score == -2 / SCORE_TICK_SCALE


def test_seed_and_pool_ties_break_on_lex_id() -> None:
    source = _vector(values={5: 20, 3: 20, 8: 19}, fill=-100)
    snapshot = compile_seven_red_score_pool(
        source_vector=source,
        configuration=SevenRedScorePoolConfig(seed_top_n=2, pool_top_n=10),
        target_issue="2026002",
    )

    assert [seed.six_red.lex_id for seed in snapshot.seeds] == [3, 5]
    ranked_keys = [
        (-row.ranking_tick, row.scored_candidate.candidate.lex_id)
        for row in snapshot.ranked_pool
    ]
    assert ranked_keys == sorted(ranked_keys)


def test_vectorized_top_m_matches_transparent_python_reference() -> None:
    minimum = int(np.iinfo(np.int64).min)
    maximum = int(np.iinfo(np.int64).max)
    ticks = np.array(
        [minimum, -5, 7, 7, -1, 7, 3, minimum + 1, maximum, -5, 8, 0],
        dtype=np.int64,
    )
    expected = np.array(
        sorted(
            range(len(ticks)),
            key=lambda lex_id: (-int(ticks[lex_id]), lex_id),
        )[: len(ticks)],
        dtype=np.int64,
    )

    actual = SevenRedScorePoolCompiler._top_seed_ids(ticks, len(ticks))

    assert np.array_equal(actual, expected)


def test_target_issue_must_be_strictly_after_bound_history() -> None:
    source = _vector(latest_issue="2026002")
    configuration = SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10)

    for target_issue in ("2026002", "2026001"):
        with pytest.raises(SevenRedScorePoolViolation) as error:
            compile_seven_red_score_pool(
                source_vector=source,
                configuration=configuration,
                target_issue=target_issue,
            )
        assert error.value.code == "seven_red_score_pool_chronology_invalid"


def test_replay_is_deterministic_and_source_tick_mutation_changes_identity() -> None:
    configuration = SevenRedScorePoolConfig(seed_top_n=2, pool_top_n=10)
    first = compile_seven_red_score_pool(
        source_vector=_vector(),
        configuration=configuration,
        target_issue="2026002",
    )
    replay = compile_seven_red_score_pool(
        source_vector=_vector(),
        configuration=configuration,
        target_issue="2026002",
    )
    changed = compile_seven_red_score_pool(
        source_vector=_vector(values={0: 1}),
        configuration=configuration,
        target_issue="2026002",
    )

    assert first.snapshot_digest == replay.snapshot_digest
    assert first.candidate_pool.artifact_digest == replay.candidate_pool.artifact_digest
    golden = SEVEN_RED_SCORE_POOL_GOLDEN_SUITE["synthetic_replay"]
    assert first.source_vector.vector_digest == golden["expected_vector_digest"]
    assert configuration.configuration_digest == golden["expected_configuration_digest"]
    assert first.candidate_pool.artifact_digest == golden["expected_candidate_pool_digest"]
    assert first.snapshot_digest == golden["expected_snapshot_digest"]
    assert changed.source_vector.vector_digest != first.source_vector.vector_digest
    assert changed.snapshot_digest != first.snapshot_digest
    SevenRedScorePoolVerifier().verify(first)

    forged = replace(first, source_vector=_vector(values={0: 1}))
    with pytest.raises(SevenRedScorePoolViolation) as error:
        SevenRedScorePoolVerifier().verify(forged)
    assert error.value.code == "seven_red_score_pool_snapshot_replay_mismatch"


def test_insufficient_deduplicated_pool_fails_closed() -> None:
    with pytest.raises(SevenRedScorePoolViolation) as error:
        compile_seven_red_score_pool(
            source_vector=_vector(),
            configuration=SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=28),
            target_issue="2026002",
        )
    assert error.value.code == "seven_red_score_pool_insufficient_candidates"
