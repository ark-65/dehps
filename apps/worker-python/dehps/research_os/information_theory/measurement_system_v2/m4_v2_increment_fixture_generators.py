from __future__ import annotations

import hashlib
from collections.abc import Iterator
from typing import Final

import numpy as np

SYNTHETIC_CELL_COUNT: Final = 14
REPLICATES_PER_CELL: Final = 512


class IncrementFixtureError(ValueError):
    pass


def child_seed_full_sha256(
    root_seed_full_sha256: str, *, cell_index: int, replicate_index: int
) -> str:
    if not (0 <= cell_index < SYNTHETIC_CELL_COUNT and 0 <= replicate_index < 512):
        raise IncrementFixtureError("increment_fixture_coordinate_invalid")
    material = (
        f"{root_seed_full_sha256}|cell={cell_index}|replicate={replicate_index}"
    ).encode()
    return hashlib.sha256(material).hexdigest()


def pcg64dxsm_generator(child_seed_sha256: str) -> np.random.Generator:
    if len(child_seed_sha256) != 64:
        raise IncrementFixtureError("increment_fixture_child_seed_invalid")
    seed_word = int(child_seed_sha256[0:16], 16)
    return np.random.Generator(np.random.PCG64DXSM(np.uint64(seed_word)))


def iter_health_coordinates() -> Iterator[tuple[int, int]]:
    for cell_index in range(SYNTHETIC_CELL_COUNT):
        for replicate_index in range(REPLICATES_PER_CELL):
            yield cell_index, replicate_index


def circular_centered_mbb_indices(
    *, sample_size: int, block_length: int, child_seed_sha256: str
) -> tuple[int, ...]:
    if sample_size <= 0 or not 1 <= block_length <= sample_size:
        raise IncrementFixtureError("increment_fixture_mbb_shape_invalid")
    rng = pcg64dxsm_generator(child_seed_sha256)
    output: list[int] = []
    while len(output) < sample_size:
        start = int(rng.integers(0, sample_size))
        output.extend((start + offset) % sample_size for offset in range(block_length))
    return tuple(output[:sample_size])


__all__ = [
    "REPLICATES_PER_CELL",
    "SYNTHETIC_CELL_COUNT",
    "IncrementFixtureError",
    "child_seed_full_sha256",
    "circular_centered_mbb_indices",
    "iter_health_coordinates",
    "pcg64dxsm_generator",
]
