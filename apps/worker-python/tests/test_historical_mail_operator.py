from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import pytest
from dehps.agents.repository import AgentRequestExecutionMetadata
from dehps.agents.requests import AgentExecutionStatus
from dehps.agents.roles import AgentRole

path=Path(__file__).resolve().parents[3]/'deploy/execution/historical-mail-operator.py'
spec=importlib.util.spec_from_file_location('mail_operator',path)
operator=importlib.util.module_from_spec(spec);spec.loader.exec_module(operator)


def metadata():
    now=datetime.now(timezone.utc)
    return AgentRequestExecutionMetadata(id=680,request_id=843,executor_role=AgentRole.OPERATOR,
        executor_id='fixture-owner',execution_type='publish_release',status=AgentExecutionStatus.RUNNING,
        environment='production',run_id='fixture-run',started_at=now,completed_at=None,created_at=now)


def test_actual_repository_dataclass_is_read_without_json_assumption():
    operator.require_active_execution([metadata()],680,'fixture-owner',843)


@pytest.mark.parametrize('change',[{'id':681},{'request_id':844},{'executor_role':AgentRole.ENGINEERING},
    {'executor_id':'another-owner'},{'status':AgentExecutionStatus.COMPLETED},{'status':AgentExecutionStatus.FAILED},
    {'environment':'development'}])
def test_readback_keeps_exact_identity_and_active_role_boundary(change):
    with pytest.raises(ValueError,match='actual Operator execution differs'):
        operator.require_active_execution([replace(metadata(),**change)],680,'fixture-owner',843)
