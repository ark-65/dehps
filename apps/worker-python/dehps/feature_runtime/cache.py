from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
import threading
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.feature_runtime.abi import (
    FEATURE_ABI_LAYOUT_DIGEST,
    FEATURE_ABI_VERSION,
    FeatureABICompiler,
    FeatureABIPackage,
    FeatureABIVerifier,
)
from dehps.feature_runtime.compiler import (
    FEATURE_COMPILER_VERSION,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
    candidate_static_digest,
)
from dehps.feature_runtime.runtime import FeatureABIRuntime
from dehps.input_contracts.feature_contract import (
    FEATURE_COMPONENT_MANIFEST_DIGEST,
    FEATURE_CONTRACT_V1,
)
from dehps.input_contracts.history_window import HistorySnapshotArtifact, WindowArtifact
from dehps.scoring_kernel.contracts import CandidateStore
from dehps.unified_runtime import (
    UNIFIED_RUNTIME_VERIFIER_VERSION,
    UnifiedRuntimeVerifier,
    VerifiedRuntimePackage,
)


RUNTIME_ABI_CACHE_PROTOCOL = "runtime_abi_cache.v1"
DEFAULT_MAX_ENTRIES = 64
DEFAULT_MAX_PAYLOAD_BYTES = 512 * 1024 * 1024


def _contract_digest(contract: ContractRef) -> str:
    return canonical_digest(
        contract.as_dict(),
        domain="dehps.runtime-abi-cache.contract-identity.v1",
    )


@dataclass(frozen=True)
class FeatureABICacheKey:
    history_contract_digest: str
    history_snapshot_digest: str
    window_contract_digest: str
    window_artifact_digest: str
    window_spec_digest: str
    candidate_contract_digest: str
    candidate_abi: str
    candidate_layout_digest: str
    candidate_package_digest: str
    candidate_static_digest: str
    feature_contract_digest: str
    feature_abi: str
    feature_layout_digest: str
    feature_manifest_digest: str
    feature_compiler_version: str
    target_context_digest: str
    start: int
    end: int

    def identity_payload(self) -> dict[str, Any]:
        return {
            "protocol": RUNTIME_ABI_CACHE_PROTOCOL,
            "history": {
                "contract_digest": self.history_contract_digest,
                "snapshot_digest": self.history_snapshot_digest,
            },
            "window": {
                "contract_digest": self.window_contract_digest,
                "artifact_digest": self.window_artifact_digest,
                "spec_digest": self.window_spec_digest,
            },
            "candidate": {
                "contract_digest": self.candidate_contract_digest,
                "abi": self.candidate_abi,
                "layout_digest": self.candidate_layout_digest,
                "package_digest": self.candidate_package_digest,
                "static_digest": self.candidate_static_digest,
            },
            "feature": {
                "contract_digest": self.feature_contract_digest,
                "abi": self.feature_abi,
                "layout_digest": self.feature_layout_digest,
                "manifest_digest": self.feature_manifest_digest,
                "compiler_version": self.feature_compiler_version,
                "target_context_digest": self.target_context_digest,
                "row_range": [self.start, self.end],
            },
        }

    @property
    def cache_key_digest(self) -> str:
        return canonical_digest(
            self.identity_payload(),
            domain="dehps.runtime-abi-cache.feature-key.v1",
        )


@dataclass(frozen=True)
class FeatureABICacheReceipt:
    package: FeatureABIPackage
    key: FeatureABICacheKey
    cache_hit: bool
    stored: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": RUNTIME_ABI_CACHE_PROTOCOL,
            "cache_key_digest": self.key.cache_key_digest,
            "cache_hit": self.cache_hit,
            "stored": self.stored,
            "package_digest": self.package.package_digest,
            "payload_bytes": int(self.package.values.nbytes),
        }


@dataclass(frozen=True)
class RuntimeABICacheCompilation:
    verified_runtime: VerifiedRuntimePackage
    feature_receipts: tuple[FeatureABICacheReceipt, ...]
    runtime_cache_hit: bool

    @property
    def all_feature_cache_hits(self) -> bool:
        return all(receipt.cache_hit for receipt in self.feature_receipts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": RUNTIME_ABI_CACHE_PROTOCOL,
            "verified_runtime_id": self.verified_runtime.verified_runtime_id,
            "runtime_verification_digest": self.verified_runtime.verification_digest,
            "runtime_cache_hit": self.runtime_cache_hit,
            "all_feature_cache_hits": self.all_feature_cache_hits,
            "feature_tiles": [receipt.as_dict() for receipt in self.feature_receipts],
        }


@dataclass(frozen=True)
class RuntimeABICacheStats:
    feature_hits: int
    feature_misses: int
    runtime_hits: int
    runtime_misses: int
    invalidations: int
    evictions: int
    feature_entries: int
    runtime_entries: int
    payload_bytes: int
    max_entries: int
    max_payload_bytes: int

    def as_dict(self) -> dict[str, int | str]:
        return {"protocol": RUNTIME_ABI_CACHE_PROTOCOL, **vars(self)}


@dataclass(frozen=True)
class _FeatureCacheEntry:
    key: FeatureABICacheKey
    package: FeatureABIPackage
    header_digest: str
    package_digest: str
    payload_bytes: int


@dataclass(frozen=True)
class _RuntimeCacheEntry:
    runtime_key: str
    verified_runtime: VerifiedRuntimePackage
    verification_digest: str


class RuntimeABICache:
    """Bounded process-local cache for compiled Feature ABI and verified runtimes.

    A cache hit is never a verifier bypass. Mutable payload digests are
    recomputed before return, and cached arrays must remain read-only.
    """

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
        feature_compiler: FeatureCompiler | None = None,
        abi_compiler: FeatureABICompiler | None = None,
        runtime_verifier: UnifiedRuntimeVerifier | None = None,
    ) -> None:
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
            raise ValueError("max_entries must be a positive integer")
        if (
            isinstance(max_payload_bytes, bool)
            or not isinstance(max_payload_bytes, int)
            or max_payload_bytes < 0
        ):
            raise ValueError("max_payload_bytes must be a non-negative integer")
        self.max_entries = max_entries
        self.max_payload_bytes = max_payload_bytes
        self.feature_compiler = feature_compiler or FeatureCompiler()
        self.abi_compiler = abi_compiler or FeatureABICompiler()
        self.runtime_verifier = runtime_verifier or UnifiedRuntimeVerifier()
        self._feature_entries: OrderedDict[str, _FeatureCacheEntry] = OrderedDict()
        self._runtime_entries: OrderedDict[str, _RuntimeCacheEntry] = OrderedDict()
        self._payload_bytes = 0
        self._feature_hits = 0
        self._feature_misses = 0
        self._runtime_hits = 0
        self._runtime_misses = 0
        self._invalidations = 0
        self._evictions = 0
        self._lock = threading.RLock()

    def feature_key(self, request: FeatureCompileRequest) -> FeatureABICacheKey:
        request.window.verify()
        request.candidate_store.validate()
        start, end = request.normalized_range()
        package = request.candidate_store.candidate_abi_package
        if package is None:  # CandidateStore.validate rejects this first.
            raise FeatureRuntimeViolation(
                "candidate_abi_missing",
                "Runtime ABI Cache requires a Candidate ABI package",
            )
        return FeatureABICacheKey(
            history_contract_digest=_contract_digest(
                request.window.envelope.history_contract
            ),
            history_snapshot_digest=request.window.envelope.history_snapshot_digest,
            window_contract_digest=_contract_digest(
                request.window.envelope.window_contract
            ),
            window_artifact_digest=request.window.artifact_digest,
            window_spec_digest=request.window.spec.spec_digest,
            candidate_contract_digest=_contract_digest(
                package.header.candidate_contract
            ),
            candidate_abi=package.header.abi_version,
            candidate_layout_digest=package.header.layout_digest,
            candidate_package_digest=package.package_digest,
            candidate_static_digest=candidate_static_digest(
                request.candidate_store,
                start=start,
                end=end,
            ),
            feature_contract_digest=_contract_digest(FEATURE_CONTRACT_V1),
            feature_abi=FEATURE_ABI_VERSION,
            feature_layout_digest=FEATURE_ABI_LAYOUT_DIGEST,
            feature_manifest_digest=FEATURE_COMPONENT_MANIFEST_DIGEST,
            feature_compiler_version=FEATURE_COMPILER_VERSION,
            target_context_digest=request.target_context_digest,
            start=start,
            end=end,
        )

    def compile_feature(self, request: FeatureCompileRequest) -> FeatureABICacheReceipt:
        with self._lock:
            key = self.feature_key(request)
            cache_key = key.cache_key_digest
            entry = self._feature_entries.get(cache_key)
            if entry is not None:
                try:
                    self._verify_feature_entry(entry, expected_key=key)
                except ValueError:
                    self._drop_feature_entry(cache_key, invalidated=True)
                else:
                    self._feature_entries.move_to_end(cache_key)
                    self._feature_hits += 1
                    return FeatureABICacheReceipt(
                        package=entry.package,
                        key=key,
                        cache_hit=True,
                        stored=True,
                    )

            self._feature_misses += 1
            artifact = self.feature_compiler.compile(request)
            package = self.abi_compiler.compile(artifact)
            if package.values is not artifact.values:
                raise FeatureRuntimeViolation(
                    "feature_abi_cache_buffer_copy",
                    "Feature ABI Cache requires the compiler to preserve the values buffer",
                )
            package.values.setflags(write=False)
            FeatureABIVerifier().verify(package, source_artifact=artifact)
            final_key = self.feature_key(request)
            if final_key != key:
                raise FeatureRuntimeViolation(
                    "feature_abi_cache_input_changed",
                    "Feature compilation inputs changed while the cache entry was being built",
                )
            self._verify_package_bindings(package, expected_key=key)
            payload_bytes = int(package.values.nbytes)
            stored = payload_bytes <= self.max_payload_bytes
            if stored:
                self._feature_entries[cache_key] = _FeatureCacheEntry(
                    key=key,
                    package=package,
                    header_digest=package.header.header_digest,
                    package_digest=package.package_digest,
                    payload_bytes=payload_bytes,
                )
                self._payload_bytes += payload_bytes
                self._evict_feature_entries()
                stored = cache_key in self._feature_entries
            return FeatureABICacheReceipt(
                package=package,
                key=key,
                cache_hit=False,
                stored=stored,
            )

    def compile_runtime(
        self,
        *,
        history_snapshot: HistorySnapshotArtifact,
        window: WindowArtifact,
        candidate_store: CandidateStore,
        tile_size: int,
        target_draw_date: date | None = None,
    ) -> RuntimeABICacheCompilation:
        if isinstance(tile_size, bool) or not isinstance(tile_size, int) or tile_size < 1:
            raise ValueError("tile_size must be a positive integer")
        history_snapshot.verify()
        window.verify()
        if (
            window.snapshot_id != history_snapshot.snapshot_id
            or window.envelope.history_snapshot_digest
            != history_snapshot.history_digest
            or window.envelope.input_draw_count != history_snapshot.draw_count
        ):
            raise FeatureRuntimeViolation(
                "feature_runtime_history_window_binding_mismatch",
                "Window Artifact does not match the requested History Snapshot",
            )
        receipts = tuple(
            self.compile_feature(
                FeatureCompileRequest(
                    window=window,
                    candidate_store=candidate_store,
                    start=start,
                    end=min(start + tile_size, len(candidate_store)),
                    target_draw_date=target_draw_date,
                )
            )
            for start in range(0, max(1, len(candidate_store)), tile_size)
        )
        candidate_package = candidate_store.candidate_abi_package
        if candidate_package is None:  # compile_feature validates this first.
            raise FeatureRuntimeViolation(
                "candidate_abi_missing",
                "Runtime ABI Cache requires a Candidate ABI package",
            )
        runtime = FeatureABIRuntime(
            history_snapshot=history_snapshot,
            window_artifact=window,
            candidate_package=candidate_package,
            feature_tiles=tuple(receipt.package for receipt in receipts),
        )
        runtime_key = self._runtime_key(runtime)
        with self._lock:
            cached_entry = self._runtime_entries.get(runtime_key)
            if cached_entry is not None:
                try:
                    cached = cached_entry.verified_runtime
                    if (
                        cached_entry.runtime_key != runtime_key
                        or cached_entry.verification_digest
                        != cached.verification_digest
                        or self._runtime_key(cached.runtime) != runtime_key
                    ):
                        raise FeatureRuntimeViolation(
                            "runtime_abi_cache_identity_mutated",
                            "cached Verified Runtime identity changed after insertion",
                        )
                    self.runtime_verifier.verify_package(cached)
                except ValueError:
                    self._runtime_entries.pop(runtime_key, None)
                    self._invalidations += 1
                else:
                    self._runtime_entries.move_to_end(runtime_key)
                    self._runtime_hits += 1
                    return RuntimeABICacheCompilation(
                        verified_runtime=cached,
                        feature_receipts=receipts,
                        runtime_cache_hit=True,
                    )
            self._runtime_misses += 1
            verified = self.runtime_verifier.verify(runtime)
            feature_entries_are_retained = all(
                (
                    entry := self._feature_entries.get(
                        receipt.key.cache_key_digest
                    )
                )
                is not None
                and entry.package is receipt.package
                for receipt in receipts
            )
            if feature_entries_are_retained:
                self._runtime_entries[runtime_key] = _RuntimeCacheEntry(
                    runtime_key=runtime_key,
                    verified_runtime=verified,
                    verification_digest=verified.verification_digest,
                )
                self._runtime_entries.move_to_end(runtime_key)
                while len(self._runtime_entries) > self.max_entries:
                    self._runtime_entries.popitem(last=False)
                    self._evictions += 1
            return RuntimeABICacheCompilation(
                verified_runtime=verified,
                feature_receipts=receipts,
                runtime_cache_hit=False,
            )

    def stats(self) -> RuntimeABICacheStats:
        with self._lock:
            return RuntimeABICacheStats(
                feature_hits=self._feature_hits,
                feature_misses=self._feature_misses,
                runtime_hits=self._runtime_hits,
                runtime_misses=self._runtime_misses,
                invalidations=self._invalidations,
                evictions=self._evictions,
                feature_entries=len(self._feature_entries),
                runtime_entries=len(self._runtime_entries),
                payload_bytes=self._payload_bytes,
                max_entries=self.max_entries,
                max_payload_bytes=self.max_payload_bytes,
            )

    def clear(self, *, reset_stats: bool = True) -> None:
        with self._lock:
            self._feature_entries.clear()
            self._runtime_entries.clear()
            self._payload_bytes = 0
            if reset_stats:
                self._feature_hits = 0
                self._feature_misses = 0
                self._runtime_hits = 0
                self._runtime_misses = 0
                self._invalidations = 0
                self._evictions = 0

    def _verify_feature_entry(
        self,
        entry: _FeatureCacheEntry,
        *,
        expected_key: FeatureABICacheKey,
    ) -> None:
        if entry.key != expected_key:
            raise FeatureRuntimeViolation(
                "feature_abi_cache_key_mismatch",
                "cached Feature ABI entry does not match the requested Contract DAG",
            )
        if (
            entry.header_digest != entry.package.header.header_digest
            or entry.package_digest != entry.package.package_digest
        ):
            raise FeatureRuntimeViolation(
                "feature_abi_cache_identity_mutated",
                "cached Feature ABI header or package identity changed after insertion",
            )
        if entry.package.values.flags.writeable:
            raise FeatureRuntimeViolation(
                "feature_abi_cache_buffer_writeable",
                "cached Feature ABI values buffer must remain read-only",
            )
        FeatureABIVerifier().verify(entry.package)
        self._verify_package_bindings(entry.package, expected_key=expected_key)

    @staticmethod
    def _verify_package_bindings(
        package: FeatureABIPackage,
        *,
        expected_key: FeatureABICacheKey,
    ) -> None:
        header = package.header
        actual = {
            "window_artifact_digest": header.window_artifact_digest,
            "candidate_package_digest": header.candidate_package_digest,
            "candidate_static_digest": header.candidate_static_digest,
            "target_context_digest": header.target_context_digest,
            "start": header.start,
            "end": header.end,
            "feature_abi": header.abi_version,
            "feature_layout_digest": header.layout_digest,
            "feature_manifest_digest": header.component_manifest_digest,
        }
        expected = {
            "window_artifact_digest": expected_key.window_artifact_digest,
            "candidate_package_digest": expected_key.candidate_package_digest,
            "candidate_static_digest": expected_key.candidate_static_digest,
            "target_context_digest": expected_key.target_context_digest,
            "start": expected_key.start,
            "end": expected_key.end,
            "feature_abi": expected_key.feature_abi,
            "feature_layout_digest": expected_key.feature_layout_digest,
            "feature_manifest_digest": expected_key.feature_manifest_digest,
        }
        if actual != expected:
            raise FeatureRuntimeViolation(
                "feature_abi_cache_binding_mismatch",
                "compiled Feature ABI package does not match the cache key",
            )

    def _drop_feature_entry(self, cache_key: str, *, invalidated: bool) -> None:
        entry = self._feature_entries.pop(cache_key, None)
        if entry is not None:
            self._payload_bytes -= entry.payload_bytes
            dependent_runtime_keys = [
                runtime_key
                for runtime_key, runtime_entry in self._runtime_entries.items()
                if any(
                    package.package_digest == entry.package.package_digest
                    for package in runtime_entry.verified_runtime.runtime.feature_tiles
                )
            ]
            for runtime_key in dependent_runtime_keys:
                self._runtime_entries.pop(runtime_key, None)
                self._evictions += 1
            if invalidated:
                self._invalidations += 1

    def _evict_feature_entries(self) -> None:
        while (
            len(self._feature_entries) > self.max_entries
            or self._payload_bytes > self.max_payload_bytes
        ):
            cache_key = next(iter(self._feature_entries))
            self._drop_feature_entry(cache_key, invalidated=False)
            self._evictions += 1

    @staticmethod
    def _runtime_key(runtime: FeatureABIRuntime) -> str:
        return canonical_digest(
            {
                "protocol": RUNTIME_ABI_CACHE_PROTOCOL,
                "verifier_version": UNIFIED_RUNTIME_VERIFIER_VERSION,
                "runtime_digest": runtime.runtime_digest,
                "history_snapshot_digest": runtime.history_snapshot.history_digest,
                "window_artifact_digest": runtime.window_artifact.artifact_digest,
                "candidate_package_digest": runtime.candidate_package.package_digest,
                "feature_package_digests": [
                    package.package_digest for package in runtime.feature_tiles
                ],
            },
            domain="dehps.runtime-abi-cache.verified-runtime-key.v1",
        )


__all__ = [
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_MAX_PAYLOAD_BYTES",
    "RUNTIME_ABI_CACHE_PROTOCOL",
    "FeatureABICacheKey",
    "FeatureABICacheReceipt",
    "RuntimeABICache",
    "RuntimeABICacheCompilation",
    "RuntimeABICacheStats",
]
