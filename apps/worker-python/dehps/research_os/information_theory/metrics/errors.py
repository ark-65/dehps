from __future__ import annotations


class MetricKernelError(ValueError):
    """Fail-closed metric error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
