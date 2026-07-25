from __future__ import annotations


class WalkForwardError(ValueError):
    """Structured fail-closed P2.3 contract error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
