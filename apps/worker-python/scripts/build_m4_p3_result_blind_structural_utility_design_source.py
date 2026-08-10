from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.structural_utility.m4_p3_result_blind_design import (
    FROZEN_CONTRACT_DIGEST,
    expected_frozen_contract,
)

SOURCE_MODULE = Path(
    "apps/worker-python/dehps/research_os/structural_utility/"
    "m4_p3_result_blind_design.py"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the M4-P3 result-blind structural-utility design source contract."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = expected_frozen_contract()
    frozen_digest = canonical_digest(
        frozen,
        domain="dehps.m4-p3.result-blind-structural-utility-frozen-contract.v1",
    )
    if frozen_digest != FROZEN_CONTRACT_DIGEST:
        raise SystemExit("M4-P3 structural-utility frozen contract digest changed")
    source_entries = [
        {
            "path": SOURCE_MODULE.as_posix(),
            "content_sha256": hashlib.sha256(
                (ROOT_DIR / SOURCE_MODULE).read_bytes()
            ).hexdigest(),
        }
    ]
    payload = {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-design-source.v1"
        ),
        "artifact_type": "m4_p3_result_blind_structural_utility_design_source",
        "artifact_digest": "",
        "contract_key": "M4_P3_RESULT_BLIND_STRUCTURAL_UTILITY_DESIGN_SOURCE",
        "research_request_key": (
            "research-m4-p3-result-blind-structural-utility-design-round-111-20260810"
        ),
        "research_request_id": 443,
        "research_execution_id": 364,
        "engineering_request_key": (
            "engineering-m4-p3-result-blind-structural-utility-design-"
            "round-112-20260810"
        ),
        "engineering_request_id": 444,
        "engineering_execution_id": 365,
        "result_blind": True,
        "result_aware": False,
        "parent_payloads_read": 0,
        "portfolios_generated": 0,
        "folds_executed": 0,
        "metric_results_read": 0,
        "new_prediction_evidence_created": False,
        "new_model_created": False,
        "production_action": "none",
        "registered_children": 3,
        "frozen_contract_digest": frozen_digest,
        "frozen_contract": frozen,
        "source_entries": source_entries,
        "source_set_digest": canonical_digest(
            source_entries,
            domain=("dehps.m4-p3.result-blind-structural-utility-design-source-set.v1"),
        ),
    }
    payload["artifact_digest"] = config_digest(payload)
    atomic_write_text(
        args.output,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    print(json.dumps({"artifact_digest": payload["artifact_digest"]}, sort_keys=True))


if __name__ == "__main__":
    main()
