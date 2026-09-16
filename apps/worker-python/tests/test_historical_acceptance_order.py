"""Reproduce slow publication / STARTING projection ordering without host writes."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location('acceptance', Path(__file__).resolve().parents[3]/'deploy/execution/historical-continuation-acceptance.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def fixture(tmp_path):
    package = {'workers': {d: {'release_sha256': d} for d in ('learning', 'observer')},
        'plans': {d: d for d in ('learning', 'observer')}, 'first_new_issues': ['2013056', '2013057']}
    states = {d: {'phase': 'waiting', 'run_id': d, 'release_sha256': d, 'plan_digest': d,
        'capability_progress': {'continuation': {'new_committed_count': 12}}} for d in ('learning', 'observer')}
    events = []; activity = {}
    def command(*args):
        events.append(args)
        if args[0] == 'runuser': return 'HISTORICAL_RECONSTRUCTION verified report'
        if args[:2] == ('systemctl', 'show'): return activity.get(args[2], 'inactive')
        return ''
    def restart(domain):
        events.append(('restart', domain)); states[domain] = {'phase': 'starting'}
    s = SimpleNamespace(command=command, canonical=lambda v: json.dumps(v).encode(),
        save=lambda p,v,mode:p.write_text(json.dumps(v)))
    installer = SimpleNamespace(progress=lambda d: copy.deepcopy(states[d]), start_worker=restart,
        exact_file=lambda p,b,mode:p.write_bytes(b))
    return s, package, installer, states, events, activity


def test_completed_observer_is_witnessed_before_restart_erases_counts(tmp_path):
    s,p,i,states,events,_ = fixture(tmp_path)
    witnessed,_,_,done = a.cycle(s,p,i,tmp_path,False,a.time.monotonic())
    assert witnessed and not done
    assert json.loads((tmp_path/'two-new-issue-witness.json').read_text())['counts']['observer'] == 12
    enabled = [n for n,e in enumerate(events) if e[:3] == ('systemctl','enable','--now')]
    assert len(enabled) == 3 and max(enabled) < events.index(('restart','observer'))
    assert states['observer'] == {'phase':'starting'}
    assert json.loads((tmp_path/'progress.json').read_text())['first_two_witnessed']


def test_publication_never_blocks_progress_or_queues_observer(tmp_path):
    s,p,i,states,events,_ = fixture(tmp_path)
    states['observer'] = {'phase': 'starting'}
    a.cycle(s,p,i,tmp_path,False,-10000)
    assert ('systemctl','start','--no-block',a.UNITS[0]+'.service') in events
    assert not any(e[:2] == ('restart','observer') for e in events)
    assert (tmp_path/'progress.json').exists()


@pytest.mark.parametrize('status',['active','activating','deactivating'])
def test_observer_and_publisher_activation_are_not_requeued(tmp_path,status):
    s,p,i,states,events,activity = fixture(tmp_path)
    activity[a.UNITS[2]+'.service'] = status
    a.cycle(s,p,i,tmp_path,True,-10000)
    assert not any(e[:2] == ('systemctl','start') or e == ('restart','observer') for e in events)


@pytest.mark.parametrize('failure',['identity','task','budget','publisher'])
def test_failures_stop_acceptance_without_starting_jobs(tmp_path,failure):
    s,p,i,states,events,activity = fixture(tmp_path)
    if failure == 'identity': states['observer']['release_sha256'] = 'wrong'
    elif failure == 'task': states['observer']['task_errors'] = {'task':'failure'}
    elif failure == 'budget': states['learning']['wait_reasons'] = {'task':'HISTORICAL_BATCH_BUDGET_EXHAUSTED'}
    else: activity[a.UNITS[0]+'.service'] = 'failed'
    with pytest.raises(ValueError): a.cycle(s,p,i,tmp_path,True,-10000)
    assert not any(e[0] == 'restart' or e[:2] == ('systemctl','start') for e in events)


def test_full_batch_uses_completed_state_before_replay_and_no_restart(tmp_path):
    s,p,i,states,events,_ = fixture(tmp_path)
    for v in states.values(): v['capability_progress']['batch_summary_registered'] = True
    _,_,_,done = a.cycle(s,p,i,tmp_path,True,-10000)
    assert done and not events
