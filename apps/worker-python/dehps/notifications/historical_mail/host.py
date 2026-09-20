"""Fixed-package host orchestration. Admission/provisioning belongs to Operator.

Worker execution stays in the canonical image with scoped database credentials.
Only this separately admitted host consumer can load existing mail credentials.
"""
import base64
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from dehps.execution.authority import AuthorityClient
from dehps.execution.coordinator import Coordinator
from dehps.execution.database import DatabaseBinding
from dehps.execution.plan import ExecutionPlan
from dehps.execution.release import Release, canonical
from dehps.execution.store import ExecutionStore, ExecutionAuthorization
from dehps.notifications.mail import QqMailConfig
from dehps.prediction.forward_learning.publisher import append_bytes
from dehps.prediction.historical_learning.readonly import ReadonlyArtifacts, ReadonlyContext, ReadonlyDatabase
from .contract import Inputs, digest, instant, require, utcnow
from .capabilities import build_capabilities
from .delivery import Delivery, registered_emails
from .publisher import publish, gate


def protected(path):
    for p in (Path(path), *Path(path).parents):
        s = p.lstat()
        require(not stat.S_ISLNK(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022, 'protected host resource required')


def config(path):
    require(os.geteuid() == 0, 'admitted host service identity required')
    protected(path); value = json.loads(Path(path).read_bytes())
    require(set(value) == {'schema','package','package_sha256','inputs','runtime','credentials','worker_credentials',
        'key','source_credentials','source_root','readers','ledger','reports','evidence','lock','formal_cgroups'}, 'closed host configuration required')
    require(value['schema'] == 'historical-mail-host.v1', 'unknown host configuration')
    package = Path(value['package']); protected(package)
    require(sha256(package.read_bytes()).hexdigest() == value['package_sha256'], 'accepted notification package differs')
    packet = json.loads(package.read_bytes())
    for name, expected in packet['files'].items():
        p = package.parent/name
        require(p.is_relative_to(package.parent) and '..' not in Path(name).parts, 'package path escaped')
        protected(p); require(sha256(p.read_bytes()).hexdigest() == expected, 'accepted host source differs')
    for name in ('inputs','runtime','ledger','reports','evidence','lock','formal_cgroups'):
        require(value[name] == packet['paths'][name], 'host path differs from admitted packet')
    return value, packet


def reader(cfg, packet):
    root = Path(cfg['inputs']); release = Release.read(root/'release.json',packet['release_sha256'])
    input_packet = json.loads((root/'execution.json').read_bytes()); p = ExecutionPlan(input_packet['plan'])
    require(p.digest == packet['plan_digest'], 'installed mail plan differs')
    db = ReadonlyDatabase(**json.loads(Path(cfg['credentials']).read_bytes()))
    request = AuthorityClient(db).get(input_packet['request_id'])
    require(request['payload'] == p.payload and request['release_sha256'] == release.digest and request['control_plane'] == 'observer',
            'notification admission binding differs')
    store = ExecutionStore(db,ReadonlyArtifacts(ReadonlyContext(Path(cfg['runtime']),'observer')),
                           ExecutionAuthorization(0,request['content_sha256'],release.digest),{})
    ctx = SimpleNamespace(inputs=root,release=release)
    engine = Coordinator(p,store,build_capabilities(p,store,ctx))
    return engine, request


def formal_busy(cfg):
    from dehps.prediction.historical_learning.contract import formal_priority_active
    if not formal_priority_active():
        return False
    root = Path(cfg['formal_cgroups']); require(root.is_dir(), 'formal dispatch guard missing')
    for name in ('dehps-forward-prequential-successor','dehps-m4-p4-forward-prequential-armed',
                 'dehps-p3-top100-pre-draw-mail','dehps-p3-top100-post-draw-mail'):
        p = root/(name+'.service')/'cgroup.procs'
        if p.exists() and p.read_text().strip():
            return True
    return False


def launch(cfg, packet, action):
    args = ['runuser','-u','dehps-observer','-g','dehps-observer','-G','docker','--','env',
        'DOCKER_HOST=unix:///var/run/docker.sock','DOCKER_CONFIG=/opt/dehps/releases/control-refactor-r5/docker-client',
        '/usr/bin/python3.14','-I','-B','/opt/dehps/releases/historical-publisher/launcher/launch.py','run',
        '--descriptor',str(Path(cfg['inputs'])/'release.json'),'--release-sha256',packet['release_sha256'],
        '--runtime-root',cfg['runtime'],'--control-domain','observer','--inputs',cfg['inputs'],
        '--credentials',cfg['worker_credentials'],'--network','none',
        '--database-socket','/run/dehps/observer-postgres-socket','--action',action]
    result = subprocess.run(args,capture_output=True,timeout=600)
    record = {'at':utcnow().isoformat(),'action':action,'exit_code':result.returncode,
              'stdout_sha256':sha256(result.stdout).hexdigest(),'stderr_sha256':sha256(result.stderr).hexdigest()}
    evidence = Path(cfg['evidence']); evidence.mkdir(parents=True,exist_ok=True)
    append_bytes(evidence/(digest(record)+'.json'),canonical(record))
    if result.returncode:
        append_bytes(evidence/(digest(record)+'.stderr'),result.stderr)
    require(result.returncode == 0, 'fixed notification worker failed; preserved private failure evidence')
    return record


def run(path, action):
    require(action in ('prepare','pre','post','replay','status'), 'unsupported host action')
    cfg, packet = config(path)
    if action == 'status':
        p = Path(cfg['runtime'])/'observer/status/execution.json'
        return json.loads(p.read_bytes()) if p.exists() else {'status':'NOT_STARTED'}
    with Path(cfg['lock']).open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        inputs = Inputs(cfg['inputs'],packet['contract_sha256'])
        if action == 'replay':
            launch(cfg,packet,'replay-prefix'); engine,_ = reader(cfg,packet)
            return {'status':'REPLAY_VERIFIED','reports':len(registered_emails(engine)),'external_delivery':False}
        if utcnow() >= instant(inputs.contract['approved_until']):
            return {'status':'WAITING','reason':'AUTHORIZATION_REQUIRED'}
        db = DatabaseBinding(**json.loads(Path(cfg['credentials']).read_bytes()))
        input_packet = json.loads((Path(cfg['inputs'])/'execution.json').read_bytes())
        authority = AuthorityClient(db); request = authority.get(input_packet['request_id'])
        require(request['payload'] == input_packet['plan'] and request['release_sha256'] == packet['release_sha256'], 'host admission differs')
        execution = authority.begin(request['id'],request['content_sha256'],packet['release_sha256'])
        reauthorize = lambda: authority.reauthorize(execution,request['content_sha256'],packet['release_sha256'])
        reauthorize()
        key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(json.loads(Path(cfg['key']).read_bytes())['ed25519_private_key']))
        if formal_busy(cfg):
            gate(inputs,key,'FORMAL_TASK_RUNNING')
            return {'status':'WAITING','reason':'FORMAL_TASK_RUNNING'}
        publication = publish(inputs,cfg['readers'],DatabaseBinding(**json.loads(Path(cfg['source_credentials']).read_bytes())),key,cfg['source_root'])
        reauthorize(); launch(cfg,packet,'run')
        status = json.loads((Path(cfg['runtime'])/'observer/status/execution.json').read_bytes())['payload']
        require(status.get('schema') == 'execution-status.v2' and status.get('plan_digest') == packet['plan_digest']
                and status.get('release_sha256') == packet['release_sha256'] and status.get('phase') in ('waiting','completed')
                and not status.get('task_errors'), 'canonical notification task failed or admission/status differs')
        launch(cfg,packet,'replay-prefix')
        engine,_ = reader(cfg,packet); messages = registered_emails(engine)
        for message in messages:
            name = message['issue']+'-'+message['kind']
            append_bytes(Path(cfg['reports'])/(name+'.md'),message['report']['text'].encode())
            append_bytes(Path(cfg['reports'])/(name+'.json'),canonical(message))
        outputs = []
        if action in ('pre','post'):
            from dotenv import dotenv_values
            names = {'DEHPS_QQ_MAIL_ADDRESS','DEHPS_QQ_MAIL_RECIPIENT','DEHPS_QQ_MAIL_AUTHORIZATION_CODE'}
            env = {}
            for file in ('/home/ark/workspace/dehps/.env','/home/ark/.config/dehps/draw-sync.env'):
                env.update({k:v for k,v in dotenv_values(file).items() if k in names and v is not None})
            delivery = Delivery(cfg['ledger'],QqMailConfig.from_environment(env),inputs.contract,
                                reauthorize=reauthorize,gate=inputs.gate)
            for message in messages:
                if message['kind'] == action:
                    outputs.append(delivery.deliver(message))
        result = {'status':'VERIFIED','at':utcnow().isoformat(),'action':action,'publication':publication,
                  'run_id':status['run_id'],
                  'consumer_replay_run_id':engine.run_id,'registered_reports':len(messages),'deliveries':outputs}
        append_bytes(Path(cfg['evidence'])/(digest(result)+'.json'),canonical(result))
        return result


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','pre','post','replay','status']);parser.add_argument('--config',type=Path,required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(run(args.config,args.action),ensure_ascii=False))
    except Exception as exc:
        # Avoid tracebacks containing connection details or transport credentials.
        import traceback
        try:
            cfg,_ = config(args.config)
            private = Path(cfg['evidence'])/('failure-'+utcnow().strftime('%Y%m%dT%H%M%S%f')+'.txt')
            fd = os.open(private,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as stream:
                stream.write(traceback.format_exc());stream.flush();os.fsync(stream.fileno())
        except Exception:
            pass
        print(json.dumps({'status':'ERROR','error_type':type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
