from __future__ import annotations

from dehps.domain.combination import normalize_red_numbers

YANG = "YANG"
YIN = "YIN"


def _encode(bits: list[bool]) -> str:
    return "-".join(YANG if bit else YIN for bit in bits)


def _binary(bits: list[bool]) -> str:
    return "".join("1" if bit else "0" for bit in bits)


def encode_odd_even_gua(numbers: list[int] | tuple[int, ...], binary: bool = False) -> str:
    nums = normalize_red_numbers(numbers)
    bits = [n % 2 == 1 for n in nums]
    return _binary(bits) if binary else _encode(bits)


def encode_small_big_gua(numbers: list[int] | tuple[int, ...], binary: bool = False) -> str:
    nums = normalize_red_numbers(numbers)
    bits = [n >= 17 for n in nums]
    return _binary(bits) if binary else _encode(bits)

