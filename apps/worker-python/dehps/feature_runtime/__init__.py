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
    feature_array_digest,
)

__all__ = [
    "FEATURE_ABI_GOLDEN_SUITE",
    "FEATURE_ABI_LAYOUT_DEFINITION",
    "FEATURE_ABI_LAYOUT_DIGEST",
    "FEATURE_ABI_VERSION",
    "FEATURE_COMPILER_VERSION",
    "CompiledFeatureArtifact",
    "FeatureABICompiler",
    "FeatureABIHeader",
    "FeatureABIPackage",
    "FeatureABIVerifier",
    "FeatureArtifactHeader",
    "FeatureArtifactVerifier",
    "FeatureBufferMetadata",
    "FeatureCompileRequest",
    "FeatureCompiler",
    "FeatureRuntimeEnvelope",
    "FeatureRuntimeViolation",
    "feature_array_digest",
]
