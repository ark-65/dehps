from __future__ import annotations

import json
import math
from dataclasses import replace
from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

from dehps.input_contracts.candidate_abi import (
    CANDIDATE_ABI_LAYOUT_DIGEST,
    CANDIDATE_ABI_VERSION,
    CANDIDATE_CONTRACT_V1,
    CANDIDATE_GOLDEN_SUITE,
    CandidateArrayCompiler,
    CandidateABIVerifier,
    CandidateCompiler,
    CandidateContractViolation,
    CandidateManifest,
    CandidateUniverseManifest,
    canonical_candidate_record_bytes,
    candidate_mask,
    candidate_numbers_from_mask,
    candidate_rank,
    candidate_record_digest,
    candidate_unrank,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "dehps"
    / "input_contracts"
    / "fixtures"
    / "candidate_abi_v1_golden.json"
)


def ssq_universe() -> CandidateUniverseManifest:
    return CandidateUniverseManifest(domain_size=33, pick_count=6)


def golden_package():
    universe = ssq_universe()
    case = CANDIDATE_GOLDEN_SUITE["package_case"]
    manifest = CandidateManifest.from_candidates(
        universe=universe,
        candidates=case["candidates"],
    )
    return CandidateCompiler().compile(manifest)


@pytest.mark.parametrize("domain_size", range(1, 11))
def test_rank_and_unrank_are_a_bijection_for_small_universes(domain_size: int) -> None:
    for pick_count in range(1, domain_size + 1):
        universe = CandidateUniverseManifest(domain_size=domain_size, pick_count=pick_count)
        expected = list(combinations(range(1, domain_size + 1), pick_count))
        assert len(expected) == universe.cardinality
        for lex_id, numbers in enumerate(expected):
            assert candidate_rank(numbers, universe=universe) == lex_id
            assert candidate_unrank(lex_id, universe=universe) == numbers
            assert candidate_rank(candidate_unrank(lex_id, universe=universe), universe=universe) == lex_id


def test_rank_and_unrank_cover_ssq_boundaries_and_golden_rows() -> None:
    universe = ssq_universe()
    assert universe.cardinality == math.comb(33, 6) == 1_107_568
    for case in CANDIDATE_GOLDEN_SUITE["records"]:
        numbers = tuple(case["numbers"])
        assert candidate_rank(numbers, universe=universe) == case["lex_id"]
        assert candidate_unrank(case["lex_id"], universe=universe) == numbers


def test_v1_width_boundaries_are_explicit_and_fail_closed() -> None:
    largest_number = CandidateUniverseManifest(domain_size=64, pick_count=1)
    assert candidate_mask((64,), universe=largest_number) == 1 << 63
    assert candidate_numbers_from_mask(1 << 63, universe=largest_number) == (64,)

    accepted_uint32_space = CandidateUniverseManifest(domain_size=34, pick_count=17)
    assert accepted_uint32_space.cardinality <= 1 << 32
    with pytest.raises(CandidateContractViolation) as overflow:
        CandidateUniverseManifest(domain_size=35, pick_count=17)
    assert overflow.value.code == "candidate_lex_id_overflow"


def test_lex_id_and_mask_bounds_are_rejected_without_wrapping() -> None:
    universe = CandidateUniverseManifest(domain_size=10, pick_count=3)
    for lex_id in (-1, universe.cardinality):
        with pytest.raises(CandidateContractViolation) as invalid_id:
            candidate_unrank(lex_id, universe=universe)
        assert invalid_id.value.code == "candidate_lex_id_out_of_range"

    with pytest.raises(CandidateContractViolation) as high_bit:
        candidate_numbers_from_mask(1 << 10, universe=universe)
    assert high_bit.value.code == "candidate_mask_high_bits_set"


def test_mask_numbers_mask_and_record_serialization_are_stable() -> None:
    universe = ssq_universe()
    for case in CANDIDATE_GOLDEN_SUITE["records"]:
        numbers = tuple(case["numbers"])
        mask = candidate_mask(numbers, universe=universe)
        assert mask == case["mask"]
        assert candidate_numbers_from_mask(mask, universe=universe) == numbers
        assert candidate_record_digest(numbers, universe=universe) == case["record_digest"]
        assert len(canonical_candidate_record_bytes(numbers, universe=universe)) == 20


def test_language_neutral_fixture_matches_executable_golden_suite() -> None:
    assert json.loads(FIXTURE_PATH.read_text(encoding="utf-8")) == CANDIDATE_GOLDEN_SUITE


def test_compiler_emits_the_frozen_soa_layout_and_verifier_accepts_it() -> None:
    package = golden_package()
    case = CANDIDATE_GOLDEN_SUITE["package_case"]

    CandidateABIVerifier().verify(package)
    assert package.header.abi_version == CANDIDATE_ABI_VERSION
    assert package.header.candidate_contract == CANDIDATE_CONTRACT_V1
    assert package.header.layout_digest == CANDIDATE_ABI_LAYOUT_DIGEST == case["expected_layout_digest"]
    assert package.header.candidate_digest == case["expected_candidate_digest"]
    assert package.header.payload_digest == case["expected_payload_digest"]
    assert package.package_digest == case["expected_package_digest"]
    assert package.numbers.dtype == np.dtype("u1")
    assert package.numbers.shape == (3, 6)
    assert package.numbers.strides == (6, 1)
    assert package.mask.dtype.str == np.dtype("<u8").str
    assert package.mask.shape == (3,)
    assert package.mask.strides == (8,)
    assert package.lex_id.dtype.str == np.dtype("<u4").str
    assert package.lex_id.shape == (3,)
    assert package.lex_id.strides == (4,)


def test_verifier_reuses_only_a_payload_bound_semantic_receipt() -> None:
    CandidateABIVerifier.clear_cache()
    package = golden_package()
    equivalent_package = golden_package()

    first = CandidateABIVerifier().verify(package)
    second = CandidateABIVerifier().verify(equivalent_package)

    # The compiler performs the first full proof; all later verifier instances may
    # reuse it only after recomputing and matching every buffer digest.
    assert first.cache_hit is True
    assert second.cache_hit is True
    assert first.verification_digest == second.verification_digest
    assert package is not equivalent_package
    assert first.package_digest == package.package_digest
    assert first.row_count == 3
    assert first.payload_bytes == (
        package.numbers.nbytes + package.mask.nbytes + package.lex_id.nbytes
    )


def test_cached_verification_rejects_payload_drift_instead_of_trusting_object_identity() -> None:
    CandidateABIVerifier.clear_cache()
    package = golden_package()
    assert CandidateABIVerifier().verify(package).cache_hit is True

    original = int(package.numbers[0, -1])
    package.numbers[0, -1] = original + 1
    try:
        with pytest.raises(CandidateContractViolation) as error:
            CandidateABIVerifier().verify(package)
        assert error.value.code == "candidate_buffer_metadata_mismatch"
    finally:
        package.numbers[0, -1] = original

    assert CandidateABIVerifier().verify(package).cache_hit is True


def test_recompiling_the_same_manifests_is_byte_reproducible() -> None:
    first = golden_package()
    second = golden_package()

    assert first.package_digest == second.package_digest
    assert first.header == second.header
    assert first.numbers.tobytes(order="C") == second.numbers.tobytes(order="C")
    assert first.mask.tobytes(order="C") == second.mask.tobytes(order="C")
    assert first.lex_id.tobytes(order="C") == second.lex_id.tobytes(order="C")


def test_compiler_and_verifier_support_a_non_ssq_domain_without_domain_code() -> None:
    universe = CandidateUniverseManifest(domain_size=10, pick_count=3)
    manifest = CandidateManifest.from_candidates(
        universe=universe,
        candidates=[(1, 2, 3), (2, 5, 10), (8, 9, 10)],
    )

    package = CandidateCompiler().compile(manifest)

    CandidateABIVerifier().verify(package)
    assert package.header.domain_size == 10
    assert package.header.pick_count == 3
    assert package.numbers.shape == (3, 3)
    assert package.lex_id.tolist() == [0, 53, 119]


def test_array_compiler_uses_existing_buffers_without_reordering_or_copying() -> None:
    universe = CandidateUniverseManifest(domain_size=10, pick_count=3)
    numbers = np.ascontiguousarray([[1, 2, 3], [2, 5, 10], [8, 9, 10]], dtype=np.uint8)
    mask = np.ascontiguousarray(
        [candidate_mask(tuple(int(value) for value in row), universe=universe) for row in numbers],
        dtype=np.dtype("<u8"),
    )
    lex_id = np.ascontiguousarray([0, 53, 119], dtype=np.dtype("<u4"))

    package = CandidateArrayCompiler().compile(
        universe=universe,
        numbers=numbers,
        mask=mask,
        lex_id=lex_id,
    )

    CandidateABIVerifier().verify(package)
    assert np.shares_memory(package.numbers, numbers)
    assert np.shares_memory(package.mask, mask)
    assert np.shares_memory(package.lex_id, lex_id)
    assert package.lex_id.tolist() == [0, 53, 119]


def test_empty_candidate_set_has_a_unique_valid_identity() -> None:
    universe = CandidateUniverseManifest(domain_size=10, pick_count=3)
    package = CandidateCompiler().compile(
        CandidateManifest.from_candidates(universe=universe, candidates=[]),
    )

    CandidateABIVerifier().verify(package)
    assert package.header.row_count == 0
    assert package.numbers.shape == (0, 3)
    assert package.mask.shape == (0,)
    assert package.lex_id.shape == (0,)


@pytest.mark.parametrize(
    ("candidates", "code"),
    [
        ([(2, 1, 3)], "noncanonical_candidate_numbers"),
        ([(1, 1, 3)], "noncanonical_candidate_numbers"),
        ([(0, 2, 3)], "candidate_number_out_of_range"),
        ([(1, 2)], "invalid_candidate_shape"),
        ([(2, 5, 10), (1, 2, 3)], "candidate_manifest_order_violation"),
        ([(1, 2, 3), (1, 2, 3)], "candidate_manifest_order_violation"),
    ],
)
def test_compiler_rejects_noncanonical_manifests_without_repair(candidates, code: str) -> None:
    universe = CandidateUniverseManifest(domain_size=10, pick_count=3)
    with pytest.raises(CandidateContractViolation) as error:
        CandidateManifest.from_candidates(universe=universe, candidates=candidates)
    assert error.value.code == code


def test_verifier_rejects_abi_version_layout_and_contract_mismatch() -> None:
    verifier = CandidateABIVerifier()
    package = golden_package()

    with pytest.raises(CandidateContractViolation) as version:
        verifier.verify(replace(package, header=replace(package.header, abi_version="candidate_abi.v2")))
    assert version.value.code == "unsupported_candidate_abi_version"

    with pytest.raises(CandidateContractViolation) as layout:
        verifier.verify(replace(package, header=replace(package.header, layout_digest="0" * 64)))
    assert layout.value.code == "candidate_layout_digest_mismatch"

    incompatible_contract = replace(CANDIDATE_CONTRACT_V1, normative_digest="0" * 64)
    with pytest.raises(CandidateContractViolation) as contract:
        verifier.verify(
            replace(package, header=replace(package.header, candidate_contract=incompatible_contract)),
        )
    assert contract.value.code == "candidate_contract_mismatch"


def test_verifier_rejects_dtype_shape_alignment_and_payload_tampering() -> None:
    verifier = CandidateABIVerifier()
    package = golden_package()

    with pytest.raises(CandidateContractViolation) as dtype_error:
        verifier.verify(replace(package, mask=package.mask.astype(">u8")))
    assert dtype_error.value.code == "candidate_buffer_dtype_mismatch"

    with pytest.raises(CandidateContractViolation) as shape_error:
        verifier.verify(replace(package, lex_id=package.lex_id.reshape(3, 1)))
    assert shape_error.value.code == "candidate_buffer_shape_mismatch"

    raw = np.empty(package.mask.nbytes + 1, dtype=np.uint8)
    misaligned_mask = raw[1:].view(np.dtype("<u8"))
    misaligned_mask[:] = package.mask
    assert misaligned_mask.flags.c_contiguous
    assert misaligned_mask.ctypes.data % 8 != 0
    with pytest.raises(CandidateContractViolation) as alignment_error:
        verifier.verify(replace(package, mask=misaligned_mask))
    assert alignment_error.value.code == "candidate_buffer_alignment_mismatch"

    changed_numbers = package.numbers.copy()
    changed_numbers[0, -1] = 7
    with pytest.raises(CandidateContractViolation) as tamper_error:
        verifier.verify(replace(package, numbers=changed_numbers))
    assert tamper_error.value.code == "candidate_buffer_metadata_mismatch"


def test_runtime_envelope_fragment_carries_candidate_contract_abi_and_identity() -> None:
    package = golden_package()
    envelope = package.runtime_envelope.as_dict()

    assert envelope["candidate_contract"]["contract_key"] == "candidate.v1.0.0"
    assert envelope["candidate_abi"] == CANDIDATE_ABI_VERSION
    assert envelope["candidate_digest"] == package.header.candidate_digest
    assert envelope["layout_digest"] == package.header.layout_digest
    assert envelope["package_digest"] == package.package_digest
