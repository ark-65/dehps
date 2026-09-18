"""Critical host authorization and timer-only mutation boundaries."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec=importlib.util.spec_from_file_location('timer_host',
    Path(__file__).resolve().parents[3]/'deploy/execution/historical-timer-defer-host.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)


@pytest.mark.parametrize('version',[256,255,249])
def test_unsupported_systemd_fails_closed(version):
    with pytest.raises(ValueError,match='systemd257'):
        host.supported(f'systemd {version}\nfeatures')


@pytest.mark.parametrize('mutation',[b'OnCalendar=*:0/5\n',b'Unit=unexpected.service\n',b'Persistent=false\n'])
def test_timer_change_rejects_unrelated_mutation(mutation):
    old=b'[Timer]\nPersistent=true\nOnCalendar=*:0/15\n'
    new=old.replace(b'Persistent=true\n',b'Persistent=true\nDeferReactivation=true\n')+mutation
    with pytest.raises(ValueError,match='Only DeferReactivation'):
        host.timer_change(old,new)


def test_chat_principal_is_not_host_review(monkeypatch):
    monkeypatch.setenv('SUDO_UID','1000');monkeypatch.setenv('SUDO_USER','ark')
    monkeypatch.setattr(host.sys,'stdin',SimpleNamespace(isatty=lambda:False))
    with pytest.raises(ValueError,match='Human local ark'):
        host.review(None,{},'a'*64)


@pytest.mark.parametrize('state',['approved','completed','failed','withdrawn'])
def test_old_or_unstarted_operator_is_rejected(state):
    support=SimpleNamespace(KEY='bound',THREAD='thread',
        bound_request=lambda _:SimpleNamespace(status=SimpleNamespace(value=state)),
        metadata_repository=lambda:SimpleNamespace(list_execution_metadata=lambda _:[]))
    with pytest.raises(ValueError,match='Actual separate Operator'):
        host.authorize(support,'a'*64,1)


def test_rollback_cannot_bypass_operator(monkeypatch):
    calls=[]
    def reject(*args):raise ValueError('revoked')
    monkeypatch.setattr(host,'authorize',reject)
    with pytest.raises(ValueError,match='revoked'):
        host.operate(SimpleNamespace(command=lambda *a:calls.append(a)),{},None,None,'rollback','a'*64,1)
    assert not calls
