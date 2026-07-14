from dataclasses import replace

from dehps.engineering.validator import ImplementationValidator
from engineering_fixtures import planner


def test_validator_accepts_complete_contract() -> None:
    service = planner()
    contract = service.build_contract(service.load_plan(None))

    report = ImplementationValidator().validate(contract)

    assert report.valid is True
    assert not report.failure_reasons


def test_validator_rejects_forbidden_path_modification() -> None:
    service = planner()
    contract = service.build_contract(service.load_plan(None))
    invalid = replace(
        contract,
        files_to_add=("infra/postgres/init/999_bad.sql",),
    )

    report = ImplementationValidator().validate(invalid)

    assert report.valid is False
    assert any("forbidden paths" in reason for reason in report.failure_reasons)
