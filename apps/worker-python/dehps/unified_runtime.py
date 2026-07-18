from __future__ import annotations

from dataclasses import dataclass
import re
import threading
import time
from typing import Any

from dehps.contracts import canonical_digest
from dehps.feature_runtime.abi import FEATURE_ABI_VERSION
from dehps.feature_runtime.runtime import FeatureABIRuntime, FeatureABIRuntimeVerifier
from dehps.input_contracts.candidate_abi import CANDIDATE_ABI_VERSION
from dehps.input_contracts.candidate_abi import CandidateABIVerification


UNIFIED_RUNTIME_VERIFIER_VERSION = "unified_runtime_verifier.v1"
VERIFIED_RUNTIME_PACKAGE_VERSION = "verified_runtime_package.v1"
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SESSION_CONSTRUCTOR_TOKEN = object()


class RuntimeVerificationViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


@dataclass(frozen=True)
class VerifiedRuntimePackage:
    package_version: str
    verifier_version: str
    runtime: FeatureABIRuntime
    verification_digest: str

    @property
    def verified_runtime_id(self) -> str:
        return f"verified_runtime.v1-{self.verification_digest[:16]}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_version": self.package_version,
            "verifier_version": self.verifier_version,
            "verified_runtime_id": self.verified_runtime_id,
            "verification_digest": self.verification_digest,
            "runtime_digest": self.runtime.runtime_digest,
            "history_snapshot_digest": self.runtime.history_snapshot.history_digest,
            "window_artifact_digest": self.runtime.window_artifact.artifact_digest,
            "candidate_package_digest": self.runtime.candidate_package.package_digest,
            "feature_package_digests": [
                package.package_digest for package in self.runtime.feature_tiles
            ],
        }


class RuntimeVerificationSession:
    """One synchronous pre/post payload-verification boundary.

    The session is not a lease: it has no TTL, is bound to one package object and
    one thread, and cannot be reused after context exit.
    """

    def __init_subclass__(cls, **kwargs) -> None:
        raise TypeError("RuntimeVerificationSession is final")

    def __init__(
        self,
        verifier: UnifiedRuntimeVerifier,
        package: VerifiedRuntimePackage,
        *,
        _token: object,
    ) -> None:
        if _token is not _SESSION_CONSTRUCTOR_TOKEN:
            raise RuntimeVerificationViolation(
                "runtime_verification_session_construction_forbidden",
                "Runtime Verification Sessions must be created by UnifiedRuntimeVerifier",
            )
        self._verifier = verifier
        self._package = package
        self._owner_thread_id: int | None = None
        self._active = False
        self._closed = False
        self._candidate_verification: CandidateABIVerification | None = None
        self.entry_verification_seconds = 0.0
        self.exit_verification_seconds = 0.0
        self.full_verification_passes = 0

    def __enter__(self) -> RuntimeVerificationSession:
        if self._active or self._closed:
            self._reject(
                "runtime_verification_session_reuse",
                "Runtime Verification Sessions are single-use",
            )
        self._owner_thread_id = threading.get_ident()
        started = time.perf_counter()
        self._candidate_verification = self._verifier.verify_package(self._package)
        self.entry_verification_seconds = time.perf_counter() - started
        self.full_verification_passes += 1
        self._active = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.require_package(self._package)
        try:
            started = time.perf_counter()
            self._verifier.verify_package(self._package)
            self.exit_verification_seconds = time.perf_counter() - started
            self.full_verification_passes += 1
        finally:
            self._active = False
            self._closed = True
        return False

    @property
    def candidate_verification(self) -> CandidateABIVerification:
        self._require_active_thread()
        if self._candidate_verification is None:
            self._reject(
                "runtime_verification_session_receipt_missing",
                "active Runtime Verification Session has no Candidate ABI receipt",
            )
        return self._candidate_verification

    @property
    def total_verification_seconds(self) -> float:
        return self.entry_verification_seconds + self.exit_verification_seconds

    def require_package(self, package: VerifiedRuntimePackage) -> None:
        self._require_active_thread()
        if package is not self._package:
            self._reject(
                "runtime_verification_session_package_mismatch",
                "Runtime Verification Session belongs to another package object",
            )

    def require_runtime(self, runtime: FeatureABIRuntime) -> None:
        self._require_active_thread()
        if runtime is not self._package.runtime:
            self._reject(
                "runtime_verification_session_runtime_mismatch",
                "Runtime Verification Session belongs to another Runtime object",
            )

    def _require_active_thread(self) -> None:
        if not self._active or self._closed:
            self._reject(
                "runtime_verification_session_inactive",
                "Runtime Verification Session is not active",
            )
        if threading.get_ident() != self._owner_thread_id:
            self._reject(
                "runtime_verification_session_thread_mismatch",
                "Runtime Verification Session cannot cross threads",
            )

    @staticmethod
    def _reject(code: str, message: str) -> None:
        raise RuntimeVerificationViolation(code, message)


def _verification_identity(runtime: FeatureABIRuntime) -> dict[str, Any]:
    candidate = runtime.candidate_package
    first_feature = runtime.feature_tiles[0]
    return {
        "package_version": VERIFIED_RUNTIME_PACKAGE_VERSION,
        "verifier_version": UNIFIED_RUNTIME_VERIFIER_VERSION,
        "runtime_digest": runtime.runtime_digest,
        "history": {
            "contract": runtime.history_snapshot.contract.normative_identity(),
            "snapshot_digest": runtime.history_snapshot.history_digest,
        },
        "window": {
            "contract": runtime.window_artifact.envelope.window_contract.normative_identity(),
            "artifact_digest": runtime.window_artifact.artifact_digest,
        },
        "candidate": {
            "contract": candidate.header.candidate_contract.normative_identity(),
            "abi": candidate.header.abi_version,
            "layout_digest": candidate.header.layout_digest,
            "package_digest": candidate.package_digest,
        },
        "feature": {
            "contract": first_feature.header.feature_contract.normative_identity(),
            "abi": first_feature.header.abi_version,
            "layout_digest": first_feature.header.layout_digest,
            "component_manifest_digest": first_feature.header.component_manifest_digest,
            "package_digests": [package.package_digest for package in runtime.feature_tiles],
        },
    }


class UnifiedRuntimeVerifier:
    """The only control-plane authority that may mint a VerifiedRuntimePackage."""

    def verify(self, runtime: FeatureABIRuntime) -> VerifiedRuntimePackage:
        if not isinstance(runtime, FeatureABIRuntime):
            self._reject(
                "runtime_package_not_raw_runtime",
                "Unified Runtime Verifier requires a FeatureABIRuntime input",
            )
        try:
            FeatureABIRuntimeVerifier().verify(runtime)
        except ValueError as exc:
            self._reject(
                "runtime_stage_verification_failed",
                "a History, Window, Candidate, or Feature runtime check failed",
                cause=_cause_payload(exc),
            )
        if runtime.candidate_package.header.abi_version != CANDIDATE_ABI_VERSION:
            self._reject("runtime_candidate_abi_mismatch", "Unified Runtime requires Candidate ABI v1")
        if any(package.header.abi_version != FEATURE_ABI_VERSION for package in runtime.feature_tiles):
            self._reject("runtime_feature_abi_mismatch", "Unified Runtime requires Feature ABI v1")
        verification_digest = canonical_digest(
            _verification_identity(runtime),
            domain="dehps.verified-runtime-package.v1",
        )
        package = VerifiedRuntimePackage(
            package_version=VERIFIED_RUNTIME_PACKAGE_VERSION,
            verifier_version=UNIFIED_RUNTIME_VERIFIER_VERSION,
            runtime=runtime,
            verification_digest=verification_digest,
        )
        self._verify_package_header(package)
        self._verify_package_seal(package)
        return package

    def verification_session(
        self,
        package: VerifiedRuntimePackage,
    ) -> RuntimeVerificationSession:
        return RuntimeVerificationSession(
            self,
            package,
            _token=_SESSION_CONSTRUCTOR_TOKEN,
        )

    def require_active_session(
        self,
        session: object,
        *,
        package: VerifiedRuntimePackage | None = None,
        runtime: FeatureABIRuntime | None = None,
    ) -> RuntimeVerificationSession:
        if not isinstance(session, RuntimeVerificationSession):
            self._reject(
                "runtime_verification_session_type_invalid",
                "nested Runtime operations require an authentic active session",
            )
        if package is not None:
            session.require_package(package)
        if runtime is not None:
            session.require_runtime(runtime)
        return session

    def verify_package(
        self,
        package: VerifiedRuntimePackage,
    ) -> CandidateABIVerification:
        self._verify_package_header(package)
        try:
            candidate_verification = FeatureABIRuntimeVerifier().verify(package.runtime)
        except ValueError as exc:
            self._reject(
                "runtime_stage_verification_failed",
                "a sealed runtime dependency no longer verifies",
                cause=_cause_payload(exc),
            )
        self._verify_package_seal(package)
        return candidate_verification

    def _verify_package_header(self, package: VerifiedRuntimePackage) -> None:
        if not isinstance(package, VerifiedRuntimePackage):
            self._reject(
                "runtime_package_not_verified",
                "Kernel boundaries require a VerifiedRuntimePackage",
            )
        if package.package_version != VERIFIED_RUNTIME_PACKAGE_VERSION:
            self._reject("verified_runtime_package_version_mismatch", "unsupported verified package version")
        if package.verifier_version != UNIFIED_RUNTIME_VERIFIER_VERSION:
            self._reject("runtime_verifier_version_mismatch", "unsupported Unified Runtime Verifier")
        if not isinstance(package.runtime, FeatureABIRuntime):
            self._reject(
                "verified_runtime_payload_invalid",
                "Verified Runtime Package payload must be FeatureABIRuntime",
            )
        if not isinstance(package.verification_digest, str) or not _DIGEST_PATTERN.fullmatch(
            package.verification_digest
        ):
            self._reject("runtime_verification_digest_invalid", "verification digest is invalid")

    def _verify_package_seal(self, package: VerifiedRuntimePackage) -> None:
        expected = canonical_digest(
            _verification_identity(package.runtime),
            domain="dehps.verified-runtime-package.v1",
        )
        if package.verification_digest != expected:
            self._reject(
                "runtime_verification_seal_mismatch",
                "Verified Runtime seal does not match its runtime inputs",
            )

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise RuntimeVerificationViolation(code, message, **context)


def _cause_payload(exc: ValueError) -> dict[str, Any]:
    serializer = getattr(exc, "as_dict", None)
    if callable(serializer):
        payload = serializer()
        if isinstance(payload, dict):
            return payload
    return {"code": getattr(exc, "code", type(exc).__name__), "message": str(exc)}
