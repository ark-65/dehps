from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dehps.artifacts import atomic_write_text
from dehps.contracts import canonical_digest


DRAW_SYNC_WATCH_LAUNCH_VERSION = "draw-sync-watch-launch.v1"
_DIGEST_DOMAIN = "dehps.draw-sync-watch-launch.v1"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class DrawSyncWatchLaunchViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": self.context}


def build_draw_sync_watch_launch_contract(
    *,
    code_commit: str,
    interval_seconds: int,
    hot_interval_seconds: int,
    cold_interval_seconds: int,
    timezone: str,
    resume_on_event: bool,
    shadow_attestation_enabled: bool,
) -> dict[str, Any]:
    payload = {
        "protocol": DRAW_SYNC_WATCH_LAUNCH_VERSION,
        "code_commit": str(code_commit),
        "schedule": {
            "interval_seconds": int(interval_seconds),
            "hot_interval_seconds": int(hot_interval_seconds),
            "cold_interval_seconds": int(cold_interval_seconds),
            "timezone": str(timezone),
        },
        "resume_on_event": bool(resume_on_event),
        "shadow_attestation_enabled": bool(shadow_attestation_enabled),
        "automatic_promotion_allowed": False,
    }
    payload["contract_digest"] = canonical_digest(payload, domain=_DIGEST_DOMAIN)
    verify_draw_sync_watch_launch_contract(payload)
    return payload


def verify_draw_sync_watch_launch_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("protocol") != DRAW_SYNC_WATCH_LAUNCH_VERSION:
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_protocol_mismatch",
            "unsupported draw-sync watcher launch contract",
        )
    commit = str(contract.get("code_commit") or "")
    if _COMMIT_PATTERN.fullmatch(commit) is None:
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_commit_invalid",
            "launch contract requires a full lowercase Git commit",
        )
    schedule = contract.get("schedule")
    if not isinstance(schedule, Mapping):
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_schedule_missing",
            "launch contract requires a structured schedule",
        )
    for field in ("interval_seconds", "hot_interval_seconds", "cold_interval_seconds"):
        value = schedule.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise DrawSyncWatchLaunchViolation(
                "draw_sync_watch_launch_interval_invalid",
                "all launch intervals must be positive integers",
                field=field,
                value=value,
            )
    timezone = str(schedule.get("timezone") or "")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_timezone_invalid",
            "launch contract timezone is not available",
            timezone=timezone,
        ) from None
    for field in (
        "resume_on_event",
        "shadow_attestation_enabled",
        "automatic_promotion_allowed",
    ):
        if not isinstance(contract.get(field), bool):
            raise DrawSyncWatchLaunchViolation(
                "draw_sync_watch_launch_boolean_invalid",
                "launch contract flags must be booleans",
                field=field,
            )
    if contract.get("automatic_promotion_allowed") is not False:
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_promotion_authority_invalid",
            "watcher launch contract cannot authorize promotion",
        )
    expected = canonical_digest(
        {key: value for key, value in contract.items() if key != "contract_digest"},
        domain=_DIGEST_DOMAIN,
    )
    if contract.get("contract_digest") != expected:
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_digest_mismatch",
            "watcher launch contract seal does not match its configuration",
        )


def write_draw_sync_watch_launch_contract(
    path: Path,
    contract: Mapping[str, Any],
) -> None:
    verify_draw_sync_watch_launch_contract(contract)
    atomic_write_text(
        path,
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def load_draw_sync_watch_launch_contract(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_file_invalid",
            "watcher launch contract file cannot be read",
            path=str(path),
            error=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise DrawSyncWatchLaunchViolation(
            "draw_sync_watch_launch_file_invalid",
            "watcher launch contract file must contain a JSON object",
            path=str(path),
        )
    verify_draw_sync_watch_launch_contract(payload)
    return payload


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError("expected a boolean value")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify a draw-sync watcher launch contract.",
    )
    parser.add_argument("--verify-file", type=Path)
    parser.add_argument("--code-commit")
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--hot-interval-seconds", type=int, default=300)
    parser.add_argument("--cold-interval-seconds", type=int, default=3600)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--resume-on-event", type=_bool, default=False)
    parser.add_argument("--shadow-attestation-enabled", type=_bool, default=False)
    parser.add_argument("--digest-only", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_file is not None:
        contract = load_draw_sync_watch_launch_contract(args.verify_file)
    else:
        if not args.code_commit:
            parser.error("--code-commit is required unless --verify-file is used")
        contract = build_draw_sync_watch_launch_contract(
            code_commit=args.code_commit,
            interval_seconds=args.interval_seconds,
            hot_interval_seconds=args.hot_interval_seconds,
            cold_interval_seconds=args.cold_interval_seconds,
            timezone=args.timezone,
            resume_on_event=args.resume_on_event,
            shadow_attestation_enabled=args.shadow_attestation_enabled,
        )
    print(
        contract["contract_digest"]
        if args.digest_only
        else json.dumps(contract, ensure_ascii=False, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
