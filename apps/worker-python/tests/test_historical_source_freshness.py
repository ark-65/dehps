"""A slow report export must not spend the next worker's source-check lifetime."""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import copy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from dehps.execution.context import BoundaryError
from dehps.prediction.historical_learning import contract, operations, publisher
from test_historical_learning import fixture


def setup(tmp_path, monkeypatch):
    learning = tmp_path/'learning'; observer = tmp_path/'observer'
    c, history, key = fixture(learning); shutil.copytree(learning, observer)
    clock = [datetime.now(timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return clock[0].astimezone(tz)
    for module in (contract, operations, publisher): monkeypatch.setattr(module, 'datetime', Clock)
    monkeypatch.setattr(contract, 'formal_priority_active', lambda now=None: False)
    monkeypatch.setattr(operations, 'signing_key', lambda path: key)
    monkeypatch.setattr(operations, 'private_json', lambda path: {})
    monkeypatch.setattr(operations, 'DatabaseBinding', lambda **kw: SimpleNamespace(connect=lambda: nullcontext(None)))
    monkeypatch.setattr(operations, 'reader_engine', lambda config: object())
    calls = []
    rows = [copy.deepcopy(r['label']) for r in history]
    receipt = json.loads((learning/'receipts'/f"{history[0]['label']['audit_sha256']}.json").read_bytes())
    def audit(connection):
        calls.append(clock[0]); return rows, receipt
    monkeypatch.setattr(operations, 'audited_source', audit)
    config = {'schema': 'historical-publisher.v1', 'activated_at': clock[0].isoformat(),
        'approved_until': (clock[0]+timedelta(hours=1)).isoformat(), 'key_file':'fixture-only',
        'contract_sha256': contract.digest(c), 'learning_inputs':str(learning), 'observer_inputs':str(observer),
        'source_credentials':'fixture-only', 'source_root':str(tmp_path), 'producer_reader':{}}
    def slow(*args, **kwargs):
        clock[0] += timedelta(seconds=1301)
        assert contract.Inputs(learning, contract.digest(c)).gate() == 'WAITING_FOR_SOURCE_CHECK'
        return [900,901]
    monkeypatch.setattr(operations, 'publish_observations', slow)
    return config, clock, calls, rows, learning, observer, slow


def test_slow_export_reaudits_sources_and_keeps_existing_freshness_limit(tmp_path, monkeypatch):
    config,clock,calls,rows,learning,observer,_ = setup(tmp_path, monkeypatch)
    result = operations.publish(config)
    assert result['status']=='EXPORTED' and result['published_reports']==[900,901]
    assert len(calls)==2 and calls[1]-calls[0]==timedelta(seconds=1301)
    for root in (learning, observer):
        inputs=contract.Inputs(root,config['contract_sha256'])
        assert inputs.gate() is None
        assert inputs.signed('dispatch.json')['observed_at']==clock[0].isoformat()
    clock[0] += timedelta(seconds=1201)
    assert contract.Inputs(learning,config['contract_sha256']).gate()=='WAITING_FOR_SOURCE_CHECK'


@pytest.mark.parametrize('failure',['conflict','broken_input','expiry','formal'])
def test_final_check_does_not_refresh_stale_success_after_new_blocker(tmp_path, monkeypatch, failure):
    config,clock,calls,rows,learning,observer,slow = setup(tmp_path, monkeypatch)
    original = json.loads((learning/'dispatch.json').read_bytes())['body']['observed_at']
    def interrupted(*args, **kwargs):
        result=slow(*args,**kwargs)
        if failure=='conflict': rows[0]['blue'] = rows[0]['blue']%16+1
        elif failure=='broken_input': (learning/'history.json').write_bytes(b'corrupt')
        elif failure=='expiry': clock[0] += timedelta(hours=1)
        else: monkeypatch.setattr(contract.Inputs,'formal_guard',lambda self,**kw:'FORMAL_TASK_RUNNING')
        return result
    monkeypatch.setattr(operations,'publish_observations',interrupted)
    if failure in ('conflict','broken_input'):
        with pytest.raises(BoundaryError): operations.publish(config)
        assert json.loads((learning/'dispatch.json').read_bytes())['body']['reason']=='SOURCE_CONFLICT'
        assert list((learning/'errors').glob('*.json'))
    else:
        result=operations.publish(config)
        assert result['status']=='WAITING'
        assert result['reason']==('AUTHORIZATION_REQUIRED' if failure=='expiry' else 'FORMAL_TASK_RUNNING')
        # Only the initial successful audit signed readiness. No final success.
        body=json.loads((learning/'dispatch.json').read_bytes())['body']
        assert datetime.fromisoformat(body['observed_at'])==calls[0]
        assert len(calls)==1
