from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


DRAW_SYNC_SUPERVISOR_OWNERSHIP_VERSION = "draw-sync-supervisor-ownership.v1"
DEFAULT_SYSTEMD_UNIT = "dehps-draw-sync.service"
DEFAULT_SYSTEMD_TIMER = "dehps-draw-sync.timer"


class DrawSyncSupervisorOwnershipViolation(RuntimeError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": self.context}


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


def _value(
    runner: CommandRunner,
    *command: str,
) -> tuple[str, int]:
    result = runner(command)
    return result.stdout.strip(), int(result.returncode)


@dataclass(frozen=True)
class DrawSyncSupervisorOwnership:
    manager: str
    unit: str
    timer: str
    unit_load_state: str
    unit_active_state: str
    unit_file_state: str
    timer_load_state: str
    timer_active_state: str
    timer_file_state: str
    main_pid: int | None
    managed: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": DRAW_SYNC_SUPERVISOR_OWNERSHIP_VERSION,
            "manager": self.manager,
            "unit": self.unit,
            "timer": self.timer,
            "unit_load_state": self.unit_load_state,
            "unit_active_state": self.unit_active_state,
            "unit_file_state": self.unit_file_state,
            "timer_load_state": self.timer_load_state,
            "timer_active_state": self.timer_active_state,
            "timer_file_state": self.timer_file_state,
            "main_pid": self.main_pid,
            "managed": self.managed,
            "reasons": list(self.reasons),
            "manual_mutation_allowed": not self.managed,
        }


def inspect_draw_sync_supervisor_ownership(
    *,
    unit: str = DEFAULT_SYSTEMD_UNIT,
    timer: str = DEFAULT_SYSTEMD_TIMER,
    runner: CommandRunner = _run,
) -> DrawSyncSupervisorOwnership:
    unit_load, unit_load_rc = _value(
        runner,
        "systemctl",
        "--user",
        "show",
        unit,
        "--property=LoadState",
        "--value",
    )
    unit_active, unit_active_rc = _value(
        runner,
        "systemctl",
        "--user",
        "show",
        unit,
        "--property=ActiveState",
        "--value",
    )
    unit_file, unit_file_rc = _value(
        runner,
        "systemctl",
        "--user",
        "is-enabled",
        unit,
    )
    timer_load, timer_load_rc = _value(
        runner,
        "systemctl",
        "--user",
        "show",
        timer,
        "--property=LoadState",
        "--value",
    )
    timer_active, timer_active_rc = _value(
        runner,
        "systemctl",
        "--user",
        "show",
        timer,
        "--property=ActiveState",
        "--value",
    )
    timer_file, timer_file_rc = _value(
        runner,
        "systemctl",
        "--user",
        "is-enabled",
        timer,
    )
    main_pid_text, main_pid_rc = _value(
        runner,
        "systemctl",
        "--user",
        "show",
        unit,
        "--property=MainPID",
        "--value",
    )

    systemd_available = any(
        rc == 0
        for rc in (
            unit_load_rc,
            unit_active_rc,
            unit_file_rc,
            timer_load_rc,
            timer_active_rc,
            timer_file_rc,
            main_pid_rc,
        )
    )
    if not systemd_available:
        return DrawSyncSupervisorOwnership(
            manager="none",
            unit=unit,
            timer=timer,
            unit_load_state="unavailable",
            unit_active_state="unavailable",
            unit_file_state="unavailable",
            timer_load_state="unavailable",
            timer_active_state="unavailable",
            timer_file_state="unavailable",
            main_pid=None,
            managed=False,
            reasons=(),
        )

    reasons: list[str] = []
    if unit_load == "loaded":
        reasons.append("systemd_unit_loaded")
    if unit_active not in {"", "inactive", "failed", "unknown"}:
        reasons.append(f"systemd_unit_{unit_active}")
    if unit_file in {"enabled", "enabled-runtime", "linked", "linked-runtime", "static"}:
        reasons.append(f"systemd_unit_file_{unit_file}")
    if timer_load == "loaded":
        reasons.append("systemd_timer_loaded")
    if timer_active not in {"", "inactive", "failed", "unknown"}:
        reasons.append(f"systemd_timer_{timer_active}")
    if timer_file in {"enabled", "enabled-runtime", "linked", "linked-runtime", "static"}:
        reasons.append(f"systemd_timer_file_{timer_file}")
    try:
        main_pid = int(main_pid_text)
    except (TypeError, ValueError):
        main_pid = None
    if main_pid == 0:
        main_pid = None
    if main_pid is not None:
        reasons.append("systemd_unit_has_main_pid")

    return DrawSyncSupervisorOwnership(
        manager="systemd_user",
        unit=unit,
        timer=timer,
        unit_load_state=unit_load or "unknown",
        unit_active_state=unit_active or "unknown",
        unit_file_state=unit_file or "unknown",
        timer_load_state=timer_load or "unknown",
        timer_active_state=timer_active or "unknown",
        timer_file_state=timer_file or "unknown",
        main_pid=main_pid,
        managed=bool(reasons),
        reasons=tuple(reasons),
    )


def require_manual_draw_sync_ownership(
    *,
    unit: str = DEFAULT_SYSTEMD_UNIT,
    timer: str = DEFAULT_SYSTEMD_TIMER,
    runner: CommandRunner = _run,
) -> DrawSyncSupervisorOwnership:
    ownership = inspect_draw_sync_supervisor_ownership(
        unit=unit,
        timer=timer,
        runner=runner,
    )
    if ownership.managed:
        raise DrawSyncSupervisorOwnershipViolation(
            "draw_sync_systemd_ownership_conflict",
            "manual watcher mutation is forbidden while systemd owns draw sync",
            ownership=ownership.as_dict(),
            recovery="use scripts/ensure_draw_sync_systemd.sh under an approved Operator request",
        )
    return ownership


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or enforce draw-sync supervisor ownership.",
    )
    parser.add_argument("--unit", default=DEFAULT_SYSTEMD_UNIT)
    parser.add_argument("--timer", default=DEFAULT_SYSTEMD_TIMER)
    parser.add_argument("--require-manual-ownership", action="store_true")
    args = parser.parse_args(argv)
    try:
        ownership = (
            require_manual_draw_sync_ownership(unit=args.unit, timer=args.timer)
            if args.require_manual_ownership
            else inspect_draw_sync_supervisor_ownership(unit=args.unit, timer=args.timer)
        )
    except DrawSyncSupervisorOwnershipViolation as exc:
        print(json.dumps({"status": "rejected", "error": exc.as_dict()}, sort_keys=True))
        return 3
    print(json.dumps({"status": "ok", "ownership": ownership.as_dict()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
