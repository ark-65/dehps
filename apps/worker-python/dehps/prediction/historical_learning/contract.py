"""Content-bound history and authenticated, ordered incremental inputs."""
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from dehps.execution.context import BoundaryError
from dehps.execution.release import canonical
from dehps.prediction.forward_learning.contract import digest, instant, require, validate_label

SCHEMA = 'historical-report-learning.v1'
POLICY = {'model': 'shrink900', 'alpha': 900, 'controls': ['old', 'uniform'],
          'minimum_history': 900, 'pool_size': 10000, 'tickets': 100, 'seed': 20260905,
          'blue_training': False, 'promotion': False, 'incremental_slots': 32,
          'admission_days': 30, 'batch_budget_seconds': 86400, 'poll_seconds': 900}

# Operational dispatch policy, not a change to the frozen scientific inputs.
FORMAL_PRIORITY_TIMEZONE = ZoneInfo('Asia/Shanghai')


def formal_priority_active(now=None):
    local = (now if now is not None else datetime.now(timezone.utc)).astimezone(FORMAL_PRIORITY_TIMEZONE)
    return 18 <= local.hour < 22


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'invalid input digest')
    return value


def validate_contract(value):
    require(set(value) == {'schema', 'policy', 'created_at', 'history_sha256', 'issues',
                           'export_public_key', 'provenance_sha256'}, 'closed historical contract required')
    require(value['schema'] == SCHEMA and value['policy'] == POLICY, 'fixed historical policy changed')
    sha(value['history_sha256']); sha(value['provenance_sha256'])
    require(instant(value['created_at']) <= datetime.now(timezone.utc), 'future contract')
    issues = value['issues']
    require(isinstance(issues, list) and len(issues) > 900
            and all(isinstance(i, str) and re.fullmatch('[0-9]{7}', i) for i in issues)
            and issues == sorted(set(issues)), 'historical issues duplicate, unordered or incomplete')
    require(len(base64.b64decode(value['export_public_key'], validate=True)) == 32, 'public key required')
    return value


class Inputs:
    def __init__(self, root: Path, contract_sha256: str):
        self.root = Path(root)
        self.contract_sha256 = sha(contract_sha256)
        self.contract = validate_contract(self.hashed('contract.json', contract_sha256))
        self.history = self.hashed('history.json', self.contract['history_sha256'])
        self.provenance = self.hashed('provenance.json', self.contract['provenance_sha256'])
        require(isinstance(self.history, list) and len(self.history) == len(self.contract['issues']), 'history count differs')
        previous = None
        for index, record in enumerate(self.history):
            self.validate_record(record)
            row = record['label']
            require(row['issue'] == self.contract['issues'][index], 'frozen issue differs')
            require(instant(row['available_at']) <= instant(self.contract['created_at']), 'unopened historical input')
            if previous:
                require(instant(previous['draw_at']) < instant(row['draw_at']), 'unordered historical draw')
            previous = row
        # Every archived machine/report source is content addressed. Text is never
        # interpreted by the estimator or treated as an instruction.
        for reference in self.provenance['sources']:
            self.blob(reference['sha256'])

    def hashed(self, name, expected):
        data = (self.root / name).read_bytes()
        require(sha256(data).hexdigest() == sha(expected), 'admitted input changed: ' + name)
        return json.loads(data)

    def blob(self, expected):
        data = (self.root/'sources'/sha(expected)).read_bytes()
        require(sha256(data).hexdigest() == expected, 'archived source corrupt')
        return data

    def verify_frozen_identity(self):
        for name, expected in (('contract.json', self.contract_sha256), ('history.json', self.contract['history_sha256']),
                               ('provenance.json', self.contract['provenance_sha256'])):
            require(sha256((self.root/name).read_bytes()).hexdigest() == expected, 'frozen historical input changed: '+name)

    def issue(self, index):
        """Projection convenience only; committed verification uses record()."""
        if index < len(self.history):
            return self.contract['issues'][index]
        body = self.signed(f'incremental/{index:05d}.json')
        require(body is not None, 'committed incremental input missing')
        return body['record']['label']['issue']

    def validate_record(self, record):
        require(set(record) == {'label', 'references'}, 'closed historical record required')
        row = validate_label(record['label'])
        require(isinstance(record['references'], list), 'reference list required')
        for ref in record['references']:
            require(set(ref) == {'kind', 'sha256', 'source', 'model', 'issue'}, 'closed source reference required')
            require(ref['kind'] in {'ORIGINAL_PREDICTION', 'HISTORICAL_EVALUATION', 'POST_DRAW_REPORT'}, 'invalid reference kind')
            require(ref['issue'] == row['issue'] and isinstance(ref['source'], str)
                    and isinstance(ref['model'], str), 'original source identity differs')
            require(not (row['issue'] == '2026104' and ref['kind'] == 'ORIGINAL_PREDICTION'), '2026104 original prediction gap is immutable')
            self.blob(ref['sha256'])
        receipt = self.hashed('receipts/'+row['audit_sha256']+'.json', row['audit_sha256'])
        require(receipt['schema'] == 'forward-source-audit.v1', 'audited machine source required')
        matches = [r for r in receipt['rows'] if r['issue'] == row['issue']]
        require(len(matches) == 1 and matches[0]['red'] == row['red'] and matches[0]['blue'] == row['blue']
                and matches[0]['draw_date'] == instant(row['draw_at']).date().isoformat(), 'label conflicts with source receipt')
        require(instant(receipt['completed_at']) <= instant(receipt['observed_at']) <= instant(row['available_at']), 'invalid source availability')
        return record

    def signed(self, name):
        path = self.root/name
        if not path.exists():
            return None
        envelope = json.loads(path.read_bytes())
        require(set(envelope) == {'body', 'signature'}, 'signed envelope required')
        try:
            key = Ed25519PublicKey.from_public_bytes(base64.b64decode(self.contract['export_public_key'], validate=True))
            key.verify(base64.b64decode(envelope['signature'], validate=True), canonical(envelope['body']))
        except (InvalidSignature, ValueError) as exc:
            raise BoundaryError('historical input signature invalid') from exc
        require(envelope['body']['contract_sha256'] == self.contract_sha256, 'signed input belongs to another contract')
        return envelope['body']

    def record(self, index):
        require(900 <= index < len(self.history)+POLICY['incremental_slots'], 'input index outside admitted plan')
        if index < len(self.history):
            record = self.history[index]
            self.validate_record(record)
        else:
            body = self.signed(f'incremental/{index:05d}.json')
            if body is None:
                return None
            require(set(body) == {'contract_sha256', 'index', 'previous_sha256', 'record'} and body['index'] == index,
                    'incremental slot binding differs')
            previous = self.history[-1] if index == len(self.history) else self.record(index-1)
            require(previous is not None and digest(previous) == body['previous_sha256'], 'incremental predecessor missing or changed')
            record = body['record']
            self.validate_record(record)
            row, prior = record['label'], previous['label']
            require(prior['issue'] < row['issue'] and instant(prior['draw_at']) < instant(row['draw_at']), 'duplicate or unordered incremental input')
            receipt = self.hashed('receipts/'+row['audit_sha256']+'.json', row['audit_sha256'])
            between = [r['issue'] for r in receipt['rows'] if prior['issue'] < r['issue'] <= row['issue']]
            require(between == [row['issue']], 'incremental input skipped an audited issue')
        require(instant(record['label']['available_at']) <= datetime.now(timezone.utc), 'label is not yet available')
        return record

    def observation(self, index):
        return self.signed(f'observations/{index:05d}.json')

    def gate(self):
        body = self.signed('dispatch.json')
        if body is None:
            return 'WAITING_FOR_SOURCE_CHECK'
        require(set(body) == {'contract_sha256', 'observed_at', 'approved_until', 'reason'}, 'closed dispatch observation required')
        now = datetime.now(timezone.utc)
        if now >= instant(body['approved_until']):
            return 'AUTHORIZATION_REQUIRED'
        age = (now-instant(body['observed_at'])).total_seconds()
        if not 0 <= age <= 1200:
            return 'WAITING_FOR_SOURCE_CHECK'
        require(body['reason'] in {None, 'FORMAL_TASK_RUNNING', 'SOURCE_CONFLICT', 'SOURCE_UNREADABLE'}, 'invalid dispatch reason')
        # Only the resource deferral expires outside the protected window. A
        # signed source error must never be cleared by a time-of-day allowance.
        if body['reason'] in {'SOURCE_CONFLICT', 'SOURCE_UNREADABLE'}:
            return body['reason']
        if not formal_priority_active(now):
            return None
        return self.formal_guard(now=now) or body['reason']

    def formal_guard(self, *, now=None):
        if not formal_priority_active(now):
            return None
        # Operator binds the host user-service cgroup directory read-only here.
        # Actual process membership is checked before EACH dispatch, without
        # acquiring a production lock or changing a formal unit. Inactive
        # oneshot units have no cgroup directory. The parent mount must exist.
        groups = self.root/'formal-cgroups'
        if not groups.is_dir():
            return 'MISSING_FORMAL_DISPATCH_GUARD'
        for unit in ('dehps-forward-prequential-successor', 'dehps-m4-p4-forward-prequential-armed',
                     'dehps-p3-top100-pre-draw-mail', 'dehps-p3-top100-post-draw-mail'):
            path = groups/(unit+'.service')/'cgroup.procs'
            try:
                if path.read_text().strip():
                    return 'FORMAL_TASK_RUNNING'
            except FileNotFoundError:
                pass
        return None
