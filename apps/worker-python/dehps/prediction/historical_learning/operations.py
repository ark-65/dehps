"""Explicit packaging and read-only publication; never a second training runner."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from dehps.execution.authority import AuthorityClient
from dehps.execution.coordinator import Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.release import Release, canonical
from dehps.execution.store import ExecutionAuthorization, ExecutionStore
from dehps.prediction.learning_inputs import FrozenLearningInputs
from dehps.prediction.forward_learning.operations import private_json, signing_key
from .capabilities import build_capabilities
from .contract import Inputs, POLICY, SCHEMA, digest, instant, require
from .plan import build_plan
from .publisher import (append_bytes, archive, audited_source, publish_dispatch,
                        publish_inputs, publish_observations, source_references)
from . import continuation
from .readonly import ReadonlyArtifacts, ReadonlyContext, ReadonlyDatabase


def freeze(*, source, retained_root, retained_sha256, source_root, output, key):
    require(not output.exists(), 'freeze requires a new output directory')
    retained = FrozenLearningInputs(retained_root, retained_sha256)
    retained.verify_files()
    original = retained.artifact('snapshot')['body']['rows']
    require(len(original) == 3499 and len(retained.manifest['issues']) == 2599, 'verified 3499/2599 baseline required')
    output.mkdir(parents=True, mode=0o700)
    with source.connect() as connection:
        rows, receipt = audited_source(connection)
        require(len(rows) >= len(original), 'audited history lost baseline rows')
        require(all(all(a[k] == b[k] for k in ('issue', 'red', 'blue'))
                    and a['draw_date'] == instant(b['draw_at']).date().isoformat()
                    for a, b in zip(original, rows[:3499], strict=True)), 'baseline labels conflict with current source')
        sources = []
        for name, ref in retained.manifest['artifacts'].items():
            identity = archive(output, (retained_root/ref['path']).read_bytes())
            sources.append({'kind': name, 'sha256': identity, 'artifact_digest': ref['artifact_digest']})
        source_ref = retained.manifest['original_source']
        sources.append({'kind': 'original_source', 'sha256': archive(output, (retained_root/source_ref['path']).read_bytes()),
                        'git_commit': source_ref['git_commit']})
        history = []
        for row in rows:
            references = []
            if row['issue'] in retained.manifest['issues']:
                value = retained.issue(row['issue'])
                ref = retained.manifest['issues'][row['issue']]
                identity = archive(output, (retained_root/ref['path']).read_bytes())
                require(value['body']['issue'] == row['issue'], 'old evaluation identity differs')
                references.append({'kind': 'HISTORICAL_EVALUATION', 'sha256': identity, 'source': ref['path'],
                    'model': 'retained-prediction-learning-v1-all-original-arms', 'issue': row['issue']})
            # Registered formal reports exist only in the recent retained lane;
            # one query per recent issue avoids thousands of empty source reads.
            if row['issue'] >= '2026097':
                references += source_references(connection, source_root, row, output)
            history.append({'label': row, 'references': references})
    append_bytes(output/'receipts'/f'{digest(receipt)}.json', canonical(receipt))
    provenance = {'schema': 'historical-provenance.v1', 'sources': sources,
        'retained_input_sha256': retained_sha256, 'baseline_labels': 3499, 'baseline_evaluations': 2599,
        'audited_source_sha256': digest(receipt), 'original_gap_2026104': True}
    contract = {'schema': SCHEMA, 'policy': POLICY, 'created_at': datetime.now(timezone.utc).isoformat(),
        'history_sha256': digest(history), 'issues': [r['label']['issue'] for r in history],
        'provenance_sha256': digest(provenance),
        'export_public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode()}
    for name, value in [('history.json', history), ('provenance.json', provenance), ('contract.json', contract),
                        ('learning-plan.json', build_plan(contract).payload),
                        ('observer-plan.json', build_plan(contract, domain='observer').payload)]:
        append_bytes(output/name, canonical(value))
    Inputs(output, digest(contract))
    return {'status': 'FROZEN_INPUTS_NOT_EXECUTED', 'contract_sha256': digest(contract),
            'history_count': len(history), 'batch_evaluations': len(history)-900,
            'first_issue': contract['issues'][0], 'last_issue': contract['issues'][-1], 'original_gap_2026104': True}


def reader_engine(config):
    inputs = Path(config['inputs'])
    release = Release.read(inputs/'release.json', config['release_sha256'])
    packet = json.loads((inputs/'execution.json').read_bytes())
    plan = ExecutionPlan(packet['plan']); plan.validate()
    domain = config.get('domain', 'learning')
    require(domain in {'learning', 'observer'}, 'reader domain differs')
    database = ReadonlyDatabase(**private_json(config['reader_credentials']))
    request = AuthorityClient(database).get(packet['request_id'])
    require(request['payload'] == plan.payload and request['release_sha256'] == release.digest
            and request['control_plane'] == domain, 'historical reader admission binding differs')
    store = ExecutionStore(database, ReadonlyArtifacts(ReadonlyContext(Path(config['runtime_root']), domain)),
        ExecutionAuthorization(0, request['content_sha256'], release.digest), {})
    context = SimpleNamespace(inputs=inputs, code_root=Path(config['code_root']), release=release)
    return Coordinator(plan, store, build_capabilities(plan, store, context))


def prepare_continuation(config, output):
    """Read existing ledgers only; write a candidate packet, never admission."""
    require(set(config) == {'schema', 'readers', 'next_releases', 'original_approved_until', 'budget_seconds'},
            'closed continuation preparation config required')
    require(config['schema'] == 'historical-continuation-preparation.v1', 'preparation schema differs')
    require(not output.exists(), 'continuation preparation requires a new directory')
    engines = {d: reader_engine({**reader, 'domain': d}) for d, reader in config['readers'].items()}
    original = json.loads((Path(config['readers']['learning']['inputs'])/'contract.json').read_bytes())
    value = continuation.capture(original, engines, next_releases=config['next_releases'],
        original_approved_until=config['original_approved_until'], budget_seconds=config['budget_seconds'])
    output.mkdir(parents=True, mode=0o700)
    append_bytes(output/'continuation.json', canonical(value))
    for domain in ('learning', 'observer'):
        append_bytes(output/(domain+'-plan.json'), canonical(build_plan(original, domain=domain, continuation=value).payload))
    return {'status': 'CONTINUATION_PREPARED_NOT_APPROVED', 'continuation_sha256': digest(value),
        'retained_count': value['retained_count'], 'next_issue': original['issues'][900+value['retained_count']],
        'training_executed': False, 'approvals_created': False}


def source_error(config, key, exc):
    if datetime.now(timezone.utc) >= instant(config['approved_until']):
        return  # expiry is not a source correction and cannot authorize a write
    from dehps.execution.context import BoundaryError
    reason = 'SOURCE_CONFLICT' if isinstance(exc, BoundaryError) else 'SOURCE_UNREADABLE'
    error = {'schema': 'historical-source-error.v1', 'contract_sha256': config['contract_sha256'],
        'observed_at': datetime.now(timezone.utc).isoformat(), 'error_type': type(exc).__name__, 'reason': reason}
    for field in ('learning_inputs', 'observer_inputs'):
        # A damaged contract cannot construct Inputs. The protected publisher
        # configuration and private signing key still bind a stop observation to
        # the exact admitted contract, allowing an existing reader to stop too.
        root = Path(config[field])
        require(root.is_absolute() and root.resolve() == root, 'canonical publisher root required')
        append_bytes(root/'errors'/f'{digest(error)}.json', canonical(error))
        target = SimpleNamespace(root=root, contract_sha256=config['contract_sha256'],
            contract={'export_public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode()})
        publish_dispatch(target, key, approved_until=config['approved_until'], reason=reason)


def _publish_sources(config):
    """Audit current machine sources and sign readiness only after validation."""
    require(set(config) == {'schema', 'activated_at', 'approved_until', 'key_file', 'contract_sha256',
        'learning_inputs', 'observer_inputs', 'source_credentials', 'source_root', 'producer_reader'}, 'closed historical publisher configuration required')
    require(config['schema'] == 'historical-publisher.v1', 'publisher schema differs')
    require(instant(config['approved_until']) <= instant(config['activated_at'])+timedelta(days=POLICY['admission_days']), 'admission exceeds 30 days')
    if datetime.now(timezone.utc) >= instant(config['approved_until']):
        return {'status': 'WAITING', 'reason': 'AUTHORIZATION_REQUIRED', 'training_executed': False}
    key = signing_key(config['key_file'])
    try:
        learning = Inputs(Path(config['learning_inputs']), config['contract_sha256'])
        observer = Inputs(Path(config['observer_inputs']), config['contract_sha256'])
    except Exception as exc:
        source_error(config, key, exc)
        raise
    guard = learning.formal_guard()
    if guard:
        return {'status': 'WAITING', 'reason': guard, 'training_executed': False}
    source = DatabaseBinding(**private_json(config['source_credentials']))
    labels = []
    try:
        with source.connect() as connection:
            rows, receipt = audited_source(connection)
            # Copy exact first publication after a crash between domains. A new
            # export observation must not change its original input identity.
            for index in range(len(learning.history), len(learning.history)+POLICY['incremental_slots']):
                for origin, destination in ((learning, observer), (observer, learning)):
                    record = origin.record(index)
                    if record is not None and destination.record(index) is None:
                        require(datetime.now(timezone.utc) < instant(config['approved_until']), 'publisher authorization expired')
                        audit = record['label']['audit_sha256']
                        append_bytes(destination.root/'receipts'/f'{audit}.json', (origin.root/'receipts'/f'{audit}.json').read_bytes())
                        for ref in record['references']:
                            append_bytes(destination.root/'sources'/ref['sha256'], origin.blob(ref['sha256']))
                        append_bytes(destination.root/'incremental'/f'{index:05d}.json', (origin.root/'incremental'/f'{index:05d}.json').read_bytes())
            def references(row):
                refs = source_references(connection, Path(config['source_root']), row, learning.root)
                for ref in refs:
                    append_bytes(observer.root/'sources'/ref['sha256'], learning.blob(ref['sha256']))
                return refs
            labels = publish_inputs(learning, rows, receipt, key, approved_until=config['approved_until'], references=references)
            # The envelope bytes, including availability, must be identical.
            for index in range(len(learning.history), len(learning.history)+POLICY['incremental_slots']):
                record = learning.record(index)
                if record is not None and observer.record(index) is None:
                    require(datetime.now(timezone.utc) < instant(config['approved_until']), 'publisher authorization expired')
                    audit = record['label']['audit_sha256']
                    append_bytes(observer.root/'receipts'/f'{audit}.json', (learning.root/'receipts'/f'{audit}.json').read_bytes())
                    append_bytes(observer.root/'incremental'/f'{index:05d}.json', (learning.root/'incremental'/f'{index:05d}.json').read_bytes())
        for inputs in (learning, observer):
            require(datetime.now(timezone.utc) < instant(config['approved_until']), 'publisher authorization expired')
            publish_dispatch(inputs, key, approved_until=config['approved_until'], reason=None)
    except Exception as exc:
        source_error(config, key, exc)
        raise
    return observer, labels, key


def publish(config):
    initial = _publish_sources(config)
    if isinstance(initial, dict):
        return initial
    observer, labels, key = initial
    reports = publish_observations(observer, reader_engine(config['producer_reader']), key,
                                   approved_until=config['approved_until'])
    # Workers are ordered after this service. A large registered-report replay
    # can consume most of the 1200-second readiness lifetime before they start.
    # Perform a NEW complete source audit, including frozen inputs, database
    # labels, expiry and formal guard. Never merely re-sign an old observation.
    final = _publish_sources(config)
    if isinstance(final, dict):
        return {**final, 'published_labels': labels, 'published_reports': reports}
    _, final_labels, _ = final
    return {'status': 'EXPORTED', 'published_labels': list(dict.fromkeys([*labels, *final_labels])), 'published_reports': reports,
            'training_executed': False, 'approvals_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    pub = commands.add_parser('publish'); pub.add_argument('--config', type=Path, required=True)
    resume = commands.add_parser('prepare-continuation')
    resume.add_argument('--config', type=Path, required=True)
    resume.add_argument('--output', type=Path, required=True)
    initial = commands.add_parser('freeze')
    for name in ('source-credentials', 'retained-root', 'source-root', 'output', 'key-file'):
        initial.add_argument('--'+name, type=Path, required=True)
    initial.add_argument('--retained-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'publish':
        result = publish(private_json(args.config))
    elif args.command == 'prepare-continuation':
        result = prepare_continuation(private_json(args.config), args.output)
    else:
        result = freeze(source=DatabaseBinding(**private_json(args.source_credentials)), retained_root=args.retained_root,
            retained_sha256=args.retained_sha256, source_root=args.source_root, output=args.output, key=signing_key(args.key_file))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
