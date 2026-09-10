"""Existing frozen decision/report computation registered through the new entry."""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json

from dehps.execution.context import BoundaryError
from dehps.execution.coordinator import Capability
from dehps.execution.ledger import MainlineLedger
from dehps.execution.release import canonical
from dehps.prediction.frozen_p3 import observation, report

SCHEMA = 'prediction-observation-result.v1'
CAPABILITIES = {'record':'prediction-observation-record.v1','report':'prediction-observation-report.v1'}


def build_capabilities(plan,store,context):
    manifest = plan.validate()
    tasks = {task.artifact_digest:task for task in manifest.tasks}
    contracts = {}
    captured = {}
    for digest, task in tasks.items():
        contract = json.loads(task.metric_contract)['observation']
        phase = contract['phase']
        expected = {'phase','issue','frozen_sha256'} | ({'opened_sha256'} if phase == 'report' else set())
        if phase not in CAPABILITIES or set(contract) != expected or task.requested_capability != CAPABILITIES[phase]:
            raise BoundaryError('observation phase/capability contract mismatch')
        digests = {contract[key] for key in contract if key.endswith('_sha256')}
        if not digests.issubset(set(task.input_artifact_digests)):
            raise BoundaryError('observation input identity absent from canonical task')
        contracts[digest] = contract

    def read(name,expected):
        data = (context.inputs / name).read_bytes()
        if sha256(data).hexdigest() != expected:
            raise BoundaryError('observation input file changed')
        return json.loads(data)

    def frozen(contract):
        raw = read('frozen.json',contract['frozen_sha256'])
        raw['predraw'] = report.PredrawBundle(**raw['predraw'])
        result = observation.FrozenInputs(**raw)
        if result.predraw.issue != contract['issue']:
            raise BoundaryError('observation issue differs from frozen prediction')
        observation.verify_frozen(result,code_root=context.code_root)
        return result

    def render(contract,record):
        inputs = frozen(contract)
        opened = read('opened.json',contract['opened_sha256'])
        if set(opened) != {'settlement','settlement_replay','payout','available_at'}:
            raise BoundaryError('closed opened outcome input required')
        bundle = report.PostdrawBundle(inputs.predraw,opened['settlement'],opened['settlement_replay'])
        value = observation.build_preview(record,bundle,opened['payout'],code_root=context.code_root,
                                           available_at=opened['available_at'])
        if value['status'] != 'OFFLINE_VERIFIED':
            raise BoundaryError('complete diagnostic report required for this capability')
        if len(value['diagnosis']['all_100_tickets']) != 100:
            raise BoundaryError('incomplete Top-100 diagnostics')
        return value

    def parent(binding):
        # Read actual committed parents, not an embedded caller-supplied record.
        parents = MainlineLedger(store).context(binding['id'])['parents']
        if len(parents) != 1 or parents[0]['commit'] is None:
            raise BoundaryError('one committed decision parent required')
        result = store.result(parents[0]['task_id'])
        if result is None:
            raise BoundaryError('decision parent unavailable')
        value = json.loads(result.data)
        if value['phase'] != 'record':
            raise BoundaryError('report parent is not a decision')
        return result,value['scientific']

    def verify(binding,data):
        contract = contracts[binding['task_digest']]
        value = json.loads(data)
        phase = contract['phase']
        fields = {'schema','phase','issue','task_digest','release_sha256','scientific'}
        if phase == 'report': fields.add('record_artifact_sha256')
        if (set(value) != fields or value['schema'] != SCHEMA or value['phase'] != phase
                or value['issue'] != contract['issue'] or value['task_digest'] != binding['task_digest']
                or value['release_sha256'] != binding['release_sha256'] or binding['artifact_schema'] != SCHEMA):
            raise BoundaryError('observation result binding mismatch')
        inputs = frozen(contract)
        if inputs.source['artifact_digest'] != binding['scientific_contract_sha256']:
            raise BoundaryError('frozen scientific contract mismatch')
        if phase == 'record':
            restored = observation.restore_decision(value['scientific'],code_root=context.code_root)
            instant = datetime.fromisoformat(value['scientific']['body']['recorded_at'])
            if asdict(restored) != asdict(inputs) or instant > datetime.now(timezone.utc):
                raise BoundaryError('decision input or actual creation time mismatch')
            # Reconstruct deterministic metadata for verification only; no new
            # record is persisted. restore_decision checks the original clock
            # fields separately. A resealed claim of predictive success, altered
            # mechanism or registration status must not pass readonly replay.
            expected = observation.capture_decision(inputs,code_root=context.code_root)['body']
            stable = lambda body: {key:item for key,item in body.items()
                                   if key not in {'recorded_at','record_mode'}}
            if stable(value['scientific']['body']) != stable(expected):
                raise BoundaryError('decision metadata differs from frozen calculation')
            persisted = MainlineLedger(store).context(binding['id'])
            if persisted['commit'] is None:
                # Only this capability's actual, current-clock capture may be
                # submitted. A caller cannot reseal an old timestamp as a new
                # observation, including before the first durable commit.
                if captured.get(binding['task_digest']) != sha256(canonical(value['scientific'])).hexdigest():
                    raise BoundaryError('decision was not captured by this execution')
            elif not (datetime.fromisoformat(persisted['attempt']['created_at']) <= instant
                      <= datetime.fromisoformat(persisted['commit']['created_at'])):
                raise BoundaryError('decision time is outside its durable attempt')
        else:
            committed,record = parent(binding)
            if value['record_artifact_sha256'] != committed.artifact.sha256 or value['scientific'] != render(contract,record):
                raise BoundaryError('report/committed decision replay mismatch')

    def execute(task,parents,artifacts):
        contract = contracts[task.artifact_digest]
        phase = contract['phase']
        value = {'schema':SCHEMA,'phase':phase,'issue':contract['issue'],
                 'task_digest':task.artifact_digest,'release_sha256':context.release.digest}
        if phase == 'record':
            if parents:
                raise BoundaryError('decision capture must not consume outcome parents')
            value['scientific'] = observation.capture_decision(frozen(contract),code_root=context.code_root)
            captured[task.artifact_digest] = sha256(canonical(value['scientific'])).hexdigest()
        else:
            if len(parents) != 1:
                raise BoundaryError('report needs one verified decision parent')
            committed = next(iter(parents.values()))
            value['record_artifact_sha256'] = committed.artifact.sha256
            value['scientific'] = render(contract,json.loads(committed.data)['scientific'])
        return canonical(value)

    return {name:Capability(name,verify,execute) for name in CAPABILITIES.values()}
