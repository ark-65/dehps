from __future__ import annotations


class HypothesisRegistryError(Exception):
    """Base error for human-operated hypothesis registry commands."""


class RegistryNotFoundError(HypothesisRegistryError):
    pass


class RegistryConflictError(HypothesisRegistryError):
    pass


class InvalidTransitionError(HypothesisRegistryError):
    pass


class PreregistrationError(HypothesisRegistryError):
    pass


class ReopenError(HypothesisRegistryError):
    pass


class ArtifactReferenceError(HypothesisRegistryError):
    pass
