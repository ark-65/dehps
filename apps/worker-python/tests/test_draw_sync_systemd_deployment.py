from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from dehps.draw_sync.systemd_deployment import (
    DrawSyncSystemdDeploymentViolation,
    build_draw_sync_systemd_deployment_contract,
    draw_sync_systemd_environment_text,
    load_draw_sync_systemd_deployment_contract,
    verify_draw_sync_systemd_environment,
    verify_draw_sync_systemd_sources,
    verify_draw_sync_systemd_deployment_contract,
    write_draw_sync_systemd_deployment_contract,
    write_draw_sync_systemd_environment,
)


def contract(tmp_path: Path) -> tuple[dict, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    unit = tmp_path / "dehps-draw-sync.service"
    timer = tmp_path / "dehps-draw-sync.timer"
    unit.write_text("[Service]\nType=oneshot\n", encoding="utf-8")
    timer.write_text("[Timer]\nOnUnitActiveSec=15min\n", encoding="utf-8")
    return (
        build_draw_sync_systemd_deployment_contract(
            code_commit="a" * 40,
            unit_path=unit,
            timer_path=timer,
            launch_contract_digest="b" * 64,
            shadow_attestation_enabled=True,
            shadow_capture_enabled=True,
            shadow_worker_count=8,
        ),
        unit,
        timer,
    )


def test_systemd_deployment_contract_binds_sources_launch_and_environment(
    tmp_path: Path,
) -> None:
    payload, unit, timer = contract(tmp_path)
    environment = tmp_path / "draw-sync.env"
    artifact = tmp_path / "deployment.json"

    write_draw_sync_systemd_environment(environment, payload)
    write_draw_sync_systemd_deployment_contract(artifact, payload)
    restored = load_draw_sync_systemd_deployment_contract(artifact)
    verify_draw_sync_systemd_sources(
        restored,
        unit_path=unit,
        timer_path=timer,
        environment_path=environment,
    )

    assert restored == payload
    assert restored["environment"]["automatic_promotion_allowed"] is False
    assert draw_sync_systemd_environment_text(restored) == (
        "DEHPS_FORWARD_SHADOW_ATTESTATION=true\n"
        "DEHPS_FORWARD_SHADOW_CAPTURE=true\n"
        "DEHPS_FORWARD_SHADOW_WORKERS=8\n"
    )


def test_systemd_deployment_rejects_tampered_contract() -> None:
    payload = {
        "protocol": "draw-sync-systemd-deployment.v1",
        "supervisor": "systemd_user",
        "unit_name": "dehps-draw-sync.service",
        "timer_name": "dehps-draw-sync.timer",
        "code_commit": "a" * 40,
        "unit_digest": "b" * 64,
        "timer_digest": "c" * 64,
        "launch_contract_digest": "d" * 64,
        "environment": {
            "shadow_attestation_enabled": True,
            "shadow_capture_enabled": True,
            "shadow_worker_count": 8,
            "automatic_promotion_allowed": False,
        },
        "contract_digest": "e" * 64,
    }

    with pytest.raises(DrawSyncSystemdDeploymentViolation) as raised:
        verify_draw_sync_systemd_deployment_contract(payload)

    assert raised.value.code == "draw_sync_systemd_contract_digest_mismatch"


def test_systemd_deployment_rejects_source_or_environment_drift(tmp_path: Path) -> None:
    payload, unit, timer = contract(tmp_path)
    environment = tmp_path / "draw-sync.env"
    write_draw_sync_systemd_environment(environment, payload)

    unit.write_text("[Service]\nType=simple\nRestart=always\n", encoding="utf-8")
    with pytest.raises(DrawSyncSystemdDeploymentViolation) as source_error:
        verify_draw_sync_systemd_sources(
            payload,
            unit_path=unit,
            timer_path=timer,
            environment_path=environment,
        )
    assert source_error.value.code == "draw_sync_systemd_installed_source_mismatch"

    _, clean_unit, clean_timer = contract(tmp_path / "clean")
    environment.write_text(
        "DEHPS_FORWARD_SHADOW_ATTESTATION=false\n"
        "DEHPS_FORWARD_SHADOW_CAPTURE=true\n"
        "DEHPS_FORWARD_SHADOW_WORKERS=8\n",
        encoding="utf-8",
    )
    with pytest.raises(DrawSyncSystemdDeploymentViolation) as env_error:
        verify_draw_sync_systemd_environment(environment, payload)
    assert env_error.value.code == "draw_sync_systemd_environment_mismatch"

    assert clean_unit.exists() and clean_timer.exists()


def test_systemd_deployment_rejects_promotion_authority(tmp_path: Path) -> None:
    payload, _, _ = contract(tmp_path)
    tampered = deepcopy(payload)
    tampered["environment"]["automatic_promotion_allowed"] = True

    with pytest.raises(DrawSyncSystemdDeploymentViolation) as raised:
        verify_draw_sync_systemd_deployment_contract(tampered)

    assert raised.value.code == "draw_sync_systemd_promotion_authority_invalid"
