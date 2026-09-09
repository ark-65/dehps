"""Run the unchanged Worker CI selection in four exhaustive deterministic shards."""
from __future__ import annotations

import hashlib
import json
import os

import numpy  # Initialize the same portable kernel as the existing workflow.
import pytest

os.environ.pop("OPENBLAS_CORETYPE", None)

# These are the six exclusions that predate PR420. No new test is excluded.
EXISTING_EXCLUSIONS = (
    "tests/test_information_theory_measurement_repair.py::test_development_selection_replays_without_formal_outcome_or_seed_reuse",
    "tests/test_information_theory_measurement_repair.py::test_repair_completion_is_result_blind_and_emits_only_availability_fact",
    "tests/test_m4_v2_branch_fixture_freeze.py::test_fixture_contract_regenerates_exact_orthogonal_truth",
    "tests/test_research_os_mainline_supervisor.py::test_supervisor_projects_preflight_and_fail_closed_repair_branch_with_replay",
    "tests/test_training_supervisor.py::test_prefilter_configs_target_parallel_matches_single_worker",
    "tests/test_training_supervisor.py::test_evaluate_configs_target_parallel_matches_single_worker",
)


class Partition:
    def __init__(self, index: int):
        if index not in range(4):
            raise ValueError("CI shard index must be 0, 1, 2 or 3")
        self.index = index

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, config, items):
        partitions = [[] for _ in range(4)]
        for item in items:
            partitions[int(hashlib.sha256(item.nodeid.encode()).hexdigest(), 16) % 4].append(item)
        ids = [{item.nodeid for item in part} for part in partitions]
        assert set.union(*ids) == {item.nodeid for item in items}
        assert sum(map(len, ids)) == len(items)
        assert all(ids), "empty CI partition"
        deselected = [item for index, part in enumerate(partitions) if index != self.index for item in part]
        items[:] = partitions[self.index]
        config.hook.pytest_deselected(items=deselected)
        print("\nCI_PARTITION " + json.dumps({
            "index": self.index, "partition_counts": list(map(len, ids)),
            "eligible_collection_sha256": hashlib.sha256("\n".join(sorted(set.union(*ids))).encode()).hexdigest(),
            "selected_nodeids": sorted(ids[self.index]),
        }, sort_keys=True))


if __name__ == "__main__":
    index = int(os.environ["DEHPS_CI_SHARD_INDEX"])
    raise SystemExit(pytest.main(["-q", "--tb=short", *["--deselect=" + node for node in EXISTING_EXCLUSIONS]],
                                plugins=[Partition(index)]))
