"""Closed scientific contract and signed, append-only input envelopes."""
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical

SCHEMA = 'forward-learning.v1'
POLICY = {'model': 'shrink900', 'alpha': 900, 'controls': ['old', 'uniform'],
          'minimum_history': 900, 'cohort_size': 60, 'pool_size': 10000, 'tickets': 100,
          'seed': 20260905, 'bootstrap_replicates': 4000, 'block_length': 13,
          'family_contrasts': 8, 'calibration_bins': 20, 'promotion': False}


def require(condition, message):
    if not condition:
        raise BoundaryError(message)


def digest(value):
    return sha256(canonical(value)).hexdigest()


def instant(value):
    require(isinstance(value, str), 'explicit timestamp required')
    result = datetime.fromisoformat(value)
    require(result.tzinfo is not None, 'timestamp timezone required')
    return result


def validate_calendar_times(cutoff, draw):
    require(cutoff.utcoffset().total_seconds() == 28800 and cutoff.hour == 17 and cutoff.minute == 0
            and cutoff.second == 0 and cutoff.microsecond == 0, 'canonical 17:00 cutoff required')
    require(draw.utcoffset().total_seconds() == 28800 and (draw.hour, draw.minute, draw.second) == (21, 15, 0)
            and draw.microsecond == 0, 'canonical 21:15 draw required')


def validate_contract(value):
    require(set(value) == {'schema', 'policy', 'targets', 'created_at', 'initial_sha256',
                           'calendar_sha256', 'calendar_source_sha256', 'export_public_key'}, 'closed forward contract required')
    require(value['schema'] == SCHEMA and value['policy'] == POLICY, 'frozen learning policy changed')
    created = instant(value['created_at'])
    require(created <= datetime.now(timezone.utc), 'future contract creation')
    for key in ('initial_sha256', 'calendar_sha256', 'calendar_source_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', value[key]) is not None, 'input digest required')
    require(len(base64.b64decode(value['export_public_key'], validate=True)) == 32, 'Ed25519 key required')
    targets = value['targets']
    require(len(targets) == 60, 'exactly 60 fixed targets required')
    previous = None
    for target in targets:
        require(set(target) == {'issue', 'deadline', 'draw_at'}, 'closed calendar target required')
        require(re.fullmatch('[0-9]{7}', target['issue']) is not None, 'invalid target issue')
        cutoff, draw = instant(target['deadline']), instant(target['draw_at'])
        require(created < cutoff < draw and cutoff.date() == draw.date(), 'calendar/seal order invalid')
        validate_calendar_times(cutoff, draw)
        if previous:
            require(previous['issue'] < target['issue'] and instant(previous['draw_at']) < cutoff,
                    'calendar targets duplicate or unordered')
        previous = target
    require(digest(targets) == value['calendar_sha256'], 'frozen calendar digest changed')
    return value


def validate_label(row, *, target=None):
    required = {'issue', 'draw_at', 'available_at', 'red', 'blue', 'audit_sha256'}
    require(set(row) == required, 'closed audited label required')
    require(isinstance(row['issue'], str) and re.fullmatch('[0-9]{7}', row['issue']), 'invalid label issue')
    require(isinstance(row['red'], list) and len(row['red']) == 6
            and all(type(n) is int for n in row['red'])
            and row['red'] == sorted(set(row['red'])) and 1 <= row['red'][0] < row['red'][-1] <= 33,
            'invalid complete red label')
    require(type(row['blue']) is int and 1 <= row['blue'] <= 16, 'invalid blue label')
    require(re.fullmatch('[0-9a-f]{64}', row['audit_sha256']) is not None, 'audit identity missing')
    require(instant(row['draw_at']) <= instant(row['available_at']), 'label available before draw')
    if target is not None:
        require(row['issue'] == target['issue'] and instant(row['draw_at']) == instant(target['draw_at']),
                'audited label conflicts with frozen calendar')
    return row


class Inputs:
    def __init__(self, root: Path, contract_sha256: str):
        self.root = root
        self.contract_sha256 = contract_sha256
        self.contract = validate_contract(self.hashed('contract.json', contract_sha256))
        self.calendar_source()

    def calendar_source(self):
        require(sha256((self.root/'calendar-source').read_bytes()).hexdigest() == self.contract['calendar_source_sha256'],
                'frozen calendar source bytes changed')

    def hashed(self, name, expected):
        data = (self.root / name).read_bytes()
        require(sha256(data).hexdigest() == expected, 'admitted input bytes changed: ' + name)
        return json.loads(data)

    def initial(self):
        rows = self.hashed('initial.json', self.contract['initial_sha256'])
        require(isinstance(rows, list) and len(rows) >= 900, 'insufficient initial history')
        previous = None
        for row in rows:
            validate_label(row)
            require(instant(row['available_at']) <= instant(self.contract['created_at']), 'initial future availability')
            require(row['issue'] < self.contract['targets'][0]['issue'], 'initial history includes target')
            if previous:
                require(previous['issue'] < row['issue'] and instant(previous['draw_at']) < instant(row['draw_at']),
                        'initial history duplicate or unordered')
            previous = row
        return rows

    def opened(self, target, *, now):
        self.hashed('contract.json', self.contract_sha256)
        path = self.root / 'opened' / (target['issue'] + '.json')
        if not path.exists():
            return None
        envelope = json.loads(path.read_bytes())
        require(set(envelope) == {'body', 'signature'}, 'signed input envelope required')
        body = envelope['body']
        require(set(body) == {'contract_sha256', 'label'}, 'closed signed outcome body required')
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(self.contract['export_public_key'], validate=True))
            key.verify(base64.b64decode(envelope['signature'], validate=True), canonical(body))
        except (InvalidSignature, ValueError) as exc:
            raise BoundaryError('outcome signature invalid') from exc
        require(body['contract_sha256'] == self.contract_sha256, 'outcome belongs to another study')
        row = validate_label(body['label'], target=target)
        require(instant(row['available_at']) <= now, 'outcome is not yet audited/available')
        return row

    def observation(self, issue):
        require(issue in {t['issue'] for t in self.contract['targets']}, 'observation issue outside cohort')
        path = self.root / 'observations' / (issue + '.json')
        if not path.exists():
            return None
        envelope = json.loads(path.read_bytes())
        require(set(envelope) == {'body', 'signature'}, 'signed observation required')
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(self.contract['export_public_key'], validate=True))
        try:
            key.verify(base64.b64decode(envelope['signature'], validate=True), canonical(envelope['body']))
        except (InvalidSignature, ValueError) as exc:
            raise BoundaryError('observation signature invalid') from exc
        body = envelope['body']
        require(set(body) == {'contract_sha256', 'issue', 'seal', 'score', 'next_checkpoint',
                              'report_sha256', 'producer_committed_at', 'window_analysis'}, 'closed observation body required')
        require(body['contract_sha256'] == self.contract_sha256 and body['issue'] == issue,
                'observation study/issue mismatch')
        require(re.fullmatch('[0-9a-f]{64}', body['report_sha256']) is not None, 'producer report identity missing')
        return body
