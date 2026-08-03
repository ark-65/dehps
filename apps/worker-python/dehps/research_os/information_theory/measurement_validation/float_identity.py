from __future__ import annotations

import math
import struct
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


class FloatIdentityError(RuntimeError):
    pass


def float64_bits(value: Real) -> str:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise FloatIdentityError("float_identity_nonfinite")
    return struct.pack(">d", normalized).hex()


def encode_float64_tree(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Real):
        return {"float64_bits": float64_bits(value)}
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise FloatIdentityError("float_identity_non_string_key")
            normalized[key] = encode_float64_tree(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [encode_float64_tree(item) for item in value]
    raise FloatIdentityError(f"float_identity_unsupported_type:{type(value).__name__}")


def assert_float64_tree(value: Any) -> None:
    if isinstance(value, (bool, int)) or value is None:
        return
    if isinstance(value, float):
        raise FloatIdentityError("float_identity_unencoded_float")
    if isinstance(value, str):
        return
    if isinstance(value, Mapping):
        if set(value) == {"float64_bits"}:
            bits = value.get("float64_bits")
            if (
                not isinstance(bits, str)
                or len(bits) != 16
                or any(character not in "0123456789abcdef" for character in bits)
            ):
                raise FloatIdentityError("float_identity_bits_invalid")
            return
        for key, item in value.items():
            if not isinstance(key, str):
                raise FloatIdentityError("float_identity_non_string_key")
            assert_float64_tree(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            assert_float64_tree(item)
        return
    raise FloatIdentityError(f"float_identity_unsupported_type:{type(value).__name__}")
