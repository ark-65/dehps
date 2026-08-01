from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dehps.artifacts import atomic_write_text
from dehps.input_contracts.history_window import HistorySnapshotArtifact
from dehps.prediction.v2.contracts import load_shadow_contract
from dehps.prediction.v2.generator import generate_shadow_pool
from dehps.prediction.v2.reports import (
    build_post_draw_report,
    build_pre_draw_report,
    render_post_draw_markdown,
    render_pre_draw_markdown,
)
from dehps.prediction.v2.replay import replay_post_draw, replay_pre_draw
from dehps.prediction.v2.state import encode_state


def persist_immutable_json(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != encoded:
        raise ValueError(f"immutable artifact collision: {path}")
    atomic_write_text(path, encoded)


def persist_immutable_text(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable artifact collision: {path}")
    atomic_write_text(path, content)


def run_pre_draw_shadow(
    *,
    root_dir: Path,
    history: HistorySnapshotArtifact,
    as_of_issue: str,
    target_issue: str,
    output_dir: Path,
) -> dict[str, Any]:
    contract = load_shadow_contract(root_dir)
    state = encode_state(history, as_of_issue=as_of_issue, target_issue=target_issue)
    pool, top100 = generate_shadow_pool(contract=contract, state=state)
    report = build_pre_draw_report(
        contract=contract,
        state=state,
        pool=pool,
        top100=top100,
    )
    replay = replay_pre_draw(
        contract=contract,
        history=history,
        expected_state=state,
        expected_pool=pool,
        expected_top100=top100,
        expected_report=report,
    )
    artifacts = (state, pool, top100, report, replay)
    for artifact in artifacts:
        persist_immutable_json(
            output_dir / str(artifact["artifact_digest"]) / "artifact.json",
            artifact,
        )
    persist_immutable_text(
        output_dir / str(report["artifact_digest"]) / "report.md",
        render_pre_draw_markdown(report),
    )
    return {
        "status": "SHADOW_READY_REPLAY_VERIFIED",
        "contract": contract,
        "state": state,
        "pool": pool,
        "top100": top100,
        "report": report,
        "replay": replay,
    }


def run_post_draw_shadow(
    *,
    pre_draw_report: Mapping[str, Any],
    actual_issue: str,
    actual_red_numbers: Sequence[object],
    output_dir: Path,
) -> dict[str, Any]:
    report = build_post_draw_report(
        pre_draw_report=pre_draw_report,
        actual_issue=actual_issue,
        actual_red_numbers=actual_red_numbers,
    )
    replay = replay_post_draw(
        pre_draw_report=pre_draw_report,
        actual_issue=actual_issue,
        actual_red_numbers=actual_red_numbers,
        expected_report=report,
    )
    for artifact in (report, replay):
        persist_immutable_json(
            output_dir / str(artifact["artifact_digest"]) / "artifact.json",
            artifact,
        )
    persist_immutable_text(
        output_dir / str(report["artifact_digest"]) / "report.md",
        render_post_draw_markdown(report),
    )
    return {"status": "SHADOW_EVALUATED_REPLAY_VERIFIED", "report": report, "replay": replay}
