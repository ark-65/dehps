"""A presentation-only Goal using the retained unified supervisor and ledger."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
from pathlib import Path

from dehps.artifacts import atomic_write_text
from dehps.notifications import p3_top100 as original
from dehps.research_os.models import ControlPlaneManifest, ResearchOSValidationError, m4_v2_domain_digest
from dehps.research_os.supervisor import AtomicArtifactPayload, AtomicCapabilityResult, ResearchEvidenceSupervisor, integration_contract
from dehps.research_os.information_theory.measurement_system_v2.migration import build_additive_task_manifest
from .render import render, require

PLANE = 'primary-p3-report-presentation-v1'
GOAL = 'PRIMARY_P3_REPORT_PRESENTATION_V1'
TYPES = {'render': 'PrimaryP3PresentationV1', 'replay': 'PrimaryP3PresentationReplayV1'}
CAPABILITIES = {p: 'primary_p3_presentation_' + p + '_v1' for p in TYPES}
DOMAIN = 'dehps.primary-p3.presentation.v1'


def digest(value):
    return sha256(original._canonical_json(value)).hexdigest()


def source_identity():
    root = Path(__file__).parent
    return digest({p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))})


def artifact(phase, body, parents):
    value = {'schema_version': 'primary-p3-presentation.v1', 'artifact_type': TYPES[phase],
             'body': body, 'parent_digests': list(parents)}
    value['artifact_digest'] = m4_v2_domain_digest(value, domain=DOMAIN)
    return value


def validate(value):
    result = dict(value); identity = result.pop('artifact_digest')
    require(result['artifact_type'] in TYPES.values() and result['schema_version'] == 'primary-p3-presentation.v1'
            and m4_v2_domain_digest(result, domain=DOMAIN) == identity, 'presentation artifact changed')
    return {**result, 'artifact_digest': identity}


def keys(issue, kind):
    require(str(issue).isdigit() and kind in ('pre', 'post'), 'invalid presentation issue/kind')
    return {p: f'{PLANE}-{issue}-{kind}-{p}' for p in TYPES}


def load_source(repository, root_dir, issue, kind, recipient):
    email = original.registered_delivery_email(repository, issue=issue, kind=kind, recipient=recipient, root_dir=root_dir)
    bundle = original.load_predraw_bundle(repository, issue=issue, root_dir=root_dir)
    types = {original.PRE_ENVELOPE_ARTIFACT_TYPE} if kind == 'pre' else {original.POST_REPORT_ARTIFACT_TYPE, original.PAYOUT_SOURCE_ARTIFACT_TYPE}
    children = original._completed_children(repository, root_dir=root_dir, control_plane_key=original.CONTROL_PLANE_KEY,
        task_key=original.issue_task_keys(issue)[kind], expected_types=types, validator=original.validate_notification_artifact)
    report = children[original.PRE_ENVELOPE_ARTIFACT_TYPE if kind == 'pre' else original.POST_REPORT_ARTIFACT_TYPE]
    require(report['artifact_digest'] == email.artifact_digest, 'email/report differs')
    source = {'email': asdict(email), 'report': report, 'tickets': original._validated_tickets(bundle.model_candidates),
              'candidate_digest': bundle.model_candidates['artifact_digest'], 'checkpoint': bundle.checkpoint}
    if kind == 'post':
        payout = children[original.PAYOUT_SOURCE_ARTIFACT_TYPE]
        source['payout'] = payout
        source['draw'] = {'red': payout['body']['actual_red_numbers'], 'blue': payout['body']['actual_blue_number']}
    return source


def rendered(source):
    email = source['email']
    return artifact('render', {'source': source, 'style_source_sha256': source_identity(),
        'subject': email['subject'], 'text': email['text'], 'html': render(source),
        'original_delivery_key': original.NotificationEmail(**email).delivery_key,
        'accounting_changed': False, 'scientific_credit': False, 'external_delivery': False},
        [email['artifact_digest'], email['replay_digest'], source['candidate_digest'],
         source['checkpoint']['artifact_digest'], digest(source), source_identity()])


def initial():
    return ControlPlaneManifest.from_dict({'schema_version': 'research-os-control-plane-v1', 'goals': [{
        'goal_key': GOAL, 'semantic_version': '1.0.0', 'objective_class': 'runtime_capability',
        'success_evidence': ['registered presentation and deterministic replay consumed by the original delivery ledger'],
        'owner_lane': 'maintenance', 'question': 'Can primary report readability improve while preserving registered calculations and delivery identity?',
        'baseline_metric_manifest': {'primary_html': 'escaped preformatted text'},
        'target_metric_manifest': {'style_source_sha256': source_identity()},
        'guardrails': ['presentation_only', 'frozen_sources_unchanged', 'no_extra_mail', 'same_ledger_and_windows'], 'status': 'active'}],
        'tasks': [], 'facts': {'artifacts': [], 'evidence': [], 'external_events': [], 'authorities': []}}).to_dict(include_digest=True)


def tasks(source):
    e = source['email']; names = keys(e['issue'], e['kind']); result = []
    for phase in TYPES:
        next_consumer = names['replay'] if phase == 'render' else 'original P3 delivery service and existing delivery ledger'
        integration = {'goal': GOAL, 'ready_condition': 'exact registered primary report and typed/generic replay',
            'runner': 'PresentationSupervisor through ResearchEvidenceSupervisor', 'upstream_artifacts': 'registered primary report, replay and sealed candidates',
            'downstream_artifacts': TYPES[phase], 'status_projection': 'primary-p3-presentation-status.v1',
            'evidence_progress_rule': 'zero scientific credit', 'decision_consumer': 'presentation replay verifier',
            'downstream_consumer': next_consumer, 'next_consumer': next_consumer}
        result.append({'task_key': names[phase], 'goal_key': GOAL, 'task_type': CAPABILITIES[phase], 'lane': 'maintenance',
            'dependencies': [] if phase == 'render' else [{'dependency_type': 'task', 'target_key': names['render'], 'required_status': 'completed'}],
            'priority': 100 if phase == 'render' else 99, 'input_artifact_digests': [digest(source), source_identity()],
            'requested_capability': CAPABILITIES[phase], 'metric_contract': {'issue': e['issue'], 'kind': e['kind'],
                'recipient_digest': e['recipient_digest'], 'mainline_integration': integration},
            'status': 'draft', 'completion_classification': 'INTEGRATION_PENDING'})
    return result


class Capability:
    def __init__(self, repository, root_dir, recipient):
        self.repository, self.root_dir, self.recipient = repository, root_dir, recipient

    def child(self, issue, kind, phase):
        return original._completed_children(self.repository, root_dir=self.root_dir, control_plane_key=PLANE,
            task_key=keys(issue, kind)[phase], expected_types={TYPES[phase]}, validator=validate)[TYPES[phase]]

    def execute(self, *, control_plane_key, task, execution_id, git_commit):
        require(control_plane_key == PLANE and task.requested_capability in CAPABILITIES.values(), 'presentation dispatch escaped allowlist')
        integration_contract(task); c = json.loads(task.metric_contract)
        source = load_source(self.repository, self.root_dir, c['issue'], c['kind'], self.recipient)
        require(c['recipient_digest'] == source['email']['recipient_digest']
                and tuple(task.input_artifact_digests) == (digest(source), source_identity()), 'presentation input changed')
        phase = next(p for p in TYPES if CAPABILITIES[p] == task.requested_capability)
        require(task.task_key == keys(c['issue'], c['kind'])[phase], 'presentation task identity differs')
        expected = rendered(source)
        if phase == 'render':
            value = expected
        else:
            registered = self.child(c['issue'], c['kind'], 'render')
            require(registered == expected, 'presentation replay changed')
            value = artifact('replay', {'status': 'REPLAY_VERIFIED', 'same_registered_content': True,
                'original_delivery_key': registered['body']['original_delivery_key'], 'external_delivery': False}, [registered['artifact_digest']])
        return AtomicCapabilityResult(artifacts=(AtomicArtifactPayload('primary-presentation-' + phase, phase + '.json', value),),
            completion_facts=(task.task_key + ':VERIFIED',), execution_metadata=(('style_source_sha256', source_identity()), ('external_delivery', False)))


class PresentationSupervisor(ResearchEvidenceSupervisor):
    def __init__(self, *, recipient, **kwargs):
        from dehps.research_os import supervisor
        require(supervisor._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE.get(PLANE) in (None, 'mainline'), 'presentation namespace differs')
        supervisor._TASK_ARTIFACT_NAMESPACE_BY_CONTROL_PLANE[PLANE] = 'mainline'
        super().__init__(control_plane_key=PLANE, **kwargs)
        self.presentation = Capability(self.repository, self.root_dir, recipient)
        self.capabilities = {name: self.presentation for name in CAPABILITIES.values()}

    @property
    def state_path(self):
        return self.root_dir / 'runtime/logs/primary-p3-presentation-supervisor-state.json'

    def _build_lane_status(self, manifest, *, snapshot, dispatch_performed, **kwargs):
        return {'schema_version': 'primary-p3-presentation-status.v1', 'control_plane_key': PLANE,
            'manifest_digest': manifest.artifact_digest, 'ready_queue': [t.task_key for t in snapshot.ready_queue],
            'next_ready_task': snapshot.ready_queue[0].task_key if snapshot.ready_queue else None,
            'tasks': {t.task_key: t.status.value for t in snapshot.resolutions}, 'dispatch_performed': dispatch_performed,
            'scientific_credit': False, 'training_dispatched': False}

    def _write_lane_status(self, payload):
        atomic_write_text(self.root_dir / 'runtime/logs/primary-p3-presentation-status.json', json.dumps(payload, sort_keys=True, indent=2) + '\n')

    def replay(self, *, task_key):
        manifest = self.repository.load_manifest(control_plane_key=PLANE)
        matches = [t for t in manifest.tasks if t.task_key == task_key]
        require(len(matches) == 1, 'replay task missing')
        task = matches[0]; c = json.loads(task.metric_contract)
        events = self.repository.list_mainline_execution_events(control_plane_key=PLANE, task_key=task_key)
        completed = [e for e in events if e['event_type'] == 'completed']
        require(len(completed) == 1, 'unique presentation completion required')
        expected = self.presentation.execute(control_plane_key=PLANE, task=task,
            execution_id=completed[0]['execution_id'], git_commit=None).artifacts[0].payload
        phase = next(p for p in TYPES if task.requested_capability == CAPABILITIES[p])
        require(self.presentation.child(c['issue'], c['kind'], phase) == expected, 'registered presentation content changed')
        return {'status': 'REPLAY_VERIFIED', 'task_key': task_key, 'execution_id': completed[0]['execution_id'],
                'artifact_digest': expected['artifact_digest'], 'dispatch_performed': False, 'durable_state_changed': False}


def prepare(repository, root_dir, recipient, issue, kind, *, git_commit=None):
    source = load_source(repository, root_dir, issue, kind, recipient)
    try:
        manifest = repository.load_manifest(control_plane_key=PLANE).to_dict(include_digest=True)
    except ResearchOSValidationError as exc:
        # Only the absent control plane is installable; malformed existing state
        # must never be converted into a fresh manifest.
        if 'not found' not in str(exc):
            raise
        manifest = initial()
    require(manifest['goals'] == initial()['goals'], 'presentation goal/source changed')
    revised, _ = build_additive_task_manifest(live_payload=manifest, new_tasks=tasks(source))
    repository.import_manifest(control_plane_key=PLANE, payload=revised, source=PLANE)
    supervisor = PresentationSupervisor(repository=repository, root_dir=root_dir, recipient=recipient, git_commit=git_commit)
    proofs = []
    for name in keys(issue, kind).values():
        live = repository.load_manifest(control_plane_key=PLANE)
        status = {r.task_key: r.status.value for r in repository.control_plane.resolve(live).resolutions}[name]
        if status != 'completed':
            require(status == 'ready', 'presentation task is not Ready: ' + status)
            supervisor.run_once(task_key=name)
        proofs.append(supervisor.replay(task_key=name))
    return consume(supervisor, issue, kind), proofs


def consume(supervisor, issue, kind):
    for name in keys(issue, kind).values():
        supervisor.replay(task_key=name)
    rendered_report = supervisor.presentation.child(issue, kind, 'render')
    body = rendered_report['body']; original_email = original.NotificationEmail(**body['source']['email'])
    result = replace(original_email, html=body['html'])
    require(result.delivery_key == body['original_delivery_key'] == original_email.delivery_key, 'delivery identity changed')
    return result


def publish_readable(root_dir, email):
    """Immutable readable projection; safe to retry after a projection failure."""
    root = root_dir / 'runtime/primary-p3-presentation/reports'
    root.mkdir(parents=True, exist_ok=True)
    path = root / f'{email.issue}-{email.kind}.html'
    content = email.html.encode('utf-8')
    if path.exists():
        require(path.read_bytes() == content, 'readable report already exists with different bytes')
    else:
        # Exclusive creation prevents a competing invocation replacing a report.
        import os
        import tempfile
        fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=root)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(content); handle.flush(); os.fsync(handle.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return str(path)
