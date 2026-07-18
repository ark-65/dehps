"""Control-plane compilation of Feature Contracts into verifiable artifacts."""

from dehps.feature_runtime.abi import (
    FEATURE_ABI_GOLDEN_SUITE,
    FEATURE_ABI_LAYOUT_DEFINITION,
    FEATURE_ABI_LAYOUT_DIGEST,
    FEATURE_ABI_VERSION,
    FeatureABICompiler,
    FeatureABIHeader,
    FeatureABIPackage,
    FeatureABIVerifier,
    FeatureBufferMetadata,
    FeatureRuntimeEnvelope,
)
from dehps.feature_runtime.compiler import (
    FEATURE_COMPILER_VERSION,
    CompiledFeatureArtifact,
    FeatureArtifactHeader,
    FeatureArtifactVerifier,
    FeatureCompileRequest,
    FeatureCompiler,
    FeatureRuntimeViolation,
    candidate_static_digest,
    feature_array_digest,
)
from dehps.feature_runtime.cache import (
    RUNTIME_ABI_CACHE_PROTOCOL,
    FeatureABICacheKey,
    FeatureABICacheReceipt,
    RuntimeABICache,
    RuntimeABICacheCompilation,
    RuntimeABICacheStats,
)
from dehps.feature_runtime.runtime import FeatureABIRuntime, FeatureABIRuntimeVerifier

__all__ = [
    "FEATURE_ABI_GOLDEN_SUITE",
    "FEATURE_ABI_LAYOUT_DEFINITION",
    "FEATURE_ABI_LAYOUT_DIGEST",
    "FEATURE_ABI_VERSION",
    "FEATURE_COMPILER_VERSION",
    "RUNTIME_ABI_CACHE_PROTOCOL",
    "CompiledFeatureArtifact",
    "FeatureABICompiler",
    "FeatureABICacheKey",
    "FeatureABICacheReceipt",
    "FeatureABIHeader",
    "FeatureABIPackage",
    "FeatureABIRuntime",
    "FeatureABIRuntimeVerifier",
    "FeatureABIVerifier",
    "FeatureArtifactHeader",
    "FeatureArtifactVerifier",
    "FeatureBufferMetadata",
    "FeatureCompileRequest",
    "FeatureCompiler",
    "FeatureRuntimeEnvelope",
    "FeatureRuntimeViolation",
    "RuntimeABICache",
    "RuntimeABICacheCompilation",
    "RuntimeABICacheStats",
    "candidate_static_digest",
    "feature_array_digest",
]
