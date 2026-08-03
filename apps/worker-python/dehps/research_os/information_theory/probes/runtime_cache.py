from __future__ import annotations

from typing import Any


class ExactProbeRuntimeCache:
    """Frozen import-safe factory for the mutable acceleration backend.

    Probe modules import this symbol for annotations.  The optimized backend is
    deliberately imported only when the observed evaluator instantiates the
    cache, so importing the literal golden oracle cannot execute acceleration
    code.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        from .runtime_cache_backend import (
            ExactProbeRuntimeCache as RuntimeCacheBackend,
        )

        return RuntimeCacheBackend(*args, **kwargs)
