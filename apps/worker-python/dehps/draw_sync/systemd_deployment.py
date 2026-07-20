from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest


DRAW_SYNC_SYSTEMD_DEPLOYMENT_VERSION = "draw-sync-systemd-deployment.v1"
_DIGEST_DOMAIN = "dehps.draw-sync-systemd-deployment.v1"
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_ENV_KEYS = (
    "DEHPS_FORWARD_SHADOW_ATTESTATION",
    "DEHPS_FORWARD_SHADOW_CAPTURE",
    "DEHPS_FORWARD_SHADOW_WORKERS",
)


class DrawSyncSystemdDeploymentViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": self.context}


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_source_unreadable",
            "systemd deployment source cannot be read",
            path=str(path),
            error=str(exc),
        ) from exc


def _environment_payload(
    *,
    shadow_attestation_enabled: bool,
    shadow_capture_enabled: bool,
    shadow_worker_count: int,
) -> dict[str, Any]:
    return {
        "shadow_attestation_enabled": bool(shadow_attestation_enabled),
        "shadow_capture_enabled": bool(shadow_capture_enabled),
        "shadow_worker_count": int(shadow_worker_count),
        "automatic_promotion_allowed": False,
    }


def build_draw_sync_systemd_deployment_contract(
    *,
    code_commit: str,
    unit_path: Path,
    timer_path: Path,
    launch_contract_digest: str,
    shadow_attestation_enabled: bool,
    shadow_capture_enabled: bool,
    shadow_worker_count: int,
) -> dict[str, Any]:
    contract = {
        "protocol": DRAW_SYNC_SYSTEMD_DEPLOYMENT_VERSION,
        "supervisor": "systemd_user",
        "unit_name": "dehps-draw-sync.service",
        "timer_name": "dehps-draw-sync.timer",
        "code_commit": str(code_commit),
        "unit_digest": _file_digest(unit_path),
        "timer_digest": _file_digest(timer_path),
        "launch_contract_digest": str(launch_contract_digest),
        "environment": _environment_payload(
            shadow_attestation_enabled=shadow_attestation_enabled,
            shadow_capture_enabled=shadow_capture_enabled,
            shadow_worker_count=shadow_worker_count,
        ),
    }
    contract["contract_digest"] = canonical_digest(contract, domain=_DIGEST_DOMAIN)
    verify_draw_sync_systemd_deployment_contract(contract)
    return contract


def verify_draw_sync_systemd_deployment_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("protocol") != DRAW_SYNC_SYSTEMD_DEPLOYMENT_VERSION:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_protocol_mismatch",
            "unsupported draw-sync systemd deployment contract",
        )
    if contract.get("supervisor") != "systemd_user":
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_supervisor_invalid",
            "deployment contract requires systemd_user ownership",
        )
    if contract.get("unit_name") != "dehps-draw-sync.service" or contract.get(
        "timer_name"
    ) != "dehps-draw-sync.timer":
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_unit_identity_invalid",
            "deployment contract unit identities are not canonical",
        )
    if _COMMIT_PATTERN.fullmatch(str(contract.get("code_commit") or "")) is None:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_commit_invalid",
            "deployment contract requires a full lowercase Git commit",
        )
    for field in ("unit_digest", "timer_digest", "launch_contract_digest"):
        if _DIGEST_PATTERN.fullmatch(str(contract.get(field) or "")) is None:
            raise DrawSyncSystemdDeploymentViolation(
                "draw_sync_systemd_digest_invalid",
                "deployment digests must be lowercase SHA-256 values",
                field=field,
            )
    environment = contract.get("environment")
    if not isinstance(environment, Mapping):
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_environment_missing",
            "deployment contract requires a structured environment",
        )
    for field in (
        "shadow_attestation_enabled",
        "shadow_capture_enabled",
        "automatic_promotion_allowed",
    ):
        if not isinstance(environment.get(field), bool):
            raise DrawSyncSystemdDeploymentViolation(
                "draw_sync_systemd_environment_invalid",
                "deployment environment flags must be booleans",
                field=field,
            )
    worker_count = environment.get("shadow_worker_count")
    if isinstance(worker_count, bool) or not isinstance(worker_count, int) or worker_count < 1:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_worker_count_invalid",
            "shadow worker count must be a positive integer",
        )
    if environment.get("automatic_promotion_allowed") is not False:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_promotion_authority_invalid",
            "draw-sync deployment cannot authorize promotion",
        )
    expected = canonical_digest(
        {key: value for key, value in contract.items() if key != "contract_digest"},
        domain=_DIGEST_DOMAIN,
    )
    if contract.get("contract_digest") != expected:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_contract_digest_mismatch",
            "deployment contract seal does not match its payload",
        )


def draw_sync_systemd_environment_text(contract: Mapping[str, Any]) -> str:
    verify_draw_sync_systemd_deployment_contract(contract)
    environment = contract["environment"]
    values = {
        "DEHPS_FORWARD_SHADOW_ATTESTATION": str(
            environment["shadow_attestation_enabled"]
        ).lower(),
        "DEHPS_FORWARD_SHADOW_CAPTURE": str(
            environment["shadow_capture_enabled"]
        ).lower(),
        "DEHPS_FORWARD_SHADOW_WORKERS": str(environment["shadow_worker_count"]),
    }
    return "".join(f"{key}={values[key]}\n" for key in _ENV_KEYS)


def write_draw_sync_systemd_environment(path: Path, contract: Mapping[str, Any]) -> None:
    atomic_write_text(path, draw_sync_systemd_environment_text(contract))


def verify_draw_sync_systemd_environment(path: Path, contract: Mapping[str, Any]) -> None:
    try:
        observed = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_environment_unreadable",
            "dedicated draw-sync environment cannot be read",
            path=str(path),
            error=str(exc),
        ) from exc
    expected = draw_sync_systemd_environment_text(contract)
    if observed != expected:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_environment_mismatch",
            "dedicated draw-sync environment differs from the approved contract",
            path=str(path),
        )


def write_draw_sync_systemd_deployment_contract(
    path: Path,
    contract: Mapping[str, Any],
) -> None:
    verify_draw_sync_systemd_deployment_contract(contract)
    atomic_write_text(
        path,
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def load_draw_sync_systemd_deployment_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_contract_file_invalid",
            "deployment contract file cannot be read",
            path=str(path),
            error=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise DrawSyncSystemdDeploymentViolation(
            "draw_sync_systemd_contract_file_invalid",
            "deployment contract file must contain an object",
            path=str(path),
        )
    verify_draw_sync_systemd_deployment_contract(payload)
    return payload


def verify_draw_sync_systemd_sources(
    contract: Mapping[str, Any],
    *,
    unit_path: Path,
    timer_path: Path,
    environment_path: Path | None = None,
) -> None:
    verify_draw_sync_systemd_deployment_contract(contract)
    for field, path in (("unit_digest", unit_path), ("timer_digest", timer_path)):
        if _file_digest(path) != contract[field]:
            raise DrawSyncSystemdDeploymentViolation(
                "draw_sync_systemd_installed_source_mismatch",
                "installed systemd source differs from the deployment contract",
                field=field,
                path=str(path),
            )
    if environment_path is not None:
        verify_draw_sync_systemd_environment(environment_path, contract)


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError("expected a boolean value")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify the draw-sync systemd deployment contract.",
    )
    parser.add_argument("--verify-file", type=Path)
    parser.add_argument("--code-commit")
    parser.add_argument("--unit-path", type=Path)
    parser.add_argument("--timer-path", type=Path)
    parser.add_argument("--environment-path", type=Path)
    parser.add_argument("--launch-contract-digest")
    parser.add_argument("--shadow-attestation-enabled", type=_bool, default=False)
    parser.add_argument("--shadow-capture-enabled", type=_bool, default=True)
    parser.add_argument("--shadow-worker-count", type=int, default=8)
    parser.add_argument("--write-environment", type=Path)
    parser.add_argument("--write-contract", type=Path)
    parser.add_argument("--digest-only", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_file is not None:
        contract = load_draw_sync_systemd_deployment_contract(args.verify_file)
        if args.unit_path is not None or args.timer_path is not None:
            if args.unit_path is None or args.timer_path is None:
                parser.error("--unit-path and --timer-path are required together")
            verify_draw_sync_systemd_sources(
                contract,
                unit_path=args.unit_path,
                timer_path=args.timer_path,
                environment_path=args.environment_path,
            )
    else:
        for field, value in (
            ("--code-commit", args.code_commit),
            ("--unit-path", args.unit_path),
            ("--timer-path", args.timer_path),
            ("--launch-contract-digest", args.launch_contract_digest),
        ):
            if value is None:
                parser.error(f"{field} is required unless --verify-file is used")
        contract = build_draw_sync_systemd_deployment_contract(
            code_commit=args.code_commit,
            unit_path=args.unit_path,
            timer_path=args.timer_path,
            launch_contract_digest=args.launch_contract_digest,
            shadow_attestation_enabled=args.shadow_attestation_enabled,
            shadow_capture_enabled=args.shadow_capture_enabled,
            shadow_worker_count=args.shadow_worker_count,
        )
    if args.write_environment is not None:
        write_draw_sync_systemd_environment(args.write_environment, contract)
    if args.write_contract is not None:
        write_draw_sync_systemd_deployment_contract(args.write_contract, contract)
    print(contract["contract_digest"] if args.digest_only else json.dumps(contract, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
