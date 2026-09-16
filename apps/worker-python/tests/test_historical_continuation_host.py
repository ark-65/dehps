"""Host handoff boundaries; no host services or identities are modified."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location('continuation_host',
    Path(__file__).resolve().parents[3]/'deploy/execution/historical-continuation-host.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


def require(value, message):
    if not value:
        raise ValueError(message)


def test_chat_identity_cannot_enter_actual_host_review(monkeypatch):
    monkeypatch.setenv('SUDO_UID','1000')
    monkeypatch.setenv('SUDO_USER','ark')
    monkeypatch.setattr(host.sys,'stdin',SimpleNamespace(isatty=lambda:False))
    with pytest.raises(ValueError,match='Human local ark sudo terminal'):
        host.review(SimpleNamespace(require=require),{},None,None,'a'*64)


def test_missing_actual_operator_cannot_start_installation():
    request=SimpleNamespace(status=SimpleNamespace(value='approved'))
    support=SimpleNamespace(KEY='exact-request',require=require,bound_request=lambda _:request,
        metadata_repository=lambda:SimpleNamespace(list_execution_metadata=lambda _:[]))
    with pytest.raises(ValueError,match='Actual Operator admission absent'):
        host.install(support,{},None,'a'*64,1)


@pytest.mark.parametrize('domain',['learning','observer'])
@pytest.mark.parametrize('prior',[True,False])
def test_replays_use_actual_service_uid_scoped_credentials_and_readonly_action(domain,prior):
    package={'prior_workers':{domain:{'release_sha256':'a'*64}},
             'workers':{domain:{'release_sha256':'b'*64}}}
    command=host.replay_command(package,domain,prior=prior)
    assert command[:4]==['runuser','-u','dehps-'+domain,'--']
    assert command[-2:]==['--action','replay-prefix']
    assert command[command.index('--credentials')+1]==str((host.OLD_CONFIG if prior else host.CONFIG)/domain/'operator.json')
    assert command[command.index('--release-sha256')+1]==('a' if prior else 'b')*64
    assert command[command.index('--network')+1]=='none'
    assert '/run/dehps/historical/'+domain+'.lock' in command
