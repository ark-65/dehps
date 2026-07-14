from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dehps.research_evidence.models import ArtifactValidationReport, file_hash, stable_hash


REQUIRED_ARTIFACTS = (
    "manifest.json",
    "issue_windows.json",
    "search_results.json",
    "frozen_results.json",
    "statistics.json",
    "validation_report.json",
    "execution_summary.md",
)
OPTIONAL_FORMAL_ARTIFACTS = ("per_issue_results.jsonl", "strata_thresholds.json", "ranker_versions.json")


class Round24ArtifactReader:
    def read(
        self,
        artifact_directory: Path,
        *,
        expected_plan_fingerprint: str | None = None,
        expected_hypothesis_key: str | None = None,
        expected_plan_key: str | None = None,
    ) -> ArtifactValidationReport:
        checks: list[dict[str, Any]] = []
        failures: list[str] = []

        def check(key: str, passed: bool, reason: str) -> None:
            checks.append({"key": key, "passed": passed, "reason": reason})
            if not passed:
                failures.append(reason)

        artifact_directory = artifact_directory.resolve()
        manifest_path = artifact_directory / "manifest.json"
        check("manifest_exists", manifest_path.is_file(), "manifest.json must exist")
        if not manifest_path.is_file():
            return ArtifactValidationReport(
                valid=False,
                artifact_directory=artifact_directory.as_posix(),
                plan_key="",
                plan_fingerprint="",
                hypothesis_key="",
                manifest_hash="",
                checks=tuple(checks),
                failure_reasons=tuple(failures),
            )

        manifest = _read_json(manifest_path)
        manifest_hash = file_hash(manifest_path)
        _validate_content_hash(manifest, "manifest", check)
        artifacts = {
            Path(str(item.get("path", ""))).name: dict(item)
            for item in manifest.get("artifacts", [])
            if isinstance(item, dict)
        }
        for filename in REQUIRED_ARTIFACTS:
            path = artifact_directory / filename
            check(f"{filename}:exists", path.is_file(), f"{filename} must exist")
            if filename == "manifest.json":
                continue
            entry = artifacts.get(filename)
            check(f"{filename}:manifest_entry", entry is not None, f"{filename} must be listed in manifest")
            if path.is_file() and entry is not None:
                check(
                    f"{filename}:hash",
                    file_hash(path) == entry.get("content_hash"),
                    f"{filename} hash must match manifest",
                )

        loaded: dict[str, Any] = {"manifest": manifest}
        for filename in REQUIRED_ARTIFACTS:
            if filename.endswith(".json") and filename != "manifest.json":
                payload = _read_json(artifact_directory / filename)
                _validate_content_hash(payload, filename, check)
                loaded[filename.removesuffix(".json")] = payload
        per_issue_path = artifact_directory / "per_issue_results.jsonl"
        if per_issue_path.is_file():
            entry = artifacts.get("per_issue_results.jsonl")
            check("per_issue_results:manifest_entry", entry is not None, "per_issue_results.jsonl must be listed when present")
            if entry is not None:
                check(
                    "per_issue_results:hash",
                    file_hash(per_issue_path) == entry.get("content_hash"),
                    "per_issue_results.jsonl hash must match manifest",
                )
            loaded["per_issue_results"] = [_read_json_line(line) for line in per_issue_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        plan_key = str(manifest.get("plan_key") or "")
        plan_fingerprint = str(manifest.get("plan_fingerprint") or "")
        hypothesis_key = str(manifest.get("hypothesis_key") or "")
        if expected_plan_key is not None:
            check("plan_key", plan_key == expected_plan_key, "plan key must match expected plan")
        if expected_plan_fingerprint is not None:
            check("plan_fingerprint", plan_fingerprint == expected_plan_fingerprint, "plan fingerprint must match expected plan")
        if expected_hypothesis_key is not None:
            check("hypothesis_key", hypothesis_key == expected_hypothesis_key, "hypothesis key must match expected hypothesis")

        windows = loaded.get("issue_windows", {}).get("payload", {})
        search = list(windows.get("search_issues") or [])
        frozen = list(windows.get("frozen_issues") or [])
        check("search_count", len(search) == int(windows.get("search_issue_count", 100)), "search issue count must match artifact")
        check("frozen_count", len(frozen) == int(windows.get("frozen_issue_count", 20)), "frozen issue count must match artifact")
        check("window_overlap", not (set(search) & set(frozen)), "search and frozen windows must not overlap")

        for key in ("search_results", "frozen_results", "statistics", "validation_report"):
            payload = dict(loaded.get(key, {}).get("payload", {}))
            check(
                f"{key}:plan_fingerprint",
                str(loaded.get(key, {}).get("plan_fingerprint") or plan_fingerprint) == plan_fingerprint,
                f"{key} plan fingerprint must match manifest",
            )
            check(f"{key}:payload_present", bool(payload), f"{key} payload must be present")

        validation_valid = bool(loaded.get("validation_report", {}).get("payload", {}).get("valid"))
        check("round24_validation_report", validation_valid, "Round 24 validation report must be valid")

        return ArtifactValidationReport(
            valid=not failures,
            artifact_directory=artifact_directory.as_posix(),
            plan_key=plan_key,
            plan_fingerprint=plan_fingerprint,
            hypothesis_key=hypothesis_key,
            manifest_hash=manifest_hash,
            checks=tuple(checks),
            failure_reasons=tuple(failures),
            loaded_artifacts=loaded,
        )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact must be a JSON object: {path}")
    return value


def _read_json_line(line: str) -> dict[str, Any]:
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("per-issue artifact line must be a JSON object")
    return value


def _validate_content_hash(payload: dict[str, Any], label: str, check) -> None:
    content_hash = payload.get("content_hash")
    if not content_hash:
        check(f"{label}:content_hash_present", False, f"{label} must include content_hash")
        return
    comparable = {key: value for key, value in payload.items() if key != "content_hash"}
    check(f"{label}:content_hash", stable_hash(comparable) == content_hash, f"{label} content_hash must verify")
