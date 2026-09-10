"""Deterministic engineering fixture; no scientific model or production runner."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import sys
import time

from dehps.execution.artifacts import ArtifactStore
from dehps.execution.context import BoundaryError,RunContext
from dehps.execution.coordinator import Capability,Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.store import ExecutionAuthorization,ExecutionStore

CONTRACT='c'*64


def coordinator(config,mode='normal'):
    root=Path(config['root'])
    def verify(binding,data):
        value=json.loads(data)
        expected={'source':7,'consume':8,'extend':9}[binding['business_key']]
        if value != {'task_digest':binding['task_digest'],'value':expected,'schema':'fixture-graph.v1'} or binding['scientific_contract_sha256'] != CONTRACT:
            raise BoundaryError('fixture graph verification failed')
    def execute(task,parents,artifacts):
        with open(root/(task.task_key+'.calls'),'ab') as stream:
            stream.write(b'compute\n'); stream.flush(); os.fsync(stream.fileno())
        if mode=='before_next' and task.task_key=='consume':
            os.kill(os.getpid(),signal.SIGKILL)
        if mode=='long_source' and task.task_key=='source':
            time.sleep(1.3)
        value=7 if not parents else json.loads(next(iter(parents.values())).data)['value']+1
        return json.dumps({'task_digest':task.artifact_digest,'value':value,'schema':'fixture-graph.v1'},sort_keys=True).encode()
    caps={name:Capability('fixture-graph.v1',verify,execute) for name in ('fixture-source','fixture-consume','fixture-extend')}
    store=ExecutionStore(DatabaseBinding(config['dsn'],config['database'],config['role']),ArtifactStore(RunContext(root,'learning')),
                         ExecutionAuthorization(**config['authorization']),{'fixture-graph.v1':verify})
    engine=Coordinator(ExecutionPlan(config['plan']),store,caps,lease_seconds=1 if mode in {'before_next','long_source','during_registration'} else 300)
    if mode=='during_registration':
        register=engine.ledger.register
        def interrupted(connection,task_id):
            register(connection,task_id)
            os.kill(os.getpid(),signal.SIGKILL)
        # Fault injection calls the real SQL registrar, then kills this process
        # inside the still-open commit transaction. No persistence is mocked.
        engine.ledger.register=interrupted
    return engine


if __name__=='__main__':
    config=json.loads(Path(sys.argv[1]).read_text())
    mode=sys.argv[2]
    engine=coordinator(config,mode)
    result=engine.replay() if mode=='replay' else engine.run()
    print(json.dumps({'run_id':engine.run_id,'manifest':result.to_dict(),'projection_errors':engine.projection_errors}))
