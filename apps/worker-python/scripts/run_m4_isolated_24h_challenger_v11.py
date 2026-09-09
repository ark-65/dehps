from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import build_m4_isolated_24h_challenger_v11_manifest as builder
from dehps.agents.repository import AgentRequestRepository
from dehps.agents.requests import (
    AgentExecutionStatus,
    AgentRequestStatus,
    AgentRequestType,
)
from dehps.agents.roles import AgentRole
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as formal_p3,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_artifacts as artifacts,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_contract as contract,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_mainline as mainline,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_reporting as reporting,
)
from dehps.research_os.information_theory.measurement_system_v2 import (
    isolated_challenger_v11_search as search,
)
from dehps.research_os.models import (
    CompletionClassification,
    ControlPlaneManifest,
    ResearchOSValidationError,
    TaskStatus,
)
from dehps.research_os.repository import PostgresResearchOSRepository
from dehps.research_os.supervisor import (
    MainlineSupervisorError,
    _event_record,
    _persist_immutable,
)

_MAINLINE_FACT = re.compile(
    r"^mainline-execution:m4-isolated-24h-challenger-v11-[^:]+:"
    r"[0-9a-f]{64}:[0-9a-f]{64}:completed$"
)
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
KNOWN_EXTERNAL_EVENTS = frozenset(
    {
        "TARGET_PROJECTION_INPUT",
        "RESOURCE_QUIESCENT_60S",
        "SELECTION_CUTOFF",
        "FREEZE_DEADLINE",
        "PREDRAW_SEND",
        "AUDITED_DRAW",
        "DAILY_SEND",
        "INCIDENT_OPEN",
        "CAPACITY_BELOW_18",
    }
)
KNOWN_AUTHORITIES = frozenset(
    {builder.RESEARCH_APPROVAL_AUTHORITY, builder.OPERATOR_CONFIGURATION_AUTHORITY}
)
PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST = (
    "99f058e6df7e36ebd07bb411c7c1960989367230cb0a9344619442466112460a"
)
APPROVED_BOOTSTRAP_PREDECESSOR_SOURCE_DIGESTS = frozenset(
    {
        PREDECESSOR_BOOTSTRAP_SOURCE_DIGEST,
        "a13889100c0f83a315f5e3997ce53ac1fb8a86b661bcd1d522d3cec59adf4fc0",
        "1d3a7766dfd7a3c09fd7cca0b54ec15ce154f5234bf1bbb97e61c63d55c92ada",
        "41d3c7431c29ae7c8af71a8b09653df5f28ed02954206835278f2e20dc7082cd",
    }
)
LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST = (
    "38ea4d38e66558f30eb4c8660555ca35dd584aa3de02801fe6f6075d09ffaff1"
)
LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS = frozenset(
    {
        LIVE_PARTIAL_PREDECESSOR_SOURCE_DIGEST,
        "45cd0aff1964f603ffb698da019a9803681dbe480c7bee9a322a592a05b79ffc",
        "fb37933e24cc32677b13909e9f4689605b20eaf635a06ed364a4401ee768124c",
        "f067bc89f60826c15793e1ab6325a3dce088dd7c2af3e1c99e984d3aada50dd1",
        "5452fc522812220b6654c2bb8e54b8844b0c2fdab251d392c2af8de501e659ec",
        "bf941daa91e4749354a237247f0c625ef0c47b57367d29acc58dc70642cda011",
        contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
    }
)
DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST = (
    "eb2c70cbaec4e22993f4e0e17c498fe963890558bd774e04e0f28deb9e9a9b8e"
)
DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST = (
    "d2cce00e714fa041789d2114addd109d32f31f9d283dac7beb311a1b0e54b1cf"
)
DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST = (
    "2394fc17b1017109a2f8f43b5672051398b3b34419b05cd44c4735a7d8be2d0a"
)
DAILY_RECOVERY_COMMITTED_EVENT_DIGEST = (
    "3533d738b178793e83b97e92a6129468f44762cf5ff1383386ca5bca5aac819b"
)
DAILY_RECOVERY_COMMITTED_SUMMARY_DIGEST = (
    "43982d737eadc050327a08b74e692e70f9f6d265a37408cc38abbe274bb7cc63"
)
DAILY_RECOVERY_COMMITTED_EXECUTION_DIGEST = (
    "d2e4d2638d04db6fdb2d58cddb08f2ca0e4ad71d3207cd5ec26f2379e0df9ec1"
)
DAILY_RECOVERY_COMMITTED_RUNTIME_SOURCE_DIGEST = (
    "5d8dacee8a6ec1059a25148e0bb41bfccbc4226c00cc9ae3703164b8d538219e"
)
DAILY_RECOVERY_COMMITTED_RUNTIME_ATTESTATION_DIGEST = (
    "83bcfe7e1ec63cfb8adf81924ab95fe695f25f5647611d98673eb32e3155b3bb"
)
DAILY_RECOVERY_COMMITTED_RUNTIME_GIT_COMMIT = "a8230e54372c9c47da297f952a89a3a2b94be133"
DAILY_RECOVERY_PRE_COMMIT_FIXTURE_DIGEST = (
    "bcb0f311f2841e009a14a9b22ea8e1bc3787a70f413d24abae6f7bf7a720365d"
)
DAILY_RECOVERY_POST_COMMIT_FIXTURE_DIGEST = (
    "cb2707fa51bb37209fea9c5aa54ef3b12d50a8f19cf7db1be934d1799626d76a"
)
DAILY_RECOVERY_FAILED_OPERATOR_SOURCE_DIGEST = (
    "710783396226aa6b643c302e4de61238ff75d905f611d6f215ba0eecb28f04b4"
)
DAILY_RECOVERY_FAILED_OPERATOR_ATTESTATION_DIGEST = (
    "31543855b1d1fce08f51cdfb6a90b97f2860d23a9b4a44783dd257f716f68cd0"
)
FORMAL_P3_FROZEN_SOURCE_SET_DIGEST = (
    "a3b34318d784d9477fe82f7e66c3c04e5640eaed87e2b4c49cd8b397fc27cd9c"
)
DAILY_RECOVERY_LEGACY_INCIDENT_OPEN_TASK_DIGEST = (
    "959b2b2809420fce64a4609a3bf60f83b4c632dbac3bea55745346a63cdaea50"
)
LIVE_PARTIAL_FROZEN_GOAL_DIGEST = (
    "b13054b699c75325c3a0fbb27ccc697e0a3176568140a7f0d5e59c9aa362d69a"
)
USER_SCOPE_RESUME_MANIFEST_DIGEST = (
    "96bf5c5b13b9f65fa48b0d8da119412f256a1ec657141be8ca8968b5fb12762f"
)
USER_SCOPE_FAILED_MANIFEST_DIGEST = (
    "1d4c0d3f1b242d94a04bb4aafa6cb9cd21dc4e34c5344c518e1dd6e820c23fbd"
)
USER_SCOPE_RESUME_TASK_KEY = "m4-isolated-24h-challenger-v11-search-batch-000000000000"
USER_SCOPE_RESUME_CAPABILITY = "M4IsolatedSearchBatchCapabilityV11"
USER_SCOPE_RESUME_TASK_DIGEST = (
    "fc6bacf51dfe3de513aabb908900a1d67b8f7f3b67b1042631bf2c8177860f0b"
)
USER_SCOPE_RESUME_EXECUTION_ID = (
    "a493038f96f8b5657ae36642ce6d4007df1f1c9911071c8fb33047995e5816ef"
)
USER_SCOPE_RESUME_STARTED_EVENT_DIGEST = (
    "13c3b265371482f3291c239f5af1a2523e88e4028505e18d42d06da3e81f8222"
)
USER_SCOPE_RESUME_FAILED_EVENT_DIGEST = (
    "71d714427c8c5e9219b8424095fa80a3fedfb7b97107dae19af79a03c47d501c"
)
USER_SCOPE_GUARD_FAILED_EVENT_DIGEST = (
    "84c7988b8442969f2c8a910a2f32116b820800ebe5dffe993ee4fb4cc2e26e43"
)
USER_SCOPE_HISTORICAL_MANIFEST_DIGEST = (
    "7ad51501ebce593745c8cd2789868d96456e719c129e74081c03f1fdff356b9a"
)
USER_SCOPE_HISTORICAL_TASK_DIGEST = (
    "df31162691e3429283464ff3406694a6b638c037177e8593ea0639a310f0a560"
)
USER_SCOPE_HISTORICAL_EXECUTION_ID = (
    "1f7c1ab2b00185315fcd78f51d3d5d2fa3fd294fad9cd0660b5faa95d97588b6"
)
USER_SCOPE_HISTORICAL_STARTED_EVENT_DIGEST = (
    "0ede8b9414e3efd99b3cab39af6e3e1f49f44e7214b77465e107d856366534de"
)
USER_SCOPE_HISTORICAL_FAILED_EVENT_DIGEST = (
    "88daf7919d3c0c3721ac0a4c1a4bb206d2a5ae0345bd7aad098265c2556d4262"
)
USER_SCOPE_HISTORICAL_SOURCE_DIGEST = (
    "5452fc522812220b6654c2bb8e54b8844b0c2fdab251d392c2af8de501e659ec"
)
USER_SCOPE_HISTORICAL_COMMIT = "5192950092e30455f7166d64ab84848d8c8398b5"
USER_SCOPE_HISTORICAL_STARTED_AT = "2026-08-27T19:41:59.920157+00:00"
USER_SCOPE_HISTORICAL_FAILED_AT = "2026-08-27T19:42:00.101801+00:00"
USER_SCOPE_RESUME_STARTED_AT = "2026-08-27T19:56:35.300063+00:00"
USER_SCOPE_RESUME_FAILED_AT = "2026-08-27T20:59:52.863000+00:00"
USER_SCOPE_GUARD_FAILED_AT = "2026-08-27T21:48:34.466338+00:00"
USER_SCOPE_RESUME_ORIGIN_COMMIT = "443a1d72e3135b9a90912bc3e890566de4338f65"
USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST = (
    "bf941daa91e4749354a237247f0c625ef0c47b57367d29acc58dc70642cda011"
)
USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST = (
    "4d2c037b172beaa525de05c855d0d0e1ad72e8978c271f3cdf68fb9d23aa6452"
)
USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST = (
    "2810d17a645483fbfb368334c20ba5264e9dcbca937908ed5dbd9471144d73e1"
)
USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST = (
    "d71b6076cb56cd2933df1e2381fc5f62034a3f2ae0299cfa044302e092481432"
)
USER_SCOPE_EVENT_ISOLATION_RUNTIME_COMMIT = "103aa7585257accf727020ea6454a3c1cc383267"
USER_SCOPE_FAILED_STATE_RECOVERY_BASE_COMMIT = (
    "c790ef74c99b1b0a691821d1825a84c19a6c89be"
)
USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-failed-state-to-running-recovery-gate-v1"
)
USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_ID = 750
USER_SCOPE_FAILED_STATE_ENGINEERING_DECISION_ID = 3182
USER_SCOPE_FAILED_STATE_ENGINEERING_EXECUTION_ID = 605
USER_SCOPE_FAILED_STATE_ENGINEERING_PAYLOAD_SHA256 = (
    "db00234098f0f27d68c05deb427c4c2897a0406860343adbc5bad281b474071b"
)
USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT = "c30db93efb428198b4d7c0c0548feefbd315ba59"
USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-sequence2-atomic-completion-gate-v1"
)
USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_ID = 752
USER_SCOPE_SEQUENCE2_ENGINEERING_DECISION_ID = 3192
USER_SCOPE_SEQUENCE2_ENGINEERING_EXECUTION_ID = 607
USER_SCOPE_SEQUENCE2_ENGINEERING_PAYLOAD_SHA256 = (
    "8be2ab76cb27cf5fff1d99519eaf8f760063d17b987585ffed1dbb4dfc37972d"
)
USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-sequence3-guard-failure-resume-v1"
)
USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_ID = 753
USER_SCOPE_SEQUENCE3_ENGINEERING_DECISION_ID = 3197
USER_SCOPE_SEQUENCE3_ENGINEERING_EXECUTION_ID = 608
USER_SCOPE_SEQUENCE3_ENGINEERING_PAYLOAD_SHA256 = (
    "c8ea6f9583faba341e9e53a660d198c80ca123a6b11e8be7411718df3844f2f0"
)
USER_SCOPE_SECOND_GUARD_REPAIR_BASE_COMMIT = "9d94a0142eca2fa27180f817d4000034f16bdf06"
USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-second-terminal-event-guard-sequence3-fix-v1"
)
USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_ID = 757
USER_SCOPE_SECOND_GUARD_ENGINEERING_DECISION_ID = 3217
USER_SCOPE_SECOND_GUARD_ENGINEERING_EXECUTION_ID = 612
USER_SCOPE_SECOND_GUARD_ENGINEERING_PAYLOAD_SHA256 = (
    "11814f6b4c461befbe051f491658dfcf634db2badfedd1a7edeaa127468bf507"
)
USER_SCOPE_RUNNING_RESUME_REPAIR_BASE_COMMIT = (
    "cdbba52de7b97b122fc3ec4ce7395c8f7588a5ef"
)
USER_SCOPE_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-exact-running-projection-resume-v1"
)
USER_SCOPE_ENGINEERING_REQUEST_ID = 759
USER_SCOPE_ENGINEERING_DECISION_ID = 3227
USER_SCOPE_ENGINEERING_EXECUTION_ID = 614
USER_SCOPE_ENGINEERING_PAYLOAD_SHA256 = (
    "fa3c627a53d82ff65b94542cf6e25d9a46f19012c8d69033a2733797f523e77f"
)
USER_SCOPE_COMMITTED_MANIFEST_DIGEST = (
    "86f0934cbe3599d9bbd4ee1cf7ca93f209868a5bcee9d1213af9c045cc56f6f5"
)
USER_SCOPE_COMMITTED_EVENT_DIGEST = (
    "c1749690a190688ae23eb270060c0d76ec8db309614833820929917b2083c7ed"
)
USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST = (
    "7b44ecf4260b6108b09673bd91c55503c54b1c08751cc9975f57c449ea3564aa"
)
USER_SCOPE_COMMITTED_PUBLICATION_BATCH_DIGEST = (
    "1bd1ac099c8c280443ff994ce40e498c53fabc1d78da2c008dd0739f049cb200"
)
USER_SCOPE_COMMITTED_REPAIR_BASE_COMMIT = "a32da3bceb5085e532631979c3a8c1be372d5bc6"
USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-exact-sequence3-committed-replay-ledger-recovery-v1"
)
USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_ID = 762
USER_SCOPE_COMMITTED_ENGINEERING_DECISION_ID = 3242
USER_SCOPE_COMMITTED_ENGINEERING_EXECUTION_ID = 617
USER_SCOPE_COMMITTED_ENGINEERING_PAYLOAD_SHA256 = (
    "1279b78cfdf498c6107ede9b351e8baf080b1ad9a6eee15e212a180d0e948637"
)
MIRROR_COMPLETENESS_REPAIR_BASE_COMMIT = "da54f0d0a31b456ab6e9b2ea694948772c7342af"
MIRROR_COMPLETENESS_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-dict-row-mirror-completeness-fix-v1"
)
MIRROR_COMPLETENESS_ENGINEERING_REQUEST_ID = 767
MIRROR_COMPLETENESS_ENGINEERING_DECISION_ID = 3267
MIRROR_COMPLETENESS_ENGINEERING_EXECUTION_ID = 622
MIRROR_COMPLETENESS_ENGINEERING_PAYLOAD_SHA256 = (
    "0b77f38eece1d87745e2ab559a80a0958c0b1cfc585c79fed4e3687680366f81"
)
DAILY_RECOVERY_TRANSITION_FIX_BASE_COMMIT = "a00a30fc703064853d52f11b8576667ac34af401"
DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_REQUEST_ID = 791
DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_DECISION_ID = 3371
DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_EXECUTION_ID = 638
DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_PAYLOAD_SHA256 = (
    "aed8a3ed96ae39d276246a60c5ee926135793e438c0cee57cd936b04c72f9df3"
)
HEALTH_PROVENANCE_RUNNING_RECOVERY_BASE_COMMIT = (
    "38a00a2c46427677e893b355c553e01b086f04eb"
)
HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-health-provenance-and-running-daily-recovery-fix-v2"
)
HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_REQUEST_ID = 795
HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_DECISION_ID = 3387
HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_EXECUTION_ID = 640
HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_PAYLOAD_SHA256 = (
    "20047c995e9ecaf64ac2732118c649488341dc65dd936b9d4a2b6b523d7fc21e"
)
COMPATIBILITY_BINDING_SCOPE_FIX_BASE_COMMIT = "6968ed917e4f8bc7e7b9bf415531c93d4012aa9d"
COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-actual-binding-scope-decoupling-v1"
)
COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID = 803
COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID = 3417
COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID = 644
COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PARENT_REQUEST_ID = 796
COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256 = (
    "360e7221b935f72ece18f1dff9c4790c01d7264e0086fa9dcc36574175d7cfb4"
)
COMMITTED_STATE_RECOVERY_CLOSURE_BASE_COMMIT = (
    "a8230e54372c9c47da297f952a89a3a2b94be133"
)
COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-committed-state-deterministic-recovery-closure-v1"
)
COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_REQUEST_ID = 807
COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_DECISION_ID = 3437
COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_EXECUTION_ID = 648
COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_PAYLOAD_SHA256 = (
    "155e56df70729cc958ba0b436e79b5beda8803878485bfbfcd16f676e71a3491"
)
USER_SCOPE_MANDATORY_MAIL_KINDS = (
    "PREDRAW_TOP100",
    "POSTDRAW_SETTLEMENT",
    "DAILY_24H_RESEARCH_SUMMARY",
    "IMMEDIATE_FAIL_CLOSED_INCIDENT",
)


class IsolatedRunnerError(contract.IsolatedChallengerContractError):
    pass


def _validate_mirror_completeness_repair_source_binding(
    source_contract: Mapping[str, Any],
) -> None:
    bindings = source_contract.get("governance_bindings")
    expected = {
        "mirror_completeness_repair_base_merged_commit": (
            MIRROR_COMPLETENESS_REPAIR_BASE_COMMIT
        ),
        "mirror_completeness_repair_engineering_approval_decision_id": (
            MIRROR_COMPLETENESS_ENGINEERING_DECISION_ID
        ),
        "mirror_completeness_repair_engineering_execution_id": (
            MIRROR_COMPLETENESS_ENGINEERING_EXECUTION_ID
        ),
        "mirror_completeness_repair_engineering_request_id": (
            MIRROR_COMPLETENESS_ENGINEERING_REQUEST_ID
        ),
        "mirror_completeness_repair_engineering_request_key": (
            MIRROR_COMPLETENESS_ENGINEERING_REQUEST_KEY
        ),
        "mirror_completeness_repair_engineering_request_payload_sha256": (
            MIRROR_COMPLETENESS_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected} != expected
    ):
        raise IsolatedRunnerError("mirror_completeness_repair_binding_changed")


def _validate_daily_recovery_transition_fix_source_binding(
    source_contract: Mapping[str, Any],
) -> None:
    bindings = source_contract.get("governance_bindings")
    expected = {
        "daily_recovery_historical_source_transition_fix_base_merged_commit": (
            DAILY_RECOVERY_TRANSITION_FIX_BASE_COMMIT
        ),
        "daily_recovery_historical_source_transition_fix_engineering_request_id": (
            DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_REQUEST_ID
        ),
        "daily_recovery_historical_source_transition_fix_engineering_approval_decision_id": (
            DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_DECISION_ID
        ),
        "daily_recovery_historical_source_transition_fix_engineering_execution_id": (
            DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_EXECUTION_ID
        ),
        "daily_recovery_historical_source_transition_fix_engineering_request_payload_sha256": (
            DAILY_RECOVERY_TRANSITION_FIX_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected} != expected
    ):
        raise IsolatedRunnerError(
            "daily_recovery_historical_source_transition_fix_binding_changed"
        )


def _validate_health_provenance_running_recovery_source_binding(
    source_contract: Mapping[str, Any],
) -> None:
    bindings = source_contract.get("governance_bindings")
    expected = {
        "health_provenance_running_recovery_base_merged_commit": (
            HEALTH_PROVENANCE_RUNNING_RECOVERY_BASE_COMMIT
        ),
        "health_provenance_running_recovery_engineering_request_key": (
            HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_REQUEST_KEY
        ),
        "health_provenance_running_recovery_engineering_request_id": (
            HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_REQUEST_ID
        ),
        "health_provenance_running_recovery_engineering_approval_decision_id": (
            HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_DECISION_ID
        ),
        "health_provenance_running_recovery_engineering_execution_id": (
            HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_EXECUTION_ID
        ),
        "health_provenance_running_recovery_engineering_request_payload_sha256": (
            HEALTH_PROVENANCE_RUNNING_RECOVERY_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected} != expected
    ):
        raise IsolatedRunnerError("health_provenance_running_recovery_binding_changed")


def _validate_compatibility_binding_scope_fix_source_binding(
    source_contract: Mapping[str, Any],
) -> None:
    bindings = source_contract.get("governance_bindings")
    expected = {
        "compatibility_binding_scope_fix_base_merged_commit": (
            COMPATIBILITY_BINDING_SCOPE_FIX_BASE_COMMIT
        ),
        "compatibility_binding_scope_fix_engineering_request_key": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY
        ),
        "compatibility_binding_scope_fix_engineering_request_id": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID
        ),
        "compatibility_binding_scope_fix_engineering_approval_decision_id": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID
        ),
        "compatibility_binding_scope_fix_engineering_execution_id": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID
        ),
        "compatibility_binding_scope_fix_engineering_request_payload_sha256": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected} != expected
    ):
        raise IsolatedRunnerError("compatibility_binding_scope_fix_binding_changed")


def _validate_committed_state_recovery_closure_source_binding(
    source_contract: Mapping[str, Any],
) -> None:
    bindings = source_contract.get("governance_bindings")
    expected = {
        "committed_state_recovery_closure_base_merged_commit": (
            COMMITTED_STATE_RECOVERY_CLOSURE_BASE_COMMIT
        ),
        "committed_state_recovery_closure_engineering_request_key": (
            COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_REQUEST_KEY
        ),
        "committed_state_recovery_closure_engineering_request_id": (
            COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_REQUEST_ID
        ),
        "committed_state_recovery_closure_engineering_approval_decision_id": (
            COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_DECISION_ID
        ),
        "committed_state_recovery_closure_engineering_execution_id": (
            COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_EXECUTION_ID
        ),
        "committed_state_recovery_closure_engineering_request_payload_sha256": (
            COMMITTED_STATE_RECOVERY_CLOSURE_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected} != expected
    ):
        raise IsolatedRunnerError("committed_state_recovery_closure_binding_changed")


def _validate_compatibility_binding_scope_fix_engineering_governance(
    repository: AgentRequestRepository,
) -> None:
    request = repository.get_request(
        COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY
    )
    approvals = [
        item
        for item in repository.list_decisions(
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY
        )
        if item.decision_code == "request_approved"
    ]
    executions = repository.list_execution_metadata(
        COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_KEY
    )
    if (
        request.id != COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID
        or request.request_type is not AgentRequestType.ENGINEERING_IMPLEMENTATION
        or request.status is not AgentRequestStatus.COMPLETED
        or request.parent_request_id
        != COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PARENT_REQUEST_ID
        or request.metadata.get("payload_sha256")
        != COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256
        or len(approvals) != 1
        or approvals[0].id != COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID
        or approvals[0].new_status != "approved"
        or approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(executions) != 1
        or executions[0].id != COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID
        or executions[0].status is not AgentExecutionStatus.COMPLETED
        or executions[0].environment != "development"
        or executions[0].executor_role is not AgentRole.ENGINEERING
    ):
        raise IsolatedRunnerError(
            "compatibility_binding_scope_fix_engineering_governance_changed"
        )


def _validate_user_scope_resume_event_set(
    events: Sequence[Mapping[str, Any]], *, allow_completed: bool
) -> tuple[dict[str, Any], ...]:
    try:
        records = {
            str(item.get("event_digest") or ""): _event_record(item) for item in events
        }
    except (MainlineSupervisorError, TypeError, ValueError) as exc:
        raise IsolatedRunnerError("user_scope_resume_event_integrity_changed") from exc
    if len(records) != len(events):
        raise IsolatedRunnerError("user_scope_resume_duplicate_event")
    required = {
        USER_SCOPE_HISTORICAL_STARTED_EVENT_DIGEST,
        USER_SCOPE_HISTORICAL_FAILED_EVENT_DIGEST,
        USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
    }
    if not required.issubset(records):
        raise IsolatedRunnerError("user_scope_resume_required_event_missing")

    def require_exact(
        digest: str,
        *,
        execution_id: str,
        manifest_digest: str,
        task_digest: str,
        event_type: str,
        sequence: int,
        recorded_at: str,
        payload: Mapping[str, Any],
    ) -> None:
        record = records[digest]
        if (
            record.execution_id != execution_id
            or record.control_plane_key != contract.CONTROL_PLANE_KEY
            or record.manifest_digest != manifest_digest
            or record.task_key != USER_SCOPE_RESUME_TASK_KEY
            or record.task_digest != task_digest
            or record.capability != USER_SCOPE_RESUME_CAPABILITY
            or record.event_type != event_type
            or record.sequence != sequence
            or record.recorded_at != recorded_at
            or dict(record.payload) != dict(payload)
        ):
            raise IsolatedRunnerError("user_scope_resume_event_identity_changed")

    require_exact(
        USER_SCOPE_HISTORICAL_STARTED_EVENT_DIGEST,
        execution_id=USER_SCOPE_HISTORICAL_EXECUTION_ID,
        manifest_digest=USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
        task_digest=USER_SCOPE_HISTORICAL_TASK_DIGEST,
        event_type="started",
        sequence=0,
        recorded_at=USER_SCOPE_HISTORICAL_STARTED_AT,
        payload={
            "input_artifact_digests": [USER_SCOPE_HISTORICAL_SOURCE_DIGEST],
            "git_commit": USER_SCOPE_HISTORICAL_COMMIT,
        },
    )
    require_exact(
        USER_SCOPE_HISTORICAL_FAILED_EVENT_DIGEST,
        execution_id=USER_SCOPE_HISTORICAL_EXECUTION_ID,
        manifest_digest=USER_SCOPE_HISTORICAL_MANIFEST_DIGEST,
        task_digest=USER_SCOPE_HISTORICAL_TASK_DIGEST,
        event_type="failed",
        sequence=1,
        recorded_at=USER_SCOPE_HISTORICAL_FAILED_AT,
        payload={
            "error": "atomic_registration_artifact_content_changed",
            "git_commit": USER_SCOPE_HISTORICAL_COMMIT,
        },
    )
    require_exact(
        USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
        manifest_digest=USER_SCOPE_RESUME_MANIFEST_DIGEST,
        task_digest=USER_SCOPE_RESUME_TASK_DIGEST,
        event_type="started",
        sequence=0,
        recorded_at=USER_SCOPE_RESUME_STARTED_AT,
        payload={
            "input_artifact_digests": [USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST],
            "git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        },
    )
    require_exact(
        USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
        manifest_digest=USER_SCOPE_RESUME_MANIFEST_DIGEST,
        task_digest=USER_SCOPE_RESUME_TASK_DIGEST,
        event_type="failed",
        sequence=1,
        recorded_at=USER_SCOPE_RESUME_FAILED_AT,
        payload={
            "error": "atomic_registration_resume_changed",
            "git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        },
    )
    require_exact(
        USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
        manifest_digest=USER_SCOPE_RESUME_MANIFEST_DIGEST,
        task_digest=USER_SCOPE_RESUME_TASK_DIGEST,
        event_type="failed",
        sequence=2,
        recorded_at=USER_SCOPE_GUARD_FAILED_AT,
        payload={
            "error": (
                "M4-v2 atomic successor does not permit failed-execution recovery"
            ),
            "git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        },
    )
    additional = set(records) - required
    if additional and (not allow_completed or len(additional) != 1):
        raise IsolatedRunnerError("user_scope_resume_unexpected_event")
    if additional:
        completed = records[next(iter(additional))]
        completed_payload = dict(completed.payload)
        try:
            completed_at = datetime.fromisoformat(completed.recorded_at)
        except ValueError as exc:
            raise IsolatedRunnerError(
                "user_scope_resume_completed_event_time_invalid"
            ) from exc
        if (
            completed.execution_id != USER_SCOPE_RESUME_EXECUTION_ID
            or completed.control_plane_key != contract.CONTROL_PLANE_KEY
            or completed.manifest_digest != USER_SCOPE_RESUME_MANIFEST_DIGEST
            or completed.task_key != USER_SCOPE_RESUME_TASK_KEY
            or completed.task_digest != USER_SCOPE_RESUME_TASK_DIGEST
            or completed.capability != USER_SCOPE_RESUME_CAPABILITY
            or completed.event_type != "completed"
            or completed.sequence != 3
            or completed_at.tzinfo is None
            or completed_payload.get("git_commit") != USER_SCOPE_RESUME_ORIGIN_COMMIT
            or not isinstance(completed_payload.get("execution_artifact_digest"), str)
            or not isinstance(completed_payload.get("execution_artifact_path"), str)
            or not isinstance(completed_payload.get("registered_artifact_count"), int)
            or completed_payload.get("registered_artifact_count", 0) < 1
            or not isinstance(completed_payload.get("publication_batch_digest"), str)
        ):
            raise IsolatedRunnerError("user_scope_resume_completed_event_changed")
    return tuple(dict(item) for item in events)


def validate_user_scope_recovery_governance(
    *,
    repository: AgentRequestRepository,
    source_contract: Mapping[str, Any],
    repaired_source_digest: str,
    git_commit: str,
    phase: str,
) -> dict[str, Any]:
    if phase not in {"resume", "post_batch_rebind"}:
        raise IsolatedRunnerError("user_scope_recovery_phase_changed")
    bindings = source_contract.get("governance_bindings")
    if not isinstance(bindings, dict) or {
        "failed_state_recovery_gate_base_merged_commit": bindings.get(
            "failed_state_recovery_gate_base_merged_commit"
        ),
        "failed_state_recovery_gate_engineering_approval_decision_id": bindings.get(
            "failed_state_recovery_gate_engineering_approval_decision_id"
        ),
        "failed_state_recovery_gate_engineering_execution_id": bindings.get(
            "failed_state_recovery_gate_engineering_execution_id"
        ),
        "failed_state_recovery_gate_engineering_request_id": bindings.get(
            "failed_state_recovery_gate_engineering_request_id"
        ),
        "failed_state_recovery_gate_engineering_request_key": bindings.get(
            "failed_state_recovery_gate_engineering_request_key"
        ),
        "failed_state_recovery_gate_engineering_request_payload_sha256": bindings.get(
            "failed_state_recovery_gate_engineering_request_payload_sha256"
        ),
    } != {
        "failed_state_recovery_gate_base_merged_commit": (
            USER_SCOPE_FAILED_STATE_RECOVERY_BASE_COMMIT
        ),
        "failed_state_recovery_gate_engineering_approval_decision_id": (
            USER_SCOPE_FAILED_STATE_ENGINEERING_DECISION_ID
        ),
        "failed_state_recovery_gate_engineering_execution_id": (
            USER_SCOPE_FAILED_STATE_ENGINEERING_EXECUTION_ID
        ),
        "failed_state_recovery_gate_engineering_request_id": (
            USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_ID
        ),
        "failed_state_recovery_gate_engineering_request_key": (
            USER_SCOPE_FAILED_STATE_ENGINEERING_REQUEST_KEY
        ),
        "failed_state_recovery_gate_engineering_request_payload_sha256": (
            USER_SCOPE_FAILED_STATE_ENGINEERING_PAYLOAD_SHA256
        ),
    }:
        raise IsolatedRunnerError("user_scope_engineering_source_binding_changed")
    if {
        "sequence2_completion_gate_base_merged_commit": bindings.get(
            "sequence2_completion_gate_base_merged_commit"
        ),
        "sequence2_completion_gate_engineering_approval_decision_id": bindings.get(
            "sequence2_completion_gate_engineering_approval_decision_id"
        ),
        "sequence2_completion_gate_engineering_execution_id": bindings.get(
            "sequence2_completion_gate_engineering_execution_id"
        ),
        "sequence2_completion_gate_engineering_request_id": bindings.get(
            "sequence2_completion_gate_engineering_request_id"
        ),
        "sequence2_completion_gate_engineering_request_key": bindings.get(
            "sequence2_completion_gate_engineering_request_key"
        ),
        "sequence2_completion_gate_engineering_request_payload_sha256": bindings.get(
            "sequence2_completion_gate_engineering_request_payload_sha256"
        ),
    } != {
        "sequence2_completion_gate_base_merged_commit": (
            USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT
        ),
        "sequence2_completion_gate_engineering_approval_decision_id": (
            USER_SCOPE_SEQUENCE2_ENGINEERING_DECISION_ID
        ),
        "sequence2_completion_gate_engineering_execution_id": (
            USER_SCOPE_SEQUENCE2_ENGINEERING_EXECUTION_ID
        ),
        "sequence2_completion_gate_engineering_request_id": (
            USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_ID
        ),
        "sequence2_completion_gate_engineering_request_key": (
            USER_SCOPE_SEQUENCE2_ENGINEERING_REQUEST_KEY
        ),
        "sequence2_completion_gate_engineering_request_payload_sha256": (
            USER_SCOPE_SEQUENCE2_ENGINEERING_PAYLOAD_SHA256
        ),
    }:
        raise IsolatedRunnerError("user_scope_completion_source_binding_changed")
    if {
        "sequence3_guard_recovery_base_merged_commit": bindings.get(
            "sequence3_guard_recovery_base_merged_commit"
        ),
        "sequence3_guard_recovery_engineering_approval_decision_id": bindings.get(
            "sequence3_guard_recovery_engineering_approval_decision_id"
        ),
        "sequence3_guard_recovery_engineering_execution_id": bindings.get(
            "sequence3_guard_recovery_engineering_execution_id"
        ),
        "sequence3_guard_recovery_engineering_request_id": bindings.get(
            "sequence3_guard_recovery_engineering_request_id"
        ),
        "sequence3_guard_recovery_engineering_request_key": bindings.get(
            "sequence3_guard_recovery_engineering_request_key"
        ),
        "sequence3_guard_recovery_engineering_request_payload_sha256": bindings.get(
            "sequence3_guard_recovery_engineering_request_payload_sha256"
        ),
    } != {
        "sequence3_guard_recovery_base_merged_commit": (
            USER_SCOPE_COMPLETION_REPAIR_BASE_COMMIT
        ),
        "sequence3_guard_recovery_engineering_approval_decision_id": (
            USER_SCOPE_SEQUENCE3_ENGINEERING_DECISION_ID
        ),
        "sequence3_guard_recovery_engineering_execution_id": (
            USER_SCOPE_SEQUENCE3_ENGINEERING_EXECUTION_ID
        ),
        "sequence3_guard_recovery_engineering_request_id": (
            USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_ID
        ),
        "sequence3_guard_recovery_engineering_request_key": (
            USER_SCOPE_SEQUENCE3_ENGINEERING_REQUEST_KEY
        ),
        "sequence3_guard_recovery_engineering_request_payload_sha256": (
            USER_SCOPE_SEQUENCE3_ENGINEERING_PAYLOAD_SHA256
        ),
    }:
        raise IsolatedRunnerError("user_scope_guard_recovery_source_binding_changed")
    if {
        "second_terminal_guard_repair_base_merged_commit": bindings.get(
            "second_terminal_guard_repair_base_merged_commit"
        ),
        "second_terminal_guard_repair_engineering_approval_decision_id": bindings.get(
            "second_terminal_guard_repair_engineering_approval_decision_id"
        ),
        "second_terminal_guard_repair_engineering_execution_id": bindings.get(
            "second_terminal_guard_repair_engineering_execution_id"
        ),
        "second_terminal_guard_repair_engineering_request_id": bindings.get(
            "second_terminal_guard_repair_engineering_request_id"
        ),
        "second_terminal_guard_repair_engineering_request_key": bindings.get(
            "second_terminal_guard_repair_engineering_request_key"
        ),
        "second_terminal_guard_repair_engineering_request_payload_sha256": bindings.get(
            "second_terminal_guard_repair_engineering_request_payload_sha256"
        ),
    } != {
        "second_terminal_guard_repair_base_merged_commit": (
            USER_SCOPE_SECOND_GUARD_REPAIR_BASE_COMMIT
        ),
        "second_terminal_guard_repair_engineering_approval_decision_id": (
            USER_SCOPE_SECOND_GUARD_ENGINEERING_DECISION_ID
        ),
        "second_terminal_guard_repair_engineering_execution_id": (
            USER_SCOPE_SECOND_GUARD_ENGINEERING_EXECUTION_ID
        ),
        "second_terminal_guard_repair_engineering_request_id": (
            USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_ID
        ),
        "second_terminal_guard_repair_engineering_request_key": (
            USER_SCOPE_SECOND_GUARD_ENGINEERING_REQUEST_KEY
        ),
        "second_terminal_guard_repair_engineering_request_payload_sha256": (
            USER_SCOPE_SECOND_GUARD_ENGINEERING_PAYLOAD_SHA256
        ),
    }:
        raise IsolatedRunnerError("user_scope_second_guard_source_binding_changed")
    if {
        "running_projection_resume_repair_base_merged_commit": bindings.get(
            "running_projection_resume_repair_base_merged_commit"
        ),
        "running_projection_resume_repair_engineering_approval_decision_id": bindings.get(
            "running_projection_resume_repair_engineering_approval_decision_id"
        ),
        "running_projection_resume_repair_engineering_execution_id": bindings.get(
            "running_projection_resume_repair_engineering_execution_id"
        ),
        "running_projection_resume_repair_engineering_request_id": bindings.get(
            "running_projection_resume_repair_engineering_request_id"
        ),
        "running_projection_resume_repair_engineering_request_key": bindings.get(
            "running_projection_resume_repair_engineering_request_key"
        ),
        "running_projection_resume_repair_engineering_request_payload_sha256": bindings.get(
            "running_projection_resume_repair_engineering_request_payload_sha256"
        ),
    } != {
        "running_projection_resume_repair_base_merged_commit": (
            USER_SCOPE_RUNNING_RESUME_REPAIR_BASE_COMMIT
        ),
        "running_projection_resume_repair_engineering_approval_decision_id": (
            USER_SCOPE_ENGINEERING_DECISION_ID
        ),
        "running_projection_resume_repair_engineering_execution_id": (
            USER_SCOPE_ENGINEERING_EXECUTION_ID
        ),
        "running_projection_resume_repair_engineering_request_id": (
            USER_SCOPE_ENGINEERING_REQUEST_ID
        ),
        "running_projection_resume_repair_engineering_request_key": (
            USER_SCOPE_ENGINEERING_REQUEST_KEY
        ),
        "running_projection_resume_repair_engineering_request_payload_sha256": (
            USER_SCOPE_ENGINEERING_PAYLOAD_SHA256
        ),
    }:
        raise IsolatedRunnerError("user_scope_running_resume_source_binding_changed")
    if source_contract.get("artifact_digest") != repaired_source_digest:
        raise IsolatedRunnerError("user_scope_repaired_source_changed")

    engineering = repository.get_request(USER_SCOPE_ENGINEERING_REQUEST_KEY)
    engineering_decisions = repository.list_decisions(
        USER_SCOPE_ENGINEERING_REQUEST_KEY
    )
    engineering_executions = repository.list_execution_metadata(
        USER_SCOPE_ENGINEERING_REQUEST_KEY
    )
    approval = [
        item
        for item in engineering_decisions
        if item.id == USER_SCOPE_ENGINEERING_DECISION_ID
        and item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    execution = [
        item
        for item in engineering_executions
        if item.id == USER_SCOPE_ENGINEERING_EXECUTION_ID
    ]
    if (
        engineering.id != USER_SCOPE_ENGINEERING_REQUEST_ID
        or engineering.request_type is not AgentRequestType.ENGINEERING_RUNTIME_FIX
        or engineering.status is not AgentRequestStatus.COMPLETED
        or engineering.metadata.get("payload_sha256")
        != USER_SCOPE_ENGINEERING_PAYLOAD_SHA256
        or len(approval) != 1
        or approval[0].decided_by_role is not AgentRole.REVIEWER
        or len(execution) != 1
        or execution[0].status is not AgentExecutionStatus.COMPLETED
        or execution[0].environment != "development"
        or execution[0].executor_role is not AgentRole.ENGINEERING
    ):
        raise IsolatedRunnerError("user_scope_engineering_governance_changed")

    operator_key = os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "")
    try:
        operator_decision_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "")
        )
        operator_execution_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "")
        )
    except ValueError as exc:
        raise IsolatedRunnerError("user_scope_operator_identity_invalid") from exc
    if not operator_key or operator_decision_id < 1 or operator_execution_id < 1:
        raise IsolatedRunnerError("user_scope_operator_identity_invalid")
    operator = repository.get_request(operator_key)
    operator_approvals = [
        item
        for item in repository.list_decisions(operator_key)
        if item.id == operator_decision_id
        and item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    operator_executions = [
        item
        for item in repository.list_execution_metadata(operator_key)
        if item.id == operator_execution_id
    ]
    checks = operator.payload.get("checks")
    recovery = (
        checks.get("user_systemd_running_batch_recovery")
        if isinstance(checks, dict)
        else None
    )
    expected_recovery = {
        "candidate_result_count": 0,
        "current_manifest_digest": USER_SCOPE_FAILED_MANIFEST_DIGEST,
        "engineering_approval_decision_id": USER_SCOPE_ENGINEERING_DECISION_ID,
        "engineering_execution_id": USER_SCOPE_ENGINEERING_EXECUTION_ID,
        "engineering_request_id": USER_SCOPE_ENGINEERING_REQUEST_ID,
        "execution_attempt_count": contract.ATTEMPTS_PER_BATCH,
        "origin_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "origin_source_contract_digest": USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "registered_candidate_count": contract.ATTEMPTS_PER_BATCH,
        "repaired_source_contract_digest": repaired_source_digest,
        "running_execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "running_task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "running_task_key": USER_SCOPE_RESUME_TASK_KEY,
        "started_event_digest": USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        "prior_failed_event_digest": USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "next_completion_sequence": 3,
        "predecessor_attestation_digest": USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST,
    }
    mail_contract = operator.payload.get("mail_contract")
    resource_contract = operator.payload.get("resource_contract")
    operations = operator.payload.get("ordered_operations")
    if (
        operator.request_type is not AgentRequestType.OPERATOR_RELEASE
        or operator.status is not AgentRequestStatus.EXECUTING
        or operator.parent_request_id != USER_SCOPE_ENGINEERING_REQUEST_ID
        or len(operator_approvals) != 1
        or operator_approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(operator_executions) != 1
        or operator_executions[0].status is not AgentExecutionStatus.RUNNING
        or operator_executions[0].environment != "production"
        or operator_executions[0].executor_role is not AgentRole.OPERATOR
        or operator.payload.get("version")
        != "m4-isolated-v11-sequence3-guard-recovery-v4"
        or operator.payload.get("commit") != git_commit
        or recovery != expected_recovery
        or not isinstance(mail_contract, dict)
        or mail_contract.get("mandatory_kinds") != list(USER_SCOPE_MANDATORY_MAIL_KINDS)
        or mail_contract.get("sent")
        != (
            "Only SMTP final DATA250 plus append-only exactly-once "
            "receipt/artifact/replay projects SENT"
        )
        or resource_contract
        != {
            "continuous_24h": True,
            "p3_mutation": False,
            "p3_preempts": True,
            "p4_p5_p6_or_promotion": False,
            "workers_max": contract.WORKER_COUNT,
        }
        or not isinstance(operations, list)
        or "resume-p3-user-scope-running-batch" not in operations
        or "recover-user-systemd-post-batch" not in operations
    ):
        raise IsolatedRunnerError("user_scope_operator_scope_changed")
    payload_sha = hashlib.sha256(
        contract.canonical_json(operator.payload).encode("utf-8")
    ).hexdigest()
    if operator.metadata.get("payload_sha256") != payload_sha:
        raise IsolatedRunnerError("user_scope_operator_payload_sha_changed")
    return {
        "phase": phase,
        "engineering_request_id": USER_SCOPE_ENGINEERING_REQUEST_ID,
        "engineering_decision_id": USER_SCOPE_ENGINEERING_DECISION_ID,
        "engineering_execution_id": USER_SCOPE_ENGINEERING_EXECUTION_ID,
        "operator_request_id": operator.id,
        "operator_decision_id": operator_decision_id,
        "operator_execution_id": operator_execution_id,
        "operator_payload_sha256": payload_sha,
    }


def validate_user_scope_committed_recovery_governance(
    *,
    repository: AgentRequestRepository,
    source_contract: Mapping[str, Any],
    repaired_source_digest: str,
    git_commit: str,
) -> dict[str, Any]:
    bindings = source_contract.get("governance_bindings")
    expected_binding = {
        "committed_replay_repair_base_merged_commit": (
            USER_SCOPE_COMMITTED_REPAIR_BASE_COMMIT
        ),
        "committed_replay_repair_engineering_approval_decision_id": (
            USER_SCOPE_COMMITTED_ENGINEERING_DECISION_ID
        ),
        "committed_replay_repair_engineering_execution_id": (
            USER_SCOPE_COMMITTED_ENGINEERING_EXECUTION_ID
        ),
        "committed_replay_repair_engineering_request_id": (
            USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_ID
        ),
        "committed_replay_repair_engineering_request_key": (
            USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_KEY
        ),
        "committed_replay_repair_engineering_request_payload_sha256": (
            USER_SCOPE_COMMITTED_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected_binding} != expected_binding
        or source_contract.get("artifact_digest") != repaired_source_digest
    ):
        raise IsolatedRunnerError("committed_recovery_engineering_binding_changed")
    engineering = repository.get_request(USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_KEY)
    approvals = [
        item
        for item in repository.list_decisions(
            USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_KEY
        )
        if item.id == USER_SCOPE_COMMITTED_ENGINEERING_DECISION_ID
        and item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    executions = [
        item
        for item in repository.list_execution_metadata(
            USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_KEY
        )
        if item.id == USER_SCOPE_COMMITTED_ENGINEERING_EXECUTION_ID
    ]
    if (
        engineering.id != USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_ID
        or engineering.request_type is not AgentRequestType.ENGINEERING_RUNTIME_FIX
        or engineering.status is not AgentRequestStatus.COMPLETED
        or engineering.metadata.get("payload_sha256")
        != USER_SCOPE_COMMITTED_ENGINEERING_PAYLOAD_SHA256
        or len(approvals) != 1
        or approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.COMPLETED
        or executions[0].environment != "development"
        or executions[0].executor_role is not AgentRole.ENGINEERING
    ):
        raise IsolatedRunnerError("committed_recovery_engineering_governance_changed")
    operator_key = os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY", "")
    try:
        operator_decision_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID", "")
        )
        operator_execution_id = int(
            os.environ.get("DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID", "")
        )
    except ValueError as exc:
        raise IsolatedRunnerError(
            "committed_recovery_operator_identity_invalid"
        ) from exc
    if not operator_key or operator_decision_id < 1 or operator_execution_id < 1:
        raise IsolatedRunnerError("committed_recovery_operator_identity_invalid")
    operator = repository.get_request(operator_key)
    operator_approvals = [
        item
        for item in repository.list_decisions(operator_key)
        if item.id == operator_decision_id
        and item.decision_code == "request_approved"
        and item.previous_status == "under_review"
        and item.new_status == "approved"
    ]
    operator_executions = [
        item
        for item in repository.list_execution_metadata(operator_key)
        if item.id == operator_execution_id
    ]
    checks = operator.payload.get("checks")
    recovery = (
        checks.get("user_systemd_committed_batch_recovery")
        if isinstance(checks, dict)
        else None
    )
    expected_recovery = {
        "candidate_result_count": 0,
        "committed_event_digest": USER_SCOPE_COMMITTED_EVENT_DIGEST,
        "committed_manifest_digest": USER_SCOPE_COMMITTED_MANIFEST_DIGEST,
        "engineering_approval_decision_id": (
            USER_SCOPE_COMMITTED_ENGINEERING_DECISION_ID
        ),
        "engineering_execution_id": USER_SCOPE_COMMITTED_ENGINEERING_EXECUTION_ID,
        "engineering_request_id": USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_ID,
        "execution_artifact_digest": (USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST),
        "execution_attempt_count": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_committed": 0,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "origin_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "origin_source_contract_digest": USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "publication_batch_digest": USER_SCOPE_COMMITTED_PUBLICATION_BATCH_DIGEST,
        "registered_artifact_count": 65,
        "registered_candidate_count": contract.ATTEMPTS_PER_BATCH,
        "repaired_source_contract_digest": repaired_source_digest,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "workload_rerun": False,
    }
    mail_contract = operator.payload.get("mail_contract")
    resource_contract = operator.payload.get("resource_contract")
    operations = operator.payload.get("ordered_operations")
    if (
        operator.request_type is not AgentRequestType.OPERATOR_RELEASE
        or operator.status is not AgentRequestStatus.EXECUTING
        or operator.parent_request_id != USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_ID
        or len(operator_approvals) != 1
        or operator_approvals[0].decided_by_role is not AgentRole.REVIEWER
        or len(operator_executions) != 1
        or operator_executions[0].status is not AgentExecutionStatus.RUNNING
        or operator_executions[0].environment != "production"
        or operator_executions[0].executor_role is not AgentRole.OPERATOR
        or operator.payload.get("version")
        != "m4-isolated-v11-sequence3-committed-replay-recovery-v1"
        or operator.payload.get("commit") != git_commit
        or recovery != expected_recovery
        or not isinstance(mail_contract, dict)
        or mail_contract.get("mandatory_kinds") != list(USER_SCOPE_MANDATORY_MAIL_KINDS)
        or mail_contract.get("timezone") != "Asia/Shanghai"
        or mail_contract.get("predraw_schedule") != "17:00 Tuesday Thursday Sunday"
        or mail_contract.get("daily_research_summary_schedule") != "09:00 daily"
        or mail_contract.get("postdraw") != "only after audited draw"
        or mail_contract.get("incident") != "immediate fail-closed"
        or mail_contract.get("sent")
        != (
            "Only SMTP final DATA250 plus append-only exactly-once "
            "receipt/artifact/replay projects SENT"
        )
        or resource_contract
        != {
            "continuous_24h": True,
            "p3_mutation": False,
            "p3_preempts": True,
            "p4_p5_p6_or_promotion": False,
            "workers_max": contract.WORKER_COUNT,
        }
        or not isinstance(operations, list)
        or "recover-committed-batch-replay-ledger" not in operations
        or "recover-user-systemd-post-batch" not in operations
        or "deploy-isolated-mail-runtime" not in operations
    ):
        raise IsolatedRunnerError("committed_recovery_operator_scope_changed")
    payload_sha = hashlib.sha256(
        contract.canonical_json(operator.payload).encode("utf-8")
    ).hexdigest()
    if operator.metadata.get("payload_sha256") != payload_sha:
        raise IsolatedRunnerError("committed_recovery_operator_payload_sha_changed")
    return {
        "phase": "committed_replay",
        "engineering_request_id": USER_SCOPE_COMMITTED_ENGINEERING_REQUEST_ID,
        "engineering_decision_id": USER_SCOPE_COMMITTED_ENGINEERING_DECISION_ID,
        "engineering_execution_id": USER_SCOPE_COMMITTED_ENGINEERING_EXECUTION_ID,
        "operator_request_id": operator.id,
        "operator_decision_id": operator_decision_id,
        "operator_execution_id": operator_execution_id,
        "operator_payload_sha256": payload_sha,
    }


DAILY_RECOVERY_RESEARCH_REQUEST_KEY = (
    "research-m4-isolated-v11-daily-mail-failure-recovery-addendum-v5"
)
DAILY_RECOVERY_ENGINEERING_REQUEST_KEY = (
    "engineering-m4-isolated-v11-real-daily-mail-recovery-v1"
)
DAILY_RECOVERY_OPERATOR_ENV_KEY = "DEHPS_ISOLATED_V11_OPERATOR_REQUEST_KEY"
DAILY_RECOVERY_OPERATOR_DECISION_ENV = "DEHPS_ISOLATED_V11_OPERATOR_DECISION_ID"
DAILY_RECOVERY_OPERATOR_EXECUTION_ENV = "DEHPS_ISOLATED_V11_OPERATOR_EXECUTION_ID"
DAILY_RECOVERY_OPERATIONS = (
    "disable-isolated-timer-and-wait-quiescent",
    "register-new-source-and-runtime-migration-input",
    "recover-daily-summary-sequence2-and-generic-replay",
    "rebind-all-unexecuted-old-source-tasks",
    "complete-daily-mail-chain-with-one-data250",
    "resolve-current-incident-and-advance-ledger",
    "prove-duplicate-cycle-zero-smtp",
    "reenable-isolated-timer-and-verify-status",
)


def validate_daily_mail_recovery_governance(
    *,
    repository: AgentRequestRepository,
    source_contract: Mapping[str, Any],
    runtime_source_digest: str,
    git_commit: str,
) -> dict[str, Any]:
    _validate_compatibility_binding_scope_fix_engineering_governance(repository)
    bindings = source_contract.get("governance_bindings")
    expected = {
        "daily_mail_recovery_base_merged_commit": (
            contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT
        ),
        "daily_mail_recovery_research_request_id": (
            contract.DAILY_RECOVERY_RESEARCH_REQUEST_ID
        ),
        "daily_mail_recovery_research_approval_decision_id": (
            contract.DAILY_RECOVERY_RESEARCH_APPROVAL_DECISION_ID
        ),
        "daily_mail_recovery_research_request_payload_sha256": (
            contract.DAILY_RECOVERY_RESEARCH_PAYLOAD_SHA256
        ),
        "daily_mail_recovery_engineering_request_id": (
            contract.DAILY_RECOVERY_ENGINEERING_REQUEST_ID
        ),
        "daily_mail_recovery_engineering_approval_decision_id": (
            contract.DAILY_RECOVERY_ENGINEERING_APPROVAL_DECISION_ID
        ),
        "daily_mail_recovery_engineering_execution_id": (
            contract.DAILY_RECOVERY_ENGINEERING_EXECUTION_ID
        ),
        "daily_mail_recovery_engineering_request_payload_sha256": (
            contract.DAILY_RECOVERY_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        not isinstance(bindings, dict)
        or {key: bindings.get(key) for key in expected} != expected
        or source_contract.get("artifact_digest") != runtime_source_digest
        or _GIT_COMMIT.fullmatch(git_commit) is None
    ):
        raise IsolatedRunnerError("daily_recovery_source_governance_changed")
    research = repository.get_request(DAILY_RECOVERY_RESEARCH_REQUEST_KEY)
    engineering = repository.get_request(DAILY_RECOVERY_ENGINEERING_REQUEST_KEY)
    research_approvals = [
        item
        for item in repository.list_decisions(DAILY_RECOVERY_RESEARCH_REQUEST_KEY)
        if item.id == contract.DAILY_RECOVERY_RESEARCH_APPROVAL_DECISION_ID
        and item.decision_code == "request_approved"
        and item.new_status == "approved"
        and item.decided_by_role is AgentRole.REVIEWER
    ]
    engineering_approvals = [
        item
        for item in repository.list_decisions(DAILY_RECOVERY_ENGINEERING_REQUEST_KEY)
        if item.id == contract.DAILY_RECOVERY_ENGINEERING_APPROVAL_DECISION_ID
        and item.decision_code == "request_approved"
        and item.new_status == "approved"
        and item.decided_by_role is AgentRole.REVIEWER
    ]
    engineering_executions = [
        item
        for item in repository.list_execution_metadata(
            DAILY_RECOVERY_ENGINEERING_REQUEST_KEY
        )
        if item.id == contract.DAILY_RECOVERY_ENGINEERING_EXECUTION_ID
    ]
    if (
        research.id != contract.DAILY_RECOVERY_RESEARCH_REQUEST_ID
        or research.status is not AgentRequestStatus.APPROVED
        or research.metadata.get("payload_sha256")
        != contract.DAILY_RECOVERY_RESEARCH_PAYLOAD_SHA256
        or len(research_approvals) != 1
        or engineering.id != contract.DAILY_RECOVERY_ENGINEERING_REQUEST_ID
        or engineering.status is not AgentRequestStatus.COMPLETED
        or engineering.parent_request_id != research.id
        or engineering.metadata.get("payload_sha256")
        != contract.DAILY_RECOVERY_ENGINEERING_PAYLOAD_SHA256
        or len(engineering_approvals) != 1
        or len(engineering_executions) != 1
        or engineering_executions[0].status is not AgentExecutionStatus.COMPLETED
        or engineering_executions[0].environment != "development"
        or engineering_executions[0].executor_role is not AgentRole.ENGINEERING
    ):
        raise IsolatedRunnerError("daily_recovery_engineering_governance_changed")
    operator_key = os.environ.get(DAILY_RECOVERY_OPERATOR_ENV_KEY, "")
    try:
        operator_decision_id = int(
            os.environ.get(DAILY_RECOVERY_OPERATOR_DECISION_ENV, "")
        )
        operator_execution_id = int(
            os.environ.get(DAILY_RECOVERY_OPERATOR_EXECUTION_ENV, "")
        )
    except ValueError as exc:
        raise IsolatedRunnerError("daily_recovery_operator_identity_invalid") from exc
    if not operator_key or operator_decision_id < 1 or operator_execution_id < 1:
        raise IsolatedRunnerError("daily_recovery_operator_identity_invalid")
    operator = repository.get_request(operator_key)
    approvals = [
        item
        for item in repository.list_decisions(operator_key)
        if item.id == operator_decision_id
        and item.decision_code == "request_approved"
        and item.new_status == "approved"
        and item.decided_by_role is AgentRole.REVIEWER
    ]
    executions = [
        item
        for item in repository.list_execution_metadata(operator_key)
        if item.id == operator_execution_id
    ]
    payload_sha = hashlib.sha256(
        contract.canonical_json(operator.payload).encode("utf-8")
    ).hexdigest()
    expected_failed = {
        "task_key": contract.DAILY_RECOVERY_TASK_KEY,
        "task_digest": contract.DAILY_RECOVERY_TASK_DIGEST,
        "execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
        "started_event_digest": contract.DAILY_RECOVERY_STARTED_EVENT_DIGEST,
        "failed_event_digest": contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST,
        "original_source_contract_digest": (
            contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
        ),
        "original_git_commit": contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT,
        "workload_rerun": False,
    }
    expected_binding_scope_fix = {
        "engineering_request_id": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_REQUEST_ID
        ),
        "engineering_approval_decision_id": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_DECISION_ID
        ),
        "engineering_execution_id": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_EXECUTION_ID
        ),
        "engineering_request_payload_sha256": (
            COMPATIBILITY_BINDING_SCOPE_FIX_ENGINEERING_PAYLOAD_SHA256
        ),
    }
    if (
        operator.request_type is not AgentRequestType.OPERATOR_RELEASE
        or operator.status is not AgentRequestStatus.EXECUTING
        or operator.parent_request_id != engineering.id
        or len(approvals) != 1
        or len(executions) != 1
        or executions[0].status is not AgentExecutionStatus.RUNNING
        or executions[0].environment != "production"
        or executions[0].executor_role is not AgentRole.OPERATOR
        or operator.payload.get("version")
        != "m4-isolated-v11-daily-mail-recovery-operator-v1"
        or operator.payload.get("commit") != git_commit
        or operator.payload.get("source_contract_digest") != runtime_source_digest
        or operator.payload.get("binding_scope_fix") != expected_binding_scope_fix
        or operator.payload.get("failed_execution") != expected_failed
        or tuple(operator.payload.get("ordered_operations") or ())
        != DAILY_RECOVERY_OPERATIONS
        or operator.payload.get("smtp_budget") != 1
        or operator.payload.get("scientific_workload_budget") != 0
        or operator.payload.get("formal_p3_access_or_mutation") is not False
        or operator.payload.get("p4_p5_p6_or_promotion") is not False
        or operator.metadata.get("payload_sha256") != payload_sha
    ):
        raise IsolatedRunnerError("daily_recovery_operator_scope_changed")
    return {
        "operator_request_id": operator.id,
        "operator_approval_decision_id": operator_decision_id,
        "operator_execution_id": operator_execution_id,
        "operator_payload_sha256": payload_sha,
        "operator_execution_started_at": executions[0].started_at.isoformat(),
    }


class IsolatedChallengerRepository(PostgresResearchOSRepository):
    """Exact fail-closed repository gate for the independent V11 control plane."""

    def __init__(self, *, context: Mapping[str, str], source_digest: str) -> None:
        super().__init__()
        self.context = dict(context)
        self.source_digest = contract.require_digest(
            source_digest, field="source_digest"
        )
        self._fact_gate: dict[str, Any] | None = None
        self._definition_gate: dict[str, Any] | None = None
        self._bootstrap_rebind_gate: dict[str, Any] | None = None
        self._user_scope_resume_event_gate = False
        self._user_scope_failed_transition_gate: dict[str, Any] | None = None
        self._daily_recovery_event_gate = False
        self._daily_recovery_transition_gate: dict[str, Any] | None = None
        self._evolving_source_rebind_gate: dict[str, Any] | None = None

    @contextmanager
    def daily_recovery_event_view(self) -> Iterator[None]:
        if (
            self._daily_recovery_event_gate
            or self._daily_recovery_transition_gate is not None
            or self._user_scope_resume_event_gate
        ):
            raise IsolatedRunnerError("daily_recovery_event_gate_reentrant")
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        if current.artifact_digest != DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST:
            raise IsolatedRunnerError("daily_recovery_current_manifest_changed")
        self._daily_recovery_event_gate = True
        self._daily_recovery_transition_gate = {
            "current_manifest_digest": DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST,
            "running_manifest_digest": DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST,
            "router_consumed": True,
            "completion_consumed": True,
            "authoritative_completion_consumed": False,
        }
        try:
            yield
        finally:
            self._daily_recovery_event_gate = False
            self._daily_recovery_transition_gate = None

    @contextmanager
    def user_scope_resume_event_view(self) -> Iterator[None]:
        if (
            self._user_scope_resume_event_gate
            or getattr(self, "_user_scope_failed_transition_gate", None) is not None
        ):
            raise IsolatedRunnerError("user_scope_resume_event_gate_reentrant")
        self._user_scope_resume_event_gate = True
        self._user_scope_failed_transition_gate = {
            "router_consumed": False,
            "completion_consumed": False,
        }
        try:
            yield
        finally:
            self._user_scope_resume_event_gate = False
            self._user_scope_failed_transition_gate = None

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        daily_query = getattr(self, "_daily_recovery_event_gate", False) and (
            task_key == contract.DAILY_RECOVERY_TASK_KEY
            or execution_id == contract.DAILY_RECOVERY_EXECUTION_ID
        )
        guarded_query = (
            self._user_scope_resume_event_gate
            and (
                task_key == USER_SCOPE_RESUME_TASK_KEY
                or execution_id == USER_SCOPE_RESUME_EXECUTION_ID
            )
        ) or daily_query
        if not guarded_query:
            return super().list_mainline_execution_events(
                control_plane_key=control_plane_key,
                task_key=task_key,
                execution_id=execution_id,
            )
        if daily_query:
            if (
                control_plane_key != contract.CONTROL_PLANE_KEY
                or task_key not in {None, contract.DAILY_RECOVERY_TASK_KEY}
                or execution_id not in {None, contract.DAILY_RECOVERY_EXECUTION_ID}
            ):
                raise IsolatedRunnerError("daily_recovery_event_query_changed")
            unfiltered = super().list_mainline_execution_events(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                task_key=contract.DAILY_RECOVERY_TASK_KEY,
            )
            records = [_event_record(item) for item in unfiltered]
            if (
                len(records) not in {2, 3}
                or [(item.event_type, item.sequence) for item in records[:2]]
                != [("started", 0), ("failed", 1)]
                or records[0].artifact_digest
                != contract.DAILY_RECOVERY_STARTED_EVENT_DIGEST
                or records[1].artifact_digest
                != contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST
                or any(
                    item.execution_id != contract.DAILY_RECOVERY_EXECUTION_ID
                    or item.task_digest != contract.DAILY_RECOVERY_TASK_DIGEST
                    for item in records
                )
                or (
                    len(records) == 3
                    and (records[2].event_type, records[2].sequence) != ("completed", 2)
                )
            ):
                raise IsolatedRunnerError("daily_recovery_event_set_changed")
            return tuple(unfiltered)
        if (
            control_plane_key != contract.CONTROL_PLANE_KEY
            or task_key not in {None, USER_SCOPE_RESUME_TASK_KEY}
            or execution_id not in {None, USER_SCOPE_RESUME_EXECUTION_ID}
        ):
            raise IsolatedRunnerError("user_scope_resume_event_query_changed")
        unfiltered = super().list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=USER_SCOPE_RESUME_TASK_KEY,
        )
        _validate_user_scope_resume_event_set(unfiltered, allow_completed=True)
        return tuple(
            item
            for item in unfiltered
            if item.get("task_digest") == USER_SCOPE_RESUME_TASK_DIGEST
            and item.get("execution_id") == USER_SCOPE_RESUME_EXECUTION_ID
        )

    def _expected_definition(
        self,
        *,
        operator_authorized: bool,
        context: Mapping[str, str] | None = None,
        source_digest: str | None = None,
    ) -> ControlPlaneManifest:
        payload, _ = builder.build_bootstrap_manifest(
            context=dict(context or self.context),
            source_digest=source_digest or self.source_digest,
            operator_configuration_authorized=operator_authorized,
        )
        return ControlPlaneManifest.from_dict(payload)

    @staticmethod
    def _definitions(manifest: ControlPlaneManifest) -> tuple[Any, ...]:
        return tuple(item.to_dict() for item in manifest.goals)

    def _verify_isolated_task_definition(
        self,
        task: Any,
        *,
        state: Any,
        artifact_facts: frozenset[str],
        partial_live_rebind: bool,
        daily_recovery_historical_only: bool = False,
    ) -> None:
        try:
            metric = json.loads(task.metric_contract)
            raw_context = metric["render_context"]
            bound_source_digest = contract.require_digest(
                metric["source_contract_digest"], field="task_source_contract_digest"
            )
            normalized = contract.render_context(
                source_max_issue=str(raw_context["source_max_issue"]),
                source_max_draw_date=str(raw_context["source_max_draw_date"]),
                target_issue=str(raw_context["target_issue"]),
                target_draw_date=str(raw_context["target_draw_date"]),
                batch_seq=int(raw_context["batch_seq"]),
                epoch_date=str(raw_context["epoch_date"]),
                minute=str(raw_context["minute"]),
                incident_id=str(raw_context["incident_id"]),
                incident_reason_code=str(raw_context["incident_reason_code"]),
                incident_offending_digest=str(raw_context["incident_offending_digest"]),
                cut_checkpoint_ref=str(raw_context["cut_checkpoint_ref"]),
                projection_time=str(raw_context["projection_time"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ResearchOSValidationError(
                "isolated_v11_task_context_changed"
            ) from exc
        if dict(raw_context) != normalized:
            raise ResearchOSValidationError("isolated_v11_task_context_changed")
        if bound_source_digest != self.source_digest:
            completion_prefix = (
                f"mainline-execution:{task.task_key}:{task.artifact_digest}:"
            )
            has_completion_fact = any(
                fact.startswith(completion_prefix) and fact.endswith(":completed")
                for fact in artifact_facts
            )
            daily_recovery_transition = (
                daily_recovery_historical_only
                and task.task_key == contract.DAILY_RECOVERY_TASK_KEY
                and task.artifact_digest == contract.DAILY_RECOVERY_TASK_DIGEST
                and bound_source_digest
                == contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
                and state.declared_status in {TaskStatus.FAILED, TaskStatus.RUNNING}
                and self._daily_recovery_transition_gate is not None
                and not has_completion_fact
            )
            unchanged_rebind_candidate = (
                daily_recovery_historical_only
                and state.declared_status is TaskStatus.DRAFT
                and self._daily_recovery_transition_gate is not None
                and not has_completion_fact
            )
            if (
                bound_source_digest not in LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS
                or (
                    state.declared_status is not TaskStatus.COMPLETED
                    and not daily_recovery_transition
                    and not unchanged_rebind_candidate
                )
                or (
                    state.declared_status is TaskStatus.COMPLETED
                    and not has_completion_fact
                )
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_historical_task_source_changed"
                )
        expected_payload, _ = builder.build_manifest(
            context=normalized,
            source_digest=bound_source_digest,
            operator_configuration_authorized=True,
            simulation_events=False,
        )
        expected = ControlPlaneManifest.from_dict(expected_payload)
        matches = [item for item in expected.tasks if item.task_key == task.task_key]
        if len(matches) != 1:
            raise ResearchOSValidationError("isolated_v11_task_definition_changed")
        expected_task = matches[0]
        if (
            task.task_key
            == (
                "m4-isolated-24h-challenger-v11-incident-"
                f"{contract.DAILY_RECOVERY_INCIDENT_ID}-open"
            )
            and task.artifact_digest == DAILY_RECOVERY_LEGACY_INCIDENT_OPEN_TASK_DIGEST
            and bound_source_digest == contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
            and state.declared_status is TaskStatus.COMPLETED
        ):
            return
        if partial_live_rebind:
            expected_task = replace(
                expected_task, goal_digest=LIVE_PARTIAL_FROZEN_GOAL_DIGEST
            )
        if expected_task.artifact_digest != task.artifact_digest:
            raise ResearchOSValidationError("isolated_v11_task_definition_changed")

    def _verify_exact_transition(self, incoming: ControlPlaneManifest) -> None:
        if len(incoming.tasks) != len({item.task_key for item in incoming.tasks}):
            raise ResearchOSValidationError("isolated_v11_task_set_changed")
        bound_sources = {
            str(json.loads(task.metric_contract).get("source_contract_digest") or "")
            for task in incoming.tasks
        }
        historical_source_present = bool(
            (bound_sources & LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS)
            - {self.source_digest}
        )
        partial_live_rebind = historical_source_present and (
            self.source_digest in bound_sources
        )
        daily_gate = getattr(self, "_daily_recovery_transition_gate", None)
        daily_recovery_historical_only = (
            historical_source_present
            and self.source_digest not in bound_sources
            and getattr(self, "_daily_recovery_event_gate", False) is True
            and isinstance(daily_gate, dict)
            and set(daily_gate)
            == {
                "current_manifest_digest",
                "running_manifest_digest",
                "router_consumed",
                "completion_consumed",
                "authoritative_completion_consumed",
            }
            and daily_gate.get("current_manifest_digest")
            == DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST
            and bound_sources.issubset(LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS)
        )
        if historical_source_present and (
            not (partial_live_rebind or daily_recovery_historical_only)
            or not bound_sources.issubset(
                LIVE_PARTIAL_COMPLETED_SOURCE_DIGESTS | {self.source_digest}
            )
        ):
            raise ResearchOSValidationError(
                "isolated_v11_partial_live_source_set_changed"
            )
        for task in incoming.tasks:
            self._verify_isolated_task_definition(
                task,
                state=incoming.task_state_by_digest[task.artifact_digest],
                artifact_facts=incoming.facts.artifacts,
                partial_live_rebind=(
                    partial_live_rebind or daily_recovery_historical_only
                ),
                daily_recovery_historical_only=daily_recovery_historical_only,
            )
        operator_authorized = (
            builder.OPERATOR_CONFIGURATION_AUTHORITY in incoming.facts.authorities
        )
        expected = self._expected_definition(operator_authorized=operator_authorized)
        if (
            not incoming.facts.evidence.issubset(frozenset())
            or not incoming.facts.external_events.issubset(KNOWN_EXTERNAL_EVENTS)
            or not incoming.facts.authorities.issubset(KNOWN_AUTHORITIES)
            or builder.RESEARCH_APPROVAL_AUTHORITY not in incoming.facts.authorities
        ):
            raise ResearchOSValidationError("isolated_v11_nonartifact_facts_changed")
        try:
            current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        except ResearchOSValidationError as exc:
            if "control plane not found" not in str(exc):
                raise
            if (
                self._definitions(incoming) != self._definitions(expected)
                or incoming.facts.artifacts
                or incoming.facts.external_events
                or {item.artifact_digest for item in incoming.tasks}
                != {item.artifact_digest for item in expected.tasks}
            ):
                raise ResearchOSValidationError("isolated_v11_initial_facts_changed")
            return
        evolving_gate = getattr(self, "_evolving_source_rebind_gate", None)
        if evolving_gate is not None:
            if (
                evolving_gate.get("consumed") is not False
                or evolving_gate.get("current_manifest_digest")
                != current.artifact_digest
                or evolving_gate.get("incoming_manifest_digest")
                != incoming.artifact_digest
                or evolving_gate.get("current_manifest")
                != current.to_dict(include_digest=True)
                or evolving_gate.get("incoming_manifest")
                != incoming.to_dict(include_digest=True)
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_evolving_rebind_gate_changed"
                )
            evolving_gate["consumed"] = True
            return
        rebind_gate = self._bootstrap_rebind_gate
        if rebind_gate is not None:
            if (
                rebind_gate.get("consumed") is not False
                or rebind_gate.get("current_manifest_digest") != current.artifact_digest
                or rebind_gate.get("incoming_manifest_digest")
                != incoming.artifact_digest
                or rebind_gate.get("current_manifest")
                != current.to_dict(include_digest=True)
                or rebind_gate.get("incoming_manifest")
                != incoming.to_dict(include_digest=True)
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_bootstrap_rebind_gate_changed"
                )
            rebind_gate["consumed"] = True
            return
        if self._definitions(current) != self._definitions(incoming):
            raise ResearchOSValidationError("isolated_v11_goal_transition_changed")
        current_tasks = {item.task_key: item for item in current.tasks}
        incoming_tasks = {item.task_key: item for item in incoming.tasks}
        if not set(current_tasks).issubset(incoming_tasks) or any(
            incoming_tasks[key].artifact_digest != task.artifact_digest
            for key, task in current_tasks.items()
        ):
            raise ResearchOSValidationError("isolated_v11_task_definition_regression")
        added_tasks = set(incoming_tasks) - set(current_tasks)
        added_events = set(incoming.facts.external_events) - set(
            current.facts.external_events
        )
        if added_tasks or added_events:
            gate = self._definition_gate
            if (
                gate is None
                or gate.get("consumed") is not False
                or gate.get("manifest_digest") != incoming.artifact_digest
                or gate.get("added_task_keys") != frozenset(added_tasks)
                or gate.get("added_external_events") != frozenset(added_events)
            ):
                raise ResearchOSValidationError("isolated_v11_definition_gate_changed")
            gate["consumed"] = True
        if (
            not current.facts.artifacts.issubset(incoming.facts.artifacts)
            or not current.facts.external_events.issubset(
                incoming.facts.external_events
            )
            or not current.facts.authorities.issubset(incoming.facts.authorities)
        ):
            raise ResearchOSValidationError("isolated_v11_fact_regression")
        current_states = current.task_state_by_digest
        incoming_states = incoming.task_state_by_digest
        state_changes: list[tuple[str, str, str]] = []
        for task in current.tasks:
            old = current_states[task.artifact_digest]
            new = incoming_states[task.artifact_digest]
            if old != new:
                state_changes.append(
                    (
                        task.task_key,
                        old.declared_status.value,
                        new.declared_status.value,
                    )
                )
        if len(state_changes) > 1:
            raise ResearchOSValidationError("isolated_v11_multi_task_state_change")
        if state_changes:
            changed_task_key, old, new = state_changes[0]
            transition = (old, new)
            if transition == (TaskStatus.FAILED.value, TaskStatus.RUNNING.value):
                daily_gate = getattr(self, "_daily_recovery_transition_gate", None)
                if changed_task_key == contract.DAILY_RECOVERY_TASK_KEY:
                    if (
                        daily_gate is None
                        or daily_gate.get("router_consumed") is not False
                        or daily_gate.get("completion_consumed") is not False
                        or daily_gate.get("authoritative_completion_consumed")
                        is not False
                        or daily_gate.get("current_manifest_digest")
                        != current.artifact_digest
                        or daily_gate.get("running_manifest_digest")
                        not in {None, incoming.artifact_digest}
                        or current_tasks[changed_task_key].artifact_digest
                        != contract.DAILY_RECOVERY_TASK_DIGEST
                        or added_tasks
                        or added_events
                    ):
                        raise ResearchOSValidationError(
                            "isolated_v11_daily_recovery_transition_gate_changed"
                        )
                    daily_gate["running_manifest_digest"] = incoming.artifact_digest
                    daily_gate["router_consumed"] = True
                else:
                    gate = self._user_scope_failed_transition_gate
                    if (
                        gate is None
                        or gate.get("router_consumed") is not False
                        or gate.get("completion_consumed") is not False
                        or current.artifact_digest != USER_SCOPE_FAILED_MANIFEST_DIGEST
                        or incoming.artifact_digest != USER_SCOPE_RESUME_MANIFEST_DIGEST
                        or changed_task_key != USER_SCOPE_RESUME_TASK_KEY
                        or current_tasks[changed_task_key].artifact_digest
                        != USER_SCOPE_RESUME_TASK_DIGEST
                    ):
                        raise ResearchOSValidationError(
                            "isolated_v11_failed_recovery_transition_gate_changed"
                        )
                    gate["router_consumed"] = True
            elif (
                transition
                == (
                    TaskStatus.RUNNING.value,
                    TaskStatus.COMPLETED.value,
                )
                and changed_task_key == contract.DAILY_RECOVERY_TASK_KEY
            ):
                if (
                    not daily_recovery_historical_only
                    or self._daily_recovery_event_gate is not True
                    or daily_gate.get("router_consumed") is not True
                    or daily_gate.get("completion_consumed") is not True
                    or daily_gate.get("authoritative_completion_consumed") is not False
                    or daily_gate.get("current_manifest_digest")
                    != DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST
                    or daily_gate.get("running_manifest_digest")
                    != current.artifact_digest
                    or current_tasks[changed_task_key].artifact_digest
                    != contract.DAILY_RECOVERY_TASK_DIGEST
                    or added_tasks
                    or added_events
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_daily_recovery_authoritative_transition_gate_changed"
                    )
            elif transition not in {
                (TaskStatus.DRAFT.value, TaskStatus.RUNNING.value),
                (TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value),
                (TaskStatus.RUNNING.value, TaskStatus.FAILED.value),
            }:
                raise ResearchOSValidationError("isolated_v11_task_state_regression")
        if (added_tasks or added_events) and state_changes:
            raise ResearchOSValidationError("isolated_v11_extension_changed_task_state")
        added = set(incoming.facts.artifacts) - set(current.facts.artifacts)
        mainline_facts = {item for item in added if _MAINLINE_FACT.fullmatch(item)}
        gated_facts = added - mainline_facts
        if mainline_facts and not state_changes:
            raise ResearchOSValidationError("isolated_v11_orphan_completion_fact")
        if gated_facts:
            gate = self._fact_gate
            if (
                gate is None
                or gate.get("consumed") is not False
                or gate.get("manifest_digest") != incoming.artifact_digest
                or gate.get("added_facts") != frozenset(gated_facts)
                or state_changes
            ):
                raise ResearchOSValidationError("isolated_v11_fact_gate_changed")
            gate["consumed"] = True

    def _verify_mainline_completion_records(
        self,
        cursor: Any,
        *,
        control_plane_key: str,
        manifest: ControlPlaneManifest,
        m4_v2_lifecycle_verified: bool = False,
    ) -> None:
        if control_plane_key != contract.CONTROL_PLANE_KEY:
            raise ResearchOSValidationError("isolated_v11_control_plane_changed")
        row = cursor.execute(
            "SELECT current_manifest_digest FROM research_os_control_planes "
            "WHERE control_plane_key=%s",
            (control_plane_key,),
        ).fetchone()
        if row is not None:
            stored = cursor.execute(
                "SELECT manifest_json FROM research_os_manifests "
                "WHERE manifest_digest=%s",
                (str(row["current_manifest_digest"]),),
            ).fetchone()
            if stored is None:
                raise ResearchOSValidationError("isolated_v11_current_manifest_missing")
            current = ControlPlaneManifest.from_dict(dict(stored["manifest_json"]))
            evolving_gate = getattr(self, "_evolving_source_rebind_gate", None)
            if evolving_gate is not None:
                if (
                    evolving_gate.get("consumed") is not True
                    or evolving_gate.get("current_manifest_digest")
                    != current.artifact_digest
                    or evolving_gate.get("incoming_manifest_digest")
                    != manifest.artifact_digest
                    or evolving_gate.get("current_manifest")
                    != current.to_dict(include_digest=True)
                    or evolving_gate.get("incoming_manifest")
                    != manifest.to_dict(include_digest=True)
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_evolving_rebind_completion_gate_changed"
                    )
                PostgresResearchOSRepository._verify_mainline_completion_records(
                    cursor,
                    control_plane_key=control_plane_key,
                    manifest=manifest,
                    m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
                )
                return
            rebind_gate = self._bootstrap_rebind_gate
            if rebind_gate is not None:
                if (
                    rebind_gate.get("consumed") is not True
                    or rebind_gate.get("current_manifest_digest")
                    != current.artifact_digest
                    or rebind_gate.get("incoming_manifest_digest")
                    != manifest.artifact_digest
                    or rebind_gate.get("current_manifest")
                    != current.to_dict(include_digest=True)
                    or rebind_gate.get("incoming_manifest")
                    != manifest.to_dict(include_digest=True)
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_bootstrap_rebind_completion_gate_changed"
                    )
                PostgresResearchOSRepository._verify_mainline_completion_records(
                    cursor,
                    control_plane_key=control_plane_key,
                    manifest=manifest,
                    m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
                )
                return
            current_tasks = {item.task_key: item for item in current.tasks}
            incoming_tasks = {item.task_key: item for item in manifest.tasks}
            if not set(current_tasks).issubset(incoming_tasks) or any(
                incoming_tasks[key].artifact_digest != value.artifact_digest
                for key, value in current_tasks.items()
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_completion_task_definition_changed"
                )
            state_changes = []
            for key, task in current_tasks.items():
                before = current.task_state_by_digest[task.artifact_digest]
                after = manifest.task_state_by_digest[task.artifact_digest]
                if before != after:
                    state_changes.append(
                        (
                            key,
                            before.declared_status.value,
                            after.declared_status.value,
                        )
                    )
            added_facts = set(manifest.facts.artifacts) - set(current.facts.artifacts)
            if state_changes:
                if len(state_changes) != 1:
                    raise ResearchOSValidationError(
                        "isolated_v11_atomic_completion_transition_changed"
                    )
                transition = state_changes[0][1:]
                if transition == ("failed", "running"):
                    if state_changes[0][0] == contract.DAILY_RECOVERY_TASK_KEY:
                        gate = getattr(self, "_daily_recovery_transition_gate", None)
                        if (
                            gate is None
                            or self._daily_recovery_event_gate is not True
                            or gate.get("router_consumed") is not True
                            or gate.get("completion_consumed") is not False
                            or gate.get("authoritative_completion_consumed")
                            is not False
                            or gate.get("current_manifest_digest")
                            != current.artifact_digest
                            or gate.get("running_manifest_digest")
                            != manifest.artifact_digest
                            or added_facts
                        ):
                            raise ResearchOSValidationError(
                                "isolated_v11_daily_recovery_completion_gate_changed"
                            )
                        gate["completion_consumed"] = True
                    else:
                        gate = self._user_scope_failed_transition_gate
                        if (
                            gate is None
                            or gate.get("router_consumed") is not True
                            or gate.get("completion_consumed") is not False
                            or current.artifact_digest
                            != USER_SCOPE_FAILED_MANIFEST_DIGEST
                            or manifest.artifact_digest
                            != USER_SCOPE_RESUME_MANIFEST_DIGEST
                            or state_changes[0][0] != USER_SCOPE_RESUME_TASK_KEY
                            or added_facts
                        ):
                            raise ResearchOSValidationError(
                                "isolated_v11_failed_recovery_completion_gate_changed"
                            )
                        gate["completion_consumed"] = True
                elif transition in {("draft", "running"), ("running", "failed")}:
                    if added_facts:
                        raise ResearchOSValidationError(
                            "isolated_v11_atomic_completion_transition_changed"
                        )
                elif transition == ("running", "completed"):
                    if (
                        len(added_facts) != 1
                        or _MAINLINE_FACT.fullmatch(next(iter(added_facts))) is None
                    ):
                        raise ResearchOSValidationError(
                            "isolated_v11_atomic_completion_transition_changed"
                        )
                    if state_changes[0][0] == contract.DAILY_RECOVERY_TASK_KEY:
                        gate = getattr(self, "_daily_recovery_transition_gate", None)
                        if (
                            gate is None
                            or self._daily_recovery_event_gate is not True
                            or gate.get("router_consumed") is not True
                            or gate.get("completion_consumed") is not True
                            or gate.get("authoritative_completion_consumed")
                            is not False
                            or gate.get("current_manifest_digest")
                            != DAILY_RECOVERY_CURRENT_MANIFEST_DIGEST
                            or gate.get("running_manifest_digest")
                            != current.artifact_digest
                            or current_tasks[state_changes[0][0]].artifact_digest
                            != contract.DAILY_RECOVERY_TASK_DIGEST
                        ):
                            raise ResearchOSValidationError(
                                "isolated_v11_daily_recovery_authoritative_completion_gate_changed"
                            )
                        gate["authoritative_completion_consumed"] = True
                else:
                    raise ResearchOSValidationError(
                        "isolated_v11_atomic_completion_transition_changed"
                    )
            elif added_facts:
                gate = self._fact_gate
                if (
                    gate is None
                    or gate.get("consumed") is not True
                    or gate.get("manifest_digest") != manifest.artifact_digest
                    or gate.get("added_facts") != frozenset(added_facts)
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_completion_fact_gate_changed"
                    )
        PostgresResearchOSRepository._verify_mainline_completion_records(
            cursor,
            control_plane_key=control_plane_key,
            manifest=manifest,
            m4_v2_lifecycle_verified=m4_v2_lifecycle_verified,
        )

    def import_bootstrap_manifest(self, payload: Mapping[str, Any]) -> tuple[Any, str]:
        incoming = ControlPlaneManifest.from_dict(dict(payload))
        try:
            current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        except ResearchOSValidationError as exc:
            if "control plane not found" not in str(exc):
                raise
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-24h-challenger-v11-operator-install",
            )
            return result, incoming.artifact_digest
        if current.artifact_digest == incoming.artifact_digest:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-24h-challenger-v11-operator-install",
            )
            return result, incoming.artifact_digest
        if self._bootstrap_rebind_gate is not None:
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_gate_reentrant"
            )
        current_contexts = tuple(_task_context(task) for task in current.tasks)
        incoming_contexts = {
            json.dumps(_task_context(task), sort_keys=True, separators=(",", ":"))
            for task in incoming.tasks
        }
        if not current_contexts or len(incoming_contexts) != 1:
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_context_changed"
            )
        incoming_context = json.loads(next(iter(incoming_contexts)))
        target_fields = (
            "source_max_issue",
            "source_max_draw_date",
            "target_issue",
            "target_draw_date",
        )
        incoming_target = tuple(incoming_context[key] for key in target_fields)
        if any(
            tuple(item[key] for key in target_fields) != incoming_target
            for item in current_contexts
        ):
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_target_changed"
            )

        def rebuild_task_set(source_digest: str) -> ControlPlaneManifest:
            base = self._expected_definition(
                operator_authorized=True,
                context=current_contexts[0],
                source_digest=source_digest,
            )
            tasks = []
            states = []
            for stored, item_context in zip(
                current.tasks, current_contexts, strict=True
            ):
                expected_payload, _ = builder.build_manifest(
                    context=item_context,
                    source_digest=source_digest,
                    operator_configuration_authorized=True,
                    simulation_events=False,
                )
                expected = ControlPlaneManifest.from_dict(expected_payload)
                if (
                    expected.goals != base.goals
                    or expected.goal_states != base.goal_states
                ):
                    raise ResearchOSValidationError(
                        "isolated_v11_bootstrap_rebind_goal_changed"
                    )
                matches = tuple(
                    task for task in expected.tasks if task.task_key == stored.task_key
                )
                if len(matches) != 1:
                    raise ResearchOSValidationError(
                        "isolated_v11_bootstrap_rebind_task_changed"
                    )
                task = matches[0]
                tasks.append(task)
                states.append(expected.task_state_by_digest[task.artifact_digest])
            return ControlPlaneManifest(
                goals=base.goals,
                tasks=tuple(tasks),
                goal_states=base.goal_states,
                task_states=tuple(states),
                facts=base.facts,
                schema_version=base.schema_version,
            )

        predecessor_matches = tuple(
            candidate
            for candidate in (
                rebuild_task_set(predecessor_source_digest)
                for predecessor_source_digest in sorted(
                    APPROVED_BOOTSTRAP_PREDECESSOR_SOURCE_DIGESTS
                )
            )
            if current.to_dict(include_digest=True)
            == candidate.to_dict(include_digest=True)
        )
        expected_incoming = rebuild_task_set(self.source_digest)
        live_incoming = self._expected_definition(
            operator_authorized=True,
            context=incoming_context,
        )
        if (
            len(predecessor_matches) != 1
            or incoming.to_dict(include_digest=True)
            != live_incoming.to_dict(include_digest=True)
            or len(current.tasks) < 14
            or len(expected_incoming.tasks) != len(current.tasks)
            or any(
                state.declared_status is not TaskStatus.DRAFT
                for state in current.task_states
            )
            or current.facts.artifacts
            or current.facts.evidence
            or current.facts.external_events
            or current.facts.authorities != predecessor_matches[0].facts.authorities
            or self.list_mainline_execution_event_metadata(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                task_keys=tuple(task.task_key for task in current.tasks),
            )
        ):
            raise ResearchOSValidationError(
                "isolated_v11_bootstrap_rebind_precondition_changed"
            )
        self._bootstrap_rebind_gate = {
            "current_manifest_digest": current.artifact_digest,
            "incoming_manifest_digest": expected_incoming.artifact_digest,
            "current_manifest": current.to_dict(include_digest=True),
            "incoming_manifest": expected_incoming.to_dict(include_digest=True),
            "consumed": False,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=expected_incoming.to_dict(include_digest=True),
                source="m4-isolated-24h-challenger-v11-exact-bootstrap-rebind",
            )
            if self._bootstrap_rebind_gate.get("consumed") is not True:
                raise ResearchOSValidationError(
                    "isolated_v11_bootstrap_rebind_gate_not_consumed"
                )
            return result, expected_incoming.artifact_digest
        finally:
            self._bootstrap_rebind_gate = None

    def import_manifest(
        self,
        *,
        control_plane_key: str,
        payload: dict[str, Any],
        source: str = "native",
    ):
        if control_plane_key != contract.CONTROL_PLANE_KEY:
            raise ResearchOSValidationError("isolated_v11_control_plane_changed")
        incoming = ControlPlaneManifest.from_dict(payload)
        self._verify_exact_transition(incoming)
        return super().import_manifest(
            control_plane_key=control_plane_key, payload=payload, source=source
        )

    def import_verified_facts(self, facts: Sequence[str]):
        if not facts or len(facts) != len(set(facts)):
            raise ResearchOSValidationError("isolated_v11_fact_delta_invalid")
        live = self.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        payload = builder.manifest_with_facts(live, add_artifact_facts=facts)
        manifest = ControlPlaneManifest.from_dict(payload)
        self._fact_gate = {
            "manifest_digest": manifest.artifact_digest,
            "added_facts": frozenset(facts),
            "consumed": False,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=payload,
                source="isolated-v11-after-typed-and-generic-replay",
            )
            if self._fact_gate.get("consumed") is not True:
                raise ResearchOSValidationError("isolated_v11_fact_gate_not_consumed")
            return result
        finally:
            self._fact_gate = None

    def rebind_unexecuted_daily_recovery_source(self) -> dict[str, Any]:
        if self._evolving_source_rebind_gate is not None:
            raise ResearchOSValidationError(
                "isolated_v11_evolving_rebind_gate_reentrant"
            )
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        # Reconstruct both sides from the immutable POST_COMMIT manifest, never
        # from a possibly partial or modified set of live replacement tasks.
        source = artifacts.load_source_contract(root_dir=ROOT_DIR)
        registered_source = mainline.load_registered_input(
            repository=self,
            artifact_digest=self.source_digest,
            expected_artifact_type=contract.SOURCE_ARTIFACT_TYPE,
        )
        if (
            self.source_digest == contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
            or source != registered_source
            or source["artifact_digest"] != self.source_digest
        ):
            raise ResearchOSValidationError("isolated_v11_rebind_source_changed")
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT manifest_json FROM research_os_manifests WHERE manifest_digest=%s",
                (DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST,),
            ).fetchone()
        if row is None:
            raise ResearchOSValidationError("isolated_v11_rebind_origin_missing")
        origin = ControlPlaneManifest.from_dict(dict(row[0]))
        if origin.artifact_digest != DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST:
            raise ResearchOSValidationError("isolated_v11_rebind_origin_changed")
        frozen_keys = frozenset(
            {
                "m4-isolated-24h-challenger-v11-multiplicity-risk-limit",
                "m4-isolated-24h-challenger-v11-daily-20260828-delivery",
                "m4-isolated-24h-challenger-v11-daily-20260828-mail-replay",
                "m4-isolated-24h-challenger-v11-daily-20260828-mail-envelope",
                "m4-isolated-24h-challenger-v11-daily-20260828-summary-replay",
                "m4-isolated-24h-challenger-v11-search-checkpoint-000000000004-replay",
            }
        )
        origin_by_key = {item.task_key: item for item in origin.tasks}
        replacements: dict[str, tuple[Any, Any]] = {}
        for key in sorted(frozen_keys):
            old = origin_by_key[key]
            old_state = origin.task_state_by_digest[old.artifact_digest]
            if (
                old_state.declared_status is not TaskStatus.DRAFT
                or json.loads(old.metric_contract)["source_contract_digest"]
                != contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_rebind_origin_shape_changed"
                )
            payload, _ = builder.build_manifest(
                context=_task_context(old),
                source_digest=self.source_digest,
                operator_configuration_authorized=True,
                simulation_events=False,
            )
            expected = ControlPlaneManifest.from_dict(payload)
            candidate = next(item for item in expected.tasks if item.task_key == key)
            replacement = replace(
                candidate, goal_digest=origin.goals[0].artifact_digest
            )
            replacements[key] = (
                replacement,
                replace(
                    expected.task_state_by_digest[candidate.artifact_digest],
                    task_digest=replacement.artifact_digest,
                ),
            )
        task_by_key = {item.task_key: item for item in current.tasks}
        if len(task_by_key) != len(current.tasks) or (
            current.goals != origin.goals or current.goal_states != origin.goal_states
        ):
            raise ResearchOSValidationError("isolated_v11_rebind_goal_or_keys_changed")
        old_keys = {
            key
            for key in frozen_keys
            if key in task_by_key and task_by_key[key] == origin_by_key[key]
        }
        new_keys = {
            key
            for key in frozen_keys
            if key in task_by_key and task_by_key[key] == replacements[key][0]
        }
        if (old_keys, new_keys) not in ((frozen_keys, set()), (set(), frozen_keys)):
            raise ResearchOSValidationError(
                "isolated_v11_rebind_mixed_or_partial_closure"
            )
        already_rebound = new_keys == frozen_keys
        # Historical completed old-source tasks remain immutable. Only the six
        # named, previously unexecuted tasks belong to this replacement closure.
        for key, old in origin_by_key.items():
            if key in frozen_keys:
                continue
            if (
                task_by_key.get(key) != old
                or current.task_state_by_digest[old.artifact_digest]
                != origin.task_state_by_digest[old.artifact_digest]
            ):
                raise ResearchOSValidationError("isolated_v11_rebind_history_changed")
        extra_keys = set(task_by_key) - set(origin_by_key)
        if extra_keys:
            incident = origin_by_key[
                f"m4-isolated-24h-challenger-v11-incident-{contract.DAILY_RECOVERY_INCIDENT_ID}-open"
            ]
            extension = ControlPlaneManifest.from_dict(
                builder.extend_manifest(
                    origin.to_dict(include_digest=True),
                    context=_task_context(incident),
                    source_digest=self.source_digest,
                    template_names=frozenset({"incident_resolution"}),
                )
            )
            permitted = {
                item.task_key: item
                for item in extension.tasks
                if item.task_key not in origin_by_key
            }
            if (
                not already_rebound
                or extra_keys != set(permitted)
                or any(task_by_key[key] != value for key, value in permitted.items())
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_rebind_extra_tasks_changed"
                )
        daily = task_by_key.get(contract.DAILY_RECOVERY_TASK_KEY)
        if daily is None:
            raise ResearchOSValidationError("isolated_v11_daily_recovery_task_missing")
        daily_state = current.task_state_by_digest[daily.artifact_digest]
        if (
            daily.artifact_digest != contract.DAILY_RECOVERY_TASK_DIGEST
            or daily_state.declared_status is not TaskStatus.COMPLETED
        ):
            raise ResearchOSValidationError(
                "isolated_v11_daily_recovery_not_completed_before_rebind"
            )
        candidates: list[Any] = []
        for task in current.tasks:
            source = str(json.loads(task.metric_contract)["source_contract_digest"])
            state = current.task_state_by_digest[task.artifact_digest]
            if source != contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST:
                continue
            if state.declared_status is TaskStatus.COMPLETED:
                continue
            if state.declared_status is not TaskStatus.DRAFT:
                raise ResearchOSValidationError(
                    "isolated_v11_old_source_nonterminal_state_changed"
                )
            candidates.append(task)
        if already_rebound:
            if candidates:
                raise ResearchOSValidationError(
                    "isolated_v11_rebind_residual_old_tasks"
                )
            for key in sorted(frozen_keys | extra_keys):
                task = task_by_key[key]
                state = current.task_state_by_digest[task.artifact_digest]
                events = self.list_mainline_execution_events(
                    control_plane_key=contract.CONTROL_PLANE_KEY, task_key=key
                )
                if state.declared_status is TaskStatus.DRAFT:
                    if key in replacements and state != replacements[key][1]:
                        raise ResearchOSValidationError(
                            "isolated_v11_rebind_draft_state_changed"
                        )
                    with self.connection_factory() as connection:
                        count = connection.execute(
                            "SELECT count(*) FROM research_os_mainline_artifacts "
                            "WHERE control_plane_key=%s AND task_key=%s",
                            (contract.CONTROL_PLANE_KEY, key),
                        ).fetchone()[0]
                    if (
                        events
                        or count
                        or any(
                            fact.startswith((f"{key}:", f"mainline-execution:{key}:"))
                            for fact in current.facts.artifacts
                        )
                    ):
                        raise ResearchOSValidationError(
                            "isolated_v11_rebind_draft_provenance_changed"
                        )
                elif state.declared_status is TaskStatus.COMPLETED:
                    if (
                        state.completion_classification
                        is not CompletionClassification.COMPLETE
                    ):
                        raise ResearchOSValidationError(
                            "isolated_v11_rebind_completed_state_changed"
                        )
                    # Use the same locked V11 path adapter as publication;
                    # this is registration validation, not another replay.
                    with mainline._PUBLICATION_PATCH_LOCK:
                        module = mainline.supervisor_module
                        original_path = module._canonical_task_artifact_path
                        module._canonical_task_artifact_path = (
                            mainline._isolated_canonical_task_artifact_path
                        )
                        try:
                            module._load_single_completed_execution(
                                repository=self,
                                root_dir=ROOT_DIR,
                                control_plane_key=contract.CONTROL_PLANE_KEY,
                                task_key=key,
                            )
                        finally:
                            module._canonical_task_artifact_path = original_path
                else:
                    raise ResearchOSValidationError(
                        "isolated_v11_rebind_nonterminal_state_changed"
                    )
            # Prove the complete replacement was durably imported, including
            # the pre-existing facts. The summary activation can precede rebind.
            rebound = replace(
                origin,
                tasks=tuple(
                    replacements[t.task_key][0] if t.task_key in replacements else t
                    for t in origin.tasks
                ),
                task_states=tuple(
                    replacements[t.task_key][1]
                    if t.task_key in replacements
                    else origin.task_state_by_digest[t.artifact_digest]
                    for t in origin.tasks
                ),
            )
            daily_activation = f"{contract.DAILY_RECOVERY_TASK_KEY}:COMPLETE"
            activated = ControlPlaneManifest.from_dict(
                builder.manifest_with_facts(
                    rebound.to_dict(include_digest=True),
                    add_artifact_facts=(daily_activation,),
                )
            )
            with self.connection_factory() as connection:
                rows = connection.execute(
                    "SELECT manifest_digest,manifest_json FROM research_os_manifests "
                    "WHERE manifest_digest=ANY(%s)",
                    ([rebound.artifact_digest, activated.artifact_digest],),
                ).fetchall()
            if (
                not rows
                or any(
                    ControlPlaneManifest.from_dict(dict(raw)).artifact_digest != digest
                    for digest, raw in rows
                )
                or self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
                != current
            ):
                raise ResearchOSValidationError(
                    "isolated_v11_rebind_committed_head_changed"
                )
            return {
                "status": "ALREADY_REBOUND",
                "previous_manifest_digest": current.artifact_digest,
                "manifest_digest": current.artifact_digest,
                "task_keys": sorted(frozen_keys),
                "task_count": len(frozen_keys),
                "source_digest": self.source_digest,
            }
        if {item.task_key for item in candidates} != frozen_keys:
            raise ResearchOSValidationError("isolated_v11_rebind_required_set_changed")
        if any(
            current.task_state_by_digest[item.artifact_digest]
            != origin.task_state_by_digest[item.artifact_digest]
            for item in candidates
        ):
            raise ResearchOSValidationError(
                "isolated_v11_rebind_required_state_changed"
            )
        candidate_keys = tuple(item.task_key for item in candidates)
        if self.list_mainline_execution_event_metadata(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_keys=candidate_keys,
        ):
            raise ResearchOSValidationError(
                "isolated_v11_rebind_candidate_has_execution_event"
            )
        with self.connection_factory() as connection, connection.cursor() as cursor:
            registration_count = int(
                cursor.execute(
                    "SELECT count(*) FROM research_os_mainline_artifacts "
                    "WHERE control_plane_key=%s AND task_key=ANY(%s)",
                    (contract.CONTROL_PLANE_KEY, list(candidate_keys)),
                ).fetchone()[0]
            )
        if registration_count:
            raise ResearchOSValidationError(
                "isolated_v11_rebind_candidate_has_registration"
            )
        if any(
            fact.startswith((f"{task_key}:", f"mainline-execution:{task_key}:"))
            for task_key in candidate_keys
            for fact in current.facts.artifacts
        ):
            raise ResearchOSValidationError("isolated_v11_rebind_candidate_has_fact")
        tasks: list[Any] = []
        states: list[Any] = []
        for task in current.tasks:
            replacement = replacements.get(task.task_key)
            if replacement is None:
                tasks.append(task)
                states.append(current.task_state_by_digest[task.artifact_digest])
            else:
                tasks.append(replacement[0])
                states.append(replacement[1])
        incoming = ControlPlaneManifest(
            goals=current.goals,
            tasks=tuple(tasks),
            goal_states=current.goal_states,
            task_states=tuple(states),
            facts=current.facts,
            schema_version=current.schema_version,
        )
        self._evolving_source_rebind_gate = {
            "current_manifest_digest": current.artifact_digest,
            "incoming_manifest_digest": incoming.artifact_digest,
            "current_manifest": current.to_dict(include_digest=True),
            "incoming_manifest": incoming.to_dict(include_digest=True),
            "candidate_keys": frozenset(candidate_keys),
            "consumed": False,
        }
        try:
            self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-v11-exact-unexecuted-old-source-rebind",
            )
            if self._evolving_source_rebind_gate.get("consumed") is not True:
                raise ResearchOSValidationError(
                    "isolated_v11_evolving_rebind_gate_not_consumed"
                )
        finally:
            self._evolving_source_rebind_gate = None
        return {
            "status": "REBIND_REQUIRED",
            "previous_manifest_digest": current.artifact_digest,
            "manifest_digest": incoming.artifact_digest,
            "task_keys": sorted(candidate_keys),
            "task_count": len(candidate_keys),
            "source_digest": self.source_digest,
        }

    def import_extension(self, payload: Mapping[str, Any]):
        incoming = ControlPlaneManifest.from_dict(dict(payload))
        current = self.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        added = {item.task_key for item in incoming.tasks} - {
            item.task_key for item in current.tasks
        }
        added_events = set(incoming.facts.external_events) - set(
            current.facts.external_events
        )
        if not added and not added_events:
            return None
        self._definition_gate = {
            "manifest_digest": incoming.artifact_digest,
            "added_task_keys": frozenset(added),
            "added_external_events": frozenset(added_events),
            "consumed": False,
        }
        try:
            result = self.import_manifest(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                payload=incoming.to_dict(include_digest=True),
                source="m4-isolated-v11-exact-task-extension",
            )
            if self._definition_gate.get("consumed") is not True:
                raise ResearchOSValidationError(
                    "isolated_v11_definition_gate_not_consumed"
                )
            return result
        finally:
            self._definition_gate = None


def _p3_source_identity() -> dict[str, Any]:
    source = formal_p3.load_source_contract(root_dir=ROOT_DIR)
    if source["artifact_digest"] != contract.FORMAL_P3_SOURCE_DIGEST:
        raise IsolatedRunnerError("formal_p3_source_digest_changed")
    return {
        "artifact_digest": source["artifact_digest"],
        "source_set_digest": source["source_set_digest"],
        "entries": [
            (item["path"], item["sha256"]) for item in source["source_entries"]
        ],
    }


def _resource_observation() -> dict[str, Any]:
    command = [
        "systemctl",
        "--user",
        "show",
        contract.FORMAL_P3_UNIT,
        "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
        "--no-pager",
    ]
    observed_ns = time.monotonic_ns()
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "query_ok": False,
            "LoadState": None,
            "ActiveState": None,
            "SubState": None,
            "MainPID": None,
            "ControlPID": None,
            "observed_monotonic_ns": observed_ns,
        }
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in values:
            return {
                "query_ok": False,
                "LoadState": None,
                "ActiveState": None,
                "SubState": None,
                "MainPID": None,
                "ControlPID": None,
                "observed_monotonic_ns": observed_ns,
            }
        values[key] = value
    required = {"LoadState", "ActiveState", "SubState", "MainPID", "ControlPID"}
    query_ok = result.returncode == 0 and set(values) == required
    try:
        main_pid = int(values.get("MainPID", "-1"))
        control_pid = int(values.get("ControlPID", "-1"))
    except ValueError:
        query_ok = False
        main_pid = control_pid = -1
    return {
        "query_ok": query_ok,
        "LoadState": values.get("LoadState"),
        "ActiveState": values.get("ActiveState"),
        "SubState": values.get("SubState"),
        "MainPID": main_pid,
        "ControlPID": control_pid,
        "observed_monotonic_ns": observed_ns,
    }


def _continuous_quiescence(*, seconds: float = 60.0) -> dict[str, Any]:
    started = time.monotonic()
    last: dict[str, Any] | None = None
    while True:
        last = _resource_observation()
        if contract.formal_p3_activity_state(last) != "QUIESCENT":
            raise IsolatedRunnerError("formal_p3_not_continuously_quiescent")
        elapsed = time.monotonic() - started
        if elapsed >= seconds:
            return last
        time.sleep(min(1.0, seconds - elapsed))


def _latest_history_identity() -> tuple[str, str]:
    repository = PostgresResearchOSRepository()
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        rows = cursor.execute(
            "SELECT issue,draw_date FROM ssq_history "
            "WHERE issue=(SELECT MAX(issue) FROM ssq_history) ORDER BY id"
        ).fetchall()
    if not rows:
        raise IsolatedRunnerError("ssq_history_empty")
    if len(rows) != 1 or rows[0][1] is None:
        raise IsolatedRunnerError("ssq_history_latest_identity_changed")
    issue = contract.require_issue(rows[0][0])
    draw_date = contract.require_history_draw_date(
        rows[0][1], field="source_max_draw_date"
    ).isoformat()
    return issue, draw_date


def _task_context(task: Any) -> dict[str, str]:
    try:
        metric = json.loads(task.metric_contract)
        raw = metric["render_context"]
        context = contract.render_context(
            source_max_issue=str(raw["source_max_issue"]),
            source_max_draw_date=str(raw["source_max_draw_date"]),
            target_issue=str(raw["target_issue"]),
            target_draw_date=str(raw["target_draw_date"]),
            batch_seq=int(raw["batch_seq"]),
            epoch_date=str(raw["epoch_date"]),
            minute=str(raw["minute"]),
            incident_id=str(raw["incident_id"]),
            incident_reason_code=str(raw["incident_reason_code"]),
            incident_offending_digest=str(raw["incident_offending_digest"]),
            cut_checkpoint_ref=str(raw["cut_checkpoint_ref"]),
            projection_time=str(raw["projection_time"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise IsolatedRunnerError("task_render_context_changed") from exc
    if context != dict(raw):
        raise IsolatedRunnerError("task_render_context_changed")
    return context


def _issue_exists(repository: PostgresResearchOSRepository, *, issue: str) -> bool:
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        return bool(
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM ssq_history WHERE issue=%s)",
                (issue,),
            ).fetchone()[0]
        )


def _scheduled_minute(now: datetime, scheduled: datetime) -> bool:
    return scheduled <= now < scheduled + timedelta(minutes=1)


def _delivery_absent(
    *,
    now: datetime,
    scheduled: datetime,
    stop_at: datetime,
    delivery_task_key: str,
    facts: set[str],
) -> bool:
    if not scheduled + timedelta(minutes=1) <= now < stop_at:
        return False
    return (
        f"{delivery_task_key}:SENT" not in facts
        and f"{delivery_task_key}:UNCERTAIN" not in facts
    )


def _latest_registered_health_artifact(
    *,
    repository: IsolatedChallengerRepository,
    manifest: ControlPlaneManifest,
    facts: set[str],
    before: datetime,
    context: Mapping[str, str],
) -> dict[str, Any]:
    if facts != set(manifest.facts.artifacts):
        raise IsolatedRunnerError("runtime_health_manifest_facts_changed")
    preregistration = mainline._unique_type(
        mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=contract.task_template_by_name("preregistration").key(context),
        ),
        "M4IsolatedPreregistrationV11",
    )
    history = mainline.validated_runtime_health_history(
        repository=repository,
        root_dir=ROOT_DIR,
        preregistration=preregistration,
        manifest=manifest,
    )
    before_utc = before.astimezone(UTC)
    eligible = [item for item in history if item["completed_at"] < before_utc]
    return dict(eligible[-1]["artifact"]) if eligible else preregistration


def _roll_forward(
    *,
    repository: IsolatedChallengerRepository,
    context: Mapping[str, str],
    source_digest: str,
    now: datetime | None = None,
) -> None:
    now = (now or datetime.now(contract.TIMEZONE)).astimezone(contract.TIMEZONE)
    current = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    manifest = ControlPlaneManifest.from_dict(current)
    facts = set(manifest.facts.artifacts)
    task_keys = {item.task_key for item in manifest.tasks}
    names: set[str] = {"runtime_health"}
    events: set[str] = set()

    target_key = contract.task_template_by_name("target_issue_projection").key(context)
    if target_key not in task_keys:
        names.update({"target_issue_projection", "history_snapshot"})
        events.add("TARGET_PROJECTION_INPUT")

    epoch_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        daily_batches = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches "
                "WHERE epoch_date=%s",
                (epoch_start.date(),),
            ).fetchone()[0]
        )
        issue_batches = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.registration_batches "
                "WHERE target_issue=%s",
                (context["target_issue"],),
            ).fetchone()[0]
        )
        head = cursor.execute(
            "SELECT registration_seq,m_total FROM m4_isolated_v11.multiplicity_head "
            "WHERE singleton=TRUE"
        ).fetchone()
    if head is None:
        raise IsolatedRunnerError("multiplicity_head_missing")
    latest_completed_batch = -1
    for task in manifest.tasks:
        metric = json.loads(task.metric_contract)
        if metric.get("task_template") != "search_checkpoint_replay":
            continue
        item_context = _task_context(task)
        fact = f"{task.task_key}:REGISTERED_REPLAY_VERIFIED"
        if fact in facts:
            latest_completed_batch = max(
                latest_completed_batch, int(item_context["batch_seq"])
            )
    next_batch = latest_completed_batch + 1
    next_context = {
        **dict(context),
        "batch_seq": f"{next_batch:012d}",
        "epoch_date": now.strftime("%Y%m%d"),
        "minute": now.strftime("%Y%m%d%H%M"),
    }
    next_batch_key = contract.task_template_by_name("search_batch").key(next_context)
    target_schedule = contract.schedule_for_issue(
        context["target_issue"], target_draw_date=context["target_draw_date"]
    )
    # The frozen retry path can consume three 1,800-second attempts plus
    # quiescence and process-termination grace.  Stop admitting new batches two
    # hours before the scientific cut so the minute runner remains available
    # for the 16:40/16:45/17:00 freeze and mail chain.
    search_pause_start = target_schedule["selection_cutoff"] - timedelta(hours=2)
    search_pause_end = target_schedule["predraw_send"] + timedelta(minutes=1)
    daily_send_for_pause = now.replace(
        hour=contract.DAILY_SEND_TIME.hour,
        minute=contract.DAILY_SEND_TIME.minute,
        second=0,
        microsecond=0,
    )
    official_draw = datetime.combine(
        contract.require_draw_date(
            context["target_draw_date"], field="target_draw_date"
        ),
        contract.OFFICIAL_DRAW_TIME,
        contract.TIMEZONE,
    )
    search_temporarily_paused = bool(
        search_pause_start <= now < search_pause_end
        or daily_send_for_pause - timedelta(hours=2)
        <= now
        < daily_send_for_pause + timedelta(minutes=15)
        or official_draw - timedelta(hours=2)
        <= now
        < official_draw + timedelta(hours=2)
    )
    add_search = (
        contract.MAIL_CONFIGURATION_FACT in facts
        and next_batch_key not in task_keys
        and not search_temporarily_paused
        and daily_batches < contract.DAILY_BATCH_LIMIT
        and issue_batches < contract.ISSUE_BATCH_LIMIT
        and int(head[1]) + contract.ATTEMPTS_PER_BATCH
        <= contract.LIFETIME_MULTIPLICITY_LIMIT
    )

    daily_send = daily_send_for_pause
    if _scheduled_minute(now, daily_send):
        names.update(builder.DAILY_TEMPLATE_NAMES)
        events.add("DAILY_SEND")

    incident_context: dict[str, str] | None = None
    incident_ledger = mainline.projected_incident_ledger_state(
        repository=repository, root_dir=ROOT_DIR, manifest=manifest
    )
    has_open_incident = incident_ledger["open_count"] > 0
    latest_health: dict[str, Any] | None = None
    if contract.FREEZE_FACT in facts:
        latest_health = _latest_registered_health_artifact(
            repository=repository,
            manifest=manifest,
            facts=facts,
            before=now,
            context=context,
        )
    if contract.MAIL_CONFIGURATION_FACT in facts and latest_health is None:
        raise IsolatedRunnerError("mail_configuration_without_preregistration")
    if (
        not has_open_incident
        and latest_health is not None
        and latest_health["artifact_type"] == "M4IsolatedRuntimeHealthV11"
        and latest_health["body"].get("status")
        in {"THERMAL_PAUSED", "THERMAL_HARD_STOP", "RESOURCE_GUARD_TRIGGERED"}
    ):
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="RESOURCE_GUARD_TRIGGERED",
            incident_offending_digest=latest_health["artifact_digest"],
            projection_time=context["projection_time"],
        )
    uncertain_delivery_keys = sorted(
        fact.removesuffix(":UNCERTAIN")
        for fact in facts
        if fact.startswith("m4-isolated-24h-challenger-v11-")
        and fact.endswith(":UNCERTAIN")
    )
    if not has_open_incident and uncertain_delivery_keys:
        uncertain_receipt = mainline._unique_type(
            mainline.load_completed_task_artifacts(
                repository=repository,
                root_dir=ROOT_DIR,
                task_key=uncertain_delivery_keys[0],
            ),
            "M4IsolatedDeliveryReceiptV11",
        )
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="UNVERIFIED_PREDICTION_DELIVERY_ATTEMPT",
            incident_offending_digest=uncertain_receipt["artifact_digest"],
            projection_time=context["projection_time"],
        )
    daily_context = {
        **dict(context),
        "epoch_date": now.strftime("%Y%m%d"),
        "minute": now.strftime("%Y%m%d%H%M"),
    }
    daily_delivery_key = contract.task_template_by_name("daily_delivery").key(
        daily_context
    )
    if (
        not has_open_incident
        and _delivery_absent(
            now=now,
            scheduled=daily_send,
            stop_at=daily_send + timedelta(days=1),
            delivery_task_key=daily_delivery_key,
            facts=facts,
        )
        and contract.MAIL_CONFIGURATION_FACT in facts
    ):
        offending = latest_health
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="DEADLINE_OR_ABSENCE",
            incident_offending_digest=offending["artifact_digest"],
            projection_time=context["projection_time"],
        )

    if target_schedule["selection_cutoff"] <= now < target_schedule["freeze_deadline"]:
        names.update({"multiplicity_seal", "eligibility"})
        events.add("SELECTION_CUTOFF")
    if _scheduled_minute(now, target_schedule["freeze_deadline"]):
        names.update(
            {
                "challenger_freeze",
                "random_baseline_freeze",
                "random_baseline_freeze_replay",
                "prediction",
                "prediction_replay",
            }
        )
        events.add("FREEZE_DEADLINE")
    prediction_replay_key = contract.task_template_by_name("prediction_replay").key(
        context
    )
    predraw_delivery_key = contract.task_template_by_name("predraw_delivery").key(
        context
    )
    if _scheduled_minute(now, target_schedule["predraw_send"]):
        if f"{prediction_replay_key}:REGISTERED_REPLAY_VERIFIED" in facts:
            names.update(
                {
                    "predraw_mail_envelope",
                    "predraw_mail_replay",
                    "predraw_delivery",
                }
            )
            events.add("PREDRAW_SEND")
        elif contract.MAIL_CONFIGURATION_FACT in facts and not has_open_incident:
            offending = latest_health
            incident_context = contract.render_context(
                source_max_issue=context["source_max_issue"],
                source_max_draw_date=context["source_max_draw_date"],
                target_issue=context["target_issue"],
                target_draw_date=context["target_draw_date"],
                batch_seq=int(context["batch_seq"]),
                epoch_date=now.strftime("%Y%m%d"),
                minute=now.strftime("%Y%m%d%H%M"),
                incident_reason_code="DEADLINE_OR_ABSENCE",
                incident_offending_digest=offending["artifact_digest"],
                projection_time=context["projection_time"],
            )
    if (
        not has_open_incident
        and _delivery_absent(
            now=now,
            scheduled=target_schedule["predraw_send"],
            stop_at=official_draw,
            delivery_task_key=predraw_delivery_key,
            facts=facts,
        )
        and contract.MAIL_CONFIGURATION_FACT in facts
    ):
        incident_context = contract.render_context(
            source_max_issue=context["source_max_issue"],
            source_max_draw_date=context["source_max_draw_date"],
            target_issue=context["target_issue"],
            target_draw_date=context["target_draw_date"],
            batch_seq=int(context["batch_seq"]),
            epoch_date=now.strftime("%Y%m%d"),
            minute=now.strftime("%Y%m%d%H%M"),
            incident_reason_code="DEADLINE_OR_ABSENCE",
            incident_offending_digest=latest_health["artifact_digest"],
            projection_time=context["projection_time"],
        )

    settlement_names = {
        "settlement",
        "random_baseline_settlement",
        "formal_p3_comparison_input",
        "formal_p3_comparison",
        "settlement_report",
        "settlement_replay",
        "post_mail_envelope",
        "post_mail_replay",
        "post_delivery",
    }
    settlement_contexts: list[dict[str, str]] = []
    if now.minute % 15 == 0:
        for task in manifest.tasks:
            metric = json.loads(task.metric_contract)
            if metric.get("task_template") != "prediction_replay":
                continue
            item_context = _task_context(task)
            if (
                now
                >= contract.schedule_for_issue(
                    item_context["target_issue"],
                    target_draw_date=item_context["target_draw_date"],
                )["predraw_send"]
                and f"{task.task_key}:REGISTERED_REPLAY_VERIFIED" in facts
                and _issue_exists(repository, issue=item_context["target_issue"])
            ):
                settlement_contexts.append(item_context)

    cut_context = {
        **dict(context),
        "batch_seq": f"{max(0, latest_completed_batch):012d}",
        "cut_checkpoint_ref": (
            "GENESIS"
            if latest_completed_batch < 0
            else f"{latest_completed_batch:012d}"
        ),
        "epoch_date": now.strftime("%Y%m%d"),
        "minute": now.strftime("%Y%m%d%H%M"),
    }
    payload = builder.extend_manifest(
        current,
        context=cut_context,
        source_digest=source_digest,
        template_names=frozenset(names),
        add_external_events=tuple(sorted(events)),
    )
    repository.import_extension(payload)
    if incident_context is not None:
        live = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        incident_payload = builder.extend_manifest(
            live,
            context=incident_context,
            source_digest=source_digest,
            template_names=builder.INCIDENT_TEMPLATE_NAMES,
            add_external_events=("INCIDENT_OPEN",),
        )
        repository.import_extension(incident_payload)
    if add_search:
        live = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        payload = builder.extend_manifest(
            live,
            context=next_context,
            source_digest=source_digest,
            template_names=builder.SEARCH_TEMPLATE_NAMES,
        )
        repository.import_extension(payload)
    for old_context in sorted(
        settlement_contexts, key=lambda item: item["target_issue"]
    ):
        live = repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
        payload = builder.extend_manifest(
            live,
            context=old_context,
            source_digest=source_digest,
            template_names=frozenset(settlement_names),
            add_external_events=("AUDITED_DRAW",),
        )
        repository.import_extension(payload)


def _activation_facts(
    *,
    task_key: str,
    template: contract.TaskTemplate,
    context: Mapping[str, str],
    repository: PostgresResearchOSRepository,
) -> tuple[str, ...]:
    if template.activation_mode == contract.PAIRED:
        if template.name == "search_batch":
            _mirror_search_batch_ledger(
                repository=repository,
                task_key=task_key,
            )
        return ()
    if template.activation_mode == contract.REPLAY:
        upstream_name = {
            "genesis_replay": "genesis",
            "search_batch_replay": "search_batch",
            "search_checkpoint_replay": "search_checkpoint",
            "random_baseline_freeze_replay": "random_baseline_freeze",
            "prediction_replay": "prediction",
            "settlement_replay": "settlement_report",
            "daily_summary_replay": "daily_summary",
            "predraw_mail_replay": "predraw_mail_envelope",
            "post_mail_replay": "post_mail_envelope",
            "daily_mail_replay": "daily_mail_envelope",
            "incident_mail_replay": "incident_envelope",
        }.get(template.name)
        if upstream_name is None:
            raise IsolatedRunnerError("replay_activation_upstream_changed")
        if template.name in {"genesis_replay", "search_checkpoint_replay"}:
            _mirror_search_checkpoint(
                repository=repository,
                context=context,
                replay_task_key=task_key,
                replay_template_name=template.name,
            )
        upstream_key = contract.task_template_by_name(upstream_name).key(context)
        return (
            f"{upstream_key}:COMPLETE",
            f"{task_key}:REGISTERED_REPLAY_VERIFIED",
        )
    if template.activation_mode == contract.DELIVERY:
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        receipts = [
            item
            for item in values
            if item["artifact_type"] == "M4IsolatedDeliveryReceiptV11"
        ]
        if len(receipts) != 1:
            raise IsolatedRunnerError("delivery_receipt_not_unique")
        receipt = receipts[0]
        body = receipt["body"]
        state = body.get("state")
        terminal_at = (
            body.get("smtp_data_accepted_at")
            or body.get("created_at")
            or body.get("smtp_transaction_started_at")
        )
        with (
            repository.connection_factory() as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "INSERT INTO m4_isolated_v11.delivery_ledger ("
                "delivery_key,mail_kind,target_identity,content_digest,"
                "recipient_set_digest,state,attempt_count,receipt_artifact_digest,"
                "started_at,terminal_at) VALUES ("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (delivery_key) DO NOTHING",
                (
                    body["delivery_key"],
                    body["mail_kind"],
                    (
                        body.get("target_issue")
                        or body.get("target_identity")
                        or receipt["body"].get("target_issue")
                        or task_key
                    ),
                    body["content_digest"],
                    body["recipient_set_digest"],
                    state,
                    body["attempt_count"],
                    receipt["artifact_digest"],
                    body["smtp_transaction_started_at"],
                    terminal_at,
                ),
            )
            stored = cursor.execute(
                "SELECT mail_kind,content_digest,recipient_set_digest,state,"
                "attempt_count,receipt_artifact_digest FROM "
                "m4_isolated_v11.delivery_ledger WHERE delivery_key=%s",
                (body["delivery_key"],),
            ).fetchone()
        if stored is None or tuple(stored) != (
            body["mail_kind"],
            body["content_digest"],
            body["recipient_set_digest"],
            state,
            body["attempt_count"],
            receipt["artifact_digest"],
        ):
            raise IsolatedRunnerError("delivery_ledger_mirror_changed")
        if state == "SENT":
            return (f"{task_key}:SENT",)
        if state == "UNCERTAIN":
            return (f"{task_key}:UNCERTAIN",)
        raise IsolatedRunnerError("external_delivery_receipt_not_authoritative")
    if template.name == "challenger_freeze":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        types = {item["artifact_type"] for item in values}
        if types == {"M4IsolatedChallengerFreezeV11"}:
            return (f"{task_key}:FROZEN",)
        if types == {"M4IsolatedNoChallengerV11"}:
            return (f"{task_key}:NO_ELIGIBLE_CHALLENGER",)
        raise IsolatedRunnerError("challenger_freeze_artifact_set_changed")
    if template.name == "formal_p3_comparison_input":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        if len(values) != 1:
            raise IsolatedRunnerError("formal_p3_input_artifact_not_unique")
        artifact_type = values[0]["artifact_type"]
        if artifact_type == "M4IsolatedFormalP3IssueProjectionV11":
            subtype = "COMPLETE"
        elif artifact_type == "M4IsolatedFormalP3PendingMarkerV11":
            subtype = "PENDING_LEGAL_COMPARISON"
        else:
            raise IsolatedRunnerError("formal_p3_input_artifact_type_changed")
        return (f"{task_key}:{subtype}", f"{task_key}:RESOLVED")
    if template.name == "formal_p3_comparison":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        comparison = next(
            (
                item
                for item in values
                if item["artifact_type"] == "M4IsolatedFormalP3ComparisonV11"
            ),
            None,
        )
        status = comparison["body"].get("status") if comparison else None
        if status not in {"COMPLETE", "PENDING_LEGAL_COMPARISON"}:
            raise IsolatedRunnerError("formal_p3_comparison_status_changed")
        return (f"{task_key}:{status}", f"{task_key}:RESOLVED")
    if template.name == "incident_resolution":
        values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        resolution = mainline._unique_type(values, "M4IsolatedIncidentResolutionV11")
        head = mainline._unique_type(values, "M4IsolatedIncidentLedgerHeadV11")
        if (
            resolution["body"].get("status") != "RESOLVED"
            or head["body"].get("transition_kind") != "RESOLVED"
            or resolution["body"].get("incident_id") != head["body"].get("incident_id")
        ):
            raise IsolatedRunnerError("incident_resolution_artifact_set_changed")
        return (
            f"{task_key}:RESOLVED",
            (
                "m4-isolated-24h-challenger-v11-incident-ledger-head-"
                f"{head['body']['transition_seq']}:ADVANCED"
            ),
        )
    suffix = {
        "preregistration": contract.FREEZE_FACT,
        "operator_attestation": contract.OPERATOR_ATTESTATION_FACT,
        "mail_configuration": contract.MAIL_CONFIGURATION_FACT,
        "incident_open": f"{task_key}:OPEN",
    }.get(template.name, f"{task_key}:COMPLETE")
    return (suffix,)


def _mirror_search_checkpoint(
    *,
    repository: IsolatedChallengerRepository,
    context: Mapping[str, str],
    replay_task_key: str,
    replay_template_name: str,
) -> None:
    replay_values = mainline.load_completed_task_artifacts(
        repository=repository,
        root_dir=ROOT_DIR,
        task_key=replay_task_key,
    )
    replay = next(
        (
            item
            for item in replay_values
            if item["artifact_type"] == "M4IsolatedSearchCheckpointReplayV11"
        ),
        None,
    )
    if replay is None:
        raise IsolatedRunnerError("checkpoint_replay_artifact_missing")
    if replay_template_name == "genesis_replay":
        checkpoint_task_key = contract.task_template_by_name("genesis").key(context)
        checkpoint_values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=checkpoint_task_key,
        )
        checkpoint = next(
            (
                item
                for item in checkpoint_values
                if item["artifact_type"] == "M4IsolatedSearchCheckpointV11"
            ),
            None,
        )
        row = (
            -1,
            context["target_issue"],
            None,
            None,
            None,
            None,
            checkpoint["artifact_digest"] if checkpoint else None,
            replay["artifact_digest"],
        )
    elif replay_template_name == "search_checkpoint_replay":
        checkpoint_task_key = contract.task_template_by_name("search_checkpoint").key(
            context
        )
        checkpoint_values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=checkpoint_task_key,
        )
        checkpoint = next(
            (
                item
                for item in checkpoint_values
                if item["artifact_type"] == "M4IsolatedSearchCheckpointV11"
            ),
            None,
        )
        if checkpoint is None or len(checkpoint["parent_digests"]) != 4:
            raise IsolatedRunnerError("checkpoint_parent_chain_changed")
        batch_seq = int(context["batch_seq"])
        previous_context = {**dict(context), "batch_seq": f"{batch_seq - 1:012d}"}
        previous_replay_key = (
            contract.task_template_by_name("genesis_replay").key(context)
            if batch_seq == 0
            else contract.task_template_by_name("search_checkpoint_replay").key(
                previous_context
            )
        )
        previous_replay_values = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=previous_replay_key,
        )
        previous_replay = next(
            (
                item
                for item in previous_replay_values
                if item["artifact_type"] == "M4IsolatedSearchCheckpointReplayV11"
            ),
            None,
        )
        if previous_replay is None:
            raise IsolatedRunnerError("checkpoint_predecessor_replay_missing")
        row = (
            batch_seq,
            context["target_issue"],
            previous_replay["artifact_digest"],
            checkpoint["parent_digests"][1],
            checkpoint["parent_digests"][2],
            checkpoint["parent_digests"][3],
            checkpoint["artifact_digest"],
            replay["artifact_digest"],
        )
    else:
        raise IsolatedRunnerError("checkpoint_replay_template_changed")
    if row[6] is None:
        raise IsolatedRunnerError("checkpoint_artifact_missing")
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO m4_isolated_v11.search_checkpoints ("
            "batch_seq,target_issue,predecessor_replay_digest,batch_digest,"
            "batch_replay_digest,multiplicity_delta_digest,checkpoint_digest,"
            "replay_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (batch_seq) DO NOTHING",
            row,
        )
        stored = cursor.execute(
            "SELECT batch_seq,target_issue,predecessor_replay_digest,batch_digest,"
            "batch_replay_digest,multiplicity_delta_digest,checkpoint_digest,"
            "replay_digest FROM m4_isolated_v11.search_checkpoints "
            "WHERE batch_seq=%s",
            (row[0],),
        ).fetchone()
    if stored is None or tuple(stored) != row:
        raise IsolatedRunnerError("checkpoint_ledger_mirror_changed")


def _mirror_search_batch_ledger(
    *, repository: PostgresResearchOSRepository, task_key: str
) -> None:
    values = mainline.load_completed_task_artifacts(
        repository=repository,
        root_dir=ROOT_DIR,
        task_key=task_key,
    )
    registrations = {
        str(item["body"]["candidate_id"]): item
        for item in values
        if item["artifact_type"] == "M4IsolatedCandidateRegistrationV11"
    }
    attempts = {
        str(item["body"]["execution_attempt_id"]): item
        for item in values
        if item["artifact_type"] == "M4IsolatedExecutionAttemptV11"
    }
    results = {
        str(item["body"]["candidate_id"]): item
        for item in values
        if item["artifact_type"] == "M4IsolatedCandidateResultV11"
    }
    if (
        len(registrations) != contract.ATTEMPTS_PER_BATCH
        or not contract.ATTEMPTS_PER_BATCH <= len(attempts) <= 54
        or len(results) != contract.ATTEMPTS_PER_BATCH
        or set(registrations) != set(results)
    ):
        raise IsolatedRunnerError("search_batch_ledger_cardinality_changed")
    with (
        repository.connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        registration_rows = {
            str(item["candidate_id"]): dict(item)
            for item in cursor.execute(
                "SELECT candidate_id,artifact_digest,state FROM "
                "m4_isolated_v11.candidate_registrations "
                "WHERE candidate_id=ANY(%s) FOR UPDATE",
                (list(registrations),),
            ).fetchall()
        }
        if set(registration_rows) != set(registrations):
            raise IsolatedRunnerError("candidate_registration_ledger_incomplete")
        for candidate_id, artifact in registrations.items():
            row = registration_rows[candidate_id]
            if (
                row["artifact_digest"] != artifact["artifact_digest"]
                or row["state"] != "TERMINAL"
            ):
                raise IsolatedRunnerError("candidate_registration_ledger_changed")
        for attempt_id, artifact in attempts.items():
            body = artifact["body"]
            rows = cursor.execute(
                "SELECT candidate_id,retry_ordinal,worker_started_at,terminal_at,"
                "status,reason,artifact_digest,artifact_committed FROM "
                "m4_isolated_v11.execution_attempts "
                "WHERE execution_attempt_id=%s FOR UPDATE",
                (attempt_id,),
            ).fetchall()
            if len(rows) != 1:
                raise IsolatedRunnerError("execution_attempt_ledger_missing")
            row = dict(rows[0])
            exact = (
                row["candidate_id"] == body["candidate_id"]
                and int(row["retry_ordinal"]) == int(body["retry_ordinal"])
                and row["worker_started_at"].isoformat() == body["started_at"]
                and row["terminal_at"].isoformat() == body["completed_at"]
                and row["status"] == body["status"]
                and row["reason"] == body["reason"]
            )
            if not exact:
                raise IsolatedRunnerError("execution_attempt_ledger_changed")
            if bool(row["artifact_committed"]):
                if row["artifact_digest"] != artifact["artifact_digest"]:
                    raise IsolatedRunnerError("execution_attempt_artifact_changed")
                continue
            updated = cursor.execute(
                "UPDATE m4_isolated_v11.execution_attempts SET "
                "artifact_digest=%s,artifact_committed=TRUE "
                "WHERE execution_attempt_id=%s AND artifact_digest IS NULL "
                "AND artifact_committed=FALSE",
                (artifact["artifact_digest"], attempt_id),
            )
            if updated.rowcount != 1:
                raise IsolatedRunnerError("execution_attempt_artifact_commit_changed")
        for candidate_id, artifact in results.items():
            body = artifact["body"]
            ordered_attempt_ids = list(body["ordered_attempt_ids"])
            if any(attempt_id not in attempts for attempt_id in ordered_attempt_ids):
                raise IsolatedRunnerError("candidate_result_attempt_parent_missing")
            cursor.execute(
                "INSERT INTO m4_isolated_v11.candidate_results ("
                "candidate_id,status,terminal_reason,ordered_attempt_ids_json,"
                "fold_values_hex_json,primary_mean_hex,block_means_hex_json,"
                "eligible,artifact_digest,completed_at) VALUES ("
                "%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,FALSE,%s,%s) "
                "ON CONFLICT (candidate_id) DO NOTHING",
                (
                    candidate_id,
                    body["status"],
                    body["terminal_reason"],
                    json.dumps(ordered_attempt_ids, separators=(",", ":")),
                    (
                        json.dumps(body["fold_values_hex"], separators=(",", ":"))
                        if body["status"] == "SUCCEEDED"
                        else None
                    ),
                    (
                        body["primary_mean_hex"]
                        if body["status"] == "SUCCEEDED"
                        else None
                    ),
                    (
                        json.dumps(body["block_means_hex"], separators=(",", ":"))
                        if body["status"] == "SUCCEEDED"
                        else None
                    ),
                    artifact["artifact_digest"],
                    datetime.fromisoformat(
                        str(attempts[ordered_attempt_ids[-1]]["body"]["completed_at"])
                    ),
                ),
            )
        stored = {
            str(item["candidate_id"]): str(item["artifact_digest"])
            for item in cursor.execute(
                "SELECT candidate_id,artifact_digest FROM "
                "m4_isolated_v11.candidate_results WHERE candidate_id=ANY(%s)",
                (list(results),),
            ).fetchall()
        }
    expected = {
        candidate_id: str(item["artifact_digest"])
        for candidate_id, item in results.items()
    }
    if stored != expected:
        raise IsolatedRunnerError("candidate_result_ledger_changed")


def _search_batch_mirror_complete(
    *, repository: PostgresResearchOSRepository, context: Mapping[str, str]
) -> bool:
    batch_seq = int(context["batch_seq"])
    with (
        repository.connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        batch = cursor.execute(
            "SELECT registration_seq FROM m4_isolated_v11.registration_batches "
            "WHERE batch_seq=%s",
            (batch_seq,),
        ).fetchone()
        if batch is None:
            return False
        counts = cursor.execute(
            "SELECT "
            "(SELECT count(*) FROM m4_isolated_v11.candidate_registrations "
            " WHERE registration_seq=%s) AS candidates,"
            "(SELECT count(*) FROM m4_isolated_v11.candidate_registrations "
            " WHERE registration_seq=%s AND state='TERMINAL') AS terminal,"
            "(SELECT count(*) FROM m4_isolated_v11.candidate_results x JOIN "
            " m4_isolated_v11.candidate_registrations r USING(candidate_id) "
            " WHERE r.registration_seq=%s) AS results,"
            "(SELECT count(*) FROM m4_isolated_v11.execution_attempts a JOIN "
            " m4_isolated_v11.candidate_registrations r USING(candidate_id) "
            " WHERE r.registration_seq=%s) AS attempts,"
            "(SELECT count(*) FROM m4_isolated_v11.execution_attempts a JOIN "
            " m4_isolated_v11.candidate_registrations r USING(candidate_id) "
            " WHERE r.registration_seq=%s AND a.artifact_committed) "
            "AS committed_attempts",
            (int(batch["registration_seq"]),) * 5,
        ).fetchone()
    if counts is None:
        return False
    expected_count_keys = {
        "candidates",
        "terminal",
        "results",
        "attempts",
        "committed_attempts",
    }
    if not isinstance(counts, Mapping) or set(counts) != expected_count_keys:
        raise IsolatedRunnerError("search_batch_mirror_count_row_changed")
    try:
        candidates = int(counts["candidates"])
        terminal = int(counts["terminal"])
        results = int(counts["results"])
        attempts = int(counts["attempts"])
        committed_attempts = int(counts["committed_attempts"])
    except (TypeError, ValueError) as exc:
        raise IsolatedRunnerError("search_batch_mirror_count_value_changed") from exc
    return bool(
        candidates == contract.ATTEMPTS_PER_BATCH
        and terminal == candidates
        and results == candidates
        and contract.ATTEMPTS_PER_BATCH <= attempts <= 54
        and committed_attempts == attempts
    )


def _activation_present(
    *,
    template: contract.TaskTemplate,
    task_key: str,
    context: Mapping[str, str],
    facts: set[str],
    repository: PostgresResearchOSRepository,
) -> bool:
    if template.activation_mode == contract.PAIRED:
        return template.name != "search_batch" or _search_batch_mirror_complete(
            repository=repository,
            context=context,
        )
    if template.activation_mode == contract.REPLAY:
        return f"{task_key}:REGISTERED_REPLAY_VERIFIED" in facts
    if template.activation_mode == contract.DELIVERY:
        return bool({f"{task_key}:SENT", f"{task_key}:UNCERTAIN"}.intersection(facts))
    if template.name == "challenger_freeze":
        return bool(
            {
                f"{task_key}:FROZEN",
                f"{task_key}:NO_ELIGIBLE_CHALLENGER",
                f"{task_key}:FREEZE_DEADLINE_MISSED",
            }.intersection(facts)
        )
    if template.name in {"formal_p3_comparison_input", "formal_p3_comparison"}:
        return f"{task_key}:RESOLVED" in facts
    expected = {
        "preregistration": contract.FREEZE_FACT,
        "operator_attestation": contract.OPERATOR_ATTESTATION_FACT,
        "mail_configuration": contract.MAIL_CONFIGURATION_FACT,
        "incident_open": f"{task_key}:OPEN",
    }.get(template.name, f"{task_key}:COMPLETE")
    return expected in facts


def _verify_generic_replay(generic: Mapping[str, Any]) -> None:
    if (
        generic.get("status") != "REPLAY_VERIFIED"
        or generic.get("same_execution_identity") is not True
        or generic.get("same_artifact_identity") is not True
        or generic.get("same_artifact_content") is not True
        or generic.get("all_registrations_and_parent_chains_exact") is not True
        or generic.get("manual_input_assembly") is not False
        or generic.get("dispatch_performed") is not False
    ):
        raise IsolatedRunnerError("generic_replay_failed")


def _recover_completed_activations(
    *,
    repository: IsolatedChallengerRepository,
    source_digest: str,
) -> list[dict[str, Any]]:
    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    facts = set(manifest.facts.artifacts)
    recovered: list[dict[str, Any]] = []
    for task in sorted(manifest.tasks, key=lambda item: item.task_key):
        state = manifest.task_state_by_digest[task.artifact_digest]
        if state.declared_status != TaskStatus.COMPLETED:
            continue
        context = _task_context(task)
        template = mainline.template_for_task_key(task.task_key, context=context)
        if _activation_present(
            template=template,
            task_key=task.task_key,
            context=context,
            facts=facts,
            repository=repository,
        ):
            continue
        events = repository.list_mainline_execution_events(
            control_plane_key=contract.CONTROL_PLANE_KEY,
            task_key=task.task_key,
        )
        completed = [item for item in events if item.get("event_type") == "completed"]
        if len(completed) != 1:
            raise IsolatedRunnerError("completed_activation_event_not_unique")
        execution_id = str(completed[0].get("execution_id") or "")
        supervisor = mainline.IsolatedChallengerSupervisor(
            repository=repository,
            context=context,
            source_digest=source_digest,
            simulation=False,
        )
        generic = supervisor.replay(
            task_key=task.task_key,
            execution_id=execution_id,
        )
        _verify_generic_replay(generic)
        activated = _activation_facts(
            task_key=task.task_key,
            template=template,
            context=context,
            repository=repository,
        )
        if activated:
            repository.import_verified_facts(activated)
            facts.update(activated)
        recovered.append(
            {
                "task_key": task.task_key,
                "execution_id": execution_id,
                "activated_facts": list(activated),
            }
        )
    return recovered


def _validate_user_scope_resume_live_state(
    *, repository: IsolatedChallengerRepository
) -> tuple[ControlPlaneManifest, dict[str, str]]:
    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    expected_target_status = {
        USER_SCOPE_FAILED_MANIFEST_DIGEST: TaskStatus.FAILED,
        USER_SCOPE_RESUME_MANIFEST_DIGEST: TaskStatus.RUNNING,
    }.get(manifest.artifact_digest)
    if expected_target_status is None:
        raise IsolatedRunnerError("user_scope_resume_manifest_changed")
    if len(manifest.tasks) != 27:
        raise IsolatedRunnerError("user_scope_resume_task_count_changed")
    state_counts: dict[TaskStatus, int] = {}
    for state in manifest.task_states:
        state_counts[state.declared_status] = (
            state_counts.get(state.declared_status, 0) + 1
        )
    expected_state_counts = {
        TaskStatus.COMPLETED: 22,
        TaskStatus.DRAFT: 4,
        expected_target_status: 1,
    }
    if state_counts != expected_state_counts:
        raise IsolatedRunnerError("user_scope_resume_task_states_changed")
    matches = [
        task for task in manifest.tasks if task.task_key == USER_SCOPE_RESUME_TASK_KEY
    ]
    if len(matches) != 1 or matches[0].artifact_digest != USER_SCOPE_RESUME_TASK_DIGEST:
        raise IsolatedRunnerError("user_scope_resume_task_changed")
    task = matches[0]
    state = manifest.task_state_by_digest[task.artifact_digest]
    if (
        state.declared_status is not expected_target_status
        or state.completion_classification is not CompletionClassification.INTEGRATED
        or state.superseded_by_task_digest is not None
    ):
        raise IsolatedRunnerError("user_scope_resume_running_state_changed")
    context = _task_context(task)
    if (
        context["batch_seq"] != "000000000000"
        or context["target_issue"] != "2026100"
        or json.loads(task.metric_contract).get("source_contract_digest")
        != USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
    ):
        raise IsolatedRunnerError("user_scope_resume_task_context_changed")
    events = repository.list_mainline_execution_events(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=USER_SCOPE_RESUME_TASK_KEY,
    )
    _validate_user_scope_resume_event_set(events, allow_completed=False)
    current_events = [
        item
        for item in events
        if item.get("task_digest") == USER_SCOPE_RESUME_TASK_DIGEST
    ]
    if len(current_events) != 3:
        raise IsolatedRunnerError("user_scope_resume_event_count_changed")
    current_by_digest = {
        str(item.get("event_digest") or ""): item for item in current_events
    }
    started = current_by_digest.get(USER_SCOPE_RESUME_STARTED_EVENT_DIGEST, {})
    failed = current_by_digest.get(USER_SCOPE_RESUME_FAILED_EVENT_DIGEST, {})
    guard_failed = current_by_digest.get(USER_SCOPE_GUARD_FAILED_EVENT_DIGEST, {})
    if (
        started.get("event_digest") != USER_SCOPE_RESUME_STARTED_EVENT_DIGEST
        or started.get("execution_id") != USER_SCOPE_RESUME_EXECUTION_ID
        or started.get("event_type") != "started"
        or started.get("sequence") != 0
        or started.get("capability") != task.requested_capability
        or started.get("manifest_digest") != USER_SCOPE_RESUME_MANIFEST_DIGEST
        or dict(started.get("payload") or ())
        != {
            "git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
            "input_artifact_digests": [USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST],
        }
    ):
        raise IsolatedRunnerError("user_scope_resume_started_event_changed")
    if (
        failed.get("event_digest") != USER_SCOPE_RESUME_FAILED_EVENT_DIGEST
        or failed.get("execution_id") != USER_SCOPE_RESUME_EXECUTION_ID
        or failed.get("event_type") != "failed"
        or failed.get("sequence") != 1
        or failed.get("capability") != task.requested_capability
        or failed.get("manifest_digest") != USER_SCOPE_RESUME_MANIFEST_DIGEST
        or dict(failed.get("payload") or ())
        != {
            "error": "atomic_registration_resume_changed",
            "git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        }
    ):
        raise IsolatedRunnerError("user_scope_resume_failed_event_changed")
    if (
        guard_failed.get("event_digest") != USER_SCOPE_GUARD_FAILED_EVENT_DIGEST
        or guard_failed.get("execution_id") != USER_SCOPE_RESUME_EXECUTION_ID
        or guard_failed.get("event_type") != "failed"
        or guard_failed.get("sequence") != 2
        or guard_failed.get("recorded_at") != USER_SCOPE_GUARD_FAILED_AT
        or guard_failed.get("capability") != task.requested_capability
        or guard_failed.get("manifest_digest") != USER_SCOPE_RESUME_MANIFEST_DIGEST
        or dict(guard_failed.get("payload") or ())
        != {
            "error": (
                "M4-v2 atomic successor does not permit failed-execution recovery"
            ),
            "git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        }
    ):
        raise IsolatedRunnerError("user_scope_guard_failed_event_changed")
    if repository.list_mainline_artifacts(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
    ):
        raise IsolatedRunnerError("user_scope_resume_artifact_already_present")
    facts = set(manifest.facts.artifacts)
    if any(
        fact.endswith((":SENT", ":UNCERTAIN"))
        or "PASS_TO_P4" in fact
        or "PASS_TO_P5" in fact
        or "PROMOTION" in fact
        for fact in facts
    ):
        raise IsolatedRunnerError("user_scope_resume_forbidden_fact_present")
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        batches = cursor.execute(
            "SELECT registration_seq,batch_seq,target_issue,registration_execution_id,"
            "m_before,m_after,candidate_count FROM "
            "m4_isolated_v11.registration_batches ORDER BY registration_seq"
        ).fetchall()
        candidates = cursor.execute(
            "SELECT registration_seq,state,source_contract_digest,count(*) FROM "
            "m4_isolated_v11.candidate_registrations GROUP BY "
            "registration_seq,state,source_contract_digest"
        ).fetchall()
        attempts = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.execution_attempts"
            ).fetchone()[0]
        )
        attempt_state = cursor.execute(
            "SELECT count(*),"
            "count(*) FILTER (WHERE worker_started_at IS NOT NULL),"
            "count(*) FILTER (WHERE terminal_at IS NOT NULL),"
            "count(*) FILTER (WHERE status IN ('SUCCEEDED','FAILED')) ,"
            "count(*) FILTER (WHERE artifact_digest IS NULL),"
            "count(*) FILTER (WHERE artifact_committed=FALSE),"
            "min(retry_ordinal),max(retry_ordinal) FROM "
            "m4_isolated_v11.execution_attempts"
        ).fetchone()
        results = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.candidate_results"
            ).fetchone()[0]
        )
        deliveries = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger"
            ).fetchone()[0]
        )
        head = cursor.execute(
            "SELECT registration_seq,m_total FROM m4_isolated_v11.multiplicity_head "
            "WHERE singleton=TRUE"
        ).fetchone()
    if batches != [
        (
            0,
            0,
            "2026100",
            USER_SCOPE_RESUME_EXECUTION_ID,
            0,
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
        )
    ]:
        raise IsolatedRunnerError("user_scope_resume_registration_batch_changed")
    if candidates != [
        (
            0,
            "TERMINAL",
            USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            contract.ATTEMPTS_PER_BATCH,
        )
    ]:
        raise IsolatedRunnerError("user_scope_resume_candidates_changed")
    if (
        attempts != contract.ATTEMPTS_PER_BATCH
        or attempt_state
        != (
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
            0,
            0,
        )
        or results != 0
        or deliveries != 0
        or head != (0, 18)
    ):
        raise IsolatedRunnerError("user_scope_resume_ledger_changed")
    _p3_source_identity()
    return manifest, context


def _user_scope_committed_ledger_state(
    *, repository: PostgresResearchOSRepository
) -> str:
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        batches = cursor.execute(
            "SELECT registration_seq,batch_seq,target_issue,registration_execution_id,"
            "m_before,m_after,candidate_count FROM "
            "m4_isolated_v11.registration_batches ORDER BY registration_seq"
        ).fetchall()
        candidates = cursor.execute(
            "SELECT count(*),count(*) FILTER (WHERE state='TERMINAL') FROM "
            "m4_isolated_v11.candidate_registrations"
        ).fetchone()
        attempts = cursor.execute(
            "SELECT count(*),count(*) FILTER (WHERE artifact_committed),"
            "count(*) FILTER (WHERE artifact_digest IS NULL),"
            "count(*) FILTER (WHERE artifact_digest IS NOT NULL),"
            "count(*) FILTER (WHERE worker_started_at IS NOT NULL),"
            "count(*) FILTER (WHERE terminal_at IS NOT NULL),"
            "count(*) FILTER (WHERE status IN ('SUCCEEDED','FAILED')) FROM "
            "m4_isolated_v11.execution_attempts"
        ).fetchone()
        results = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.candidate_results"
            ).fetchone()[0]
        )
        deliveries = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger"
            ).fetchone()[0]
        )
        head = cursor.execute(
            "SELECT registration_seq,m_total FROM m4_isolated_v11.multiplicity_head "
            "WHERE singleton=TRUE"
        ).fetchone()
    if batches != [
        (
            0,
            0,
            "2026100",
            USER_SCOPE_RESUME_EXECUTION_ID,
            0,
            contract.ATTEMPTS_PER_BATCH,
            contract.ATTEMPTS_PER_BATCH,
        )
    ]:
        raise IsolatedRunnerError("committed_recovery_registration_batch_changed")
    if (
        candidates != (contract.ATTEMPTS_PER_BATCH, contract.ATTEMPTS_PER_BATCH)
        or attempts is None
        or tuple(attempts[:1] + attempts[4:]) != (contract.ATTEMPTS_PER_BATCH,) * 4
        or deliveries != 0
        or head != (0, contract.ATTEMPTS_PER_BATCH)
    ):
        raise IsolatedRunnerError("committed_recovery_ledger_identity_changed")
    _, committed, null_digests, nonnull_digests, *_ = map(int, attempts)
    if (
        committed == 0
        and null_digests == contract.ATTEMPTS_PER_BATCH
        and nonnull_digests == 0
        and results == 0
    ):
        return "PRE_MIRROR"
    if (
        committed == contract.ATTEMPTS_PER_BATCH
        and null_digests == 0
        and nonnull_digests == contract.ATTEMPTS_PER_BATCH
        and results == contract.ATTEMPTS_PER_BATCH
    ):
        return "MIRRORED"
    raise IsolatedRunnerError("committed_recovery_partial_ledger_forbidden")


def _validate_user_scope_committed_live_state(
    *, repository: IsolatedChallengerRepository
) -> tuple[ControlPlaneManifest, dict[str, str], str]:
    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    if (
        manifest.artifact_digest != USER_SCOPE_COMMITTED_MANIFEST_DIGEST
        or len(manifest.tasks) != 27
    ):
        raise IsolatedRunnerError("committed_recovery_manifest_changed")
    state_counts: dict[TaskStatus, int] = {}
    for state in manifest.task_states:
        state_counts[state.declared_status] = (
            state_counts.get(state.declared_status, 0) + 1
        )
    if state_counts != {TaskStatus.COMPLETED: 23, TaskStatus.DRAFT: 4}:
        raise IsolatedRunnerError("committed_recovery_task_states_changed")
    matches = [
        task for task in manifest.tasks if task.task_key == USER_SCOPE_RESUME_TASK_KEY
    ]
    if len(matches) != 1 or matches[0].artifact_digest != USER_SCOPE_RESUME_TASK_DIGEST:
        raise IsolatedRunnerError("committed_recovery_task_changed")
    task = matches[0]
    state = manifest.task_state_by_digest[task.artifact_digest]
    context = _task_context(task)
    if (
        state.declared_status is not TaskStatus.COMPLETED
        or state.completion_classification is not CompletionClassification.COMPLETE
        or state.superseded_by_task_digest is not None
        or context["batch_seq"] != "000000000000"
        or context["target_issue"] != "2026100"
        or json.loads(task.metric_contract).get("source_contract_digest")
        != USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
    ):
        raise IsolatedRunnerError("committed_recovery_task_identity_changed")
    events = repository.list_mainline_execution_events(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=USER_SCOPE_RESUME_TASK_KEY,
    )
    _validate_user_scope_resume_event_set(events, allow_completed=True)
    current_events = [
        item
        for item in events
        if item.get("task_digest") == USER_SCOPE_RESUME_TASK_DIGEST
    ]
    current_by_digest = {
        str(item.get("event_digest") or ""): item for item in current_events
    }
    completed = current_by_digest.get(USER_SCOPE_COMMITTED_EVENT_DIGEST, {})
    completed_payload = dict(completed.get("payload") or ())
    if (
        len(current_events) != 4
        or completed.get("execution_id") != USER_SCOPE_RESUME_EXECUTION_ID
        or completed.get("event_type") != "completed"
        or completed.get("sequence") != 3
        or completed.get("manifest_digest") != USER_SCOPE_RESUME_MANIFEST_DIGEST
        or completed_payload.get("execution_artifact_digest")
        != USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST
        or completed_payload.get("publication_batch_digest")
        != USER_SCOPE_COMMITTED_PUBLICATION_BATCH_DIGEST
        or completed_payload.get("registered_artifact_count") != 65
        or completed_payload.get("workload_rerun") is not False
        or completed_payload.get("formal_p3_mutated") is not False
        or completed_payload.get("promotion_triggered") is not False
    ):
        raise IsolatedRunnerError("committed_recovery_completed_event_changed")
    registrations = repository.list_mainline_artifacts(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
    )
    if len(registrations) != 65:
        raise IsolatedRunnerError("committed_recovery_registration_count_changed")
    facts = set(manifest.facts.artifacts)
    if any(
        fact.endswith((":SENT", ":UNCERTAIN"))
        or "PASS_TO_P4" in fact
        or "PASS_TO_P5" in fact
        or "PROMOTION" in fact
        for fact in facts
    ):
        raise IsolatedRunnerError("committed_recovery_forbidden_fact_present")
    ledger_state = _user_scope_committed_ledger_state(repository=repository)
    _p3_source_identity()
    return manifest, context, ledger_state


def _load_user_scope_predecessor_attestation() -> dict[str, Any]:
    foundation = {
        "schema_version": "dehps-m4-isolated-v11-user-systemd-runtime-migration.v1",
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "origin_git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": "dea22d7ca1cc876d278b1d18e4e68801a41291fd",
        "origin_source_contract_digest": USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "f6d043e22862c1ffd850dc5932a7be3c6f2dbaab4e9cf1d57db8a3f8158157ef"
        ),
        "repair": "SYSTEMD_SYSTEM_MANAGER_TO_EXACT_USER_MANAGER_QUERY",
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 745,
            "engineering_decision_id": 3157,
            "engineering_execution_id": 600,
            "operator_request_id": 746,
            "operator_decision_id": 3162,
            "operator_execution_id": 601,
            "operator_payload_sha256": (
                "019bfa1769bd0359bc94b4b4d023c13ec3d02ce9a7a93c91a9bca86b5b2d876d"
            ),
        },
        "parent_digests": [
            USER_SCOPE_RESUME_TASK_DIGEST,
            USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "f6d043e22862c1ffd850dc5932a7be3c6f2dbaab4e9cf1d57db8a3f8158157ef",
            "019bfa1769bd0359bc94b4b4d023c13ec3d02ce9a7a93c91a9bca86b5b2d876d",
        ],
    }
    latest = {
        "schema_version": (
            "dehps-m4-isolated-v11-same-key-event-isolation-runtime-migration.v2"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "origin_git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": USER_SCOPE_EVENT_ISOLATION_RUNTIME_COMMIT,
        "origin_source_contract_digest": USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed"
        ),
        "repair": "EXACT_SAME_KEY_EVENT_VIEW_AFTER_USER_SYSTEMD_GUARD_REPAIR",
        "predecessor_attestation_digest": (USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST),
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 747,
            "engineering_decision_id": 3167,
            "engineering_execution_id": 602,
            "operator_request_id": 748,
            "operator_decision_id": 3172,
            "operator_execution_id": 603,
            "operator_payload_sha256": (
                "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f"
            ),
        },
        "parent_digests": [
            USER_SCOPE_RESUME_TASK_DIGEST,
            USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "eaebe90afc17a3a226e08cb40891b38705eb0e48194d3ea656654210c69356ed",
            USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
            "4a44a44bb4805bb80d9a026dd7a1556f2cbf9b98498095d13a8acfdc98186c8f",
        ],
    }
    guard = {
        "schema_version": (
            "dehps-m4-isolated-v11-utc-registration-failed-event-runtime-migration.v3"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST,
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "origin_git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": "c30db93efb428198b4d7c0c0548feefbd315ba59",
        "origin_source_contract_digest": USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": (
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780"
        ),
        "repair": "UTC_REGISTRATION_RESUME_AND_EXACT_FAILED_EVENT_RECOVERY",
        "predecessor_attestation_digest": USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": 0,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": {
            "phase": "resume",
            "engineering_request_id": 750,
            "engineering_decision_id": 3182,
            "engineering_execution_id": 605,
            "operator_request_id": 751,
            "operator_decision_id": 3187,
            "operator_execution_id": 606,
            "operator_payload_sha256": (
                "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5"
            ),
        },
        "parent_digests": [
            USER_SCOPE_RESUME_TASK_DIGEST,
            USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
            USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            "7ef55ac4b726e39d1cfe5a0a6f3382d435c5d123c10618b4aee91a51454c1780",
            USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
            "9b533534e88b9b0476f9becd02456863cd70e8385c19053e19f023c2e5e123a5",
        ],
    }
    expected_chain = (
        (
            foundation,
            USER_SCOPE_FOUNDATION_ATTESTATION_DIGEST,
            "dehps.m4.isolated-24h-challenger.user-systemd-runtime-migration.v11",
        ),
        (
            latest,
            USER_SCOPE_SEQUENCE2_ATTESTATION_DIGEST,
            (
                "dehps.m4.isolated-24h-challenger."
                "same-key-event-isolation-runtime-migration.v11"
            ),
        ),
        (
            guard,
            USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST,
            (
                "dehps.m4.isolated-24h-challenger."
                "utc-registration-failed-event-runtime-migration.v11"
            ),
        ),
    )
    for expected, digest, domain in expected_chain:
        path = (
            ROOT_DIR
            / "runtime/research-os/mainline/tasks"
            / USER_SCOPE_RESUME_TASK_KEY
            / USER_SCOPE_RESUME_EXECUTION_ID
            / "runtime-migrations"
            / digest
            / "user-systemd-runtime-migration.json"
        )
        if not path.is_file():
            raise IsolatedRunnerError("user_scope_predecessor_attestation_missing")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IsolatedRunnerError(
                "user_scope_predecessor_attestation_unreadable"
            ) from exc
        identity = dict(expected)
        identity.pop("artifact_digest")
        if (
            payload != expected
            or contract.domain_digest(identity, domain=domain) != digest
        ):
            raise IsolatedRunnerError("user_scope_predecessor_attestation_changed")
    return guard


def _user_scope_runtime_attestation(
    *,
    repaired_source_digest: str,
    repaired_git_commit: str,
    governance: Mapping[str, Any],
    predecessor_attestation_digest: str,
) -> tuple[Path, dict[str, Any]]:
    if predecessor_attestation_digest != USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST:
        raise IsolatedRunnerError("user_scope_predecessor_attestation_changed")
    body = {
        "schema_version": (
            "dehps-m4-isolated-v11-sequence3-guard-failure-runtime-migration.v4"
        ),
        "artifact_type": "m4_isolated_v11_user_systemd_runtime_migration",
        "artifact_digest": "",
        "scientific_contract_changed": False,
        "workload_definition_changed": False,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "started_event_digest": USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
        "failed_event_digest": USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        "prior_failed_event_digest": USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
        "origin_git_commit": USER_SCOPE_RESUME_ORIGIN_COMMIT,
        "runtime_git_commit": repaired_git_commit,
        "origin_source_contract_digest": USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        "runtime_source_contract_digest": repaired_source_digest,
        "repair": "EXACT_SEQUENCE3_GUARD_FAILURE_ZERO_RETRAINING_RECOVERY",
        "predecessor_attestation_digest": predecessor_attestation_digest,
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts_before_resume": contract.ATTEMPTS_PER_BATCH,
        "candidate_results_before_resume": 0,
        "mail_delivery_before_resume": 0,
        "governance": dict(governance),
        "parent_digests": [
            USER_SCOPE_RESUME_TASK_DIGEST,
            USER_SCOPE_RESUME_STARTED_EVENT_DIGEST,
            USER_SCOPE_RESUME_FAILED_EVENT_DIGEST,
            USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
            USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
            repaired_source_digest,
            predecessor_attestation_digest,
            str(governance["operator_payload_sha256"]),
        ],
    }
    identity = dict(body)
    identity.pop("artifact_digest")
    body["artifact_digest"] = contract.domain_digest(
        identity,
        domain=(
            "dehps.m4.isolated-24h-challenger."
            "sequence3-guard-failure-runtime-migration.v11"
        ),
    )
    path = (
        ROOT_DIR
        / "runtime/research-os/mainline/tasks"
        / USER_SCOPE_RESUME_TASK_KEY
        / USER_SCOPE_RESUME_EXECUTION_ID
        / "runtime-migrations"
        / str(body["artifact_digest"])
        / "user-systemd-runtime-migration.json"
    )
    return path, body


def recover_p3_user_scope_committed_batch(
    *,
    apply: bool,
    repository: IsolatedChallengerRepository,
    repaired_source_digest: str,
    repaired_git_commit: str,
) -> dict[str, Any]:
    governance = validate_user_scope_committed_recovery_governance(
        repository=AgentRequestRepository(),
        source_contract=artifacts.load_source_contract(root_dir=ROOT_DIR),
        repaired_source_digest=repaired_source_digest,
        git_commit=repaired_git_commit,
    )
    manifest, task_context, ledger_state_before = (
        _validate_user_scope_committed_live_state(repository=repository)
    )
    p3_before = _p3_source_identity()
    supervisor = mainline.IsolatedChallengerSupervisor(
        repository=repository,
        context=task_context,
        source_digest=USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        git_commit=USER_SCOPE_RESUME_ORIGIN_COMMIT,
        simulation=False,
    )
    generic = supervisor.replay(
        task_key=USER_SCOPE_RESUME_TASK_KEY,
        execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
    )
    _verify_generic_replay(generic)
    if not apply:
        if _p3_source_identity() != p3_before:
            raise IsolatedRunnerError(
                "formal_p3_source_changed_during_committed_replay"
            )
        return {
            "schema_version": (
                "dehps-m4-isolated-v11-committed-replay-ledger-recovery.v1"
            ),
            "status": "COMMITTED_RECOVERY_DRY_RUN_VERIFIED",
            "apply": False,
            "manifest_digest": manifest.artifact_digest,
            "task_key": USER_SCOPE_RESUME_TASK_KEY,
            "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
            "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
            "completed_event_digest": USER_SCOPE_COMMITTED_EVENT_DIGEST,
            "execution_artifact_digest": (
                USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST
            ),
            "registered_artifact_count": 65,
            "ledger_state": ledger_state_before,
            "generic_replay": "REPLAY_VERIFIED",
            "scientific_workloads_executed": 0,
            "run_once_calls": 0,
            "smtp_calls": 0,
            "mandatory_mail_kinds": list(USER_SCOPE_MANDATORY_MAIL_KINDS),
            "mail_integration": "PENDING_REAL_SCHEDULED_DATA250_RECEIPT_REPLAY",
            "formal_p3_mutated": False,
            "p4_p5_p6_or_promotion_triggered": False,
            "governance": governance,
        }
    _mirror_search_batch_ledger(
        repository=repository,
        task_key=USER_SCOPE_RESUME_TASK_KEY,
    )
    ledger_state_after = _user_scope_committed_ledger_state(repository=repository)
    if ledger_state_after != "MIRRORED":
        raise IsolatedRunnerError("committed_recovery_ledger_mirror_incomplete")
    if _p3_source_identity() != p3_before:
        raise IsolatedRunnerError("formal_p3_source_changed_during_committed_recovery")
    return {
        "schema_version": "dehps-m4-isolated-v11-committed-replay-ledger-recovery.v1",
        "status": "BATCH_COMPLETE_AND_REPLAY_VERIFIED",
        "apply": True,
        "manifest_digest": manifest.artifact_digest,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "completed_event_digest": USER_SCOPE_COMMITTED_EVENT_DIGEST,
        "execution_artifact_digest": USER_SCOPE_COMMITTED_EXECUTION_ARTIFACT_DIGEST,
        "registered_artifact_count": 65,
        "ledger_state_before": ledger_state_before,
        "ledger_state_after": ledger_state_after,
        "generic_replay": "REPLAY_VERIFIED",
        "scientific_workloads_executed": 0,
        "run_once_calls": 0,
        "smtp_calls": 0,
        "mandatory_mail_kinds": list(USER_SCOPE_MANDATORY_MAIL_KINDS),
        "mail_integration": "PENDING_REAL_SCHEDULED_DATA250_RECEIPT_REPLAY",
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
        "governance": governance,
    }


def resume_p3_user_scope_running_batch(
    *,
    apply: bool,
    context: Mapping[str, str],
    repaired_source_digest: str,
    repaired_git_commit: str,
) -> dict[str, Any]:
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise IsolatedRunnerError("dirty_worktree")
    source_contract = artifacts.load_source_contract(root_dir=ROOT_DIR)
    if source_contract["artifact_digest"] != repaired_source_digest:
        raise IsolatedRunnerError("user_scope_repaired_source_changed")
    if (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
        ).strip()
        != repaired_git_commit
    ):
        raise IsolatedRunnerError("user_scope_repaired_commit_changed")
    repository = IsolatedChallengerRepository(
        context=context, source_digest=USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST
    )
    current_manifest = repository.load_manifest(
        control_plane_key=contract.CONTROL_PLANE_KEY
    )
    if current_manifest.artifact_digest == USER_SCOPE_COMMITTED_MANIFEST_DIGEST:
        return recover_p3_user_scope_committed_batch(
            apply=apply,
            repository=repository,
            repaired_source_digest=repaired_source_digest,
            repaired_git_commit=repaired_git_commit,
        )
    governance = validate_user_scope_recovery_governance(
        repository=AgentRequestRepository(),
        source_contract=source_contract,
        repaired_source_digest=repaired_source_digest,
        git_commit=repaired_git_commit,
        phase="resume",
    )
    manifest, task_context = _validate_user_scope_resume_live_state(
        repository=repository
    )
    predecessor_attestation = _load_user_scope_predecessor_attestation()
    attestation_path, attestation = _user_scope_runtime_attestation(
        repaired_source_digest=repaired_source_digest,
        repaired_git_commit=repaired_git_commit,
        governance=governance,
        predecessor_attestation_digest=str(predecessor_attestation["artifact_digest"]),
    )
    if not apply:
        return {
            "schema_version": "dehps-m4-isolated-v11-user-systemd-resume.v1",
            "status": "DRY_RUN_VERIFIED",
            "apply": False,
            "manifest_digest": manifest.artifact_digest,
            "task_key": USER_SCOPE_RESUME_TASK_KEY,
            "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
            "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
            "attestation_digest": attestation["artifact_digest"],
            "registered_candidates": contract.ATTEMPTS_PER_BATCH,
            "execution_attempts": contract.ATTEMPTS_PER_BATCH,
            "candidate_results": 0,
            "smtp_calls": 0,
            "formal_p3_mutated": False,
            "p4_p5_p6_or_promotion_triggered": False,
        }
    _persist_immutable(attestation_path, attestation)
    p3_before = _p3_source_identity()
    supervisor = mainline.IsolatedChallengerSupervisor(
        repository=repository,
        context=task_context,
        source_digest=USER_SCOPE_RESUME_ORIGIN_SOURCE_DIGEST,
        git_commit=USER_SCOPE_RESUME_ORIGIN_COMMIT,
        simulation=False,
        failed_recovery_event_digest=USER_SCOPE_GUARD_FAILED_EVENT_DIGEST,
        failed_recovery_attestation_digest=(USER_SCOPE_PREDECESSOR_ATTESTATION_DIGEST),
    )
    with repository.user_scope_resume_event_view():
        result = supervisor.run_once(task_key=USER_SCOPE_RESUME_TASK_KEY)
        if (
            result.get("status") != "COMPLETE"
            or result.get("task_key") != USER_SCOPE_RESUME_TASK_KEY
            or result.get("execution_id") != USER_SCOPE_RESUME_EXECUTION_ID
        ):
            raise IsolatedRunnerError("user_scope_resume_completion_changed")
        generic = supervisor.replay(
            task_key=USER_SCOPE_RESUME_TASK_KEY,
            execution_id=USER_SCOPE_RESUME_EXECUTION_ID,
        )
        _verify_generic_replay(generic)
    template = mainline.template_for_task_key(
        USER_SCOPE_RESUME_TASK_KEY, context=task_context
    )
    activated = _activation_facts(
        task_key=USER_SCOPE_RESUME_TASK_KEY,
        template=template,
        context=task_context,
        repository=repository,
    )
    if activated:
        raise IsolatedRunnerError("user_scope_resume_unexpected_activation_fact")
    if _p3_source_identity() != p3_before:
        raise IsolatedRunnerError("formal_p3_source_changed_during_user_scope_resume")
    completed = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    completed_task = next(
        item for item in completed.tasks if item.task_key == USER_SCOPE_RESUME_TASK_KEY
    )
    completed_state = completed.task_state_by_digest[completed_task.artifact_digest]
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        attempts = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.execution_attempts"
            ).fetchone()[0]
        )
        terminal = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.candidate_registrations "
                "WHERE state='TERMINAL'"
            ).fetchone()[0]
        )
        results = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.candidate_results"
            ).fetchone()[0]
        )
        deliveries = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger"
            ).fetchone()[0]
        )
    if (
        completed_state.declared_status is not TaskStatus.COMPLETED
        or completed_state.completion_classification
        is not CompletionClassification.COMPLETE
        or not contract.ATTEMPTS_PER_BATCH <= attempts <= 54
        or terminal != contract.ATTEMPTS_PER_BATCH
        or results != contract.ATTEMPTS_PER_BATCH
        or deliveries != 0
    ):
        raise IsolatedRunnerError("user_scope_resume_postcondition_changed")
    return {
        "schema_version": "dehps-m4-isolated-v11-user-systemd-resume.v1",
        "status": "BATCH_COMPLETE_AND_REPLAY_VERIFIED",
        "apply": True,
        "manifest_digest": completed.artifact_digest,
        "task_key": USER_SCOPE_RESUME_TASK_KEY,
        "task_digest": USER_SCOPE_RESUME_TASK_DIGEST,
        "execution_id": USER_SCOPE_RESUME_EXECUTION_ID,
        "attestation_digest": attestation["artifact_digest"],
        "attestation_path": str(attestation_path.relative_to(ROOT_DIR)),
        "registered_candidates": contract.ATTEMPTS_PER_BATCH,
        "execution_attempts": attempts,
        "candidate_results": results,
        "generic_replay": "REPLAY_VERIFIED",
        "smtp_calls": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def install(
    *,
    apply: bool,
    context: Mapping[str, str],
    source_digest: str,
    operator_configuration_authorized: bool,
    git_commit: str | None = None,
) -> dict[str, Any]:
    payload, dry_run = builder.build_bootstrap_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=operator_configuration_authorized,
    )
    if not apply:
        return dry_run
    repository = IsolatedChallengerRepository(
        context=context, source_digest=source_digest
    )
    repository.ensure_schema()
    schema_attestation = _attest_database_schema(
        repository=repository,
        git_commit=str(git_commit or ""),
    )
    source_contract = artifacts.load_source_contract(root_dir=ROOT_DIR)
    if source_contract["artifact_digest"] != source_digest:
        raise IsolatedRunnerError("install_source_contract_changed")
    registered_source = mainline.register_input_artifact(
        repository=repository,
        payload=source_contract,
        git_commit=str(git_commit or ""),
        source_path=contract.SOURCE_CONTRACT_PATH,
        content_bytes=(ROOT_DIR / contract.SOURCE_CONTRACT_PATH).read_bytes(),
    )
    database_schema = mainline.build_registered_input(
        artifact_type="M4IsolatedDatabaseSchemaIdentityV11",
        body={
            "schema_version": contract.DATABASE_SCHEMA_VERSION,
            "contract_digest": contract.CONTRACT_DIGEST,
            "source_contract_digest": source_digest,
            "installed_git_commit": schema_attestation["installed_git_commit"],
        },
        parent_digests=(source_digest,),
    )
    registered_schema = mainline.register_input_artifact(
        repository=repository,
        payload=database_schema,
        git_commit=str(git_commit or ""),
    )
    result, imported_manifest_digest = repository.import_bootstrap_manifest(payload)
    return {
        "status": "IMPORTED",
        "manifest_digest": imported_manifest_digest,
        "import_result": str(result),
        "database_schema_attestation": schema_attestation,
        "registered_source_contract_digest": registered_source["artifact_digest"],
        "registered_database_schema_digest": registered_schema["artifact_digest"],
        "smtp_calls": 0,
        "workloads": 0,
        "formal_p3_mutated": False,
    }


def _isolated_units_quiescent() -> dict[str, dict[str, str | int]]:
    units = (
        "dehps-m4-isolated-24h-challenger-v11.timer",
        "dehps-m4-isolated-24h-challenger-v11.service",
    )
    observed: dict[str, dict[str, str | int]] = {}
    for unit in units:
        is_service = unit.endswith(".service")
        required = {"LoadState", "ActiveState", "SubState"}
        if is_service:
            required |= {"MainPID", "ControlPID"}
        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "show",
                    unit,
                    "--property=LoadState,ActiveState,SubState,MainPID,ControlPID",
                    "--no-pager",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise IsolatedRunnerError(
                "daily_recovery_isolated_units_not_quiescent"
            ) from exc
        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if not line:
                continue
            if "=" not in line:
                raise IsolatedRunnerError("daily_recovery_isolated_units_not_quiescent")
            key, value = line.split("=", 1)
            if key not in required or key in values:
                raise IsolatedRunnerError("daily_recovery_isolated_units_not_quiescent")
            values[key] = value
        main_pid = control_pid = 0
        if is_service:
            try:
                main_pid = int(values.get("MainPID", "-1"))
                control_pid = int(values.get("ControlPID", "-1"))
            except ValueError as exc:
                raise IsolatedRunnerError(
                    "daily_recovery_isolated_units_not_quiescent"
                ) from exc
        if (
            result.returncode != 0
            or set(values) != required
            or values["LoadState"] != "loaded"
            or values["ActiveState"] != "inactive"
            or values["SubState"] != "dead"
            or (is_service and (main_pid != 0 or control_pid != 0))
        ):
            raise IsolatedRunnerError("daily_recovery_isolated_units_not_quiescent")
        observed[unit] = {
            "LoadState": values["LoadState"],
            "ActiveState": values["ActiveState"],
            "SubState": values["SubState"],
        }
        if is_service:
            observed[unit].update({"MainPID": main_pid, "ControlPID": control_pid})
    return observed


def _daily_recovery_failed_operator_input_prestate(
    *, repository: IsolatedChallengerRepository
) -> None:
    expected = {
        DAILY_RECOVERY_FAILED_OPERATOR_SOURCE_DIGEST,
        DAILY_RECOVERY_FAILED_OPERATOR_ATTESTATION_DIGEST,
    }
    with (
        repository.connection_factory() as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        rows = cursor.execute(
            "SELECT artifact_digest,artifact_type,artifact_json,"
            "parent_digests_json,git_commit,source_path,content_sha256 "
            "FROM m4_isolated_v11.registered_inputs WHERE artifact_digest=ANY(%s)",
            (list(expected),),
        ).fetchall()
    if len(rows) != 2 or {str(row["artifact_digest"]) for row in rows} != expected:
        raise IsolatedRunnerError("daily_recovery_failed_operator_input_changed")
    parsed_by_digest: dict[str, dict[str, Any]] = {}
    git_by_digest: dict[str, str] = {}
    for row in rows:
        digest = str(row["artifact_digest"])
        parsed = mainline.validate_registered_input_payload(dict(row["artifact_json"]))
        parents = list(row["parent_digests_json"])
        git_commit = str(row["git_commit"] or "")
        source_path = row["source_path"]
        if (
            parsed["artifact_digest"] != digest
            or parsed["artifact_type"] != str(row["artifact_type"])
            or list(parsed.get("parent_digests") or ()) != parents
            or _GIT_COMMIT.fullmatch(git_commit) is None
        ):
            raise IsolatedRunnerError("daily_recovery_failed_operator_input_changed")
        if digest == DAILY_RECOVERY_FAILED_OPERATOR_SOURCE_DIGEST:
            if source_path != contract.SOURCE_CONTRACT_PATH or parents:
                raise IsolatedRunnerError(
                    "daily_recovery_failed_operator_source_changed"
                )
            archived = subprocess.run(
                ["git", "show", f"{git_commit}:{source_path}"],
                cwd=ROOT_DIR,
                check=False,
                capture_output=True,
            )
            try:
                archived_json = json.loads(archived.stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise IsolatedRunnerError(
                    "daily_recovery_failed_operator_source_changed"
                ) from exc
            if (
                archived.returncode != 0
                or hashlib.sha256(archived.stdout).hexdigest()
                != str(row["content_sha256"] or "")
                or archived_json != parsed
            ):
                raise IsolatedRunnerError(
                    "daily_recovery_failed_operator_source_changed"
                )
        else:
            content = contract.canonical_json(parsed).encode("ascii")
            if source_path is not None or hashlib.sha256(content).hexdigest() != str(
                row["content_sha256"] or ""
            ):
                raise IsolatedRunnerError(
                    "daily_recovery_failed_operator_attestation_changed"
                )
        parsed_by_digest[digest] = parsed
        git_by_digest[digest] = git_commit
    attestation = parsed_by_digest[DAILY_RECOVERY_FAILED_OPERATOR_ATTESTATION_DIGEST]
    body = attestation["body"]
    if (
        attestation["parent_digests"]
        != [
            contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
            DAILY_RECOVERY_FAILED_OPERATOR_SOURCE_DIGEST,
        ]
        or body.get("runtime_source_contract_digest")
        != DAILY_RECOVERY_FAILED_OPERATOR_SOURCE_DIGEST
        or body.get("runtime_git_commit")
        != git_by_digest[DAILY_RECOVERY_FAILED_OPERATOR_SOURCE_DIGEST]
        or git_by_digest[DAILY_RECOVERY_FAILED_OPERATOR_ATTESTATION_DIGEST]
        != body.get("runtime_git_commit")
        or body.get("operator_request_id") != 793
        or body.get("operator_approval_decision_id") != 3379
        or body.get("operator_execution_id") != 639
        or body.get("operator_payload_sha256")
        != "315c8271b91f4a6d454f16ac393f32d5d05ac9861a4e15bef60088ee0baa64d9"
    ):
        raise IsolatedRunnerError("daily_recovery_failed_operator_attestation_changed")


def _daily_recovery_live_preflight(
    *, repository: IsolatedChallengerRepository
) -> tuple[ControlPlaneManifest, dict[str, str], dict[str, Any]]:
    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    failures: list[Any] = []
    running: list[Any] = []
    daily_task = None
    for task in manifest.tasks:
        state = manifest.task_state_by_digest[task.artifact_digest]
        if state.declared_status is TaskStatus.FAILED:
            failures.append(task)
        elif state.declared_status is TaskStatus.RUNNING:
            running.append(task)
        if task.task_key == contract.DAILY_RECOVERY_TASK_KEY:
            daily_task = task
    if daily_task is None:
        raise IsolatedRunnerError("daily_recovery_live_task_state_changed")
    daily_state = manifest.task_state_by_digest[daily_task.artifact_digest]
    running_shape = (
        manifest.artifact_digest == DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST
        and not failures
        and running == [daily_task]
        and daily_state.declared_status is TaskStatus.RUNNING
        and daily_state.completion_classification is CompletionClassification.INTEGRATED
    )
    if (
        not running_shape
        or daily_task.artifact_digest != contract.DAILY_RECOVERY_TASK_DIGEST
        or json.loads(daily_task.metric_contract).get("source_contract_digest")
        != contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST
    ):
        raise IsolatedRunnerError("daily_recovery_live_task_state_changed")
    events = repository.list_mainline_execution_events(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
    )
    records = [_event_record(item) for item in events]
    if (
        len(records) != 2
        or [(item.event_type, item.sequence) for item in records]
        != [("started", 0), ("failed", 1)]
        or records[0].artifact_digest != contract.DAILY_RECOVERY_STARTED_EVENT_DIGEST
        or records[1].artifact_digest != contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST
        or any(
            item.execution_id != contract.DAILY_RECOVERY_EXECUTION_ID
            or item.task_digest != contract.DAILY_RECOVERY_TASK_DIGEST
            for item in records
        )
    ):
        raise IsolatedRunnerError("daily_recovery_live_event_prefix_changed")
    registrations = repository.list_mainline_artifacts(
        control_plane_key=contract.CONTROL_PLANE_KEY,
        execution_id=contract.DAILY_RECOVERY_EXECUTION_ID,
    )
    if registrations:
        raise IsolatedRunnerError("daily_recovery_live_registration_changed")
    execution_roots = (
        ROOT_DIR
        / "runtime/isolated-24h-challenger-v11/artifacts"
        / contract.DAILY_RECOVERY_TASK_KEY
        / contract.DAILY_RECOVERY_EXECUTION_ID,
        ROOT_DIR
        / "runtime/research-os/mainline/.staging"
        / contract.DAILY_RECOVERY_TASK_KEY
        / contract.DAILY_RECOVERY_EXECUTION_ID,
    )
    if any(path.exists() for path in execution_roots):
        raise IsolatedRunnerError("daily_recovery_live_output_changed")
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        daily_rows = int(
            cursor.execute(
                "SELECT count(*) FROM m4_isolated_v11.delivery_ledger "
                "WHERE mail_kind='DAILY_24H_RESEARCH_SUMMARY' "
                "AND target_identity='20260828'"
            ).fetchone()[0]
        )
    incident_state = mainline.latest_incident_ledger_state(
        repository=repository, root_dir=ROOT_DIR
    )
    if (
        daily_rows != 0
        or incident_state["open_incident_ids"] != [contract.DAILY_RECOVERY_INCIDENT_ID]
        or incident_state["transition_seq"] != 0
    ):
        raise IsolatedRunnerError("daily_recovery_delivery_or_incident_state_changed")
    p3 = _p3_source_identity()
    if (
        p3["artifact_digest"] != contract.FORMAL_P3_SOURCE_DIGEST
        or p3["source_set_digest"] != FORMAL_P3_FROZEN_SOURCE_SET_DIGEST
    ):
        raise IsolatedRunnerError("daily_recovery_formal_p3_identity_changed")
    _daily_recovery_failed_operator_input_prestate(repository=repository)
    _isolated_units_quiescent()
    return manifest, _task_context(daily_task), incident_state


def _daily_recovery_committed_state_preflight(
    *, repository: IsolatedChallengerRepository
) -> tuple[str, ControlPlaneManifest, dict[str, str], dict[str, Any]]:
    """Classify only the frozen PRE/POST committed recovery states."""

    manifest = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    if manifest.artifact_digest == DAILY_RECOVERY_RUNNING_MANIFEST_DIGEST:
        pre_manifest, context, incident = _daily_recovery_live_preflight(
            repository=repository
        )
        return "PRE_COMMIT", pre_manifest, context, incident

    mainline.load_recovered_daily_summary_completed_execution(
        repository=repository,
        root_dir=ROOT_DIR,
        runtime_migration_attestation_digest=(
            DAILY_RECOVERY_COMMITTED_RUNTIME_ATTESTATION_DIGEST
        ),
    )
    daily_tasks = [
        task
        for task in manifest.tasks
        if task.task_key == contract.DAILY_RECOVERY_TASK_KEY
    ]
    if len(daily_tasks) != 1:
        raise IsolatedRunnerError("daily_recovery_committed_task_not_unique")
    daily_task = daily_tasks[0]
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        delivery_rows = cursor.execute(
            "SELECT state,count(*) FROM m4_isolated_v11.delivery_ledger "
            "WHERE mail_kind='DAILY_24H_RESEARCH_SUMMARY' "
            "AND target_identity='20260828' GROUP BY state ORDER BY state"
        ).fetchall()
    delivery_state = {str(state): int(count) for state, count in delivery_rows}
    if (
        delivery_state.get("UNCERTAIN", 0) > 0
        or any(state not in {"SENT"} for state in delivery_state)
        or delivery_state.get("SENT", 0) > 1
    ):
        raise IsolatedRunnerError("daily_recovery_smtp_state_uncertain_or_changed")
    incident_state = mainline.latest_incident_ledger_state(
        repository=repository, root_dir=ROOT_DIR
    )
    allowed_incident_states = (
        incident_state["open_incident_ids"] == [contract.DAILY_RECOVERY_INCIDENT_ID]
        and incident_state["resolved_incident_ids"] == []
        and incident_state["transition_seq"] == 0
    ) or (
        incident_state["open_incident_ids"] == []
        and incident_state["resolved_incident_ids"]
        == [contract.DAILY_RECOVERY_INCIDENT_ID]
        and incident_state["transition_seq"] == 1
    )
    if not allowed_incident_states:
        raise IsolatedRunnerError("daily_recovery_incident_progress_changed")
    p3 = _p3_source_identity()
    if (
        p3["artifact_digest"] != contract.FORMAL_P3_SOURCE_DIGEST
        or p3["source_set_digest"] != FORMAL_P3_FROZEN_SOURCE_SET_DIGEST
    ):
        raise IsolatedRunnerError("daily_recovery_formal_p3_identity_changed")
    _daily_recovery_failed_operator_input_prestate(repository=repository)
    _isolated_units_quiescent()
    state = (
        "POST_COMMIT"
        if manifest.artifact_digest == DAILY_RECOVERY_POST_COMMIT_MANIFEST_DIGEST
        else "POST_COMMIT_RESUME"
    )
    return state, manifest, _task_context(daily_task), incident_state


def _resume_committed_daily_summary(
    *,
    repository: IsolatedChallengerRepository,
    context: Mapping[str, str],
) -> dict[str, Any]:
    completed, execution, _ = mainline.load_recovered_daily_summary_completed_execution(
        repository=repository,
        root_dir=ROOT_DIR,
        runtime_migration_attestation_digest=(
            DAILY_RECOVERY_COMMITTED_RUNTIME_ATTESTATION_DIGEST
        ),
    )
    children = mainline.load_completed_task_artifacts(
        repository=repository,
        root_dir=ROOT_DIR,
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
    )
    summaries = [
        item
        for item in children
        if item.get("artifact_type") == "M4IsolatedDailySummaryV11"
    ]
    if len(summaries) != 1:
        raise IsolatedRunnerError("daily_recovery_committed_summary_not_unique")
    typed = artifacts.replay_artifact(
        summaries[0], expected_parent_digests=summaries[0]["parent_digests"]
    )
    if (
        typed.get("status") != "REPLAY_VERIFIED"
        or typed.get("artifact_digest") != DAILY_RECOVERY_COMMITTED_SUMMARY_DIGEST
        or typed.get("dispatch_performed") is not False
    ):
        raise IsolatedRunnerError("daily_recovery_typed_replay_failed")
    supervisor = mainline.IsolatedChallengerSupervisor(
        repository=repository,
        context=context,
        source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
        git_commit=contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT,
        simulation=False,
        failed_recovery_event_digest=contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST,
        failed_recovery_attestation_digest=(
            DAILY_RECOVERY_COMMITTED_RUNTIME_ATTESTATION_DIGEST
        ),
        runtime_git_commit=DAILY_RECOVERY_COMMITTED_RUNTIME_GIT_COMMIT,
        runtime_source_contract_digest=(DAILY_RECOVERY_COMMITTED_RUNTIME_SOURCE_DIGEST),
    )
    generic = supervisor.replay(
        task_key=contract.DAILY_RECOVERY_TASK_KEY,
        execution_id=contract.DAILY_RECOVERY_EXECUTION_ID,
    )
    _verify_generic_replay(generic)
    task = next(
        task
        for task in repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        ).tasks
        if task.task_key == contract.DAILY_RECOVERY_TASK_KEY
    )
    template = mainline.template_for_task_key(task.task_key, context=context)
    activated = _activation_facts(
        task_key=task.task_key,
        template=template,
        context=context,
        repository=repository,
    )
    live_facts = set(
        repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        ).facts.artifacts
    )
    additions = tuple(item for item in activated if item not in live_facts)
    if additions:
        repository.import_verified_facts(additions)
    return {
        "task_key": task.task_key,
        "task_digest": task.artifact_digest,
        "execution_id": execution["execution_id"],
        "completed_event_digest": completed["event_digest"],
        "execution_artifact_digest": execution["artifact_digest"],
        "typed_replay": "REPLAY_VERIFIED",
        "generic_replay": "REPLAY_VERIFIED",
        "activated_facts": list(activated),
        "dispatch_performed": False,
        "workload_rerun": False,
    }


def _dispatch_recovery_task(
    *,
    repository: IsolatedChallengerRepository,
    task_key: str,
    context: Mapping[str, str],
    source_digest: str,
    git_commit: str,
    runtime_source_digest: str,
    runtime_git_commit: str,
    attestation_digest: str,
) -> dict[str, Any]:
    supervisor = mainline.IsolatedChallengerSupervisor(
        repository=repository,
        context=context,
        source_digest=source_digest,
        git_commit=git_commit,
        simulation=False,
        failed_recovery_event_digest=contract.DAILY_RECOVERY_FAILED_EVENT_DIGEST,
        failed_recovery_attestation_digest=attestation_digest,
        runtime_git_commit=runtime_git_commit,
        runtime_source_contract_digest=runtime_source_digest,
    )
    before = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    matches = [item for item in before.tasks if item.task_key == task_key]
    if len(matches) != 1:
        raise IsolatedRunnerError("daily_recovery_dispatch_task_not_unique")
    task = matches[0]
    state = before.task_state_by_digest[task.artifact_digest]
    dispatch_performed = state.declared_status is not TaskStatus.COMPLETED
    if dispatch_performed:
        result = supervisor.run_once(task_key=task_key)
        if result.get("status") != "COMPLETE" or result.get("task_key") != task_key:
            raise IsolatedRunnerError("daily_recovery_dispatch_not_complete")
        execution_id = str(result["execution_id"])
    else:
        completed = [
            item
            for item in repository.list_mainline_execution_events(
                control_plane_key=contract.CONTROL_PLANE_KEY,
                task_key=task_key,
            )
            if item.get("event_type") == "completed"
        ]
        if len(completed) != 1:
            raise IsolatedRunnerError("daily_recovery_completed_event_not_unique")
        execution_id = str(completed[0].get("execution_id") or "")
    typed_replay = None
    if task_key == contract.DAILY_RECOVERY_TASK_KEY:
        children = mainline.load_completed_task_artifacts(
            repository=repository,
            root_dir=ROOT_DIR,
            task_key=task_key,
        )
        summaries = [
            item
            for item in children
            if item.get("artifact_type") == "M4IsolatedDailySummaryV11"
        ]
        if len(summaries) != 1:
            raise IsolatedRunnerError("daily_recovery_committed_summary_not_unique")
        typed = artifacts.replay_artifact(
            summaries[0], expected_parent_digests=summaries[0]["parent_digests"]
        )
        if typed.get("status") != "REPLAY_VERIFIED":
            raise IsolatedRunnerError("daily_recovery_typed_replay_failed")
        typed_replay = "REPLAY_VERIFIED"
    generic = supervisor.replay(task_key=task_key, execution_id=execution_id)
    _verify_generic_replay(generic)
    task = next(
        item
        for item in repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        ).tasks
        if item.task_key == task_key
    )
    template = mainline.template_for_task_key(task_key, context=context)
    activated = _activation_facts(
        task_key=task_key,
        template=template,
        context=context,
        repository=repository,
    )
    live_facts = set(
        repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        ).facts.artifacts
    )
    additions = tuple(item for item in activated if item not in live_facts)
    if additions:
        repository.import_verified_facts(additions)
    return {
        "task_key": task_key,
        "task_digest": task.artifact_digest,
        "execution_id": execution_id,
        "activated_facts": list(activated),
        "dispatch_performed": dispatch_performed,
        "typed_replay": typed_replay,
        "generic_replay": "REPLAY_VERIFIED",
    }


def recover_daily_mail_chain(
    *,
    apply: bool,
    context: Mapping[str, str],
    source_contract: Mapping[str, Any],
    source_digest: str,
    git_commit: str,
) -> dict[str, Any]:
    p3_before = _p3_source_identity()
    repository = IsolatedChallengerRepository(
        context=context, source_digest=source_digest
    )
    start_state, manifest, daily_context, incident_before = (
        _daily_recovery_committed_state_preflight(repository=repository)
    )
    preflight = {
        "status": "DAILY_MAIL_RECOVERY_PREFLIGHT_VALID",
        "apply": False,
        "manifest_digest": manifest.artifact_digest,
        "recovery_start_state": start_state,
        "failed_task_key": contract.DAILY_RECOVERY_TASK_KEY,
        "failed_execution_id": contract.DAILY_RECOVERY_EXECUTION_ID,
        "open_incident_ids": incident_before["open_incident_ids"],
        "smtp_calls": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }
    if not apply:
        return preflight
    units = _isolated_units_quiescent()
    governance = validate_daily_mail_recovery_governance(
        repository=AgentRequestRepository(),
        source_contract=source_contract,
        runtime_source_digest=source_digest,
        git_commit=git_commit,
    )
    registered_source = mainline.register_input_artifact(
        repository=repository,
        payload=source_contract,
        git_commit=git_commit,
        source_path=contract.SOURCE_CONTRACT_PATH,
        content_bytes=(ROOT_DIR / contract.SOURCE_CONTRACT_PATH).read_bytes(),
    )
    attestation = mainline.build_runtime_migration_attestation_input(
        runtime_git_commit=git_commit,
        runtime_source_contract_digest=source_digest,
        **governance,
    )
    mainline.register_input_artifact(
        repository=repository,
        payload=attestation,
        git_commit=git_commit,
    )
    if start_state == "PRE_COMMIT":
        with repository.daily_recovery_event_view():
            recovered_summary = _dispatch_recovery_task(
                repository=repository,
                task_key=contract.DAILY_RECOVERY_TASK_KEY,
                context=daily_context,
                source_digest=contract.DAILY_RECOVERY_ORIGINAL_SOURCE_DIGEST,
                git_commit=contract.DAILY_RECOVERY_ORIGINAL_GIT_COMMIT,
                runtime_source_digest=source_digest,
                runtime_git_commit=git_commit,
                attestation_digest=attestation["artifact_digest"],
            )
    else:
        recovered_summary = _resume_committed_daily_summary(
            repository=repository,
            context=daily_context,
        )
    rebind = repository.rebind_unexecuted_daily_recovery_source()
    downstream: list[dict[str, Any]] = []
    for template_name in (
        "daily_summary_replay",
        "daily_mail_envelope",
        "daily_mail_replay",
        "daily_delivery",
    ):
        downstream.append(
            _dispatch_recovery_task(
                repository=repository,
                task_key=contract.task_template_by_name(template_name).key(
                    daily_context
                ),
                context=daily_context,
                source_digest=source_digest,
                git_commit=git_commit,
                runtime_source_digest=source_digest,
                runtime_git_commit=git_commit,
                attestation_digest=attestation["artifact_digest"],
            )
        )
    incident_task_key = (
        "m4-isolated-24h-challenger-v11-incident-"
        f"{contract.DAILY_RECOVERY_INCIDENT_ID}-open"
    )
    current = repository.load_manifest(control_plane_key=contract.CONTROL_PLANE_KEY)
    incident_task = next(
        item for item in current.tasks if item.task_key == incident_task_key
    )
    incident_context = _task_context(incident_task)
    extension = builder.extend_manifest(
        repository.export_manifest(control_plane_key=contract.CONTROL_PLANE_KEY),
        context=incident_context,
        source_digest=source_digest,
        template_names=frozenset({"incident_resolution"}),
    )
    repository.import_extension(extension)
    resolution_key = contract.task_template_by_name("incident_resolution").key(
        incident_context
    )
    resolution = _dispatch_recovery_task(
        repository=repository,
        task_key=resolution_key,
        context=incident_context,
        source_digest=source_digest,
        git_commit=git_commit,
        runtime_source_digest=source_digest,
        runtime_git_commit=git_commit,
        attestation_digest=attestation["artifact_digest"],
    )
    state = mainline.latest_incident_ledger_state(
        repository=repository, root_dir=ROOT_DIR
    )
    if (
        state["open_count"] != 0
        or contract.DAILY_RECOVERY_INCIDENT_ID not in state["resolved_incident_ids"]
        or state["transition_seq"] != 1
    ):
        raise IsolatedRunnerError("daily_recovery_incident_not_resolved")
    daily_delivery_key = contract.task_template_by_name("daily_delivery").key(
        daily_context
    )
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        before_duplicate = cursor.execute(
            "SELECT count(*),min(receipt_artifact_digest),max(receipt_artifact_digest) "
            "FROM m4_isolated_v11.delivery_ledger "
            "WHERE mail_kind='DAILY_24H_RESEARCH_SUMMARY' "
            "AND target_identity='20260828' AND state='SENT'"
        ).fetchone()
    duplicate = _dispatch_recovery_task(
        repository=repository,
        task_key=daily_delivery_key,
        context=daily_context,
        source_digest=source_digest,
        git_commit=git_commit,
        runtime_source_digest=source_digest,
        runtime_git_commit=git_commit,
        attestation_digest=attestation["artifact_digest"],
    )
    with repository.connection_factory() as connection, connection.cursor() as cursor:
        after_duplicate = cursor.execute(
            "SELECT count(*),min(receipt_artifact_digest),max(receipt_artifact_digest) "
            "FROM m4_isolated_v11.delivery_ledger "
            "WHERE mail_kind='DAILY_24H_RESEARCH_SUMMARY' "
            "AND target_identity='20260828' AND state='SENT'"
        ).fetchone()
    if (
        tuple(before_duplicate) != tuple(after_duplicate)
        or int(after_duplicate[0]) != 1
        or after_duplicate[1] != after_duplicate[2]
        or duplicate["execution_id"] != downstream[-1]["execution_id"]
    ):
        raise IsolatedRunnerError("daily_recovery_duplicate_delivery_changed")
    p3_after = _p3_source_identity()
    if p3_before != p3_after:
        raise IsolatedRunnerError("formal_p3_source_changed_during_daily_recovery")
    return {
        "schema_version": "dehps-m4-isolated-v11-daily-mail-recovery.v1",
        "status": "DAILY_MAIL_RECOVERED_SENT_AND_INCIDENT_RESOLVED",
        "apply": True,
        "quiescent_units": units,
        "registered_source_contract_digest": registered_source["artifact_digest"],
        "runtime_migration_attestation_digest": attestation["artifact_digest"],
        "recovery_start_state": start_state,
        "recovered_summary": recovered_summary,
        "source_rebind": rebind,
        "downstream": downstream,
        "incident_resolution": resolution,
        "terminal_incident_open_count": state["open_count"],
        "daily_sent_receipt_digest": after_duplicate[1],
        "duplicate_cycle_smtp_calls": 0,
        "smtp_calls": 1,
        "activation_ready": True,
        "systemd_activation_performed": False,
        "scientific_workloads": 0,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def _attest_database_schema(
    *, repository: IsolatedChallengerRepository, git_commit: str
) -> dict[str, str]:
    if _GIT_COMMIT.fullmatch(git_commit) is None:
        raise IsolatedRunnerError("database_schema_git_commit_invalid")
    expected = (
        contract.DATABASE_SCHEMA_VERSION,
        contract.CONTRACT_DIGEST,
        git_commit,
    )
    with (
        repository.connection_factory() as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO m4_isolated_v11.schema_identity ("
            "singleton,schema_version,contract_digest,installed_git_commit) "
            "VALUES (TRUE,%s,%s,%s) ON CONFLICT (singleton) DO NOTHING",
            expected,
        )
        row = cursor.execute(
            "SELECT schema_version,contract_digest,installed_git_commit FROM "
            "m4_isolated_v11.schema_identity WHERE singleton=TRUE"
        ).fetchone()
    if row is None:
        raise IsolatedRunnerError("database_schema_identity_changed")
    actual = tuple(str(item) for item in row)
    if actual[:2] != expected[:2] or _GIT_COMMIT.fullmatch(actual[2]) is None:
        raise IsolatedRunnerError("database_schema_identity_changed")
    if actual[2] != git_commit:
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", actual[2], git_commit],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
        )
        if ancestry.returncode != 0:
            raise IsolatedRunnerError("database_schema_install_commit_not_ancestor")
    return {
        "schema_version": actual[0],
        "contract_digest": actual[1],
        "installed_git_commit": actual[2],
    }


def cycle(
    *,
    apply: bool,
    context: Mapping[str, str],
    source_digest: str,
) -> dict[str, Any]:
    repository = IsolatedChallengerRepository(
        context=context, source_digest=source_digest
    )
    if not apply:
        status = mainline.compact_status(repository=repository)
        return {**status, "dispatch_performed": False}
    p3_before = _p3_source_identity()
    recovered = _recover_completed_activations(
        repository=repository,
        source_digest=source_digest,
    )
    _roll_forward(
        repository=repository,
        context=context,
        source_digest=source_digest,
    )
    dispatched: list[dict[str, Any]] = list(recovered)
    search_dispatched = False
    resource_state = "PREEMPT"
    observation: dict[str, Any] = {}
    thermal_blocked = True
    thermal_state: dict[str, Any] = {}
    try:
        thermal_guard = mainline.ThermalGuard(root_dir=ROOT_DIR)
        thermal_state = thermal_guard.sample(force=True)
        thermal_blocked = thermal_guard.paused
    except mainline.IsolatedMainlineError:
        thermal_state = mainline.thermal_observation()
    for _ in range(64):
        manifest = repository.load_manifest(
            control_plane_key=contract.CONTROL_PLANE_KEY
        )
        snapshot = repository.control_plane.resolve(manifest)
        task_by_key = {item.task_key: item for item in manifest.tasks}
        candidates: list[tuple[bool, int, str, Any, dict[str, str], Any]] = []
        observation = _resource_observation()
        resource_state = contract.formal_p3_activity_state(observation)
        ready_keys = [item.task_key for item in snapshot.ready_queue]
        running_keys = [
            task.task_key
            for task in manifest.tasks
            if manifest.task_state_by_digest[task.artifact_digest].declared_status
            == TaskStatus.RUNNING
        ]
        if len(running_keys) > 1:
            raise IsolatedRunnerError("multiple_running_isolated_tasks")
        dispatch_keys = running_keys or ready_keys
        for dispatch_key in dispatch_keys:
            task = task_by_key[dispatch_key]
            dispatch_context = _task_context(task)
            template = mainline.template_for_task_key(
                task.task_key, context=dispatch_context
            )
            if template.name == "search_batch" and (
                search_dispatched or resource_state != "QUIESCENT" or thermal_blocked
            ):
                continue
            candidates.append(
                (
                    template.name == "search_batch",
                    -int(task.priority),
                    task.task_key,
                    task,
                    dispatch_context,
                    template,
                )
            )
        if not candidates:
            if (
                contract.MAIL_CONFIGURATION_FACT in manifest.facts.artifacts
                and "RESOURCE_QUIESCENT_60S" not in manifest.facts.external_events
                and resource_state == "QUIESCENT"
            ):
                try:
                    observation = _continuous_quiescence()
                except IsolatedRunnerError:
                    break
                live = repository.export_manifest(
                    control_plane_key=contract.CONTROL_PLANE_KEY
                )
                event_payload = builder.extend_manifest(
                    live,
                    context=context,
                    source_digest=source_digest,
                    template_names=builder.HEALTH_TEMPLATE_NAMES,
                    add_external_events=("RESOURCE_QUIESCENT_60S",),
                )
                repository.import_extension(event_payload)
                continue
            break
        _, _, task_key, task, dispatch_context, template = min(candidates)
        facts = set(manifest.facts.artifacts)
        if (
            template.name in {"genesis", "search_batch"}
            and contract.MAIL_CONFIGURATION_FACT not in facts
        ):
            raise IsolatedRunnerError(
                "search_lease_without_verified_mail_configuration"
            )
        if template.name == "search_batch":
            try:
                observation = _continuous_quiescence()
            except IsolatedRunnerError:
                break
            resource_state = contract.formal_p3_activity_state(observation)
            if resource_state != "QUIESCENT":
                break
            search_dispatched = True
            if "RESOURCE_QUIESCENT_60S" not in manifest.facts.external_events:
                live = repository.export_manifest(
                    control_plane_key=contract.CONTROL_PLANE_KEY
                )
                event_payload = builder.extend_manifest(
                    live,
                    context=dispatch_context,
                    source_digest=source_digest,
                    template_names=builder.HEALTH_TEMPLATE_NAMES,
                    add_external_events=("RESOURCE_QUIESCENT_60S",),
                )
                repository.import_extension(event_payload)
        supervisor = mainline.IsolatedChallengerSupervisor(
            repository=repository,
            context=dispatch_context,
            source_digest=source_digest,
            simulation=False,
        )
        result = supervisor.run_once(task_key=task_key)
        if result.get("task_key") != task_key or result.get("status") != "COMPLETE":
            return {
                **result,
                "dispatches": dispatched,
                "formal_p3_mutated": False,
            }
        generic = supervisor.replay(
            task_key=task_key, execution_id=str(result["execution_id"])
        )
        _verify_generic_replay(generic)
        activated = _activation_facts(
            task_key=task_key,
            template=template,
            context=dispatch_context,
            repository=repository,
        )
        if activated:
            repository.import_verified_facts(activated)
        dispatched.append(
            {
                "task_key": task_key,
                "execution_id": result["execution_id"],
                "activated_facts": list(activated),
            }
        )
    if _p3_source_identity() != p3_before:
        raise IsolatedRunnerError("formal_p3_source_changed_during_cycle")
    if not dispatched:
        status = mainline.compact_status(repository=repository)
        return {
            **status,
            "status": (
                "PREEMPTED_FOR_FORMAL_P3"
                if resource_state != "QUIESCENT"
                else (
                    "THERMAL_GUARD_PAUSED" if thermal_blocked else status.get("status")
                )
            ),
            "resource_state": resource_state,
            "observation": observation,
            "thermal_observation": thermal_state,
            "dispatch_performed": False,
            "new_leases": 0,
            "formal_p3_mutated": False,
        }
    last = dispatched[-1]
    return {
        "status": "COMPLETE_AND_REPLAY_VERIFIED",
        "task_key": last["task_key"],
        "execution_id": last["execution_id"],
        "activated_facts": last["activated_facts"],
        "dispatches": dispatched,
        "dispatch_count": len(dispatched),
        "resource_state": resource_state,
        "dispatch_performed": True,
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def simulation(
    *, context: Mapping[str, str], source_digest: str, git_commit: str
) -> dict[str, Any]:
    p3_before = _p3_source_identity()
    payload, dry_run = builder.build_manifest(
        context=context,
        source_digest=source_digest,
        operator_configuration_authorized=True,
        simulation_events=True,
    )
    manifest = ControlPlaneManifest.from_dict(payload)
    if len(manifest.tasks) != 43:
        raise IsolatedRunnerError("simulation_manifest_task_count_changed")
    chain = mainline.simulate_artifact_chain(
        context=context,
        git_commit=git_commit,
        source_digest=source_digest,
    )
    snapshot_digest = hashlib.sha256(b"isolated-v11-synthetic-snapshot").hexdigest()
    configurations = search.base_configurations(
        snapshot_digest=snapshot_digest, source_contract_digest=source_digest
    )
    jobs = search.plan_batch(configurations, cursor=0)
    single = search.execute_jobs(jobs, worker_count=1)
    parallel = search.execute_jobs(jobs, worker_count=contract.WORKER_COUNT)
    single_equivalence = _parallel_equivalence_bundle(
        single,
        target_issue=context["target_issue"],
    )
    parallel_equivalence = _parallel_equivalence_bundle(
        parallel,
        target_issue=context["target_issue"],
    )
    if (
        search.result_bytes(single) != search.result_bytes(parallel)
        or single_equivalence != parallel_equivalence
    ):
        raise IsolatedRunnerError("PARALLEL_EQUIVALENCE_FAILED")
    registry = search.AtomicCandidateRegistry()
    state = registry.register_batch(jobs)
    if state.m_total != 18:
        raise IsolatedRunnerError("simulation_multiplicity_changed")
    probabilities = tuple(0.12 + index / 1000 for index in range(33))
    red_top100 = search.top_red_combinations(
        lambda candidate: search.probability_combination_score(candidate, probabilities)
    )
    prediction_seed = hashlib.sha256(
        f"prediction:{context['target_issue']}".encode()
    ).hexdigest()[:32]
    tickets = search.add_deterministic_blue(red_top100, seed_hex=prediction_seed)
    baseline = search.baseline_set(context["target_issue"])
    synthetic_result = tickets[0]
    settlement = reporting.settle_portfolio(
        tickets,
        winning_reds=synthetic_result[0],
        winning_blue=synthetic_result[1],
        first_prize_cny="5000000.00",
        second_prize_cny="100000.00",
    )
    baseline_gross = [
        reporting.settle_portfolio(
            item,
            winning_reds=synthetic_result[0],
            winning_blue=synthetic_result[1],
            first_prize_cny="5000000.00",
            second_prize_cny="100000.00",
        )["gross_prize_cny"]
        for item in baseline
    ]
    percentile = reporting.percentile_position(
        settlement["gross_prize_cny"], baseline_gross
    )
    p3_after = _p3_source_identity()
    if p3_before != p3_after:
        raise IsolatedRunnerError("formal_p3_bytes_changed_during_simulation")
    return {
        "schema_version": "dehps-m4-isolated-v11-result-blind-simulation.v1",
        "status": "SIMULATION_COMPLETE",
        "manifest_dry_run": dry_run,
        "chain": chain,
        "parallel_equivalence": "BYTE_IDENTICAL",
        "parallel_equivalence_bundle_sha256": hashlib.sha256(
            single_equivalence
        ).hexdigest(),
        "single_worker_sha256": hashlib.sha256(search.result_bytes(single)).hexdigest(),
        "worker18_sha256": hashlib.sha256(search.result_bytes(parallel)).hexdigest(),
        "multiplicity_m_total": state.m_total,
        "top100_count": len(tickets),
        "baseline_replicates": len(baseline),
        "hypothetical_cost_cny": settlement["cost_cny"],
        "gross_prize_cny": settlement["gross_prize_cny"],
        "estimated_tax_cny": settlement["estimated_tax_cny"],
        "estimated_after_tax_cny": settlement["estimated_after_tax_cny"],
        "net_cny": settlement["net_cny"],
        "roi": settlement["roi"],
        "baseline_percentile": percentile,
        "mail_transport": "FAKE_EPHEMERAL",
        "external_sent_count": 0,
        "smtp_calls": 0,
        "formal_p3_source_digest": p3_after["artifact_digest"],
        "formal_p3_mutated": False,
        "p4_p5_p6_or_promotion_triggered": False,
    }


def _parallel_equivalence_bundle(
    results: Sequence[search.CandidateOutcome], *, target_issue: str
) -> bytes:
    """Bind every frozen downstream identity to the ordered worker output."""

    if len(results) != contract.ATTEMPTS_PER_BATCH:
        raise IsolatedRunnerError("equivalence_candidate_count_changed")
    candidate_result_bytes = search.result_bytes(results)
    candidate_result_digest = hashlib.sha256(candidate_result_bytes).hexdigest()
    ordered = sorted(
        results,
        key=lambda item: (
            item.status != "SUCCEEDED",
            -item.primary_mean,
            item.configuration_id,
            item.seed_ordinal,
            item.candidate_id,
        ),
    )
    selected = ordered[0]
    probability_seed = hashlib.sha256(
        f"{target_issue}\0{selected.candidate_id}".encode("ascii")
    ).digest()
    probabilities = tuple(
        0.10 + probability_seed[index % len(probability_seed)] / 2000.0
        for index in range(33)
    )
    red_top100 = search.top_red_combinations(
        lambda candidate: search.probability_combination_score(candidate, probabilities)
    )
    tickets = search.add_deterministic_blue(
        red_top100,
        seed_hex=hashlib.sha256(
            f"equivalence-blue\0{target_issue}\0{selected.candidate_id}".encode("ascii")
        ).hexdigest()[:32],
    )
    ordering = [item.candidate_id for item in ordered]
    top100_digest = contract.domain_digest(
        [[[int(value) for value in reds], blue] for reds, blue in tickets],
        domain="dehps.m4.isolated-24h-challenger.equivalence-top100.v11",
    )
    checkpoint = {
        "candidate_result_digest": candidate_result_digest,
        "candidate_order": ordering,
        "selected_candidate_id": selected.candidate_id,
        "top100_digest": top100_digest,
    }
    checkpoint_digest = contract.domain_digest(
        checkpoint,
        domain="dehps.m4.isolated-24h-challenger.equivalence-checkpoint.v11",
    )
    artifact_digest = contract.domain_digest(
        {
            "target_issue": target_issue,
            "checkpoint_digest": checkpoint_digest,
            "top100_digest": top100_digest,
        },
        domain="dehps.m4.isolated-24h-challenger.equivalence-artifact.v11",
    )
    replay_digest = contract.domain_digest(
        {
            "artifact_digest": artifact_digest,
            "checkpoint_digest": checkpoint_digest,
            "status": "REPLAY_VERIFIED",
        },
        domain="dehps.m4.isolated-24h-challenger.equivalence-replay.v11",
    )
    return contract.canonical_json(
        {
            "candidate_results": json.loads(candidate_result_bytes),
            "candidate_order": ordering,
            "selected_candidate_id": selected.candidate_id,
            "top100": [{"red": list(reds), "blue": blue} for reds, blue in tickets],
            "checkpoint_digest": checkpoint_digest,
            "artifact_digest": artifact_digest,
            "replay_digest": replay_digest,
        }
    ).encode("ascii")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "status",
            "simulate",
            "install",
            "cycle",
            "resume-p3-user-scope-running-batch",
            "recover-daily-mail",
        ),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-max-issue")
    parser.add_argument("--source-max-draw-date")
    parser.add_argument("--target-issue")
    parser.add_argument("--target-draw-date")
    parser.add_argument("--batch-seq", type=int, default=0)
    parser.add_argument("--epoch-date")
    parser.add_argument("--minute")
    parser.add_argument("--incident-id")
    parser.add_argument("--incident-reason-code", default="DEADLINE_OR_ABSENCE")
    parser.add_argument("--incident-offending-digest")
    parser.add_argument("--projection-time")
    parser.add_argument("--operator-configuration-authorized", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if bool(args.source_max_issue) != bool(args.source_max_draw_date):
        raise IsolatedRunnerError("source_history_identity_incomplete")
    if args.command == "simulate" and args.source_max_issue:
        source_max_issue = args.source_max_issue
        source_max_draw_date = args.source_max_draw_date
    else:
        live_source_issue, live_source_draw_date = _latest_history_identity()
        source_max_issue = args.source_max_issue or live_source_issue
        source_max_draw_date = args.source_max_draw_date or live_source_draw_date
        if (
            source_max_issue != live_source_issue
            or source_max_draw_date != live_source_draw_date
        ):
            raise IsolatedRunnerError("rendered_source_history_identity_changed")
    context = contract.render_context(
        source_max_issue=source_max_issue,
        source_max_draw_date=source_max_draw_date,
        target_issue=args.target_issue,
        target_draw_date=args.target_draw_date,
        batch_seq=args.batch_seq,
        epoch_date=args.epoch_date,
        minute=args.minute,
        incident_id=args.incident_id,
        incident_reason_code=args.incident_reason_code,
        incident_offending_digest=args.incident_offending_digest,
        projection_time=(
            args.projection_time
            or (
                datetime.now(contract.TIMEZONE).isoformat()
                if args.command in {"status", "install", "cycle", "recover-daily-mail"}
                else None
            )
        ),
    )
    source = artifacts.load_source_contract(root_dir=ROOT_DIR)
    _validate_mirror_completeness_repair_source_binding(source)
    _validate_daily_recovery_transition_fix_source_binding(source)
    _validate_health_provenance_running_recovery_source_binding(source)
    _validate_compatibility_binding_scope_fix_source_binding(source)
    _validate_committed_state_recovery_closure_source_binding(source)
    source_digest = str(source["artifact_digest"])
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, text=True
    ).strip()
    if args.command == "simulate":
        result = simulation(
            context=context, source_digest=source_digest, git_commit=git_commit
        )
    elif args.command == "resume-p3-user-scope-running-batch":
        result = resume_p3_user_scope_running_batch(
            apply=args.apply,
            context=context,
            repaired_source_digest=source_digest,
            repaired_git_commit=git_commit,
        )
    elif args.command == "install":
        result = install(
            apply=args.apply,
            context=context,
            source_digest=source_digest,
            operator_configuration_authorized=(args.operator_configuration_authorized),
            git_commit=git_commit,
        )
    elif args.command == "recover-daily-mail":
        result = recover_daily_mail_chain(
            apply=args.apply,
            context=context,
            source_contract=source,
            source_digest=source_digest,
            git_commit=git_commit,
        )
    else:
        repository = IsolatedChallengerRepository(
            context=context, source_digest=source_digest
        )
        if args.command == "status":
            result = mainline.compact_status(repository=repository)
        else:
            result = cycle(
                apply=args.apply, context=context, source_digest=source_digest
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
