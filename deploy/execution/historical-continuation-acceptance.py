"""Resume acceptance of installed831 only; never install or re-admit a plan.

Runs under a separate exact authenticated Operator request. Frozen831 remains
the source of worker/replay commands. Read committed state before scheduling;
publication is nonblocking and shares the existing observer lock.
"""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

STAGE = Path('/opt/dehps/releases/historical-acceptance-833')
OLD = Path('/opt/dehps/releases/historical-continuation-831')
OLD_SHA = '466634f8a7aa684f440780e31431f1bed835194495cb048bf817362e33b20512'
KEY = 'operator-historical-acceptance-resume-20260916-v1'
DEADLINE = datetime.fromisoformat('2026-09-17T10:36:56+00:00')
UNITS = ('dehps-historical-publisher', 'dehps-historical-worker@learning',
         'dehps-historical-worker@observer')


def require(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc)


def load(path):
    spec = importlib.util.spec_from_file_location('frozen_continuation_host', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup(expected):
    require(os.geteuid() == 0, 'Actual administrator required')
    require(Path(__file__) == STAGE/'acceptance.py', 'Exact staged entry required')
    raw = (OLD/'activation-packet.json').read_bytes()
    require(sha256(raw).hexdigest() == OLD_SHA, 'Original packet differs')
    old = json.loads(raw)
    path = OLD/'continuation-host.py'
    require(sha256(path.read_bytes()).hexdigest() == old['files']['continuation-host.py']['sha256'], 'Frozen host differs')
    host = load(path)
    s, package, installer, _ = host.bootstrap(OLD_SHA)
    for p in (STAGE/'packet.json', Path(__file__)):
        s.protected(p)
    require(s.sha(STAGE/'packet.json') == expected, 'Acceptance packet differs')
    binding = json.loads((STAGE/'packet.json').read_bytes())
    require(binding['source_sha256'] == s.sha(Path(__file__)) and
            binding['old_packet_sha256'] == OLD_SHA and
            binding['deadline'] == DEADLINE.isoformat(), 'Exact acceptance binding differs')
    for name, digest in binding['installed_files'].items():
        p = Path(name); s.protected(p)
        require(s.sha(p) == digest, 'Installed runtime identity differs: '+name)
    expected_units = set(UNITS) | {'dehps-control-status@learning', 'dehps-control-status@observer'}
    require(set(binding['unit_sha256']) == expected_units, 'Closed installed unit set required')
    for unit, digest in binding['unit_sha256'].items():
        content = s.command('systemctl', 'cat', unit+'.service').encode()
        require(sha256(content).hexdigest() == digest, 'Installed unit changed: '+unit)
    identity = json.loads((OLD/'evidence/runtime-identities.json').read_bytes())
    require(identity['outer_request'] == 832 and identity['outer_execution'] == 670 and
            identity['workers'] == package['workers'] and
            identity['scoped_executions'] == {'learning': 3, 'observer': 3} and
            identity['original_approved_until'] == package['approved_until'], 'Installed execution differs')
    require(not installer.active('dehps-historical-continuation-670.service'), 'Previous acceptance still active')
    for domain in ('learning', 'observer'):
        host.check_replay_identity(s, domain)
        require(json.loads(s.command('docker', 'image', 'inspect', package['workers'][domain]['image_id']))[0]['Id'] == package['workers'][domain]['image_id'], 'Installed image absent')
    return s, package, installer, host


def authorize(s, expected, execution):
    repository = s.metadata_repository()
    request = repository.get_request(KEY)
    require(request.request_type.value == 'operator_release' and request.status.value == 'executing'
            and request.requested_by == s.THREAD
            and request.payload['scope']['acceptance_packet_sha256'] == expected,
            'Exact active Operator request required')
    records = [x for x in repository.list_execution_metadata(KEY) if x.id == execution]
    require(len(records) == 1 and records[0].status.value == 'running' and
            records[0].executor_role.value == 'operator' and records[0].executor_id == s.THREAD,
            'Actual Operator execution required')


def validate(state, package):
    for domain, p in state.items():
        require(p.get('phase') != 'failed' and not p.get('task_errors'), 'Runtime error: '+domain)
        if p.get('capability_progress'):
            require(p.get('release_sha256') == package['workers'][domain]['release_sha256'] and
                    p.get('plan_digest') == package['plans'][domain], 'Runtime identity drift')
        require('HISTORICAL_BATCH_BUDGET_EXHAUSTED' not in p.get('wait_reasons', {}).values(),
                'Original finite batch budget exhausted')


def progressed(state):
    return all(p.get('capability_progress', {}).get('continuation', {}).get('new_committed_count', 0) >= 2
               for p in state.values())


def complete(state):
    return all(p.get('capability_progress', {}).get('batch_summary_registered') for p in state.values())


def busy(s, unit):
    state = s.command('systemctl', 'show', unit+'.service', '-p', 'ActiveState', '--value')
    require(state != 'failed', 'Historical service failed: '+unit)
    return state in {
        'active', 'activating', 'deactivating', 'reloading'}


def cycle(s, package, installer, evidence, witnessed, last_publish):
    """Consume completed state before any command can replace it with STARTING."""
    state = {d: installer.progress(d) for d in ('learning', 'observer')}
    validate(state, package)
    if not witnessed and progressed(state):
        for issue in package['first_new_issues']:
            path = Path('/opt/dehps/inputs/historical-continuation-831-observer/reports')/(issue+'.md')
            report = s.command('runuser', '-u', 'dehps-observer', '--', 'cat', str(path))
            require('HISTORICAL_RECONSTRUCTION' in report, 'Independent report unreadable/mislabeled')
            installer.exact_file(evidence/(issue+'.md'), (report+'\n').encode(), 0o644)
        s.save(evidence/'two-new-issue-witness.json', {'issues': package['first_new_issues'],
            'runs': {d: p['run_id'] for d, p in state.items()},
            'counts': {d: p['capability_progress']['continuation']['new_committed_count'] for d, p in state.items()},
            'registered_independent_observations': True, 'external_delivery': False}, 0o644)
        for unit in UNITS:
            s.command('systemctl', 'enable', '--now', unit+'.timer')
        witnessed = True
    done = complete(state)
    status = {'at': now().isoformat(), 'first_two_witnessed': witnessed, **state}
    target = evidence/'progress.json'; temporary = target.with_suffix('.new')
    temporary.write_bytes(s.canonical(status)); temporary.chmod(0o644); temporary.replace(target)
    if done:
        require(witnessed, 'Full batch lacks independent two-issue witness')
        return witnessed, last_publish, state, True
    # A blocking publisher used to hide many minutes of committed progress.
    # The existing service lock serializes publisher and observer; avoid queuing
    # either while the other is still activating, including its final readback.
    publishing = busy(s, UNITS[0]); observing = busy(s, UNITS[2])
    if time.monotonic()-last_publish >= (900 if witnessed else 30) and not publishing and not observing:
        s.command('systemctl', 'start', '--no-block', UNITS[0]+'.service')
        last_publish = time.monotonic()
    elif not publishing and not observing:
        installer.start_worker('observer')
    installer.start_worker('learning')
    return witnessed, last_publish, state, False


def run(expected, execution):
    s, package, installer, host = setup(expected)
    authorize(s, expected, execution)
    evidence = STAGE/'evidence'; evidence.mkdir(mode=0o755, exist_ok=True)
    if not (evidence/'before.json').exists():
        s.save(evidence/'before.json', host.snapshot(s), 0o644)
    witness = evidence/'two-new-issue-witness.json'
    # A restart never resets budgets or treats a previous projection as proof.
    witnessed = witness.exists()
    if witnessed:
        proof = json.loads(witness.read_bytes())
        require(proof['issues'] == package['first_new_issues'] and proof['registered_independent_observations'], 'Prior witness differs')
        require(now() < min(DEADLINE, datetime.fromisoformat(package['approved_until'])), 'Original deadline expired')
        for unit in UNITS:
            s.command('systemctl', 'enable', '--now', unit+'.timer')
    last_publish = time.monotonic()
    while now() < min(DEADLINE, datetime.fromisoformat(package['approved_until'])):
        authorize(s, expected, execution)
        witnessed, last_publish, state, done = cycle(s, package, installer, evidence, witnessed, last_publish)
        if done:
            s.save(evidence/'batch-complete-awaiting-replay.json', state, 0o644)
            break
        time.sleep(30)
    else:
        raise RuntimeError('Original bounded acceptance window ended; no deadline extension')
    for domain in ('learning', 'observer'):
        authorize(s, expected, execution)
        result = subprocess.run(host.replay_command(package, domain, prior=False), capture_output=True, text=True)
        s.save(evidence/(domain+'-new-replay.json'), {'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}, 0o644)
        require(result.returncode == 0, 'Fresh fixed-image readonly replay failed')
    after = host.snapshot(s); s.save(evidence/'after.json', after, 0o644)
    original = json.loads((OLD/'evidence/before.json').read_bytes())
    changed = [p for p, h in original['files'].items() if after['files'].get(p) != h]
    s.save(evidence/'acceptance.json', {'new_two_witnessed': witnessed, 'batch_complete': True,
        'replay_verified': True, 'formal_changed_files': changed, 'mail_sent_by_acceptance': False,
        'requires_formal_readonly_review': bool(changed)}, 0o644)
    require(not changed, 'Formal bytes changed; retain strict refusal and inspect legitimate timer events')


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 3, 'Exact packet and active execution required')
        run(sys.argv[1], int(sys.argv[2]))
    except Exception as exc:
        folder = STAGE/'evidence'; folder.mkdir(mode=0o755, exist_ok=True)
        path = folder/('failure-'+now().strftime('%Y%m%dT%H%M%S%f')+'.json')
        with path.open('x') as stream:
            json.dump({'at': now().isoformat(), 'type': type(exc).__name__, 'error': str(exc)}, stream)
        raise
