from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_search as search,
)


def _jobs():
    digest = "1" * 64
    configurations = search.base_configurations(
        snapshot_digest=digest, source_contract_digest="2" * 64
    )
    return search.plan_batch(configurations, cursor=0)


def test_single_and_18_worker_outputs_are_byte_identical() -> None:
    jobs = _jobs()
    one = search.execute_jobs(jobs, worker_count=1)
    eighteen = search.execute_jobs(jobs, worker_count=18)
    assert search.result_bytes(one) == search.result_bytes(eighteen)
    assert len(one) == 18


def test_atomic_registration_capacity_and_no_partial_batch() -> None:
    jobs = _jobs()
    registry = search.AtomicCandidateRegistry(
        search.RegistryState(m_total=999_982, registration_seq=4)
    )
    assert registry.register_batch(jobs).m_total == 1_000_000
    with pytest.raises(search.IsolatedSearchError, match="MULTIPLICITY_RISK_LIMIT"):
        registry.register_batch(
            tuple(
                search.CandidateJob(
                    job.configuration,
                    job.seed_ordinal,
                    ("f" if index == 0 else "e") + job.candidate_id[1:],
                    job.seed_hex,
                )
                for index, job in enumerate(jobs)
            )
        )
    with pytest.raises(search.IsolatedSearchError, match="exactly_18"):
        search.AtomicCandidateRegistry().register_batch(jobs[:-1])


def test_retry_reducer_is_contiguous_and_stops_after_success() -> None:
    job = _jobs()[0]
    attempts = search.retry_attempts(job, ["P3_PREEMPTED", None])
    assert [item["retry_ordinal"] for item in attempts] == [0, 1]
    with pytest.raises(search.IsolatedSearchError, match="post_success"):
        search.retry_attempts(job, [None, "WORKER_PROCESS_CRASH"])
    with pytest.raises(search.IsolatedSearchError, match="nonretryable"):
        search.retry_attempts(job, ["INVALID_FEATURES", None])


def test_18_worker_retry_executor_retries_same_candidate_and_seed(monkeypatch) -> None:
    jobs = _jobs()
    calls: dict[str, int] = {}
    first_in_scheduler_order = min(job.candidate_id for job in jobs)

    class _Future:
        def __init__(self, job):
            self.job = job

        def result(self):
            ordinal = calls.get(self.job.candidate_id, 0)
            calls[self.job.candidate_id] = ordinal + 1
            if self.job.candidate_id == first_in_scheduler_order and ordinal == 0:
                raise RuntimeError("fixture worker crash")
            return search.deterministic_candidate_result(self.job)

    class _Executor:
        def __init__(self, *, max_workers):
            assert max_workers == contract.WORKER_COUNT
            self._processes = {}

        def submit(self, _function, payload, acknowledgement_queue):
            acknowledgement_queue.put(payload[0].candidate_id)
            return _Future(payload[0])

        def shutdown(self, **_kwargs):
            return None

    monkeypatch.setattr(search, "ProcessPoolExecutor", _Executor)
    monkeypatch.setattr(
        search,
        "wait",
        lambda futures, **_kwargs: (set(futures), set()),
    )
    waits: list[bool] = []
    outcomes, attempts = search.execute_history_jobs_with_retries(
        jobs,
        history=search.synthetic_history(end_issue="2026100", count=3),
        activity_probe=lambda: True,
        quiescence_waiter=lambda: waits.append(True) or True,
    )
    assert len(outcomes) == 18
    assert all(item.status == "SUCCEEDED" for item in outcomes)
    assert len(attempts) == 36
    assert waits == [True]
    for job in jobs:
        candidate_attempts = [
            item for item in attempts if item.candidate_id == job.candidate_id
        ]
        assert [item.retry_ordinal for item in candidate_attempts] == [0, 1]
        assert candidate_attempts[0].reason == "WORKER_PROCESS_CRASH"
        assert candidate_attempts[1].status == "SUCCEEDED"
        assert candidate_attempts[1].reason is None


def test_preemption_before_worker_ack_releases_lease_without_attempt(
    monkeypatch,
) -> None:
    jobs = _jobs()

    class _Executor:
        def __init__(self, *, max_workers):
            assert max_workers == contract.WORKER_COUNT
            self._processes = {}

        @staticmethod
        def submit(*_args):
            return object()

        @staticmethod
        def shutdown(**_kwargs):
            return None

    monkeypatch.setattr(search, "ProcessPoolExecutor", _Executor)
    released: list[tuple[tuple[search.CandidateJob, int], ...]] = []
    with pytest.raises(search.IsolatedSearchError, match="RESOURCE_GUARD"):
        search.execute_history_jobs_with_retries(
            jobs,
            history=search.synthetic_history(end_issue="2026100", count=3),
            activity_probe=lambda: False,
            quiescence_waiter=lambda: False,
            on_unstarted=released.append,
            preemption_reason_probe=lambda: "P3_PREEMPTED",
        )
    assert len(released) == 1
    assert len(released[0]) == contract.ATTEMPTS_PER_BATCH
    assert {retry for _, retry in released[0]} == {0}


def test_baseline_is_legal_deterministic_and_distinct() -> None:
    first = search.random_baseline_portfolio("2026101", 0)
    assert first == search.random_baseline_portfolio("2026101", 0)
    assert len(first) == contract.PORTFOLIO_SIZE
    assert len({reds for reds, _ in first}) == contract.PORTFOLIO_SIZE
    assert all(len(reds) == 6 and 1 <= blue <= 16 for reds, blue in first)
    assert search.combination_unrank(0) == (1, 2, 3, 4, 5, 6)
    assert search.combination_unrank(contract.LEGAL_RED_COMBINATION_COUNT - 1) == (
        28,
        29,
        30,
        31,
        32,
        33,
    )


def test_full_legal_space_top100_has_exact_order() -> None:
    probabilities = tuple(0.10 + index / 1000 for index in range(33))
    top = search.top_red_combinations(
        lambda candidate: search.probability_combination_score(candidate, probabilities)
    )
    assert len(top) == 100
    assert len(set(top)) == 100
    assert top[0] == (28, 29, 30, 31, 32, 33)


def test_history_physical_projection_rejects_target_or_column_drift() -> None:
    target = "2026101"
    rows = []
    for row_id, item in enumerate(
        search.synthetic_history(end_issue="2026100", count=3), start=1
    ):
        rows.append(
            {
                "id": row_id,
                "issue": item.issue,
                "draw_date": item.draw_date,
                "red_numbers": list(item.red_numbers),
                **{
                    f"r{index}": value
                    for index, value in enumerate(item.red_numbers, 1)
                },
                "blue_number": item.blue_number,
                "source": item.source,
                "created_at": datetime.now(UTC),
            }
        )
    normalized = search.normalize_history_rows(rows, target_issue=target)
    assert normalized[-1].issue == "2026100"
    rows[-1]["issue"] = target
    with pytest.raises(search.IsolatedSearchError, match="DATA_BOUNDARY"):
        search.normalize_history_rows(rows, target_issue=target)


def test_official_off_schedule_history_is_valid_and_calendar_one_hot_is_zero() -> None:
    historical = search.HistoryRow(
        issue="2004080",
        draw_date=date(2004, 9, 24),
        red_numbers=(1, 2, 3, 4, 5, 6),
        blue_number=7,
        source="audited-fixture",
    )
    cube = search._base_feature_cube(
        (historical,), search.CALENDAR_COMPONENT_IDS
    )
    assert cube.shape == (1, 33, 3)
    assert not bool(cube.any())

    row = {
        "id": 1,
        "issue": historical.issue,
        "draw_date": historical.draw_date,
        "red_numbers": list(historical.red_numbers),
        **{
            f"r{index}": value
            for index, value in enumerate(historical.red_numbers, 1)
        },
        "blue_number": historical.blue_number,
        "source": historical.source,
        "created_at": datetime(2004, 9, 24, 22, tzinfo=UTC),
    }
    normalized = search.normalize_history_rows(
        (row,), target_issue="2004081", target_draw_date="2004-09-26"
    )
    assert normalized == (historical,)


def test_worker_rss_guard_is_fail_closed(monkeypatch) -> None:
    class _Process:
        pid = 123

        @staticmethod
        def is_alive() -> bool:
            return True

    class _StatusPath:
        def __init__(self, _value: str) -> None:
            pass

        @staticmethod
        def read_text(*, encoding: str) -> str:
            assert encoding == "ascii"
            kib = contract.WORKER_RSS_HARD_LIMIT_BYTES // 1024
            return f"Name:\tpython\nVmRSS:\t{kib} kB\n"

    monkeypatch.setattr(search, "Path", _StatusPath)
    observed = search.worker_rss_observation((_Process(),))
    assert observed["query_ok"] is True
    assert observed["soft_limit_exceeded"] is True
    assert observed["hard_limit_exceeded"] is True
