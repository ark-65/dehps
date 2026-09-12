"""Trusted input publication, separate from prediction execution.

The caller supplies a dedicated readonly source connection and the approved
signing key. Workers never receive either. Publication cannot register tasks,
approve requests, fit a model, or assert a runtime completion.
"""
import base64
from datetime import datetime, time, timezone
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

from dehps.draw_sync.audit import DrawDatabaseAuditor
from dehps.execution.release import canonical
from .contract import Inputs, digest, instant, require, validate_label

SHANGHAI = ZoneInfo('Asia/Shanghai')


def append_bytes(path: Path, data: bytes):
    """fsync + no-clobber link: retries and concurrent publishers are identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush()
            # Operator-provisioned setgid input directories grant the consuming
            # domain read access; worker mounts remain readonly. No world access.
            os.fchmod(stream.fileno(), 0o640)
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            require(path.read_bytes() == data, 'immutable publication conflicts: ' + path.name)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def signed(body, key, public_key):
    require(base64.b64encode(key.public_key().public_bytes_raw()).decode() == public_key,
            'publisher key differs from frozen public key')
    return canonical({'body': body, 'signature': base64.b64encode(key.sign(canonical(body))).decode()})


def audited_source(connection, *, before_issue=None):
    """Read one consistent source snapshot; preserve raw audit receipt separately.

    SET TRANSACTION READ ONLY protects the source even with an incorrectly
    provisioned role. Deployment must additionally grant SELECT only.
    """
    connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    rows = connection.execute('SELECT issue, draw_date, red_numbers, blue_number FROM ssq_history ORDER BY issue').fetchall()
    audit = DrawDatabaseAuditor().audit(tuple((str(r[0]), tuple(r[2]), r[3]) for r in rows))
    require(audit.passed and all(r[3] is not None for r in rows), 'source history audit failed/incomplete blue labels')
    event = connection.execute('''
        SELECT e.event_key, e.history_fingerprint, e.audit_report_hash, r.run_key, r.completed_at
        FROM draw_issue_events e JOIN draw_sync_runs r ON r.event_key = e.event_key
        WHERE e.new_issue = %s AND r.audit_passed IS TRUE AND r.status = 'new_issue'
          AND r.completed_at IS NOT NULL AND e.history_fingerprint = %s
        ORDER BY r.completed_at ASC, r.run_key ASC LIMIT 1
    ''', (audit.latest_issue, audit.history_fingerprint)).fetchone()
    require(event is not None, 'current history has no matching durable audited event')
    observed = datetime.now(timezone.utc)
    require(event[4] <= observed, 'future source audit')
    receipt = {'schema': 'forward-source-audit.v1', 'observed_at': observed.isoformat(),
        'event_key': str(event[0]), 'history_fingerprint': event[1], 'audit_report_hash': event[2],
        'run_key': str(event[3]), 'completed_at': event[4].isoformat(), 'latest_issue': audit.latest_issue,
        'rows': [{'issue': str(r[0]), 'draw_date': r[1].isoformat(), 'red': list(r[2]), 'blue': r[3]} for r in rows]}
    audit_sha = digest(receipt)
    labels = [validate_label({'issue': r['issue'],
              'draw_at': datetime.combine(datetime.fromisoformat(r['draw_date']).date(), time(21, 15), SHANGHAI).isoformat(),
              # Conservatively use this export observation, never invent earlier
              # point-in-time availability for historical rows.
              'available_at': observed.isoformat(), 'red': r['red'], 'blue': r['blue'], 'audit_sha256': audit_sha})
              for r in receipt['rows'] if before_issue is None or r['issue'] < before_issue]
    return labels, receipt


def publish_labels(inputs: Inputs, labels, receipt, key, *, approved_until):
    now = datetime.now(timezone.utc)
    require(now < instant(approved_until), 'publisher authorization window expired')
    targets = {t['issue']: t for t in inputs.contract['targets']}
    receipt_sha = digest(receipt)
    published = []
    for row in labels:
        if row['issue'] not in targets:
            continue
        target = targets[row['issue']]
        validate_label(row, target=target)
        require(row['audit_sha256'] == receipt_sha and instant(row['available_at']) <= now,
                'unbound/future exported label')
        path = inputs.root/'opened'/f'{row["issue"]}.json'
        if path.exists():
            previous = inputs.opened(target, now=now)
            require(all(previous[k] == row[k] for k in ('issue', 'draw_at', 'red', 'blue')),
                    'source correction conflicts with already published label')
            continue
        body = {'contract_sha256': inputs.contract_sha256, 'label': row}
        append_bytes(inputs.root/'receipts'/f'{receipt_sha}.json', canonical(receipt))
        append_bytes(path, signed(body, key, inputs.contract['export_public_key']))
        published.append(row['issue'])
    return published


def publish_observation(inputs: Inputs, learning_engine, issue, key, *, approved_until):
    """Only a verified producer ledger can produce a signed observer input.

    The injected engine is read-only: prefix replay verifies registered artifacts
    and all upstream calculations. Status JSON and hand-written reports are not
    accepted. The observer still recalculates before committing in its own DB.
    """
    with learning_engine.store.verification_scope():
        return _publish_observation(inputs, learning_engine, issue, key, approved_until=approved_until)


def _publish_observation(inputs, learning_engine, issue, key, *, approved_until):
    require(datetime.now(timezone.utc) < instant(approved_until), 'publisher authorization window expired')
    manifest = learning_engine.replay(require_complete=False)
    records = {}
    for task in manifest.tasks:
        definition = json.loads(task.metric_contract)['forward']
        if definition['issue'] != issue or definition['phase'] not in {'seal', 'score', 'report'}:
            continue
        require(definition['contract_sha256'] == inputs.contract_sha256, 'producer study differs')
        task_id = learning_engine.bindings[task.artifact_digest]
        result = learning_engine.store.result(task_id)
        if result is None:
            return False
        learning_engine.ledger.verify(task_id)
        records[definition['phase']] = (result, learning_engine.ledger.context(task_id))
    require(set(records) == {'seal', 'score', 'report'}, 'producer issue not in plan')
    report, ledger = records['report']
    value = json.loads(report.data)['scientific']
    body = {'contract_sha256': inputs.contract_sha256, 'issue': issue,
        'seal': json.loads(records['seal'][0].data)['scientific'],
        'score': json.loads(records['score'][0].data)['scientific'], 'next_checkpoint': value['next_checkpoint'],
        'report_sha256': report.artifact.sha256, 'producer_committed_at': ledger['commit']['created_at'],
        'window_analysis': value['window_analysis']}
    append_bytes(inputs.root/'observations'/f'{issue}.json', signed(body, key, inputs.contract['export_public_key']))
    append_bytes(inputs.root/'reports'/f'{issue}.md', value['text'].encode('utf-8'))
    return True
