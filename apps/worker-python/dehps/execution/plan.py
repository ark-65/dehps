"""Frozen canonical definitions and exact execution bindings; no new DAG model."""
from copy import deepcopy
from dataclasses import dataclass

from dehps.research_os.mainline import integration_contract
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.ready_queue import ReadyQueue
from dehps.research_os.resolver import TaskDependencyResolver

from .context import BoundaryError


@dataclass(frozen=True)
class ExecutionPlan:
    payload: dict

    @classmethod
    def build(cls, manifest: ControlPlaneManifest, specs: list[dict]):
        payload = {
            'schema':'execution-plan.v2', 'tasks':deepcopy(specs),
            'canonical':{
                'manifest':{'digest':manifest.artifact_digest,'value':manifest.to_dict()},
                'goals':[{'digest':goal.artifact_digest,'value':goal.to_dict()} for goal in manifest.goals],
                'tasks':[{'digest':task.artifact_digest,'value':task.to_dict()} for task in manifest.tasks],
            },
        }
        result = cls(payload)
        result.validate()
        return result

    def validate(self) -> ControlPlaneManifest:
        payload = self.payload
        if set(payload) != {'schema','tasks','canonical'} or payload['schema'] != 'execution-plan.v2':
            raise BoundaryError('unsupported or noncanonical execution plan')
        canonical = payload['canonical']
        if set(canonical) != {'manifest','goals','tasks'}:
            raise BoundaryError('canonical definition packet mismatch')
        manifest = ControlPlaneManifest.from_dict(canonical['manifest']['value'])
        expected = {
            'manifest':{'digest':manifest.artifact_digest,'value':manifest.to_dict()},
            'goals':[{'digest':goal.artifact_digest,'value':goal.to_dict()} for goal in manifest.goals],
            'tasks':[{'digest':task.artifact_digest,'value':task.to_dict()} for task in manifest.tasks],
        }
        if canonical != expected:
            raise BoundaryError('canonical definition digest or bytes mismatch')
        specs = payload['tasks']
        if not isinstance(specs,list) or not specs or any(not isinstance(s,dict) for s in specs):
            raise BoundaryError('task bindings required')
        by_digest = {s['task_digest']:s for s in specs}
        if len(by_digest) != len(specs) or len({s['business_key'] for s in specs}) != len(specs):
            raise BoundaryError('duplicate task or business binding')
        if set(by_digest) != {t.artifact_digest for t in manifest.tasks}:
            raise BoundaryError('plan must bind every canonical task exactly once')
        for task in manifest.tasks:
            if not task.requested_capability:
                raise BoundaryError('coordinator tasks require explicit capabilities')
            if manifest.task_state_by_digest[task.artifact_digest].declared_status is not TaskStatus.DRAFT:
                raise BoundaryError('initial status declarations cannot assert execution facts')
            integration_contract(task)
            if set(by_digest[task.artifact_digest]) != {'business_key','task_digest','manifest_digest','scientific_contract_sha256','verifier_id','artifact_schema'}:
                raise BoundaryError('closed task specification required')
        # Reuse canonical graph validation; do not implement an alternate resolver.
        resolutions = TaskDependencyResolver().resolve(manifest)
        ReadyQueue.build(manifest,resolutions)
        return manifest

    @property
    def digest(self):
        return self.validate().artifact_digest
