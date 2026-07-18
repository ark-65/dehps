from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import itertools

import numpy as np
import pytest

import dehps.feature_runtime.abi as feature_abi_module
import dehps.feature_runtime.compiler as feature_compiler_module
import dehps.feature_runtime.producer as feature_producer_module
from dehps.feature_runtime import (
    FEATURE_ABI_DIRECT_PRODUCER_VERSION,
    DirectFeatureABIProducer,
    FeatureABIVerifier,
    FeatureCompileRequest,
    FeatureRuntimeViolation,
    RuntimeABICache,
    StagedFeatureABIProducer,
    feature_artifact_digest,
)
from dehps.input_contracts import HistorySnapshotArtifact, WindowMode, WindowSpec
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.scoring_kernel import candidate_store_from_matrix
from dehps.scoring_kernel.numpy_backend import component_tile


def _case(candidate_count: int = 600):
    combinations = list(
        itertools.islice(itertools.combinations(range(1, 34), 6), candidate_count)
    )
    matrix = build_ranked_universe(
        combinations,
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    store = candidate_store_from_matrix(matrix)
    start_date = date(2026, 1, 1)
    history = [
        (
            f"2025{index:03d}",
            start_date + timedelta(days=index),
            tuple(int(number) for number in row),
        )
        for index, row in enumerate(matrix.numbers[50:450:20], start=1)
    ]
    snapshot = HistorySnapshotArtifact.from_history(history)
    expanding = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue=history[-1][0],
        include_as_of=True,
        size=None,
        target_issue="2026051",
    ).materialize(snapshot)
    rolling = WindowSpec(
        mode=WindowMode.ROLLING,
        as_of_issue=history[-1][0],
        include_as_of=True,
        size=10,
        target_issue="2026051",
    ).materialize(snapshot)
    return snapshot, expanding, rolling, store


@pytest.mark.parametrize("row_range", [(0, 0), (0, 1), (0, 257), (257, 600)])
@pytest.mark.parametrize("window_name", ["expanding", "rolling"])
@pytest.mark.parametrize("with_target_date", [False, True])
def test_direct_feature_abi_producer_is_exact_staged_identity(
    row_range,
    window_name,
    with_target_date,
) -> None:
    _, expanding, rolling, store = _case()
    window = expanding if window_name == "expanding" else rolling
    target_draw_date = (
        max(record.draw_date for record in window.records) + timedelta(days=1)
        if with_target_date
        else None
    )
    request = FeatureCompileRequest(
        window=window,
        candidate_store=store,
        start=row_range[0],
        end=row_range[1],
        target_draw_date=target_draw_date,
    )
    produced_values = []

    def capture_component_buffer(*args):
        values = component_tile(*args)
        produced_values.append(values)
        return values

    direct = DirectFeatureABIProducer(
        component_producer=capture_component_buffer
    ).produce(request)
    staged = StagedFeatureABIProducer().produce(request)

    assert len(produced_values) == 1
    assert direct.package.values is produced_values[0]
    assert direct.source_header == staged.source_header
    assert direct.source_artifact_digest == staged.source_artifact_digest
    assert direct.package.header == staged.package.header
    assert direct.package.package_digest == staged.package.package_digest
    assert np.array_equal(direct.package.values, staged.package.values)
    assert direct.payload_materializations == 1
    assert direct.abi_buffer_copied is False
    FeatureABIVerifier().verify(direct.package)


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        (lambda values: values.astype(np.float32), "dtype_mismatch"),
        (lambda values: values[:, ::-1], "not_contiguous"),
        (
            lambda values: np.where(
                np.indices(values.shape)[0] == 0,
                np.nan,
                values,
            ),
            "non_finite",
        ),
    ],
)
def test_direct_feature_abi_producer_rejects_nonconforming_component_output(
    mutation,
    error_code,
) -> None:
    _, window, _, store = _case()

    def malformed(*args):
        return mutation(component_tile(*args))

    producer = DirectFeatureABIProducer(component_producer=malformed)
    with pytest.raises(FeatureRuntimeViolation, match=error_code):
        producer.produce(
            FeatureCompileRequest(
                window=window,
                candidate_store=store,
                start=0,
                end=100,
            )
        )


def test_runtime_cache_rejects_forged_direct_producer_receipt() -> None:
    _, window, _, store = _case()

    class ForgedReceiptProducer(DirectFeatureABIProducer):
        def produce(self, request):
            return replace(
                super().produce(request),
                source_artifact_digest="f" * 64,
            )

    cache = RuntimeABICache(feature_producer=ForgedReceiptProducer())
    with pytest.raises(
        FeatureRuntimeViolation,
        match="feature_abi_cache_source_seal_mismatch",
    ):
        cache.compile_feature(
            FeatureCompileRequest(
                window=window,
                candidate_store=store,
                start=0,
                end=100,
            )
        )


def test_runtime_cache_recomputes_direct_source_artifact_payload_digest() -> None:
    _, window, _, store = _case()

    class ForgedArtifactPayloadProducer(DirectFeatureABIProducer):
        def produce(self, request):
            result = super().produce(request)
            forged_source = replace(result.source_header, values_digest="f" * 64)
            forged_digest = feature_artifact_digest(forged_source)
            forged_package = replace(
                result.package,
                header=replace(
                    result.package.header,
                    source_artifact_digest=forged_digest,
                ),
            )
            return replace(
                result,
                package=forged_package,
                source_header=forged_source,
                source_artifact_digest=forged_digest,
            )

    cache = RuntimeABICache(feature_producer=ForgedArtifactPayloadProducer())
    with pytest.raises(FeatureRuntimeViolation, match="feature_values_digest_mismatch"):
        cache.compile_feature(
            FeatureCompileRequest(
                window=window,
                candidate_store=store,
                start=0,
                end=100,
            )
        )


def test_runtime_cache_binds_producer_identity_but_preserves_runtime_identity() -> None:
    snapshot, window, _, store = _case()
    direct_cache = RuntimeABICache(feature_producer=DirectFeatureABIProducer())
    staged_cache = RuntimeABICache(feature_producer=StagedFeatureABIProducer())

    direct = direct_cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )
    staged = staged_cache.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=200,
    )

    assert direct.verified_runtime.verified_runtime_id == (
        staged.verified_runtime.verified_runtime_id
    )
    assert direct.source_artifact_payload_verification_passes == 3
    assert staged.source_artifact_payload_verification_passes == 3
    assert tuple(
        receipt.package.package_digest for receipt in direct.feature_receipts
    ) == tuple(receipt.package.package_digest for receipt in staged.feature_receipts)
    assert tuple(
        receipt.key.cache_key_digest for receipt in direct.feature_receipts
    ) != tuple(receipt.key.cache_key_digest for receipt in staged.feature_receipts)
    assert all(
        receipt.producer_version == FEATURE_ABI_DIRECT_PRODUCER_VERSION
        and receipt.payload_materializations == 1
        and receipt.abi_buffer_copied is False
        and receipt.package.values.flags.writeable is False
        for receipt in direct.feature_receipts
    )


def test_direct_producer_reduces_feature_digest_work_without_skipping_verifiers(
    monkeypatch,
) -> None:
    snapshot, window, _, store = _case()
    original = feature_compiler_module.feature_array_digest
    measurements = {"calls": 0, "bytes": 0}

    def measured_digest(array, *, domain):
        measurements["calls"] += 1
        measurements["bytes"] += int(array.nbytes)
        return original(array, domain=domain)

    monkeypatch.setattr(
        feature_compiler_module,
        "feature_array_digest",
        measured_digest,
    )
    monkeypatch.setattr(
        feature_abi_module,
        "feature_array_digest",
        measured_digest,
    )
    monkeypatch.setattr(
        feature_producer_module,
        "feature_array_digest",
        measured_digest,
    )

    direct = RuntimeABICache(feature_producer=DirectFeatureABIProducer())
    direct_compilation = direct.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=len(store),
    )
    direct_work = dict(measurements)
    measurements.update(calls=0, bytes=0)

    staged = RuntimeABICache(feature_producer=StagedFeatureABIProducer())
    staged_compilation = staged.compile_runtime(
        history_snapshot=snapshot,
        window=window,
        candidate_store=store,
        tile_size=len(store),
    )
    staged_work = dict(measurements)

    assert direct_compilation.feature_payload_verification_passes == 1
    assert direct_compilation.source_artifact_payload_verification_passes == 1
    assert direct_compilation.runtime_payload_verification_passes == 1
    assert staged_compilation.feature_payload_verification_passes == 1
    assert staged_compilation.source_artifact_payload_verification_passes == 1
    assert staged_compilation.runtime_payload_verification_passes == 1
    assert direct_work["calls"] < staged_work["calls"]
    assert direct_work["bytes"] < staged_work["bytes"]
