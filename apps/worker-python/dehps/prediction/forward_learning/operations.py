"""Explicit input-export operations; no training, approval or schema mutation."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.authority import AuthorityClient
from dehps.execution.context import RunContext
from dehps.execution.coordinator import Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.release import Release, canonical
from dehps.execution.store import ExecutionAuthorization, ExecutionStore
from .capabilities import build_capabilities
from .contract import Inputs, POLICY, SCHEMA, digest, instant, require, validate_contract
from .plan import build_plan
from .publisher import append_bytes, audited_source, publish_labels, publish_observation


def private_json(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, 'absolute non-symlink private path required')
    info = path.stat()
    require(info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0, 'private file owner/mode mismatch')
    return json.loads(path.read_bytes())


def signing_key(path):
    value = private_json(path)
    require(set(value) == {'ed25519_private_key'}, 'closed signing key required')
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(value['ed25519_private_key'], validate=True))


def freeze(*, source, calendar, calendar_sha256, calendar_source, output, key):
    """Freeze a reviewed explicit calendar, never infer future issue identities.

    calendar_source is the archived normative source, separately content bound.
    Deployment review must establish its completeness, including year rollover
    and market closures. This function does not invent that review approval.
    """
    packet = json.loads(calendar.read_bytes())
    require(digest(packet) == calendar_sha256, 'reviewed calendar changed')
    require(set(packet) == {'schema', 'targets', 'source_sha256', 'source_description'}
            and packet['schema'] == 'forward-calendar.v1' and packet['source_description'], 'closed reviewed calendar required')
    from hashlib import sha256
    require(sha256(calendar_source.read_bytes()).hexdigest() == packet['source_sha256'], 'calendar source changed')
    require(not output.exists(), 'freeze output must be a new directory; preserve prior cohort')
    with source.connect() as connection:
        rows, receipt = audited_source(connection, before_issue=packet['targets'][0]['issue'])
    contract = {'schema': SCHEMA, 'policy': POLICY, 'targets': packet['targets'],
        'created_at': datetime.now(timezone.utc).isoformat(), 'initial_sha256': digest(rows),
        'calendar_sha256': digest(packet['targets']),
        'calendar_source_sha256': packet['source_sha256'],
        'export_public_key': base64.b64encode(key.public_key().public_bytes_raw()).decode()}
    validate_contract(contract)
    require(rows and receipt['latest_issue'] == rows[-1]['issue'], 'source already includes target; do not backfill a cohort')
    output.mkdir(mode=0o700)
    for name, value in [('contract.json', contract), ('initial.json', rows), ('calendar-provenance.json', packet),
                        ('learning-plan.json', build_plan(contract).payload),
                        ('observer-plan.json', build_plan(contract, domain='observer').payload)]:
        append_bytes(output/name, canonical(value))
    append_bytes(output/'receipts'/f'{digest(receipt)}.json', canonical(receipt))
    append_bytes(output/'receipts'/packet['source_sha256'], calendar_source.read_bytes())
    append_bytes(output/'calendar-source', calendar_source.read_bytes())
    Inputs(output, digest(contract)).initial()
    return {'contract_sha256': digest(contract), 'targets': [t['issue'] for t in contract['targets']],
            'status': 'FROZEN_INPUTS_NOT_EXECUTED', 'initial_count': len(rows)}


def reader_engine(config):
    # Run this trusted readonly bridge from the exact accepted host release.
    # It receives a reader login, never an operator/reviewer login. The normal
    # entry remains the only path which begins or commits an execution.
    inputs = Path(config['inputs'])
    release = Release.read(inputs/'release.json', config['release_sha256'])
    packet = json.loads((inputs/'execution.json').read_bytes())
    plan = ExecutionPlan(packet['plan']); plan.validate()
    database = DatabaseBinding(**private_json(config['reader_credentials']))
    request = AuthorityClient(database).get(packet['request_id'])
    require(request['payload'] == plan.payload and request['release_sha256'] == release.digest
            and request['control_plane'] == 'learning', 'producer reader binding differs')
    store = ExecutionStore(database, ArtifactStore(RunContext(Path(config['runtime_root']), 'learning')),
        ExecutionAuthorization(0, request['content_sha256'], release.digest), {})
    context = SimpleNamespace(inputs=inputs, code_root=Path(config['code_root']), release=release)
    return Coordinator(plan, store, build_capabilities(plan, store, context))


def publish(config):
    require(set(config) == {'schema', 'approved_until', 'key_file', 'contract_sha256',
            'learning_inputs', 'observer_inputs', 'source_credentials', 'producer_reader'}, 'closed publisher configuration required')
    require(config['schema'] == 'forward-publisher.v1', 'publisher schema differs')
    if datetime.now(timezone.utc) >= instant(config['approved_until']):
        return {'status': 'WAITING', 'reason': 'AUTHORIZATION_REQUIRED', 'published_labels': [], 'published_reports': []}
    key = signing_key(config['key_file'])
    learning = Inputs(Path(config['learning_inputs']), config['contract_sha256'])
    observer = Inputs(Path(config['observer_inputs']), config['contract_sha256'])
    now = datetime.now(timezone.utc)
    pending_labels = [t for t in learning.contract['targets'] if instant(t['draw_at']) <= now
                      and (learning.opened(t, now=now) is None or observer.opened(t, now=now) is None)]
    labels = []
    if pending_labels:
        source = DatabaseBinding(**private_json(config['source_credentials']))
        with source.connect() as connection:
            rows, receipt = audited_source(connection)
        # A power loss between domains is recoverable. Copy the exact previously
        # signed point-in-time envelope before considering a fresh observation.
        for target in pending_labels:
            name = target['issue']+'.json'
            for origin, destination in ((learning, observer), (observer, learning)):
                existing = origin.opened(target, now=now)
                if existing is not None and destination.opened(target, now=now) is None:
                    append_bytes(destination.root/'opened'/name, (origin.root/'opened'/name).read_bytes())
                    audit = existing['audit_sha256']
                    append_bytes(destination.root/'receipts'/f'{audit}.json', (origin.root/'receipts'/f'{audit}.json').read_bytes())
        labels = publish_labels(learning, rows, receipt, key, approved_until=config['approved_until'])
        publish_labels(observer, rows, receipt, key, approved_until=config['approved_until'])
    reports = []
    now = datetime.now(timezone.utc)
    pending_reports = [t for t in learning.contract['targets'] if instant(t['draw_at']) <= now
                       and observer.opened(t, now=now) is not None
                       and (observer.observation(t['issue']) is None
                            or not (observer.root/'reports'/f'{t["issue"]}.md').exists())]
    if pending_reports:
        engine = reader_engine(config['producer_reader'])
        for target in pending_reports:
            if publish_observation(observer, engine, target['issue'], key, approved_until=config['approved_until']):
                reports.append(target['issue'])
    return {'status': 'EXPORTED', 'published_labels': labels, 'published_reports': reports,
            'training_executed': False, 'approvals_created': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    pub = commands.add_parser('publish'); pub.add_argument('--config', type=Path, required=True)
    initial = commands.add_parser('freeze')
    for name in ('source-credentials', 'calendar', 'calendar-source', 'output', 'key-file'):
        initial.add_argument('--'+name, type=Path, required=True)
    initial.add_argument('--calendar-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'publish':
        result = publish(private_json(args.config))
    else:
        result = freeze(source=DatabaseBinding(**private_json(args.source_credentials)), calendar=args.calendar,
            calendar_sha256=args.calendar_sha256, calendar_source=args.calendar_source, output=args.output,
            key=signing_key(args.key_file))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
