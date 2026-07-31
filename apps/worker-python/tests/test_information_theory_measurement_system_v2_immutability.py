from __future__ import annotations

import copy
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from dehps.research_os.information_theory.measurement_system_v2 import (
    build_design_artifacts,
    load_measurement_contract_v2,
    validate_measurement_contract_v2,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    ROOT / "configs/research-os/m4-measurement-contract-v2.json"
)


def test_validated_contract_is_deeply_immutable_and_detached() -> None:
    source = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract = validate_measurement_contract_v2(source)

    with pytest.raises(TypeError):
        contract.payload["status"] = "MUTATED"
    with pytest.raises(TypeError):
        contract.branches[1]["baseline"]["fallback"] = "MUTATED"
    with pytest.raises(AttributeError):
        contract.payload["estimand_contract"]["branches"].append({})
    with pytest.raises(TypeError):
        contract.mechanism_rows[0]["roles"]["MARGINAL_STATIC"][
            "role"
        ] = "MUTATED"
    with pytest.raises(TypeError):
        contract.payload._values = MappingProxyType({"status": "MUTATED"})

    source["status"] = "MUTATED"
    source["estimand_contract"]["branches"][1]["baseline"][
        "fallback"
    ] = "MUTATED"
    assert contract.payload["status"] == "FROZEN_SOURCE_INTEGRATION_PENDING"
    assert contract.branches[1]["baseline"]["fallback"] == "FORBIDDEN"


def test_frozen_contract_can_be_copied_and_build_json_artifacts() -> None:
    contract = load_measurement_contract_v2(CONTRACT_PATH)
    candidate = copy.deepcopy(dict(contract.payload))
    candidate["gate_compiler_contract"][
        "practical_threshold_bits_per_issue"
    ] = 0.02
    assert (
        contract.payload["gate_compiler_contract"][
            "practical_threshold_bits_per_issue"
        ]
        == 0.01
    )

    run = build_design_artifacts(
        contract,
        execution_id="1" * 64,
        git_commit="2" * 40,
    )
    serialized = json.dumps(run.artifacts, sort_keys=True)
    assert serialized
    assert all(
        json.loads(json.dumps(artifact)) == artifact
        for artifact in run.artifacts
    )
