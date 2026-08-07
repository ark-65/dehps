from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2 import (
    runtime_audit as runtime_audit_module,
)
from dehps.research_os.information_theory.measurement_validation import (
    source_compatibility as compatibility_module,
)
from dehps.research_os.information_theory.measurement_validation.source_integrity import (
    APPROVED_ACCELERATION_SOURCE_PATHS,
    AUDIT_ORCHESTRATION_SOURCE_PATHS,
    BASELINE_GIT_COMMIT,
    INDEPENDENT_ORACLE_SOURCE_PATHS,
    SHARED_FROZEN_SOURCE_PATHS,
    content_sha256,
    git_blob_sha1,
    golden_source_integrity_identity,
    source_set_digest,
)

ROOT = Path(__file__).resolve().parents[3]
OLD_PLAN_PATH = (
    ROOT
    / "configs/research-os/m4-p2-9-measurement-runtime-audit-plan-v1.1.5.json"
)
NEW_PLAN_PATH = ROOT / runtime_audit_module.RUNTIME_AUDIT_PLAN_PATH
FIXTURE_PATH = (
    ROOT / compatibility_module.P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH
)
CANDIDATE_COMMIT = "0842201871aef856b97838c38bb53d536e1e5893"


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _entry(path: str, data: bytes) -> dict[str, str]:
    return {
        "path": path,
        "content_sha256": content_sha256(data),
        "git_blob_oid": git_blob_sha1(data),
    }


def _current_entries(paths: tuple[str, ...]) -> list[dict[str, str]]:
    return [_entry(path, (ROOT / path).read_bytes()) for path in paths]


def _commit_entries(commit: str, paths: tuple[str, ...]) -> list[dict[str, str]]:
    return [_entry(path, _git_bytes("show", f"{commit}:{path}")) for path in paths]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    old_plan = json.loads(OLD_PLAN_PATH.read_text(encoding="utf-8"))
    source = copy.deepcopy(old_plan["source_integrity_contract"])
    partitions = (
        (
            "shared_frozen_source_allowlist",
            "shared_frozen_source_set_digest",
            SHARED_FROZEN_SOURCE_PATHS,
            "shared-frozen",
        ),
        (
            "approved_acceleration_source_allowlist",
            "approved_acceleration_source_set_digest",
            APPROVED_ACCELERATION_SOURCE_PATHS,
            "approved-acceleration",
        ),
        (
            "independent_oracle_source_allowlist",
            "independent_oracle_source_set_digest",
            INDEPENDENT_ORACLE_SOURCE_PATHS,
            "independent-oracle",
        ),
        (
            "audit_orchestration_source_allowlist",
            "audit_orchestration_source_set_digest",
            AUDIT_ORCHESTRATION_SOURCE_PATHS,
            "audit-orchestration",
        ),
    )
    for allowlist_field, digest_field, paths, kind in partitions:
        entries = _current_entries(paths)
        source[allowlist_field] = entries
        source[digest_field] = source_set_digest(entries, kind=kind)
    source["reviewed_shared_compatibility_fixture_path"] = (
        compatibility_module.P263_REVIEWED_SOURCE_COMPATIBILITY_FIXTURE_PATH.as_posix()
    )
    source["reviewed_shared_compatibility_fixture_digest"] = "0" * 64
    source["reviewed_shared_compatibility_paths"] = list(
        compatibility_module.P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS
    )

    new_plan = copy.deepcopy(old_plan)
    new_plan["artifact_digest"] = ""
    new_plan["semantic_version"] = "1.1.6"
    new_plan["supersedes_artifact_digest"] = old_plan["artifact_digest"]
    new_plan["execution_policy"] = copy.deepcopy(
        runtime_audit_module._P263_EXECUTION_POLICY
    )
    new_plan["observed_phases"] = list(runtime_audit_module._P263_OBSERVED_PHASES)
    new_plan["source_integrity_contract"] = source
    new_plan["measurement_supersession_contract"] = copy.deepcopy(
        runtime_audit_module._P263_MEASUREMENT_SUPERSESSION_CONTRACT
    )
    new_plan["result_blind_contract"] = copy.deepcopy(
        runtime_audit_module._P263_RESULT_BLIND_CONTRACT
    )
    new_plan["periodic_refit_temporal_contract"] = copy.deepcopy(
        runtime_audit_module._P263_PERIODIC_REFIT_TEMPORAL_CONTRACT
    )

    fixture_paths = compatibility_module.P263_REVIEWED_SOURCE_COMPATIBILITY_PATHS
    candidate_entries = _commit_entries(CANDIDATE_COMMIT, fixture_paths)
    if candidate_entries != _current_entries(fixture_paths):
        raise RuntimeError(
            "P2.6.3 reviewed shared sources changed after the compatibility commit"
        )
    fixture: dict[str, Any] = {
        "schema_version": (
            compatibility_module.P263_REVIEWED_SOURCE_COMPATIBILITY_SCHEMA
        ),
        "artifact_type": (
            compatibility_module.P263_REVIEWED_SOURCE_COMPATIBILITY_TYPE
        ),
        "artifact_digest": "",
        "fixture_key": "M4-P2.6.3_PERIODIC_REFIT_SUPERSEDING_SOURCE",
        "status": "REVIEWED_RESULT_BLIND_COMPATIBILITY",
        "baseline_git_commit": BASELINE_GIT_COMMIT,
        "candidate_git_commit": CANDIDATE_COMMIT,
        "changed_paths": list(fixture_paths),
        "baseline_source_entries": _commit_entries(
            BASELINE_GIT_COMMIT,
            fixture_paths,
        ),
        "candidate_source_entries": candidate_entries,
        "registered_golden_source_integrity_identity": (
            golden_source_integrity_identity(old_plan)
        ),
        "candidate_golden_source_integrity_identity": (
            golden_source_integrity_identity(new_plan)
        ),
        "source_roles": copy.deepcopy(compatibility_module._P263_SOURCE_ROLES),
        "result_blind": copy.deepcopy(compatibility_module._P263_RESULT_BLIND),
        "periodic_refit_temporal_contract": copy.deepcopy(
            compatibility_module._P263_TEMPORAL_CONTRACT
        ),
        "governance": copy.deepcopy(compatibility_module._P263_GOVERNANCE),
    }
    fixture["artifact_digest"] = config_digest(fixture)
    source["reviewed_shared_compatibility_fixture_digest"] = fixture[
        "artifact_digest"
    ]
    new_plan["artifact_digest"] = config_digest(new_plan)
    return fixture, new_plan


def main() -> None:
    fixture, plan = build()
    _write_json(FIXTURE_PATH, fixture)
    _write_json(NEW_PLAN_PATH, plan)
    print(
        json.dumps(
            {
                "fixture_path": FIXTURE_PATH.relative_to(ROOT).as_posix(),
                "fixture_digest": fixture["artifact_digest"],
                "plan_path": NEW_PLAN_PATH.relative_to(ROOT).as_posix(),
                "plan_digest": plan["artifact_digest"],
                "source_counts": {
                    "shared": len(SHARED_FROZEN_SOURCE_PATHS),
                    "acceleration": len(APPROVED_ACCELERATION_SOURCE_PATHS),
                    "oracle": len(INDEPENDENT_ORACLE_SOURCE_PATHS),
                    "audit": len(AUDIT_ORCHESTRATION_SOURCE_PATHS),
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
