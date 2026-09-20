"""Closed operational contract. Existing estimators and research contracts stay fixed."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.prediction.forward_learning.contract import digest, instant, require, validate_label
from dehps.prediction.historical_learning.contract import sha

SCHEMA = 'historical-learning-mail.v1'
PHASES = ('seal', 'pre-report', 'pre-replay', 'result', 'post-report', 'post-replay')
POLICY = {'model': 'shrink900', 'tickets': 100, 'pool_size': 10000,
          'blue_training': False, 'promotion': False, 'conclusion': '证据不足',
          'pre_hour': 17, 'post_poll_seconds': 900, 'timezone': 'Asia/Shanghai'}


def utcnow():
    return datetime.now(timezone.utc)


def validate(value):
    require(set(value) == {'schema', 'policy', 'historical_contract_sha256', 'sources',
                          'targets', 'recipient_sha256', 'export_public_key', 'approved_until'},
            'closed notification contract required')
    require(value['schema'] == SCHEMA and value['policy'] == POLICY, 'notification policy differs')
    sha(value['historical_contract_sha256']); sha(value['recipient_sha256'])
    require(set(value['sources']) == {'learning', 'observer'}, 'both source domains required')
    for source in value['sources'].values():
        require(set(source) == {'plan_digest', 'release_sha256'}, 'closed source binding required')
        sha(source['plan_digest']); sha(source['release_sha256'])
    require(len(base64.b64decode(value['export_public_key'], validate=True)) == 32, 'signing key invalid')
    targets = value['targets']; require(0 < len(targets) <= 32, 'bounded target calendar required')
    prior = None
    for target in targets:
        require(set(target) == {'issue', 'previous_issue', 'draw_at', 'send_at'}, 'closed target required')
        require(all(isinstance(target[k], str) and re.fullmatch('[0-9]{7}', target[k])
                    for k in ('issue', 'previous_issue')), 'invalid issue')
        draw, send = instant(target['draw_at']), instant(target['send_at'])
        local = send.astimezone(ZoneInfo(POLICY['timezone']))
        require(target['previous_issue'] < target['issue'] and send < draw < instant(value['approved_until'])
                and local.hour == 17 and local.minute == local.second == 0
                and local.weekday() in (1, 3, 6) and local.date() == draw.astimezone(local.tzinfo).date(),
                'target time/cutoff invalid')
        if prior:
            require(target['previous_issue'] == prior['issue'] and instant(prior['draw_at']) < send,
                    'target calendar order differs')
        prior = target
    return value


class Inputs:
    def __init__(self, root, expected):
        self.root = Path(root); self.identity = sha(expected)
        self.contract = validate(self.read_contract())

    def read_contract(self):
        value = json.loads((self.root/'contract.json').read_bytes())
        require(digest(value) == self.identity, 'notification contract changed')
        return value

    def read(self, relative):
        self.read_contract()
        path = self.root/relative
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        require(set(value) == {'body', 'signature'}, 'signed source envelope required')
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(self.contract['export_public_key'], validate=True))
            key.verify(base64.b64decode(value['signature'], validate=True), canonical(value['body']))
        except Exception as exc:
            raise BoundaryError('notification source signature invalid') from exc
        require(value['body']['contract_sha256'] == self.identity, 'notification source contract differs')
        return value['body']

    def snapshot(self, target):
        value = self.read('checkpoints/'+target['issue']+'.json')
        if value is None:
            return None
        require(set(value) == {'contract_sha256', 'target_issue', 'observed_at', 'checkpoint',
                              'checkpoint_sha256', 'source_records', 'audit_sha256'}, 'closed checkpoint export required')
        cp = value['checkpoint']
        require(value['target_issue'] == target['issue'] and cp['training_end_issue'] == target['previous_issue']
                and digest(cp) == value['checkpoint_sha256'], 'checkpoint issue/digest differs')
        require(set(cp) == {'count', 'counts', 'blue_counts', 'training_end_issue', 'last_input_sha256'},
                'closed sufficient checkpoint required')
        from dehps.prediction.forward_learning.calculation import probabilities
        probabilities(cp['counts'], cp['count'])
        require(len(cp['blue_counts']) == 16 and all(type(x) is int and x >= 0 for x in cp['blue_counts'])
                and sum(cp['blue_counts']) == cp['count'], 'complete blue labels required')
        require(instant(value['observed_at']) < instant(target['draw_at']), 'checkpoint exported after draw')
        require(set(value['source_records']) == {'learn', 'report', 'summary', 'observe', 'observe-summary'},
                'complete producer and independent consumer registrations required')
        for record in value['source_records'].values():
            require(set(record) == {'artifact_sha256', 'registration_digest', 'completed_event_digest', 'committed_at'},
                    'closed source registration required')
            for field in ('artifact_sha256', 'registration_digest', 'completed_event_digest'):
                sha(record[field])
            require(instant(record['committed_at']) <= instant(value['observed_at']), 'future source commit')
        sha(value['audit_sha256'])
        return value

    def label(self, target):
        value = self.read('labels/'+target['issue']+'.json')
        if value is None:
            return None
        require(set(value) == {'contract_sha256', 'label', 'receipt'}, 'closed label export required')
        label = validate_label(value['label'])
        require(label['issue'] == target['issue'] and instant(label['draw_at']) == instant(target['draw_at'])
                and digest(value['receipt']) == label['audit_sha256'], 'draw source binding differs')
        rows = [r for r in value['receipt']['rows'] if r['issue'] == target['issue']]
        require(len(rows) == 1 and rows[0]['red'] == label['red'] and rows[0]['blue'] == label['blue']
                and rows[0]['draw_date'] == instant(target['draw_at']).date().isoformat(), 'draw conflicts with audit')
        require(instant(value['receipt']['completed_at']) <= instant(value['receipt']['observed_at'])
                <= instant(label['available_at']) <= utcnow(), 'draw availability invalid')
        return value

    def gate(self):
        if utcnow() >= instant(self.contract['approved_until']):
            return 'AUTHORIZATION_REQUIRED'
        gate = self.read('gate.json')
        if gate is None:
            return 'WAITING_FOR_SOURCE_CHECK'
        require(set(gate) == {'contract_sha256', 'observed_at', 'reason'}, 'closed source gate required')
        if not 0 <= (utcnow()-instant(gate['observed_at'])).total_seconds() <= 1200:
            return 'WAITING_FOR_SOURCE_CHECK'
        require(gate['reason'] in (None, 'SOURCE_CONFLICT', 'SOURCE_UNREADABLE', 'FORMAL_TASK_RUNNING'),
                'invalid gate reason')
        return gate['reason']
