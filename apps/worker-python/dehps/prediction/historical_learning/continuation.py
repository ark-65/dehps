"""Exact old/new release bridge; prior execution facts remain in their store.

This contract is part of each newly approved execution plan. It is not an
approval itself and does not renew the original batch or runtime admission.
"""
from datetime import timedelta
import json

from .contract import POLICY, digest, instant, require, sha, validate_contract

SCHEMA = 'historical-continuation.v1'
CHAIN_SCHEMA = 'historical-continuation.v2'


def lineage(value):
    """Bounded immutable ancestry; old contracts are embedded, never edited."""
    result = []
    while value is not None:
        require(isinstance(value, dict) and len(result) < 8
                and all(value is not item for item in result), 'invalid continuation ancestry')
        result.append(value)
        value = value.get('prior_continuation')
    return result


def release_for(value, domain, definition):
    chain = lineage(value)
    owner = definition.get('continuation_sha256')
    if owner is None:
        return chain[-1]['domains'][domain]['prior_release_sha256']
    matches = [item for item in chain if digest(item) == owner]
    require(len(matches) == 1, 'retained task continuation owner differs')
    return matches[0]['domains'][domain]['next_release_sha256']


def retained_tasks(plan, count):
    result = []
    for task in plan.validate().tasks:
        d = json.loads(task.metric_contract)['historical']
        if d['phase'] in {'freeze', 'resume', 'observe-resume'} or (900 <= d['index'] < 900+count
                and d['phase'] in {'learn', 'report', 'observe'}):
            result.append(task)
    return result


def validate(value, original):
    from .plan import build_plan
    validate_contract(original)
    lineage(value)
    chained = value.get('schema') == CHAIN_SCHEMA
    fields = {'schema', 'contract_sha256', 'retained_count', 'original_approved_until', 'budget_seconds', 'domains'}
    require(set(value) == fields | ({'prior_continuation'} if chained else set()), 'closed historical continuation required')
    require(value['schema'] in {SCHEMA, CHAIN_SCHEMA} and value['contract_sha256'] == digest(original), 'continuation source differs')
    prior = value.get('prior_continuation')
    if chained:
        require(isinstance(prior, dict), 'chained continuation requires exact prior contract')
        validate(prior, original)
        require(value['original_approved_until'] == prior['original_approved_until'], 'original admission expiry changed')
        require(value['retained_count'] > prior['retained_count'], 'chained continuation requires new committed progress')
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
        plan = build_plan(original, domain=domain, continuation=prior)
        if prior:
            require(binding['prior_release_sha256'] == prior['domains'][domain]['next_release_sha256'],
                    'immediate prior release differs')
            previous_releases = {item['domains'][domain][key] for item in lineage(prior)
                                 for key in ('prior_release_sha256', 'next_release_sha256')}
            require(binding['next_release_sha256'] not in previous_releases, 'continuation release reused')
        require(binding['prior_plan_digest'] == plan.digest, 'retained plan identity differs')
        require(set(binding['artifacts']) == {t.task_key for t in retained_tasks(plan, count)},
                'retained artifact list is incomplete, unordered or outside prefix')
        for identity in binding['artifacts'].values():
            sha(identity)
    return value


def deadline(value, started_at):
    return min(instant(started_at)+timedelta(seconds=value['budget_seconds']),
               instant(value['original_approved_until'])).isoformat()


def capture(original, engines, *, next_releases, original_approved_until, budget_seconds=86400,
            prior_continuation=None):
    """Readonly replay and exact committed frontier, before proposing admission.

    Callers must hold the existing domain locks to keep the frontier fixed until
    activation. The runtime independently verifies every retained binding and
    digest against the actual store before it can dispatch a new calculation.
    """
    from .plan import build_plan
    require(set(engines) == set(next_releases) == {'learning', 'observer'}, 'both engines required')
    if prior_continuation:
        validate(prior_continuation, original)
    snapshots = {}
    counts = {}
    for domain, engine in engines.items():
        require(engine.plan.payload == build_plan(original, domain=domain, continuation=prior_continuation).payload,
                'capture prior frozen historical plan differs')
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
                expected_release = (release_for(prior_continuation, domain, json.loads(task.metric_contract)['historical'])
                                    if prior_continuation else engine.store.authorization.release_sha256)
                require(result.task['release_sha256'] == expected_release,
                        'retained release differs')
                artifacts[task.task_key] = result.artifact.sha256
            snapshots[domain] = {'prior_plan_digest': engine.plan.digest,
                'prior_release_sha256': engine.store.authorization.release_sha256,
                'next_release_sha256': next_releases[domain], 'artifacts': artifacts}
    require(counts['learning'] == counts['observer'], 'independent observer has not consumed complete prefix')
    value = {'schema': CHAIN_SCHEMA if prior_continuation else SCHEMA,
        'contract_sha256': digest(original), 'retained_count': counts['learning'],
        'original_approved_until': original_approved_until, 'budget_seconds': budget_seconds, 'domains': snapshots}
    if prior_continuation:
        value['prior_continuation'] = prior_continuation
    return validate(value, original)
