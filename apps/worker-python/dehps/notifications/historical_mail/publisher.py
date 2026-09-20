"""Read-only upstream verification and signed publication; never train or send."""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from dehps.execution.ledger import canonical_records
from dehps.execution.plan import ExecutionPlan
from dehps.execution.release import canonical
from dehps.prediction.forward_learning.publisher import append_bytes, audited_source, signed
from dehps.prediction.historical_learning.readonly import ReadonlyDatabase
from .contract import Inputs, digest, instant, require, utcnow


def registered(connection, stored, task, runtime):
    row = connection.execute('SELECT execution_store.mainline_context(%s)',
                             (stored['bindings'][task['task_digest']],)).fetchone()[0]
    if row['commit'] is None:
        return None
    require(row['records'] == canonical_records(row) and row['event_count'] == 2 and row['registration_count'] == 1,
            'upstream mainline registration differs')
    identity = row['commit']['artifact_sha256']
    raw = (runtime/row['task']['control_plane']/'artifacts/objects'/(identity+'.blob')).read_bytes()
    require(sha256(raw).hexdigest() == identity and len(raw) == row['commit']['artifact_size'], 'upstream artifact corrupt')
    value = json.loads(raw)
    require(value['task_digest'] == row['task']['task_digest'] and value['release_sha256'] == row['task']['release_sha256'],
            'upstream artifact task identity differs')
    receipt = {'artifact_sha256': identity, 'registration_digest': row['records']['registration']['digest'],
               'completed_event_digest': row['records']['completed']['digest'], 'committed_at': row['commit']['created_at']}
    return value, receipt


def source_checkpoint(contract, readers):
    """Read immutable registered results, not a status projection or model refit."""
    output = {}; checkpoint = None; selected_index = None
    for domain in ('learning', 'observer'):
        cfg = readers[domain]; root = Path(cfg['inputs'])
        packet = json.loads((root/'execution.json').read_bytes())
        db = ReadonlyDatabase(**json.loads(Path(cfg['credentials']).read_bytes()))
        with db.connect() as c:
            request = c.execute('SELECT execution_authority.request_get(%s)', (packet['request_id'],)).fetchone()[0]
            source = contract['sources'][domain]
            require(request['payload'] == packet['plan'] and request['control_plane'] == domain
                    and request['release_sha256'] == source['release_sha256'], 'upstream admission differs')
            stored = c.execute('SELECT execution_store.read_plan(%s)', (source['plan_digest'],)).fetchone()[0]
            require(stored['payload'] == packet['plan'], 'upstream plan changed')
            definitions = {t.artifact_digest: json.loads(t.metric_contract)['historical']
                           for t in ExecutionPlan(stored['payload']).validate().tasks}
            tasks = {}
            for task in stored['payload']['tasks']:
                phase = definitions[task['task_digest']]['phase']
                if phase:
                    tasks.setdefault(phase, []).append(task)
            summary_phase = 'summary' if domain == 'learning' else 'observe-summary'
            summaries = [registered(c, stored, t, Path(cfg['runtime'])) for t in tasks.get(summary_phase, [])]
            summaries = [s for s in summaries if s is not None]
            require(len(summaries) == 1, 'historical batch summary not registered')
            summary, receipt = summaries[0]
            require(summary['scientific']['summary']['status'] == 'HISTORICAL_BATCH_COMPLETE', 'historical batch incomplete')
            output[summary_phase] = receipt
            if domain == 'learning':
                last_task = None
                for task in sorted(tasks.get('learn', []), key=lambda t: definitions[t['task_digest']]['index'], reverse=True):
                    row = c.execute('SELECT execution_store.read_result(%s)', (stored['bindings'][task['task_digest']],)).fetchone()[0]
                    if row['commit']:
                        last_task = task
                        break
                require(last_task is not None, 'no committed historical update')
                last = registered(c, stored, last_task, Path(cfg['runtime']))
                value, receipt = last; checkpoint = value['scientific']['after']; selected_index = value['index']
                output['learn'] = receipt
                require(checkpoint['count'] == selected_index+1 and value['scientific']['after_sha256'] == digest(checkpoint),
                        'registered checkpoint count/digest differs')
                wanted_phase = 'report'
            else:
                wanted_phase = 'observe'
            matches = []
            for task in tasks.get(wanted_phase, []):
                if definitions[task['task_digest']]['index'] != selected_index:
                    continue
                value = registered(c, stored, task, Path(cfg['runtime']))
                if value is not None:
                    matches.append(value)
            if not matches:
                return None
            require(len(matches) == 1, 'ambiguous registered source report')
            value, receipt = matches[0]; output[wanted_phase] = receipt
            if domain == 'learning':
                require(value['scientific']['checkpoint_sha256'] == digest(checkpoint), 'report checkpoint differs')
            else:
                require(value['scientific']['producer_report_sha256'] == output['report']['artifact_sha256'], 'observer consumed another report')
    return checkpoint, output


def verify_prefix(contract, root, checkpoint, rows):
    """Check every consumed label against current audited source; never fit."""
    raw = (root/'contract.json').read_bytes(); original = json.loads(raw)
    require(sha256(raw).hexdigest() == contract['historical_contract_sha256'], 'historical source contract changed')
    data = (root/'history.json').read_bytes()
    require(sha256(data).hexdigest() == original['history_sha256'], 'frozen historical labels changed')
    records = json.loads(data)
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(original['export_public_key'], validate=True))
    while len(records) < checkpoint['count']:
        envelope = json.loads((root/'incremental'/f'{len(records):05d}.json').read_bytes())
        key.verify(base64.b64decode(envelope['signature'], validate=True), canonical(envelope['body']))
        body = envelope['body']
        require(body['contract_sha256'] == contract['historical_contract_sha256'] and body['index'] == len(records)
                and body['previous_sha256'] == digest(records[-1]), 'historical incremental chain changed')
        records.append(body['record'])
    require(len(records) == checkpoint['count'] and records[-1]['label']['issue'] == checkpoint['training_end_issue']
            and digest(records[-1]) == checkpoint['last_input_sha256'], 'historical checkpoint prefix differs')
    current = {r['issue']: r for r in rows}; reds = [0]*33; blues = [0]*16
    for record in records:
        label = record['label']; row = current.get(label['issue'])
        require(row is not None and all(row[k] == label[k] for k in ('red', 'blue', 'draw_at')), 'source correction conflicts with learned prefix')
        for number in label['red']:
            reds[number-1] += 1
        blues[label['blue']-1] += 1
    require(reds == checkpoint['counts'] and blues == checkpoint['blue_counts'], 'checkpoint label conservation differs')


def gate(inputs, key, reason):
    body = {'contract_sha256': inputs.identity, 'observed_at': utcnow().isoformat(), 'reason': reason}
    data = signed(body, key, inputs.contract['export_public_key'])
    fd, name = tempfile.mkstemp(prefix='.gate-', dir=inputs.root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); os.fchmod(stream.fileno(), 0o640); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, inputs.root/'gate.json')
        fd = os.open(inputs.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_calendar(connection, source_root, target):
    from dehps.prediction.frozen_p3.calculation import validate_artifact
    rows = connection.execute('''SELECT artifact_digest, artifact_path FROM research_os_mainline_artifacts
        WHERE artifact_type = 'M4P3ForwardPrequentialCheckpoint' AND task_key LIKE %s''',
        ('%'+target['issue']+'-predraw',)).fetchall()
    if not rows:
        return False
    for identity, relative in rows:
        path = Path(source_root)/relative
        require(path.is_relative_to(Path(source_root)) and path.resolve() == path, 'calendar source path escaped')
        value = json.loads(path.read_bytes()); validate_artifact(value); body = value['body']
        require(value['artifact_digest'] == identity and body['target_issue'] == target['issue']
                and instant(body['official_draw_time']) == instant(target['draw_at'])
                and body['training_end_issue'] == target['previous_issue'], 'registered official calendar differs')
    return True


def publish(inputs, readers, source, key, source_root):
    require(utcnow() < instant(inputs.contract['approved_until']), 'notification publication expired')
    try:
        with source.connect() as connection:
            rows, receipt = audited_source(connection)
            calendars = {t['issue']: verify_calendar(connection, source_root, t) for t in inputs.contract['targets']
                         if rows[-1]['issue'] == t['previous_issue']}
        selected = source_checkpoint(inputs.contract, readers)
        if selected is None:
            gate(inputs, key, None)
            return {'status': 'WAITING_FOR_REGISTERED_OBSERVER'}
        checkpoint, records = selected
        verify_prefix(inputs.contract, Path(readers['learning']['inputs']), checkpoint, rows)
        by_issue = {r['issue']: r for r in rows}
        for target in inputs.contract['targets']:
            path = inputs.root/'checkpoints'/(target['issue']+'.json')
            if path.exists():
                # Existing exports are immutable, including their observation time.
                inputs.snapshot(target)
            elif target['previous_issue'] == checkpoint['training_end_issue'] and rows[-1]['issue'] == target['previous_issue'] and calendars.get(target['issue']) and utcnow() < instant(target['draw_at']):
                value = {'contract_sha256': inputs.identity, 'target_issue': target['issue'], 'observed_at': utcnow().isoformat(),
                         'checkpoint': checkpoint, 'checkpoint_sha256': digest(checkpoint), 'source_records': records,
                         'audit_sha256': digest(receipt)}
                append_bytes(path, signed(value, key, inputs.contract['export_public_key']))
            label_path = inputs.root/'labels'/(target['issue']+'.json')
            if label_path.exists():
                old = inputs.label(target)['label']; current = by_issue.get(target['issue'])
                require(current is not None and all(old[k] == current[k] for k in ('red', 'blue', 'draw_at')), 'published label correction')
            elif target['issue'] in by_issue:
                value = {'contract_sha256': inputs.identity, 'label': by_issue[target['issue']], 'receipt': receipt}
                require(instant(value['label']['draw_at']) == instant(target['draw_at']), 'official calendar differs')
                append_bytes(label_path, signed(value, key, inputs.contract['export_public_key']))
        gate(inputs, key, None)
        return {'status': 'SOURCE_VERIFIED', 'latest_learned_issue': checkpoint['training_end_issue']}
    except Exception as exc:
        if utcnow() < instant(inputs.contract['approved_until']):
            from dehps.execution.context import BoundaryError
            reason = 'SOURCE_CONFLICT' if isinstance(exc, BoundaryError) else 'SOURCE_UNREADABLE'
            error = {'at': utcnow().isoformat(), 'reason': reason, 'error_type': type(exc).__name__}
            append_bytes(inputs.root/'errors'/(digest(error)+'.json'), canonical(error))
            gate(inputs, key, reason)
        raise
