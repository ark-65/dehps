from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from dehps.draw_sync.supervisor_ownership import (
    DrawSyncSupervisorOwnershipViolation,
    inspect_draw_sync_supervisor_ownership,
    require_manual_draw_sync_ownership,
)


def runner_for(values: dict[tuple[str, ...], tuple[int, str]]):
    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        key = tuple(command)
        returncode, stdout = values.get(key, (1, ""))
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    return run


def systemctl_values(
    *,
    unit_load: str = "not-found",
    unit_active: str = "inactive",
    unit_enabled: str = "disabled",
    timer_load: str = "not-found",
    timer_active: str = "inactive",
    timer_enabled: str = "disabled",
    main_pid: str = "0",
) -> dict[tuple[str, ...], tuple[int, str]]:
    unit = "dehps-draw-sync.service"
    timer = "dehps-draw-sync.timer"
    return {
        ("systemctl", "--user", "show", unit, "--property=LoadState", "--value"): (
            0,
            unit_load,
        ),
        ("systemctl", "--user", "show", unit, "--property=ActiveState", "--value"): (
            0,
            unit_active,
        ),
        ("systemctl", "--user", "is-enabled", unit): (0, unit_enabled),
        ("systemctl", "--user", "show", timer, "--property=LoadState", "--value"): (
            0,
            timer_load,
        ),
        ("systemctl", "--user", "show", timer, "--property=ActiveState", "--value"): (
            0,
            timer_active,
        ),
        ("systemctl", "--user", "is-enabled", timer): (0, timer_enabled),
        ("systemctl", "--user", "show", unit, "--property=MainPID", "--value"): (
            0,
            main_pid,
        ),
    }


def test_manual_ownership_is_allowed_when_no_systemd_unit_exists() -> None:
    ownership = require_manual_draw_sync_ownership(
        runner=runner_for(systemctl_values()),
    )

    assert ownership.managed is False
    assert ownership.main_pid is None
    assert ownership.as_dict()["manual_mutation_allowed"] is True


def test_loaded_systemd_unit_rejects_manual_mutation_even_when_inactive() -> None:
    runner = runner_for(
        systemctl_values(
            unit_load="loaded",
            unit_enabled="enabled",
            timer_load="loaded",
            timer_active="active",
            timer_enabled="enabled",
        )
    )

    with pytest.raises(DrawSyncSupervisorOwnershipViolation) as raised:
        require_manual_draw_sync_ownership(runner=runner)

    assert raised.value.code == "draw_sync_systemd_ownership_conflict"
    ownership = raised.value.context["ownership"]
    assert ownership["managed"] is True
    assert "systemd_unit_loaded" in ownership["reasons"]
    assert "systemd_timer_active" in ownership["reasons"]


def test_active_systemd_main_pid_is_reported_as_owner() -> None:
    ownership = inspect_draw_sync_supervisor_ownership(
        runner=runner_for(
            systemctl_values(
                unit_load="loaded",
                unit_active="active",
                unit_enabled="enabled",
                main_pid="1013083",
            )
        )
    )

    assert ownership.managed is True
    assert ownership.main_pid == 1013083
    assert "systemd_unit_has_main_pid" in ownership.reasons


def test_unavailable_user_systemd_does_not_claim_ownership() -> None:
    ownership = inspect_draw_sync_supervisor_ownership(runner=runner_for({}))

    assert ownership.manager == "none"
    assert ownership.managed is False
