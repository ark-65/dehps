from __future__ import annotations

from copy import deepcopy
import json

import pytest

from dehps.draw_sync.launch_contract import (
    DrawSyncWatchLaunchViolation,
    build_draw_sync_watch_launch_contract,
    load_draw_sync_watch_launch_contract,
    verify_draw_sync_watch_launch_contract,
    write_draw_sync_watch_launch_contract,
)


def contract(*, attestation: bool = False) -> dict:
    return build_draw_sync_watch_launch_contract(
        code_commit="a" * 40,
        interval_seconds=900,
        hot_interval_seconds=300,
        cold_interval_seconds=3600,
        timezone="Asia/Shanghai",
        resume_on_event=False,
        shadow_attestation_enabled=attestation,
    )


def test_launch_contract_is_deterministic_and_configuration_sensitive() -> None:
    disabled = contract(attestation=False)
    repeated = contract(attestation=False)
    enabled = contract(attestation=True)

    assert disabled == repeated
    assert disabled["contract_digest"] != enabled["contract_digest"]
    assert disabled["automatic_promotion_allowed"] is False
    verify_draw_sync_watch_launch_contract(disabled)


def test_launch_contract_file_is_atomic_and_fail_closed(tmp_path) -> None:
    path = tmp_path / "draw-sync-watch.launch.json"
    expected = contract()
    write_draw_sync_watch_launch_contract(path, expected)

    assert load_draw_sync_watch_launch_contract(path) == expected

    tampered = deepcopy(expected)
    tampered["shadow_attestation_enabled"] = True
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(
        DrawSyncWatchLaunchViolation,
        match="draw_sync_watch_launch_digest_mismatch",
    ):
        load_draw_sync_watch_launch_contract(path)

    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(
        DrawSyncWatchLaunchViolation,
        match="draw_sync_watch_launch_file_invalid",
    ):
        load_draw_sync_watch_launch_contract(path)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("code_commit", "short", "draw_sync_watch_launch_commit_invalid"),
        ("resume_on_event", "false", "draw_sync_watch_launch_boolean_invalid"),
        (
            "automatic_promotion_allowed",
            True,
            "draw_sync_watch_launch_promotion_authority_invalid",
        ),
    ],
)
def test_launch_contract_rejects_invalid_identity(field, value, code) -> None:
    payload = contract()
    payload[field] = value
    with pytest.raises(DrawSyncWatchLaunchViolation, match=code):
        verify_draw_sync_watch_launch_contract(payload)
