"""Registered report consumer with durable, per-issue conservative SMTP dedupe."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile

from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from dehps.notifications.mail import QqMailService
from .contract import SCHEMA, digest, instant, require, utcnow


def registered_emails(engine):
    manifest = engine.replay(require_complete=False)
    output = []
    with engine.store.verification_scope():
        for task in manifest.tasks:
            d = json.loads(task.metric_contract)['notification']
            if d['phase'] not in ('pre-replay', 'post-replay'):
                continue
            result = engine.store.result(engine.bindings[task.artifact_digest])
            if result is None:
                continue
            MainlineLedger(engine.store).verify(result.task['id'])
            value = json.loads(result.data)['value']
            require(value['status'] == 'REPLAY_VERIFIED', 'email replay missing')
            output.append({'kind': d['phase'].split('-')[0], 'issue': d['issue'],
                'artifact_sha256': value['envelope_sha256'], 'replay_sha256': result.artifact.sha256,
                'seal_status': value['seal']['status'], 'report': value['report']})
    return output


class Delivery:
    def __init__(self, path, config, contract, *, reauthorize, gate, mail=None):
        self.path = Path(path); self.config = config; self.contract = contract
        self.reauthorize = reauthorize; self.gate = gate; self.mail = mail or QqMailService(config)

    def key(self, message):
        # A changed artifact must not create a second send for the same issue.
        return digest({'protocol': SCHEMA, 'kind': message['kind'], 'issue': message['issue'],
                       'recipient_sha256': self.contract['recipient_sha256']})

    @contextmanager
    def lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix('.lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def read(self):
        if not self.path.exists():
            return {'schema': SCHEMA, 'deliveries': {}}
        value = json.loads(self.path.read_bytes())
        require(set(value) == {'schema', 'deliveries'} and value['schema'] == SCHEMA
                and isinstance(value['deliveries'], dict), 'mail ledger invalid')
        return value

    def write(self, value):
        fd, name = tempfile.mkstemp(prefix='.ledger-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def deliver(self, message):
        from hashlib import sha256
        require(sha256(self.config.destination.strip().lower().encode()).hexdigest() == self.contract['recipient_sha256'],
                'notification recipient differs')
        targets = {t['issue']: t for t in self.contract['targets']}; target = targets[message['issue']]
        require(message['kind'] in ('pre', 'post'), 'unknown mail kind')
        with self.lock():
            self.reauthorize()
            require(utcnow() < instant(self.contract['approved_until']), 'notification authorization expired')
            require(self.gate() is None, 'source gate prevents mail delivery')
            moment = utcnow()
            if message['kind'] == 'pre':
                if not instant(target['send_at']) <= moment < instant(target['draw_at']):
                    return {'status': 'PENDING_DELIVERY' if moment < instant(target['send_at']) else 'MISSED_PRE_DELIVERY'}
                require(message['seal_status'] == 'SEALED_BEFORE_DRAW', 'no sealed forecast to deliver')
            else:
                require(moment >= instant(target['draw_at']), 'result cannot be delivered before draw')
            state = self.read(); key = self.key(message); old = state['deliveries'].get(key)
            if old:
                require(old['artifact_sha256'] == message['artifact_sha256'] and old['replay_sha256'] == message['replay_sha256'],
                        'delivery artifact changed; retained prior send')
                require(old['status'] == 'sent', 'previous SMTP outcome uncertain; reconciliation required')
                return {'status': 'ALREADY_SENT', 'issue': message['issue'], 'kind': message['kind']}
            row = {k: message[k] for k in ('kind', 'issue', 'artifact_sha256', 'replay_sha256')}
            row.update(status='sending', started_at=moment.isoformat(), recipient_sha256=self.contract['recipient_sha256'])
            state['deliveries'][key] = row; self.write(state)
            try:
                # Check immediately before crossing the external side-effect boundary.
                self.reauthorize()
                require(utcnow() < instant(self.contract['approved_until']), 'mail admission expired before SMTP')
                if message['kind'] == 'pre':
                    require(utcnow() < instant(target['draw_at']), 'mail crossed draw deadline')
                receipt = self.mail.send(subject=message['report']['subject'], text=message['report']['text'],
                                         html=message['report']['html'], recipient=self.config.destination)
            except BaseException:
                row.update(status='uncertain', completed_at=utcnow().isoformat()); self.write(state)
                raise
            row.update(status='sent', completed_at=utcnow().isoformat(), message_id=receipt.message_id)
            self.write(state)
            return {'status': 'SENT', 'issue': message['issue'], 'kind': message['kind']}
