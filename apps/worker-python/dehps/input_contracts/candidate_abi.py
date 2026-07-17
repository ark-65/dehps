from __future__ import annotations

import math
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import numpy as np

from dehps.contracts import ContractRef, canonical_digest


CANDIDATE_ABI_VERSION = "candidate_abi.v1"
CANDIDATE_ABI_LAYOUT_VERSION = "dehps.candidate-abi.layout.v1"

_UINT32_CAPACITY = 1 << 32
_DIGEST_LENGTH = 64

CANDIDATE_NORMATIVE_DEFINITION = {
    "contract": "candidate.v1.0.0",
    "scope": "finite_fixed_cardinality_combination_universe",
    "universe_manifest": {
        "domain_size": "integer_in_[1,64]",
        "pick_count": "integer_in_[1,domain_size]",
        "cardinality": "binomial(domain_size,pick_count)_must_fit_uint32_lex_id_space",
    },
    "candidate": {
        "numbers": "pick_count_unique_integers_strictly_increasing",
        "range": "closed_interval_[1,domain_size]",
        "canonical_order": "ascending_numeric_within_row",
    },
    "enumeration": {
        "order": "lexicographic_ascending_over_canonical_number_tuples",
        "lex_id_origin": 0,
        "lex_id_scope": "full_unfiltered_universe",
        "bijection": "rank(unrank(lex_id))_equals_lex_id",
    },
    "candidate_set": {
        "row_order": "strictly_increasing_lex_id",
        "duplicates": "forbidden",
        "empty_set": "allowed",
        "filter_semantics": "manifest_or_artifact_metadata_not_candidate_contract",
    },
    "mask": {
        "width": 64,
        "number_to_bit": "number_minus_one",
        "unused_high_bits": "zero",
    },
    "canonical_record_serialization": {
        "fields": ["domain_size:u8", "pick_count:u8", "numbers:u8[pick_count]", "mask:<u8", "lex_id:<u4"],
        "byte_order": "little",
        "digest": "sha256_domain_separated_dehps.candidate-record.v1",
    },
    "failure_policy": "reject_ambiguous_noncanonical_or_incompatible_input_without_repair",
}

CANDIDATE_GOLDEN_SUITE = {
    "suite": "candidate_abi_golden.v1",
    "universe": {"domain_size": 33, "pick_count": 6, "cardinality": 1_107_568},
    "records": [
        {
            "numbers": [1, 2, 3, 4, 5, 6],
            "lex_id": 0,
            "mask": 63,
            "record_digest": "33b549d9f7addd8345fa2111d9eb641a22855e79c47ccc237548251dbbccd613",
        },
        {
            "numbers": [1, 2, 3, 4, 5, 33],
            "lex_id": 27,
            "mask": 4_294_967_327,
            "record_digest": "aa1d667b651e3cb14c2b1c110e96c5e7e8964064ec481cb0f45985d7429bea5c",
        },
        {
            "numbers": [3, 8, 12, 18, 25, 33],
            "lex_id": 454_194,
            "mask": 4_311_877_764,
            "record_digest": "f28b99157308218c1bdd4355eb9a5dc1dc56b57bd17e46bfd4f13b1d626cd6e3",
        },
        {
            "numbers": [28, 29, 30, 31, 32, 33],
            "lex_id": 1_107_567,
            "mask": 8_455_716_864,
            "record_digest": "ad2f6309920b5c247441754d91ee1f4179576946a4ef2f912bd9d53b21662903",
        },
    ],
    "package_case": {
        "candidates": [
            [1, 2, 3, 4, 5, 6],
            [3, 8, 12, 18, 25, 33],
            [28, 29, 30, 31, 32, 33],
        ],
        "expected_candidate_digest": "a107cdf57651d385e8a9081b68a807647709c9c05717ba8fd9ca506100e9e102",
        "expected_layout_digest": "aaf29afc661c4814d1234407cbfb3ca952c4eae4fc6cd293fc455c70c7bbcd66",
        "expected_payload_digest": "b4610df5fb470c3949e910cb9c1282a485f8acae60779f3c5b97a62675c968a6",
        "expected_package_digest": "a0cd69fcf681456f66ff5d6f3056fd473c0e74d15bbe69c5e4ae1665bb6f885b",
    },
}

CANDIDATE_CONTRACT_V1 = ContractRef.from_definition(
    family="candidate",
    semantic_version="1.0.0",
    schema_version="dehps.candidate.schema.v1",
    normative_definition=CANDIDATE_NORMATIVE_DEFINITION,
    golden_suite=CANDIDATE_GOLDEN_SUITE,
)

CANDIDATE_ABI_LAYOUT_DEFINITION = {
    "abi_version": CANDIDATE_ABI_VERSION,
    "organization": "struct_of_arrays",
    "buffer_order": ["numbers", "mask", "lex_id"],
    "buffers": {
        "numbers": {
            "dtype": "uint8",
            "endianness": "not_applicable",
            "shape": ["N", "pick_count"],
            "order": "C",
            "alignment": 1,
        },
        "mask": {
            "dtype": "uint64",
            "endianness": "little",
            "shape": ["N"],
            "order": "C",
            "alignment": 8,
        },
        "lex_id": {
            "dtype": "uint32",
            "endianness": "little",
            "shape": ["N"],
            "order": "C",
            "alignment": 4,
        },
    },
    "payload_framing": "independent_named_buffers_with_domain_separated_sha256",
    "pointers_and_padding_in_identity": False,
}
CANDIDATE_ABI_LAYOUT_DIGEST = canonical_digest(
    CANDIDATE_ABI_LAYOUT_DEFINITION,
    domain="dehps.candidate-abi-layout.v1",
)


class CandidateContractViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_digest(name: str, value: str) -> None:
    if len(value) != _DIGEST_LENGTH or any(char not in "0123456789abcdef" for char in value):
        raise CandidateContractViolation(
            "invalid_candidate_digest",
            f"{name} must be a lowercase sha256 digest",
            field=name,
        )


def _binary_digest(payload: bytes, *, domain: str) -> str:
    return sha256(domain.encode("ascii") + b"\x00" + payload).hexdigest()


@dataclass(frozen=True)
class CandidateUniverseManifest:
    domain_size: int
    pick_count: int
    contract: ContractRef = CANDIDATE_CONTRACT_V1

    def __post_init__(self) -> None:
        if not self.contract.normatively_equals(CANDIDATE_CONTRACT_V1):
            raise CandidateContractViolation(
                "candidate_contract_mismatch",
                "universe manifest must use candidate.v1.0.0",
            )
        if not _is_int(self.domain_size) or not 1 <= self.domain_size <= 64:
            raise CandidateContractViolation(
                "invalid_candidate_domain_size",
                "domain_size must be an integer in [1,64]",
            )
        if not _is_int(self.pick_count) or not 1 <= self.pick_count <= self.domain_size:
            raise CandidateContractViolation(
                "invalid_candidate_pick_count",
                "pick_count must be an integer in [1,domain_size]",
            )
        if self.cardinality > _UINT32_CAPACITY:
            raise CandidateContractViolation(
                "candidate_lex_id_overflow",
                "universe cardinality does not fit the uint32 lex_id space",
                cardinality=self.cardinality,
            )

    @property
    def cardinality(self) -> int:
        return math.comb(self.domain_size, self.pick_count)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "contract": self.contract.normative_identity(),
            "domain_size": self.domain_size,
            "pick_count": self.pick_count,
            "cardinality": self.cardinality,
        }

    @property
    def manifest_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.candidate-universe-manifest.v1")


def validate_candidate_numbers(
    numbers: Sequence[object],
    *,
    universe: CandidateUniverseManifest,
) -> tuple[int, ...]:
    if isinstance(numbers, (str, bytes, bytearray)):
        raise CandidateContractViolation(
            "invalid_candidate_shape",
            "candidate numbers must be an ordered sequence",
        )
    canonical = tuple(numbers)
    if len(canonical) != universe.pick_count:
        raise CandidateContractViolation(
            "invalid_candidate_shape",
            "candidate numbers must contain pick_count values",
            expected=universe.pick_count,
            actual=len(canonical),
        )
    if any(not _is_int(value) for value in canonical):
        raise CandidateContractViolation(
            "invalid_candidate_number_type",
            "candidate numbers must contain integers",
        )
    if any(value < 1 or value > universe.domain_size for value in canonical):
        raise CandidateContractViolation(
            "candidate_number_out_of_range",
            "candidate numbers must be in [1,domain_size]",
        )
    if any(left >= right for left, right in zip(canonical, canonical[1:])):
        raise CandidateContractViolation(
            "noncanonical_candidate_numbers",
            "candidate numbers must be unique and strictly increasing",
        )
    return canonical  # type: ignore[return-value]


def candidate_rank(numbers: Sequence[object], *, universe: CandidateUniverseManifest) -> int:
    canonical = validate_candidate_numbers(numbers, universe=universe)
    lex_id = 0
    previous = 0
    for index, number in enumerate(canonical):
        remaining = universe.pick_count - index - 1
        for skipped in range(previous + 1, number):
            lex_id += math.comb(universe.domain_size - skipped, remaining)
        previous = number
    return lex_id


def candidate_unrank(lex_id: int, *, universe: CandidateUniverseManifest) -> tuple[int, ...]:
    if not _is_int(lex_id) or not 0 <= lex_id < universe.cardinality:
        raise CandidateContractViolation(
            "candidate_lex_id_out_of_range",
            "lex_id must identify one row in the full universe",
            lex_id=lex_id,
            cardinality=universe.cardinality,
        )
    residual = lex_id
    result: list[int] = []
    previous = 0
    for index in range(universe.pick_count):
        remaining = universe.pick_count - index - 1
        maximum = universe.domain_size - remaining
        for number in range(previous + 1, maximum + 1):
            block_size = math.comb(universe.domain_size - number, remaining)
            if residual < block_size:
                result.append(number)
                previous = number
                break
            residual -= block_size
        else:  # pragma: no cover - guarded by the cardinality check
            raise AssertionError("unreachable candidate unrank state")
    return tuple(result)


def candidate_mask(numbers: Sequence[object], *, universe: CandidateUniverseManifest) -> int:
    canonical = validate_candidate_numbers(numbers, universe=universe)
    mask = 0
    for number in canonical:
        mask |= 1 << (number - 1)
    return mask


def candidate_numbers_from_mask(mask: int, *, universe: CandidateUniverseManifest) -> tuple[int, ...]:
    if not _is_int(mask) or mask < 0 or mask >= 1 << 64:
        raise CandidateContractViolation(
            "invalid_candidate_mask",
            "mask must be an unsigned 64-bit integer",
        )
    if mask >> universe.domain_size:
        raise CandidateContractViolation(
            "candidate_mask_high_bits_set",
            "mask contains bits outside domain_size",
        )
    numbers = tuple(index + 1 for index in range(universe.domain_size) if mask & (1 << index))
    if len(numbers) != universe.pick_count:
        raise CandidateContractViolation(
            "candidate_mask_cardinality_mismatch",
            "mask population count must equal pick_count",
        )
    return numbers


def canonical_candidate_record_bytes(
    numbers: Sequence[object],
    *,
    universe: CandidateUniverseManifest,
) -> bytes:
    canonical = validate_candidate_numbers(numbers, universe=universe)
    mask = candidate_mask(canonical, universe=universe)
    lex_id = candidate_rank(canonical, universe=universe)
    return bytes((universe.domain_size, universe.pick_count, *canonical)) + struct.pack("<QI", mask, lex_id)


def candidate_record_digest(
    numbers: Sequence[object],
    *,
    universe: CandidateUniverseManifest,
) -> str:
    return _binary_digest(
        canonical_candidate_record_bytes(numbers, universe=universe),
        domain="dehps.candidate-record.v1",
    )


@dataclass(frozen=True)
class CandidateManifest:
    universe: CandidateUniverseManifest
    candidates: tuple[tuple[int, ...], ...]

    @classmethod
    def from_candidates(
        cls,
        *,
        universe: CandidateUniverseManifest,
        candidates: Sequence[Sequence[object]],
    ) -> CandidateManifest:
        canonical = tuple(validate_candidate_numbers(row, universe=universe) for row in candidates)
        return cls(universe=universe, candidates=canonical)

    def __post_init__(self) -> None:
        previous_lex_id: int | None = None
        for row_index, numbers in enumerate(self.candidates):
            canonical = validate_candidate_numbers(numbers, universe=self.universe)
            if canonical != numbers:
                raise CandidateContractViolation(
                    "noncanonical_candidate_numbers",
                    "candidate rows must already be canonical tuples",
                    row_index=row_index,
                )
            lex_id = candidate_rank(canonical, universe=self.universe)
            if previous_lex_id is not None and lex_id <= previous_lex_id:
                raise CandidateContractViolation(
                    "candidate_manifest_order_violation",
                    "candidate rows must have strictly increasing lex_id",
                    row_index=row_index,
                    lex_id=lex_id,
                    previous_lex_id=previous_lex_id,
                )
            previous_lex_id = lex_id

    def identity_payload(self) -> dict[str, Any]:
        return {
            "universe_manifest_digest": self.universe.manifest_digest,
            "candidates": [list(numbers) for numbers in self.candidates],
        }

    @property
    def manifest_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.candidate-manifest.v1")


@dataclass(frozen=True)
class CandidateBufferMetadata:
    name: str
    dtype: str
    endianness: str
    shape: tuple[int, ...]
    strides: tuple[int, ...]
    alignment: int
    byte_length: int
    buffer_digest: str

    def identity_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "endianness": self.endianness,
            "shape": list(self.shape),
            "strides": list(self.strides),
            "alignment": self.alignment,
            "byte_length": self.byte_length,
            "buffer_digest": self.buffer_digest,
        }


@dataclass(frozen=True)
class CandidateABIHeader:
    abi_version: str
    candidate_contract: ContractRef
    universe_manifest_digest: str
    candidate_digest: str
    layout_digest: str
    payload_digest: str
    row_count: int
    domain_size: int
    pick_count: int
    universe_cardinality: int
    buffers: tuple[CandidateBufferMetadata, ...]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "abi_version": self.abi_version,
            "candidate_contract": self.candidate_contract.normative_identity(),
            "universe_manifest_digest": self.universe_manifest_digest,
            "candidate_digest": self.candidate_digest,
            "layout_digest": self.layout_digest,
            "payload_digest": self.payload_digest,
            "row_count": self.row_count,
            "domain_size": self.domain_size,
            "pick_count": self.pick_count,
            "universe_cardinality": self.universe_cardinality,
            "buffers": [buffer.identity_payload() for buffer in self.buffers],
        }

    @property
    def header_digest(self) -> str:
        return canonical_digest(self.identity_payload(), domain="dehps.candidate-abi-header.v1")


@dataclass(frozen=True)
class CandidateRuntimeEnvelope:
    candidate_contract: ContractRef
    candidate_abi: str
    candidate_digest: str
    layout_digest: str
    package_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_contract": self.candidate_contract.as_dict(),
            "candidate_abi": self.candidate_abi,
            "candidate_digest": self.candidate_digest,
            "layout_digest": self.layout_digest,
            "package_digest": self.package_digest,
        }


@dataclass(frozen=True)
class CandidateABIPackage:
    header: CandidateABIHeader
    numbers: np.ndarray
    mask: np.ndarray
    lex_id: np.ndarray

    @property
    def package_digest(self) -> str:
        return canonical_digest(
            {
                "artifact_type": "candidate_abi_package.v1",
                "header_digest": self.header.header_digest,
                "payload_digest": self.header.payload_digest,
            },
            domain="dehps.candidate-abi-package.v1",
        )

    @property
    def runtime_envelope(self) -> CandidateRuntimeEnvelope:
        return CandidateRuntimeEnvelope(
            candidate_contract=self.header.candidate_contract,
            candidate_abi=self.header.abi_version,
            candidate_digest=self.header.candidate_digest,
            layout_digest=self.header.layout_digest,
            package_digest=self.package_digest,
        )


def _buffer_digest(name: str, array: np.ndarray) -> str:
    return _binary_digest(array.tobytes(order="C"), domain=f"dehps.candidate-abi.buffer.{name}.v1")


def _metadata(
    name: str,
    array: np.ndarray,
    *,
    dtype: str,
    endianness: str,
    alignment: int,
) -> CandidateBufferMetadata:
    return CandidateBufferMetadata(
        name=name,
        dtype=dtype,
        endianness=endianness,
        shape=tuple(int(value) for value in array.shape),
        strides=tuple(int(value) for value in array.strides),
        alignment=alignment,
        byte_length=int(array.nbytes),
        buffer_digest=_buffer_digest(name, array),
    )


def _payload_digest(buffers: Sequence[CandidateBufferMetadata]) -> str:
    return canonical_digest(
        {"buffers": [buffer.identity_payload() for buffer in buffers]},
        domain="dehps.candidate-abi-payload.v1",
    )


class CandidateCompiler:
    """Control-plane reference compiler; it is intentionally not wired into CandidateStore."""

    def compile(self, manifest: CandidateManifest) -> CandidateABIPackage:
        universe = manifest.universe
        row_count = len(manifest.candidates)
        if row_count:
            numbers = np.asarray(manifest.candidates, dtype=np.uint8)
        else:
            numbers = np.empty((0, universe.pick_count), dtype=np.uint8)
        numbers = np.ascontiguousarray(numbers.reshape(row_count, universe.pick_count), dtype=np.uint8)
        mask = np.ascontiguousarray(
            [candidate_mask(row, universe=universe) for row in manifest.candidates],
            dtype=np.dtype("<u8"),
        )
        lex_id = np.ascontiguousarray(
            [candidate_rank(row, universe=universe) for row in manifest.candidates],
            dtype=np.dtype("<u4"),
        )
        buffers = (
            _metadata("numbers", numbers, dtype="uint8", endianness="not_applicable", alignment=1),
            _metadata("mask", mask, dtype="uint64", endianness="little", alignment=8),
            _metadata("lex_id", lex_id, dtype="uint32", endianness="little", alignment=4),
        )
        header = CandidateABIHeader(
            abi_version=CANDIDATE_ABI_VERSION,
            candidate_contract=universe.contract,
            universe_manifest_digest=universe.manifest_digest,
            candidate_digest=manifest.manifest_digest,
            layout_digest=CANDIDATE_ABI_LAYOUT_DIGEST,
            payload_digest=_payload_digest(buffers),
            row_count=row_count,
            domain_size=universe.domain_size,
            pick_count=universe.pick_count,
            universe_cardinality=universe.cardinality,
            buffers=buffers,
        )
        package = CandidateABIPackage(header=header, numbers=numbers, mask=mask, lex_id=lex_id)
        CandidateABIVerifier().verify(package)
        return package


class CandidateArrayCompiler:
    """Compile already-materialized candidate buffers without repairing or reordering them."""

    def compile(
        self,
        *,
        universe: CandidateUniverseManifest,
        numbers: np.ndarray,
        mask: np.ndarray,
        lex_id: np.ndarray,
    ) -> CandidateABIPackage:
        if not isinstance(numbers, np.ndarray) or numbers.ndim != 2:
            raise CandidateContractViolation(
                "candidate_buffer_shape_mismatch",
                "numbers must be a two-dimensional Candidate ABI buffer",
            )
        row_count = int(numbers.shape[0])
        buffers = (
            _metadata(
                "numbers",
                numbers,
                dtype="uint8",
                endianness="not_applicable",
                alignment=1,
            ),
            _metadata("mask", mask, dtype="uint64", endianness="little", alignment=8),
            _metadata("lex_id", lex_id, dtype="uint32", endianness="little", alignment=4),
        )
        header = CandidateABIHeader(
            abi_version=CANDIDATE_ABI_VERSION,
            candidate_contract=universe.contract,
            universe_manifest_digest=universe.manifest_digest,
            candidate_digest=_candidate_manifest_digest_from_numbers(numbers, universe=universe),
            layout_digest=CANDIDATE_ABI_LAYOUT_DIGEST,
            payload_digest=_payload_digest(buffers),
            row_count=row_count,
            domain_size=universe.domain_size,
            pick_count=universe.pick_count,
            universe_cardinality=universe.cardinality,
            buffers=buffers,
        )
        package = CandidateABIPackage(
            header=header,
            numbers=numbers,
            mask=mask,
            lex_id=lex_id,
        )
        CandidateABIVerifier().verify(package)
        return package


def _candidate_manifest_digest_from_numbers(
    numbers: np.ndarray,
    *,
    universe: CandidateUniverseManifest,
) -> str:
    digest = sha256(b"dehps.candidate-manifest.v1\x00")
    digest.update(b'{"candidates":[')
    for row_index, row in enumerate(numbers):
        if row_index:
            digest.update(b",")
        canonical = validate_candidate_numbers(
            tuple(int(value) for value in row),
            universe=universe,
        )
        digest.update(b"[")
        digest.update(",".join(str(value) for value in canonical).encode("ascii"))
        digest.update(b"]")
    digest.update(b'],"universe_manifest_digest":"')
    digest.update(universe.manifest_digest.encode("ascii"))
    digest.update(b'"}')
    return digest.hexdigest()


class CandidateABIVerifier:
    """Fail-closed verifier for Candidate ABI packages; it never coerces or repairs buffers."""

    def verify(self, package: CandidateABIPackage) -> None:
        header = package.header
        if header.abi_version != CANDIDATE_ABI_VERSION:
            self._reject("unsupported_candidate_abi_version", "unsupported Candidate ABI version")
        if not header.candidate_contract.normatively_equals(CANDIDATE_CONTRACT_V1):
            self._reject("candidate_contract_mismatch", "Candidate ABI must use candidate.v1.0.0")
        if header.layout_digest != CANDIDATE_ABI_LAYOUT_DIGEST:
            self._reject("candidate_layout_digest_mismatch", "Candidate ABI layout digest is not v1")
        for name, value in (
            ("universe_manifest_digest", header.universe_manifest_digest),
            ("candidate_digest", header.candidate_digest),
            ("layout_digest", header.layout_digest),
            ("payload_digest", header.payload_digest),
        ):
            _require_digest(name, value)
        universe = CandidateUniverseManifest(
            domain_size=header.domain_size,
            pick_count=header.pick_count,
            contract=header.candidate_contract,
        )
        if header.universe_cardinality != universe.cardinality:
            self._reject("candidate_universe_cardinality_mismatch", "header cardinality is not canonical")
        if header.universe_manifest_digest != universe.manifest_digest:
            self._reject("candidate_universe_digest_mismatch", "header universe digest is not canonical")
        if not _is_int(header.row_count) or header.row_count < 0 or header.row_count > universe.cardinality:
            self._reject("invalid_candidate_row_count", "row_count is outside the universe")

        expected_specs = (
            ("numbers", package.numbers, np.dtype("u1"), (header.row_count, header.pick_count), "uint8", "not_applicable", 1),
            ("mask", package.mask, np.dtype("<u8"), (header.row_count,), "uint64", "little", 8),
            ("lex_id", package.lex_id, np.dtype("<u4"), (header.row_count,), "uint32", "little", 4),
        )
        if len(header.buffers) != len(expected_specs):
            self._reject("candidate_buffer_count_mismatch", "Candidate ABI v1 requires three buffers")
        recomputed_metadata: list[CandidateBufferMetadata] = []
        for stored, expected in zip(header.buffers, expected_specs):
            name, array, dtype, shape, dtype_name, endianness, alignment = expected
            self._verify_buffer(name=name, array=array, dtype=dtype, shape=shape, alignment=alignment)
            actual = _metadata(
                name,
                array,
                dtype=dtype_name,
                endianness=endianness,
                alignment=alignment,
            )
            if stored != actual:
                self._reject(
                    "candidate_buffer_metadata_mismatch",
                    "buffer metadata or digest does not match the payload",
                    buffer=name,
                )
            recomputed_metadata.append(actual)
        if header.payload_digest != _payload_digest(recomputed_metadata):
            self._reject("candidate_payload_digest_mismatch", "payload digest does not match buffers")

        previous_lex_id: int | None = None
        for row_index in range(header.row_count):
            numbers = tuple(int(value) for value in package.numbers[row_index])
            canonical = validate_candidate_numbers(numbers, universe=universe)
            lex_id = int(package.lex_id[row_index])
            mask = int(package.mask[row_index])
            if candidate_rank(canonical, universe=universe) != lex_id:
                self._reject("candidate_lex_id_mismatch", "lex_id does not match candidate numbers", row_index=row_index)
            if candidate_unrank(lex_id, universe=universe) != canonical:
                self._reject("candidate_unrank_mismatch", "unrank(lex_id) does not match candidate numbers", row_index=row_index)
            if candidate_mask(canonical, universe=universe) != mask:
                self._reject("candidate_mask_mismatch", "mask does not match candidate numbers", row_index=row_index)
            if candidate_numbers_from_mask(mask, universe=universe) != canonical:
                self._reject("candidate_mask_roundtrip_mismatch", "mask round trip is not canonical", row_index=row_index)
            if previous_lex_id is not None and lex_id <= previous_lex_id:
                self._reject("candidate_abi_order_violation", "ABI rows must have strictly increasing lex_id")
            previous_lex_id = lex_id

        expected_candidate_digest = _candidate_manifest_digest_from_numbers(package.numbers, universe=universe)
        if header.candidate_digest != expected_candidate_digest:
            self._reject("candidate_digest_mismatch", "candidate digest does not match canonical rows")

    def _verify_buffer(
        self,
        *,
        name: str,
        array: np.ndarray,
        dtype: np.dtype[Any],
        shape: tuple[int, ...],
        alignment: int,
    ) -> None:
        if not isinstance(array, np.ndarray):
            self._reject("candidate_buffer_type_mismatch", "Candidate ABI buffers must be numpy arrays", buffer=name)
        if array.dtype != dtype or array.dtype.str != dtype.str:
            self._reject("candidate_buffer_dtype_mismatch", "buffer dtype or endianness is invalid", buffer=name)
        if array.shape != shape:
            self._reject("candidate_buffer_shape_mismatch", "buffer shape is invalid", buffer=name)
        if not array.flags.c_contiguous:
            self._reject("candidate_buffer_not_contiguous", "buffer must be C-contiguous", buffer=name)
        if array.ctypes.data % alignment:
            self._reject("candidate_buffer_alignment_mismatch", "buffer alignment is invalid", buffer=name)

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise CandidateContractViolation(code, message, **context)
