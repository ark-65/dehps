"""Exact old/new release bridge; prior execution facts remain in their store.

This contract is part of each newly approved execution plan. It is not an
approval itself and does not renew the original batch or runtime admission.
"""
from datetime import timedelta
import json

from .contract import POLICY, digest, instant, require, sha, validate_contract

SCHEMA = 'historical-continuation.v1'


def retained_tasks(plan, count):
    result = []
    for task in plan.validate().tasks:
        d = json.loads(task.metric_contract)['historical']
        if d['phase'] == 'freeze' or (900 <= d['index'] < 900+count
                and d['phase'] in {'learn', 'report', 'observe'}):
            result.append(task)
    return result


def validate(value, original):
    from .plan import build_plan
    validate_contract(original)
    require(set(value) == {'schema', 'contract_sha256', 'retained_count', 'original_approved_until',
        'budget_seconds', 'domains'}, 'closed historical continuation required')
    require(value['schema'] == SCHEMA and value['contract_sha256'] == digest(original), 'continuation source differs')
    count = value['retained_count']
    require(type(count) is int and 0 < count < len(original['issues'])-900,
            'continuation requires a nonempty incomplete historical prefix')
    require(type(value['budget_seconds']) is int and 0 < value['budget_seconds'] <= POLICY['batch_budget_seconds'],
            'continuation budget exceeds fixed maximum')
    instant(value['original_approved_until'])
    require(set(value['domains']) == {'learning', 'observer'}, 'both continuation domains required')
    for domain, binding in value['domains'].items():
        require(set(binding) == {'prior_plan_digest', 'prior_release_sha256', 'next_release_sha256', 'artifacts'},
                'closed continuation release binding required')
        for key in ('prior_plan_digest', 'prior_release_sha256', 'next_release_sha256'):
            sha(binding[key])
        require(binding['prior_release_sha256'] != binding['next_release_sha256'], 'continuation needs a distinct release')
        plan = build_plan(original, domain=domain)
        require(binding['prior_plan_digest'] == plan.digest, 'retained plan identity differs')
        require(set(binding['artifacts']) == {t.task_key for t in retained_tasks(plan, count)},
                'retained artifact list is incomplete, unordered or outside prefix')
        for identity in binding['artifacts'].values():
            sha(identity)
    return value


def deadline(value, started_at):
    return min(instant(started_at)+timedelta(seconds=value['budget_seconds']),
               instant(value['original_approved_until'])).isoformat()


def capture(original, engines, *, next_releases, original_approved_until, budget_seconds=86400):
    """Readonly replay and exact committed frontier, before proposing admission.

    Callers must hold the existing domain locks to keep the frontier fixed until
    activation. The runtime independently verifies every retained binding and
    digest against the actual store before it can dispatch a new calculation.
    """
    from .plan import build_plan
    require(set(engines) == set(next_releases) == {'learning', 'observer'}, 'both engines required')
    snapshots = {}
    counts = {}
    for domain, engine in engines.items():
        require(engine.plan.payload == build_plan(original, domain=domain).payload,
                'capture supports only original frozen historical plan')
        with engine.store.verification_scope():
            manifest = engine.replay(require_complete=False)
            complete = [t for t in manifest.tasks
                if manifest.task_state_by_digest[t.artifact_digest].declared_status.value == 'completed']
            definitions = [json.loads(t.metric_contract)['historical'] for t in complete]
            phase = 'learn' if domain == 'learning' else 'observe'
            indices = sorted(d['index'] for d in definitions if d['phase'] == phase)
            require(indices == list(range(900, 900+len(indices))), 'retained prefix has gaps or duplicates')
            counts[domain] = len(indices)
            require({t.task_key for t in complete} == {t.task_key for t in retained_tasks(engine.plan, len(indices))},
                    'retained prefix has missing reports or unexpected completed tasks')
            artifacts = {}
            for task in complete:
                result = engine.store.result(engine.bindings[task.artifact_digest])
                require(result is not None, 'retained commit disappeared')
                engine.ledger.verify(result.task['id'])
                require(result.task['release_sha256'] == engine.store.authorization.release_sha256,
                        'retained release differs')
                artifacts[task.task_key] = result.artifact.sha256
            snapshots[domain] = {'prior_plan_digest': engine.plan.digest,
                'prior_release_sha256': engine.store.authorization.release_sha256,
                'next_release_sha256': next_releases[domain], 'artifacts': artifacts}
    require(counts['learning'] == counts['observer'], 'independent observer has not consumed complete prefix')
    value = {'schema': SCHEMA, 'contract_sha256': digest(original), 'retained_count': counts['learning'],
        'original_approved_until': original_approved_until, 'budget_seconds': budget_seconds, 'domains': snapshots}
    return validate(value, original)
