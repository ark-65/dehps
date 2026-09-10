"""Finite historical learning through injected canonical capabilities.

Reused evidence, fresh fitting and replay verification are explicitly distinct.
No production connection, live calendar, crawler or legacy executor is loaded.
"""
import json

from dehps.execution.context import BoundaryError
from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from .frozen_learning import calculation as core, analysis
from .learning_inputs import FrozenLearningInputs

PHASES = ('fit', 'evaluate', 'analysis', 'top100', 'report')
CAPABILITIES = {phase: 'frozen-learning-' + phase + '.v1' for phase in PHASES}
SCHEMA = 'prediction-learning-execution.v1'


def verify_issue(snapshot, contract, value, *, complete=False):
    core.verify(value)
    body = value['body']; index = body['index']; rows = snapshot['body']['rows']
    if not core.MINIMUM <= index < len(rows):
        raise BoundaryError('learning issue index outside the frozen evaluation window')
    y = core.targets(rows)
    if (body['issue'] != rows[index]['issue'] or body['train_end_issue'] != rows[index-1]['issue']
            or body['contract_digest'] != contract['artifact_digest']
            or body['label_red'] != y[index].tolist() or body['label_blue'] != rows[index]['blue']):
        raise BoundaryError('learning issue labels or training boundary differ')
    expected = {'old': list(map(float, core.formal.estimate_legal_marginals(
        list(map(int, y[:index].sum(axis=0))), training_issue_count=index))), 'uniform': [6/33]*33}
    expected.update({config['name']: core.fit(y[:index], config)[0].tolist() for config in core.CONFIGS})
    if (body['probabilities'] != expected or body['log_loss_nats_per_number'] !=
            {name: core.loss(y[index], q) for name, q in expected.items()}):
        raise BoundaryError('frozen issue probabilities or losses changed')
    if complete and core.evaluate_issue(index, snapshot=snapshot['body'], contract=contract) != value:
        raise BoundaryError('complete frozen ticket and baseline replay changed')


def verify_historical_top100(snapshot, checkpoint, predicted):
    body = predicted['body']
    if body['checkpoint_digest'] != checkpoint['artifact_digest']:
        raise BoundaryError('historical Top-100 checkpoint differs')
    q = core.np.asarray(checkpoint['body']['probabilities'])
    space = core.combinations(); scores = core.scores(q, space)
    ids = core.ordered(core.np.arange(len(space)), scores, 10000)
    selected = core.diverse(ids, scores[ids], space[ids])
    blues = core.formal._blue_numbers(
        preregistration_digest=snapshot['body']['formal_preregistration']['artifact_digest'],
        target_issue=body['target_issue'])
    expected = [{'rank': rank+1, 'red': (space[index]+1).tolist(), 'blue': blues[rank]}
                for rank, index in enumerate(selected)]
    if body['tickets'] != expected:
        raise BoundaryError('historical Top-100 tickets or blue assignments differ')


def render_report(snapshot, contract, result, checkpoint, predicted):
    value = result['body']; rows = snapshot['body']['rows']
    lines = ['# Fixed historical learning verification', '', value['conclusion'], '',
             f"Snapshot: {rows[0]['issue']}–{rows[-1]['issue']}, {len(rows)} complete labels; "
             f"{value['issue_count']} chronological evaluation issues after 900 warm-up draws.",
             'Existing four configurations, seeds and comparisons are preserved. These are exploratory historical results, not independent confirmatory evidence.', '',
             '| Model | Mean log-loss | Brier score | Family interval vs old | Family interval vs uniform |',
             '| --- | ---: | ---: | --- | --- |']
    for name, metrics in value['probability'].items():
        def interval(key):
            item = metrics.get(key)
            return '—' if item is None else f"[{item['lower']:+.9f}, {item['upper']:+.9f}]"
        lines.append(f"| {name} | {metrics['mean_log_loss']:.9f} | {metrics['brier']:.9f} | "
                     f"{interval('family_vs_old')} | {interval('family_vs_uniform')} |")
    lines += ['', 'Intervals preserve 4,000 paired circular block resamples, length 13, and eight family contrasts. Full calibration bins remain in the analysis artifact.', '',
              '| Ticket arm | Mean maximum red hits | Mean net CNY | Pretax ROI | Candidate coverage | Mean overlap |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, metrics in value['tickets'].items():
        lines.append(f"| {name} | {metrics['mean_max_red_hits']:.4f} | {metrics['mean_net_cny_per_issue']:.2f} | "
                     f"{metrics['roi']:.2%} | {metrics.get('candidate_coverage', 'random')} | {metrics.get('mean_pairwise_overlap', 'random')} |")
    lines += ['', 'Read new_original/old_original as the probability comparison, old_full/old_original as coverage, and old_diverse/old_original as selection. Combined arms remain secondary.',
              'All red-selection arms retain the original shared blue-by-rank vector. Each random baseline has 32 groups per issue. Simulated historical returns are not forecasts of profit.',
              'Floating payouts use only the frozen, label-matched evidence. No new payout retrieval or production mail occurs.', '',
              'Prespecified diagnostic examples:']
    for example in value['examples']:
        lines.append(f"- {example['issue']}: old/new loss {example['old_loss']:.8f}/{example['new_loss']:.8f}; "
                     f"global ranks {example['old_global_rank']}/{example['new_global_rank']}; "
                     f"first rejection {example['old_first_rejection']}/{example['new_first_rejection']}.")
    lines += ['', 'Every retained issue includes all probabilities, labels, selected tickets, blue assignments, omitted/extra-number diagnostics and random baselines.',
              'The primary checkpoint is refitted on the entire fixed snapshot and remains RESEARCH_ONLY. That full-data checkpoint is not used for chronological historical predictions.',
              'The archived Top-100 is verified against its original target and timestamp; no new or backdated prediction is generated.', '',
              f"Contract: {contract['artifact_digest']}", f"Analysis: {result['artifact_digest']}",
              f"Checkpoint: {checkpoint['artifact_digest']}", f"Archived Top-100: {predicted['artifact_digest']}", '',
              'Integration is established by the accompanying canonical execution/registration and readonly replay records. Engineering success does not change the scientific conclusion.']
    return '\n'.join(lines) + '\n'


def build_capabilities(plan, store, context):
    manifest = plan.validate()
    contracts = {task.artifact_digest: json.loads(task.metric_contract)['learning'] for task in manifest.tasks}
    if {c['phase'] for c in contracts.values()} != set(PHASES) or len(contracts) != len(PHASES):
        raise BoundaryError('the complete finite learning path is required')
    digests = {c['inputs_sha256'] for c in contracts.values()}
    if len(digests) != 1:
        raise BoundaryError('learning tasks must share the same frozen input packet')
    inputs = FrozenLearningInputs(context.inputs, digests.pop())
    inputs.validate_execution(context.code_root)
    for task in manifest.tasks:
        contract = contracts[task.artifact_digest]
        if (set(contract) != {'phase', 'inputs_sha256'} or inputs.digest not in task.input_artifact_digests
                or task.requested_capability != CAPABILITIES[contract['phase']]):
            raise BoundaryError('learning task capability or input binding differs')
    snapshot, contract = inputs.artifact('snapshot'), inputs.artifact('contract')
    by_digest = {ref['artifact_digest']: issue for issue, ref in inputs.manifest['issues'].items()}
    def reference(phase, parent):
        """A sealed historical oracle, not fitting hidden inside read/recovery.

        This adapter migrates an already completed frozen experiment. Its admitted
        original artifacts supply exact expected results. New experiments need
        their own verifier; they must not invent a historical oracle.
        """
        if phase == 'fit':
            value = {'checkpoint': inputs.artifact('checkpoint'), 'scope': 'FRESH_REFIT_OF_FIXED_HISTORICAL_SNAPSHOT'}
        elif phase == 'evaluate':
            if parent['checkpoint'] != inputs.artifact('checkpoint'):
                raise BoundaryError('evaluation producer checkpoint differs')
            examples = set(contract['body']['examples'])
            value = {'checkpoint': parent['checkpoint'], 'issue_count': len(by_digest), 'all_probabilities_and_losses_recomputed': True,
                     'complete_ticket_calculations_recomputed': sorted(examples),
                     'retained_ticket_evaluations_verified': len(by_digest)-len(examples),
                     'evaluations': {issue: ref['artifact_digest'] for issue, ref in inputs.manifest['issues'].items()}}
        elif phase == 'analysis':
            if parent['evaluations'] != {issue: ref['artifact_digest'] for issue, ref in inputs.manifest['issues'].items()}:
                raise BoundaryError('analysis predecessor evaluation set differs')
            value = {'analysis': inputs.artifact('analysis'), 'checkpoint': parent['checkpoint']}
        elif phase == 'top100':
            value = inputs.artifact('top100')
            value = {'reference': value, 'checkpoint': parent['checkpoint'], 'analysis': parent['analysis'],
                     'new_prediction': False, 'verification': 'EXACT_ARCHIVED_TICKETS'}
        else:
            value = {'text': render_report(snapshot, contract, parent['analysis'], parent['checkpoint'], parent['reference']),
                     'scientific_conclusion': parent['analysis']['body']['conclusion'],
                     'new_scientific_experiment': False}
        return value

    def expected(task_digest, parents):
        phase = contracts[task_digest]['phase']
        if len(parents) != (0 if phase == 'fit' else 1):
            raise BoundaryError('learning phase requires its canonical predecessor')
        parent_value = None
        if parents:
            parent = json.loads(next(iter(parents.values())).data)
            if parent['phase'] != PHASES[PHASES.index(phase)-1]:
                raise BoundaryError('learning predecessor phase differs')
            parent_value = parent['scientific']
        return {'schema': SCHEMA, 'phase': phase, 'task_digest': task_digest,
                'release_sha256': context.release.digest, 'inputs_sha256': inputs.digest,
                'parents': {key: value.artifact.sha256 for key, value in parents.items()},
                'scientific': reference(phase, parent_value)}

    def verify(binding, data):
        if (binding['scientific_contract_sha256'] != contract['artifact_digest']
                or binding['artifact_schema'] != SCHEMA or binding['release_sha256'] != context.release.digest):
            raise BoundaryError('learning result contract/release binding differs')
        phase = contracts[binding['task_digest']]['phase']
        # Every descendant reads/verifies its committed predecessor recursively.
        # Rehash issue bytes at the evaluation boundary, not at every unrelated
        # checkpoint/report read. No stat-only or trusted-in-memory hash shortcut.
        inputs.verify_files(include_issues=phase == 'evaluate')
        parents = {}
        for parent in MainlineLedger(store).context(binding['id'])['parents']:
            result = store.result(parent['task_id'])
            if result is None:
                raise BoundaryError('learning predecessor is not committed')
            parents[result.task['business_key']] = result
        if json.loads(data) != expected(binding['task_digest'], parents):
            raise BoundaryError('learning result differs from its canonical computation')

    def execute(task, parents, artifacts):
        value = expected(task.artifact_digest, parents)
        phase = value['phase']
        if phase == 'fit':
            value['scientific']['checkpoint'] = analysis.refit_checkpoint(snapshot, contract)
        elif phase == 'evaluate':
            examples = set(contract['body']['examples'])
            for issue in contract['body']['outer_issues']:
                verify_issue(snapshot, contract, inputs.issue(issue), complete=issue in examples)
        elif phase == 'analysis':
            predecessor = json.loads(next(iter(parents.values())).data)['scientific']
            verified = {digest: issue for issue, digest in predecessor['evaluations'].items()}
            payouts = {issue: inputs.payout(issue) for issue in inputs.manifest['payouts']}
            value['scientific']['analysis'] = analysis.analyze(
                contract, inputs.artifact('training'), lambda digest: inputs.issue(verified[digest]), payouts)
        elif phase == 'top100':
            verify_historical_top100(snapshot, value['scientific']['checkpoint'], value['scientific']['reference'])
        # The same verifier compares this newly computed result to the admitted
        # frozen oracle on commit, readback, recovery, replay and consumption.
        return canonical(value)

    return {name: Capability(name, verify, execute) for name in CAPABILITIES.values()}
