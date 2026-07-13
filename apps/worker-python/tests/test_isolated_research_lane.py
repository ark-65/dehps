from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/run_isolated_research_lane.py"
SPEC = importlib.util.spec_from_file_location("isolated_research_lane", SCRIPT_PATH)
assert SPEC and SPEC.loader
research_lane = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_lane)


def test_completed_manifest_is_reused_only_for_the_identical_history() -> None:
    manifest = {
        "status": "completed",
        "lane_key": research_lane.LANE_KEY,
        "suite_version": research_lane.SUITE_VERSION,
        "as_of_issue": "2026079",
        "history_fingerprint": "history-a",
    }

    assert research_lane.manifest_matches(
        manifest,
        as_of_issue="2026079",
        history_fingerprint_value="history-a",
    )
    assert not research_lane.manifest_matches(
        manifest,
        as_of_issue="2026080",
        history_fingerprint_value="history-a",
    )
    assert not research_lane.manifest_matches(
        manifest,
        as_of_issue="2026079",
        history_fingerprint_value="history-b",
    )


def test_fixed_research_suite_cannot_invoke_or_write_the_main_supervisor(tmp_path: Path) -> None:
    commands = research_lane.research_commands(
        as_of_issue="2026079",
        workers=8,
        output_dir=tmp_path,
    )

    flattened = "\n".join(" ".join(command) for _, command in commands)
    assert [name for name, _ in commands] == [
        "dynamic_kdj_frozen_backtest",
        "kdj_advisor_frozen_controls",
    ]
    assert "run_training_supervisor.py" not in flattened
    assert "generate_training_next_candidates.py" not in flattened
    assert "--as-of-issue 2026079" in flattened
    assert str(tmp_path) in flattened


def test_report_states_the_main_line_boundary() -> None:
    report = research_lane.render_report(
        {
            "status": "completed",
            "as_of_issue": "2026079",
            "suite_version": research_lane.SUITE_VERSION,
            "history_fingerprint": "history-a",
            "runs": [],
        }
    )

    assert "does not run the training supervisor" in report
    assert "cannot change line selection" not in report
