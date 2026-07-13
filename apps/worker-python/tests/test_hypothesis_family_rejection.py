from __future__ import annotations

import pytest

from dehps.research.errors import RegistryConflictError
from dehps.research.service import ResearchHypothesisService
from dehps.research.status import RejectionScope


PROHIBITED = ["seed", "epochs", "depth", "nearby_weights", "same_history_search_rounds", "rename"]


def test_parameter_region_rejection_requires_parameter_boundary() -> None:
    with pytest.raises(RegistryConflictError, match="parameter_region"):
        ResearchHypothesisService._validate_rejection(
            rejection_scope=RejectionScope.PARAMETER_REGION,
            reason={
                "failed_metrics": {"objective": -1},
                "data_boundary": {"as_of": "2026079"},
                "prohibited_parameter_only_changes": PROHIBITED,
            },
            reopen_condition="new feature family",
        )


def test_mechanism_family_rejection_requires_mechanism_signature() -> None:
    with pytest.raises(RegistryConflictError, match="mechanism_signature"):
        ResearchHypothesisService._validate_rejection(
            rejection_scope=RejectionScope.MECHANISM_FAMILY,
            reason={
                "failed_metrics": {"objective": -1},
                "data_boundary": {"as_of": "2026079"},
                "prohibited_parameter_only_changes": PROHIBITED,
            },
            reopen_condition="new causal input",
        )


def test_rejection_forbids_all_superficial_retry_dimensions() -> None:
    with pytest.raises(RegistryConflictError, match="same_history_search_rounds"):
        ResearchHypothesisService._validate_rejection(
            rejection_scope=RejectionScope.MECHANISM_FAMILY,
            reason={
                "mechanism_signature": "inputs:x|target:y|protocol:z",
                "failed_metrics": {"objective": -1},
                "data_boundary": {"as_of": "2026079"},
                "prohibited_parameter_only_changes": ["seed", "epochs", "depth", "nearby_weights"],
            },
            reopen_condition="new causal input",
        )


def test_complete_rejection_contract_accepts_parameter_and_mechanism_scopes() -> None:
    common = {
        "failed_metrics": {"objective": -1},
        "data_boundary": {"as_of": "2026079"},
        "prohibited_parameter_only_changes": PROHIBITED,
    }
    ResearchHypothesisService._validate_rejection(
        rejection_scope=RejectionScope.PARAMETER_REGION,
        reason={**common, "parameter_region": {"depth": [1, 3]}},
        reopen_condition="new feature family",
    )
    ResearchHypothesisService._validate_rejection(
        rejection_scope=RejectionScope.MECHANISM_FAMILY,
        reason={**common, "mechanism_signature": "inputs:x|target:y|protocol:z"},
        reopen_condition="new causal input",
    )
