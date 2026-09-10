"""One canonical domain coordinator: injected capabilities, durable completion."""
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Thread
from uuid import uuid4

from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, DependencyType, Task, TaskStatus
from dehps.research_os.ready_queue import ReadyQueue
from dehps.research_os.resolver import TaskDependencyResolver
from .artifacts import ArtifactStore
from .context import BoundaryError
from .ledger import MainlineLedger
from .plan import ExecutionPlan
from .store import Attempt, ExecutionStore, StoredResult, Verifier


@dataclass(frozen=True)
class Capability:
    verifier_id: str
    verify: Verifier
    execute: Callable[[Task, Mapping[str,StoredResult], ArtifactStore],bytes]


class Coordinator:
    def __init__(self, plan: ExecutionPlan, store: ExecutionStore,
                 capabilities: Mapping[str,Capability], *, lease_seconds: int = 300):
        self.plan = ExecutionPlan(deepcopy(plan.payload))
        self.initial = self.plan.validate()
        self.store = store
        self.ledger = MainlineLedger(store)
        self.capabilities = dict(capabilities)
        self.lease_seconds = lease_seconds
        self.run_id = str(uuid4())
        self.projection_errors: list[str] = []
        self.bindings: dict[str,int] = {}
        self._last_manifest = self.initial
        specs = {s['task_digest']:s for s in self.plan.payload['tasks']}
        policies = {}
        for task in self.initial.tasks:
            capability = self.capabilities.get(task.requested_capability)
            if capability is None or capability.verifier_id != specs[task.artifact_digest]['verifier_id']:
                raise BoundaryError('capability/verifier version is not registered')
            previous = policies.setdefault(capability.verifier_id,capability.verify)
            if previous is not capability.verify:
                raise BoundaryError('one verifier version cannot select different policies')
        self.store.verifiers = policies

    def admit(self):
        self.plan.validate()
        with self.store.database.connect() as connection:
            self.bindings = connection.execute('SELECT execution_store.admit_plan(%s,%s,%s)',
                                               self.store.authorization.parameters()).fetchone()[0]
        self._load_plan()

    def _load_plan(self):
        with self.store.database.connect() as connection:
            stored = connection.execute('SELECT execution_store.read_plan(%s)',(self.plan.digest,)).fetchone()[0]
        if stored['payload'] != self.plan.payload:
            raise BoundaryError('persisted plan differs from frozen canonical packet')
        self.bindings = stored['bindings']
        if set(self.bindings) != {task.artifact_digest for task in self.initial.tasks}:
            raise BoundaryError('persisted plan task bindings incomplete')

    def snapshot(self, *, recover_registration: bool = False) -> ControlPlaneManifest:
        self._load_plan()
        payload = self.initial.to_dict()
        tasks = {task.task_key:task for task in self.initial.tasks}
        while True:
            manifest = ControlPlaneManifest.from_dict(payload)
            ready = ReadyQueue.build(manifest,TaskDependencyResolver().resolve(manifest))
            changed = False
            for item in ready:
                task = tasks[item.task_key]
                task_id = self.bindings[task.artifact_digest]
                result = self.store.result(task_id)
                if result is None:
                    continue
                context = self.ledger.context(task_id)
                if recover_registration and any(value is None for value in context['records'].values()):
                    self.ledger.recover_registration(task_id)
                execution = self.ledger.verify(task_id)
                for raw in payload['tasks']:
                    if raw['task_key'] == task.task_key:
                        raw['status'] = 'completed'
                        raw['completion_classification'] = 'COMPLETE'
                fact = mainline_completion_fact(task=task,execution_id=execution)
                payload['facts']['artifacts'] = sorted(set(payload['facts']['artifacts'])|{fact,result.artifact.sha256})
                changed = True
            if not changed:
                return manifest

    def _project(self, phase: str, manifest: ControlPlaneManifest):
        payload = {'schema':'execution-status.v2','run_id':self.run_id,'phase':phase,
                   'execution_id':self.store.authorization.execution_id,
                   'release_sha256':self.store.authorization.release_sha256,
                   'plan_digest':self.plan.digest,'manifest_digest':manifest.artifact_digest,
                   'updated_at':datetime.now(timezone.utc).isoformat(),
                   'tasks':{t.task_key:manifest.task_state_by_digest[t.artifact_digest].declared_status.value for t in manifest.tasks}}
        try:
            self.store.artifacts.context.write_projection('status','execution.json',payload)
        except (OSError,BoundaryError) as exc:
            # Projection failure remains visible to the caller, never reverses a
            # committed computation or fabricates a failed attempt after commit.
            self.projection_errors.append(f'{type(exc).__name__}: {exc}')

    @contextmanager
    def _lease(self, attempt: Attempt, manifest: ControlPlaneManifest):
        stopped = Event()
        failures = []
        def renew():
            while not stopped.wait(max(0.1,self.lease_seconds/3)):
                try:
                    self.store.renew(attempt,lease_seconds=self.lease_seconds)
                    self._project('running',manifest)
                except Exception as exc:
                    failures.append(exc)
                    return
        thread = Thread(target=renew,daemon=True)
        thread.start()
        try:
            yield
            if failures:
                raise BoundaryError('execution lease renewal failed') from failures[0]
        finally:
            stopped.set()
            thread.join()

    def run(self) -> ControlPlaneManifest:
        # A failed admission/readback must not leave an earlier process's success
        # as the current projection. This is status only, never a durable fact.
        self._project('starting',self.initial)
        try:
            self.admit()
            return self._run()
        except Exception:
            self._project('failed',self._last_manifest)
            raise

    def _run(self) -> ControlPlaneManifest:
        while True:
            manifest = self.snapshot(recover_registration=True)
            self._last_manifest = manifest
            ready = ReadyQueue.build(manifest,TaskDependencyResolver().resolve(manifest))
            if not ready:
                complete = all(manifest.task_state_by_digest[t.artifact_digest].declared_status is TaskStatus.COMPLETED for t in manifest.tasks)
                self._project('completed' if complete else 'waiting',manifest)
                return manifest
            self._project('running',manifest)
            progressed = False
            for item in ready:
                task = next(t for t in manifest.tasks if t.task_key == item.task_key)
                task_id = self.bindings[task.artifact_digest]
                attempt = self.store.claim(task_id,lease_seconds=self.lease_seconds)
                if attempt is None:
                    continue
                if isinstance(attempt,StoredResult):
                    progressed = True
                    continue
                try:
                    with self._lease(attempt,manifest):
                        parents = {}
                        for dependency in task.dependencies:
                            if dependency.dependency_type is DependencyType.TASK:
                                parent = next(t for t in manifest.tasks if t.task_key == dependency.target_key)
                                value = self.store.result(self.bindings[parent.artifact_digest])
                                if value is None:
                                    raise BoundaryError('ready task lost a committed parent')
                                parents[parent.task_key] = value
                        data = self.capabilities[task.requested_capability].execute(task,parents,self.store.artifacts)
                        artifact = self.store.prepare(task_id,data)
                        self.store.commit(attempt,artifact,register=self.ledger.register)
                except Exception as exc:
                    # A commit acknowledgement may have been lost. Never convert
                    # a durable success into a failure or rerun it based on error.
                    if self.store.result(task_id) is None:
                        self.store.fail(attempt,type(exc).__name__)
                        raise
                    self.ledger.recover_registration(task_id)
                progressed = True
            if not progressed:
                self._project('waiting',manifest)
                return manifest

    def replay(self) -> ControlPlaneManifest:
        manifest = self.snapshot()
        if any(manifest.task_state_by_digest[t.artifact_digest].declared_status is not TaskStatus.COMPLETED for t in manifest.tasks):
            raise BoundaryError('plan replay incomplete')
        return manifest
