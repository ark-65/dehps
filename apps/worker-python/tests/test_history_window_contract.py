from dataclasses import replace
from datetime import date

import pytest

from dehps.input_contracts import (
    HISTORY_SNAPSHOT_CONTRACT_V1,
    WINDOW_CONTRACT_V1,
    HistorySnapshotArtifact,
    InputContractViolation,
    WindowMode,
    WindowSpec,
)
from dehps.input_contracts.history_window import (
    HISTORY_SNAPSHOT_GOLDEN_SUITE,
    WINDOW_GOLDEN_SUITE,
)


def history() -> list[tuple[str, date, tuple[int, ...]]]:
    return [
        ("2026001", date(2026, 1, 1), (1, 2, 3, 4, 5, 6)),
        ("2026002", date(2026, 1, 4), (3, 8, 12, 18, 25, 33)),
        ("2026003", date(2026, 1, 6), (2, 7, 10, 22, 23, 25)),
        ("2026004", date(2026, 1, 8), (5, 9, 14, 20, 27, 31)),
    ]


def snapshot() -> HistorySnapshotArtifact:
    return HistorySnapshotArtifact.from_history(history())


def test_history_snapshot_identity_is_deterministic_and_revision_sensitive() -> None:
    first = snapshot()
    second = HistorySnapshotArtifact.from_history(history(), source="replica")
    revised_rows = history()
    revised_rows[1] = ("2026002", date(2026, 1, 5), revised_rows[1][2])
    revised = HistorySnapshotArtifact.from_history(revised_rows)

    assert first.contract == HISTORY_SNAPSHOT_CONTRACT_V1
    assert first.snapshot_id == second.snapshot_id
    assert first.history_digest == second.history_digest
    assert first.draw_count == 4
    assert first.latest_issue == "2026004"
    assert first.history_digest != revised.history_digest


@pytest.mark.parametrize(
    ("rows", "code"),
    [
        (
            [
                ("2026002", None, (1, 2, 3, 4, 5, 6)),
                ("2026001", None, (3, 8, 12, 18, 25, 33)),
            ],
            "history_issue_order_violation",
        ),
        (
            [("2026001", None, (2, 1, 3, 4, 5, 6))],
            "noncanonical_red_numbers",
        ),
        (
            [("001", None, (1, 2, 3, 4, 5, 6))],
            "invalid_issue_encoding",
        ),
    ],
)
def test_history_snapshot_rejects_noncanonical_rows(rows, code: str) -> None:
    with pytest.raises(InputContractViolation) as error:
        HistorySnapshotArtifact.from_history(rows)
    assert error.value.code == code


def test_rolling_window_include_as_of_matches_existing_slice_semantics() -> None:
    artifact = WindowSpec(
        mode=WindowMode.ROLLING,
        size=2,
        minimum_size=2,
        as_of_issue="2026003",
        include_as_of=True,
        target_issue="2026004",
    ).materialize(snapshot())

    assert artifact.spec.contract == WINDOW_CONTRACT_V1
    assert [record.issue for record in artifact.records] == ["2026002", "2026003"]
    assert artifact.start_index == 1
    assert artifact.stop_index == 3


def test_backtest_window_excludes_target_for_rolling_and_expanding_modes() -> None:
    source = snapshot()
    rolling = WindowSpec(
        mode="rolling",
        size=2,
        minimum_size=2,
        as_of_issue="2026003",
        include_as_of=False,
        target_issue="2026003",
    ).materialize(source)
    expanding = WindowSpec(
        mode="expanding",
        size=None,
        minimum_size=3,
        as_of_issue="2026004",
        include_as_of=False,
        target_issue="2026004",
    ).materialize(source)

    assert [record.issue for record in rolling.records] == ["2026001", "2026002"]
    assert [record.issue for record in expanding.records] == ["2026001", "2026002", "2026003"]
    assert rolling.as_history() == history()[:2]
    assert expanding.as_history() == history()[:3]


def test_window_rejects_leakage_missing_cutoff_and_insufficient_history() -> None:
    source = snapshot()
    with pytest.raises(InputContractViolation) as leakage:
        WindowSpec(
            mode="rolling",
            size=2,
            as_of_issue="2026003",
            include_as_of=True,
            target_issue="2026003",
        ).materialize(source)
    assert leakage.value.code == "target_issue_leakage"

    with pytest.raises(InputContractViolation) as missing:
        WindowSpec(
            mode="rolling",
            size=2,
            as_of_issue="2026999",
            include_as_of=True,
        ).materialize(source)
    assert missing.value.code == "as_of_issue_not_in_snapshot"

    with pytest.raises(InputContractViolation) as insufficient:
        WindowSpec(
            mode="rolling",
            size=3,
            minimum_size=3,
            as_of_issue="2026002",
            include_as_of=False,
            target_issue="2026002",
        ).materialize(source)
    assert insufficient.value.code == "insufficient_window_history"


def test_window_artifact_and_envelope_are_deterministic_and_tamper_evident() -> None:
    spec = WindowSpec(
        mode="rolling",
        size=3,
        as_of_issue="2026004",
        include_as_of=True,
        target_issue="2026005",
    )
    first = spec.materialize(snapshot())
    second = spec.materialize(snapshot())

    assert first.artifact_digest == second.artifact_digest
    assert first.envelope.envelope_digest == second.envelope.envelope_digest

    tampered_envelope = replace(first.envelope, window_spec_digest="0" * 64)
    with pytest.raises(InputContractViolation) as error:
        replace(first, envelope=tampered_envelope)
    assert error.value.code == "window_spec_digest_mismatch"


def test_window_modes_require_unambiguous_size_semantics() -> None:
    with pytest.raises(InputContractViolation) as rolling:
        WindowSpec(mode="rolling", size=None, as_of_issue="2026004", include_as_of=True)
    assert rolling.value.code == "invalid_rolling_size"

    with pytest.raises(InputContractViolation) as expanding:
        WindowSpec(mode="expanding", size=100, as_of_issue="2026004", include_as_of=True)
    assert expanding.value.code == "expanding_window_has_size"

    with pytest.raises(InputContractViolation) as impossible_minimum:
        WindowSpec(
            mode="rolling",
            size=10,
            minimum_size=11,
            as_of_issue="2026004",
            include_as_of=True,
        )
    assert impossible_minimum.value.code == "minimum_size_exceeds_window_size"


def test_declared_history_and_window_golden_suites_are_executable() -> None:
    for case in HISTORY_SNAPSHOT_GOLDEN_SUITE["cases"]:
        artifact = HistorySnapshotArtifact.from_history(case["records"])
        assert artifact.history_digest == case["expected_history_digest"]
        assert artifact.snapshot_id == case["expected_snapshot_id"]

    golden_snapshot = HistorySnapshotArtifact.from_history(
        [
            (issue, None, (1, 2, 3, 4, 5, 6))
            for issue in WINDOW_GOLDEN_SUITE["snapshot_issues"]
        ]
    )
    for case in WINDOW_GOLDEN_SUITE["cases"]:
        artifact = WindowSpec(
            mode=case["mode"],
            size=case["size"],
            as_of_issue=case["as_of_issue"],
            include_as_of=case["include_as_of"],
            target_issue=case.get("target_issue"),
        ).materialize(golden_snapshot)
        assert [record.issue for record in artifact.records] == case["expected_issues"]
        assert artifact.artifact_digest == case["expected_artifact_digest"]
