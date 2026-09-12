"""Forward capabilities injected into the established atomic coordinator."""
from datetime import datetime, timezone
import json

from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from . import calculation as compute
from .contract import Inputs, SCHEMA, digest, instant, require
from .plan import CAPABILITIES, build_plan
from .report import render


def build_capabilities(plan, store, context):
    tasks = {t.artifact_digest: t for t in plan.validate().tasks}
    contracts = {key: json.loads(t.metric_contract)['forward'] for key, t in tasks.items()}
    hashes = {item['contract_sha256'] for item in contracts.values()}
    require(len(hashes) == 1, 'one frozen forward contract required')
    inputs = Inputs(context.inputs, hashes.pop())
    domain = store.artifacts.context.control_plane
    require(build_plan(inputs.contract, domain=domain).payload == plan.payload, 'forward plan differs from frozen definition')
    rows = inputs.initial()
    initial_counts = [sum(i in r['red'] for r in rows) for i in range(1, 34)]
    captured = {}

    def values(parents):
        return [json.loads(value.data) for value in parents.values()]

    def statistic_input(contract, parents):
        if contract['index'] == 0:
            require(not parents, 'first seal cannot consume an outcome parent')
            return {'counts': initial_counts, 'count': len(rows), 'training_end_issue': rows[-1]['issue'],
                    'last_available_at': max((r['available_at'] for r in rows), key=instant)}
        require(len(parents) == 1, 'next seal requires previous score')
        parent = values(parents)[0]
        require(parent['phase'] == 'score' and parent['issue'] == inputs.contract['targets'][contract['index']-1]['issue'],
                'next seal predecessor mismatch')
        return parent['scientific']['training_after']

    def seal_value(contract, parents, created_at, *, fitting=False):
        target = inputs.contract['targets'][contract['index']]
        training = statistic_input(contract, parents)
        require(instant(training['last_available_at']) <= instant(created_at), 'training label not yet available')
        result = {'created_at': created_at, 'target': target, 'training': training,
                  'status': 'MISSED_SEAL', 'probabilities': {}, 'tickets': {}}
        if instant(created_at) >= instant(target['deadline']):
            return result
        result['status'] = 'SEALED_BEFORE_DRAW'
        func = compute.fit_checkpoint if fitting else compute.probabilities
        result['probabilities'] = func(training['counts'], training['count'])
        result['tickets'] = {name: compute.portfolio(result['probabilities'][name], inputs.contract_sha256, target['issue'])
                             for name in ('shrink900', 'old')}
        return result

    def expected(contract, parents, *, created_at=None, fitting=False):
        phase = contract['phase']; target = inputs.contract['targets'][contract['index']]
        if phase == 'seal':
            return seal_value(contract, parents, created_at, fitting=fitting)
        if phase == 'score':
            require(len(parents) == 1, 'score needs one committed seal')
            parent = values(parents)[0]
            require(parent['phase'] == 'seal' and parent['issue'] == target['issue'], 'score seal identity mismatch')
            label = inputs.opened(target, now=datetime.now(timezone.utc))
            require(label is not None, 'missing audited label')
            seal = parent['scientific']
            scored = compute.score(seal, label, inputs.contract_sha256)
            before = seal['training']
            require(before['training_end_issue'] < label['issue'], 'label already absorbed before score')
            scored['training_after'] = {'count': before['count']+1,
                'counts': [c + int(i in label['red']) for i, c in enumerate(before['counts'], 1)],
                'training_end_issue': label['issue'], 'last_available_at': label['available_at']}
            return scored
        if phase == 'report':
            records = values(parents)
            scored = next(row for row in records if row['phase'] == 'score')
            require(scored['issue'] == target['issue'], 'report score identity mismatch')
            next_seal = next(({'issue': row['issue'], 'status': row['scientific']['status'],
                              'artifact_sha256': parents[key].artifact.sha256}
                             for key, value in parents.items() if (row := json.loads(value.data))['phase'] == 'seal'), None)
            require(len(records) == 2, 'report successor binding mismatch')
            window = next((r['scientific'] for r in records if r['phase'] == 'analysis'), None)
            require((window is not None) == (contract['index'] == 59), 'window analysis binding mismatch')
            return {'text': render(target['issue'], scored['scientific'], next_seal, window),
                    'issue': target['issue'], 'score': scored['scientific'], 'next_checkpoint': next_seal,
                    'window_analysis': window,
                    'evidence': 'DESCRIPTIVE_ONLY', 'external_delivery': False}
        if phase == 'analysis':
            records = sorted(values(parents), key=lambda row: row['issue'])
            require(all(row['phase'] == 'score' for row in records), 'final analysis requires score parents')
            return compute.final_analysis(records, inputs.contract['targets'])
        return observe(contract)

    def observe(contract):
        # A separate domain consumes an exporter-signed committed report bundle.
        # No worker can sign an input, borrow producer credentials or use status
        # JSON to manufacture a cross-domain completion fact.
        bundle = inputs.observation(contract['issue'])
        require(bundle is not None, 'missing committed observation input')
        sealed, scored = bundle['seal'], bundle['score']
        target = inputs.contract['targets'][contract['index']]
        require(sealed['target'] == target, 'observation seal calendar mismatch')
        require(instant(bundle['producer_committed_at']) <= datetime.now(timezone.utc), 'future producer commit')
        require(instant(sealed['created_at']) <= instant(bundle['producer_committed_at']), 'invalid seal provenance')
        require(sealed['status'] in {'SEALED_BEFORE_DRAW', 'MISSED_SEAL'}, 'invalid observation seal status')
        training = sealed['training']
        require(instant(training['last_available_at']) <= instant(sealed['created_at'])
                and training['training_end_issue'] < contract['issue'], 'observation training leakage')
        if sealed['status'] == 'SEALED_BEFORE_DRAW':
            require(instant(sealed['created_at']) < instant(target['deadline']), 'backdated observation seal')
            training = sealed['training']
            q = compute.probabilities(training['counts'], training['count'])
            require(sealed['probabilities'] == q, 'observation probabilities differ')
            require(sealed['tickets'] == {name: compute.portfolio(q[name], inputs.contract_sha256, contract['issue'])
                                         for name in ('old', 'shrink900')}, 'observation tickets differ')
        else:
            require(instant(sealed['created_at']) >= instant(target['deadline'])
                    and not sealed['probabilities'] and not sealed['tickets'], 'invalid gap observation')
        label = inputs.opened(target, now=datetime.now(timezone.utc))
        require(label is not None, 'observation needs audited label')
        expected_score = compute.score(sealed, label, inputs.contract_sha256)
        require({k: v for k, v in scored.items() if k != 'training_after'} == expected_score, 'observation score differs')
        require(scored['training_after'] == {'count': training['count']+1,
            'counts': [c+int(i in label['red']) for i,c in enumerate(training['counts'], 1)],
            'training_end_issue': label['issue'], 'last_available_at': label['available_at']},
            'observation update differs')
        require((bundle['window_analysis'] is not None) == (contract['index'] == 59), 'observation window binding mismatch')
        return {'text': render(contract['issue'], scored, bundle['next_checkpoint'], bundle['window_analysis']), 'score': scored,
                'window_analysis': bundle['window_analysis'],
                'producer_report_sha256': bundle['report_sha256'], 'external_delivery': False}

    def ready(task, parents):
        contract = contracts[task.artifact_digest]
        target = inputs.contract['targets'][contract['index']]
        if contract['phase'] in {'score', 'observe'}:
            if datetime.now(timezone.utc) < instant(target['draw_at']):
                return 'WAITING_FOR_AUDITED_DRAW'
            if inputs.opened(target, now=datetime.now(timezone.utc)) is None:
                return 'MISSING_AUDITED_LABEL'
        if contract['phase'] == 'observe' and inputs.observation(contract['issue']) is None:
            return 'WAITING_FOR_REGISTERED_LEARNING_REPORT'
        return None

    def parent_results(binding):
        parents = {}
        for parent in MainlineLedger(store).context(binding['id'])['parents']:
            result = store.result(parent['task_id'])
            require(result is not None, 'committed parent missing')
            parents[result.task['business_key']] = result
        return parents

    def verify(binding, data):
        value = json.loads(data)
        contract = contracts[binding['task_digest']]
        require(set(value) == {'schema', 'phase', 'issue', 'task_digest', 'release_sha256', 'parents', 'scientific'},
                'closed forward result required')
        require(value['schema'] == binding['artifact_schema'] == SCHEMA
                and value['phase'] == contract['phase'] and value['issue'] == contract['issue']
                and value['task_digest'] == binding['task_digest']
                and value['release_sha256'] == binding['release_sha256'] == context.release.digest
                and binding['scientific_contract_sha256'] == inputs.contract_sha256, 'forward result binding mismatch')
        inputs.hashed('contract.json', inputs.contract_sha256)
        inputs.calendar_source()
        inputs.initial()
        parents = parent_results(binding)
        require(value['parents'] == {key: result.artifact.sha256 for key, result in parents.items()}, 'forward parent digest mismatch')
        created_at = value['scientific'].get('created_at') if contract['phase'] == 'seal' else None
        require(value['scientific'] == expected(contract, parents, created_at=created_at), 'forward result calculation mismatch')
        if contract['phase'] == 'seal':
            persisted = MainlineLedger(store).context(binding['id'])
            if persisted['commit'] is None:
                require(captured.get(binding['task_digest']) == digest(value), 'seal not created by this live attempt')
                if value['scientific']['status'] == 'SEALED_BEFORE_DRAW':
                    require(datetime.now(timezone.utc) < instant(value['scientific']['target']['deadline']), 'seal missed commit cutoff')
            else:
                moment = instant(created_at)
                require(instant(persisted['attempt']['created_at']) <= moment <= instant(persisted['commit']['created_at']),
                        'seal timestamp outside durable attempt')
                if value['scientific']['status'] == 'SEALED_BEFORE_DRAW':
                    require(instant(persisted['commit']['created_at']) < instant(value['scientific']['target']['deadline']),
                            'seal committed after cutoff')

    def execute(task, parents, artifacts):
        contract = contracts[task.artifact_digest]
        value = {'schema': SCHEMA, 'phase': contract['phase'], 'issue': contract['issue'],
            'task_digest': task.artifact_digest, 'release_sha256': context.release.digest,
            'parents': {key: result.artifact.sha256 for key, result in parents.items()},
            'scientific': expected(contract, parents, created_at=datetime.now(timezone.utc).isoformat(), fitting=True)}
        captured[task.artifact_digest] = digest(value)
        return canonical(value)

    def commit_guard(binding, data, server_time):
        value = json.loads(data)
        if value['phase'] == 'seal' and value['scientific']['status'] == 'SEALED_BEFORE_DRAW':
            require(server_time < instant(value['scientific']['target']['deadline']), 'seal transaction crossed cutoff')

    return {name: Capability(name, verify, execute, ready,
                             failure_isolated=phase in {'report', 'observe'}, commit_guard=commit_guard)
            for phase, name in CAPABILITIES.items()}
