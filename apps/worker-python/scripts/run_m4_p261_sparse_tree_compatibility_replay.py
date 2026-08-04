from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
P261_MANIFEST = ROOT / (
    "configs/research-os/"
    "m4-information-theory-p2-6-1-measurement-validation-v1.json"
)
SYNTHETIC_MANIFEST = ROOT / (
    "configs/research-os/"
    "m4-information-theory-p2-synthetic-run-manifest-v1.0.1.json"
)
PREREGISTRATION = ROOT / (
    "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)
HARNESS = ROOT / (
    "configs/research-os/m4-information-theory-walk-forward-harness-v1.json"
)
RESAMPLING = ROOT / (
    "configs/research-os/m4-information-theory-p2-5-resampling-kernel-v1.json"
)
FIXTURE_GIT_COMMIT = "70f83a5400c6207cbe3806e69329a233e461e311"
SCHEMA = "dehps-m4-p2-6-1-sparse-tree-compatibility-replay.v1"


def _inputs() -> tuple[Any, Any, Any]:
    from dehps.research_os.information_theory.measurement_validation import (
        golden_full_replicate,
        load_repaired_measurement_validation_manifest,
    )
    from dehps.research_os.information_theory.synthetic import (
        load_synthetic_run_manifest,
    )

    manifest = load_repaired_measurement_validation_manifest(P261_MANIFEST)
    synthetic = load_synthetic_run_manifest(SYNTHETIC_MANIFEST)
    return manifest, synthetic, golden_full_replicate(
        manifest=manifest,
        synthetic=synthetic,
    )


def _write_capture(
    *,
    mode: str,
    result_payload: Any,
    fold_traces: Any,
    journal: bytes,
    destination: Path,
    acceleration_backend_imported: bool,
) -> None:
    from dehps.research_os.information_theory.measurement_validation.float_identity import (
        encode_float64_tree,
    )

    payload = {
        "schema_version": SCHEMA,
        "mode": mode,
        "result_payload_float64_tree": encode_float64_tree(result_payload),
        "fold_traces_float64_tree": encode_float64_tree(fold_traces),
        "checkpoint_journal_utf8": journal.decode("utf-8"),
        "fold_count": len(fold_traces),
        "acceleration_backend_imported": acceleration_backend_imported,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _run_literal(*, output_dir: Path, capture_path: Path) -> None:
    from dehps.research_os.information_theory.measurement_validation.golden_reference import (
        PythonReferenceReplicateEvaluator,
    )

    manifest, synthetic, replicate = _inputs()
    evaluator = PythonReferenceReplicateEvaluator.from_paths(
        manifest=manifest,
        synthetic=synthetic,
        preregistration_path=PREREGISTRATION,
        walk_forward_harness_path=HARNESS,
        resampling_path=RESAMPLING,
        truth_by_scenario={},
        fixture_git_commit=FIXTURE_GIT_COMMIT,
        output_dir=output_dir,
    )
    evaluation = evaluator.evaluate(replicate)
    backend_imported = any(
        name.endswith(".probes.runtime_cache_backend") for name in sys.modules
    )
    if backend_imported:
        raise RuntimeError("literal_replay_imported_acceleration_backend")
    _write_capture(
        mode="literal",
        result_payload=evaluation.result_payload,
        fold_traces=evaluation.fold_traces,
        journal=evaluation.checkpoint_journal_bytes,
        destination=capture_path,
        acceleration_backend_imported=False,
    )


def _run_observed(*, output_dir: Path, capture_path: Path) -> None:
    from dehps.research_os.information_theory.measurement_validation.reference import (
        ReferenceReplicateEvaluator,
    )

    manifest, synthetic, replicate = _inputs()
    traces: list[dict[str, Any]] = []
    evaluator = ReferenceReplicateEvaluator.from_paths(
        manifest=manifest,
        synthetic=synthetic,
        preregistration_path=PREREGISTRATION,
        walk_forward_harness_path=HARNESS,
        resampling_path=RESAMPLING,
        truth_by_scenario={},
        git_commit=FIXTURE_GIT_COMMIT,
        output_dir=output_dir,
        trace_records=traces,
    )
    result = evaluator.evaluate(replicate)
    journal_path = output_dir / str(result["checkpoint_journal_path"])
    _write_capture(
        mode="observed",
        result_payload=result,
        fold_traces=traces,
        journal=journal_path.read_bytes(),
        destination=capture_path,
        acceleration_backend_imported=any(
            name.endswith(".probes.runtime_cache_backend") for name in sys.modules
        ),
    )


def _load_capture(path: Path, *, expected_mode: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA
        or payload.get("mode") != expected_mode
        or payload.get("fold_count") != 61
        or not isinstance(payload.get("result_payload_float64_tree"), dict)
        or not isinstance(payload.get("fold_traces_float64_tree"), list)
        or not isinstance(payload.get("checkpoint_journal_utf8"), str)
    ):
        raise RuntimeError(f"invalid_{expected_mode}_compatibility_capture")
    return payload


def _compare(*, literal_path: Path, observed_path: Path) -> None:
    from dehps.contracts import canonical_digest

    literal = _load_capture(literal_path, expected_mode="literal")
    observed = _load_capture(observed_path, expected_mode="observed")
    if literal.get("acceleration_backend_imported") is not False:
        raise RuntimeError("literal_replay_imported_acceleration_backend")
    for field, error in (
        ("result_payload_float64_tree", "result_payload_changed"),
        ("fold_traces_float64_tree", "fold_traces_changed"),
        ("checkpoint_journal_utf8", "checkpoint_journal_bytes_changed"),
    ):
        if literal[field] != observed[field]:
            raise RuntimeError(error)
    journal = literal["checkpoint_journal_utf8"].encode("utf-8")
    summary = {
        "schema_version": SCHEMA,
        "status": "EXACT_COMPATIBILITY_VERIFIED",
        "fold_count": 61,
        "result_float64_tree_digest": canonical_digest(
            literal["result_payload_float64_tree"],
            domain="dehps.m4.p2-6-1.round6.result-float64-tree.v1",
        ),
        "trace_set_digest": canonical_digest(
            literal["fold_traces_float64_tree"],
            domain="dehps.m4.p2-6-1.round6.fold-traces-float64-tree.v1",
        ),
        "checkpoint_journal_sha256": sha256(journal).hexdigest(),
        "checkpoint_journal_byte_count": len(journal),
        "result_object_exact": True,
        "probability_bits_exact": True,
        "probe_state_trees_exact": True,
        "fold_traces_exact": True,
        "checkpoint_and_settlement_exact": True,
        "journal_bytes_exact": True,
        "literal_acceleration_backend_imported": False,
        "observed_acceleration_backend_imported": observed.get(
            "acceleration_backend_imported"
        ),
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for mode in ("literal", "observed"):
        command = subparsers.add_parser(mode)
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--capture", type=Path, required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--literal", type=Path, required=True)
    compare.add_argument("--observed", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "literal":
        _run_literal(output_dir=args.output_dir, capture_path=args.capture)
    elif args.command == "observed":
        _run_observed(output_dir=args.output_dir, capture_path=args.capture)
    else:
        _compare(literal_path=args.literal, observed_path=args.observed)


if __name__ == "__main__":
    main()
