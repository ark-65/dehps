"""Timer-only, exact-package host handoff; no model/admission/budget changes.

Stage immutable bytes under STAGE. Review uses ark's genuine sudo terminal;
every operational action requires its separate live Operator execution.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

STAGE = Path('/opt/dehps/releases/historical-timer-defer-839')
PRIOR = Path('/opt/dehps/releases/historical-chained-continuation-837')
SUPPORT = Path('/opt/dehps/releases/historical-learning-v1-d9c9899-r2/operator-support.py')
SUPPORT_SHA = '691c2ee3042b7d77c0cc35be0d1837bc58135b2a95f6c6e749dee80dea227c9c'
PRIOR_SHA = '103ec6c260c626f8e7777418fa461f64988aa76e69e7d48d71dc17e1428bc844'
ENGINEERING = 'engineering-historical-timer-defer-20260918-v1'
TIMERS = ('dehps-historical-publisher.timer', 'dehps-historical-worker@.timer')
UNITS = ('dehps-historical-publisher', 'dehps-historical-worker@learning', 'dehps-historical-worker@observer')


def now():
    return datetime.now(timezone.utc)


def require(value, message):
    if not value:raise ValueError(message)


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def supported(version):
    require(int(version.splitlines()[0].split()[1])>=257,
            'systemd257+ required; unsupported timer properties must not be ignored')


def timer_change(old, new):
    require(old.count(b'Persistent=true\n')==1 and b'DeferReactivation=' not in old,
            'Unexpected retained timer')
    require(new==old.replace(b'Persistent=true\n',b'Persistent=true\nDeferReactivation=true\n'),
            'Only DeferReactivation=true may change')


def setup(expected):
    require(os.geteuid()==0 and Path(__file__)==STAGE/'timer-host.py', 'Protected root entry required')
    require(sha256(SUPPORT.read_bytes()).hexdigest()==SUPPORT_SHA,'Retained support changed')
    s=load('timer_support',SUPPORT);s.protected(SUPPORT);s.protected(Path(__file__))
    s.STAGE=STAGE
    package=s.packet(expected)
    require(package['schema']=='historical-timer-defer.v1','Unexpected packet schema')
    s.KEY=package['operator_request_key']
    s.protected(PRIOR/'activation-packet.json')
    require(s.sha(PRIOR/'activation-packet.json')==PRIOR_SHA,'Retained package changed')
    old=json.loads((PRIOR/'activation-packet.json').read_bytes())
    source=PRIOR/'continuation-host.py';s.protected(source)
    require(s.sha(source)==old['files']['continuation-host.py']['sha256'],'Retained replay host changed')
    host=load('retained_timer_replay',source)
    require(package['workers']==old['workers'] and package['plans']==old['plans']
            and package['approved_until']==old['approved_until'],'Worker, plan or expiry changed')
    require(s.private(Path('/etc/dehps/historical/admission-window.json'))['approved_until']==package['approved_until'],
            'Original runtime expiry changed')
    require(now()<datetime.fromisoformat(package['approved_until']), 'Original runtime approval expired')
    for folder in ('evidence','rollback'):
        (STAGE/folder).mkdir(mode=0o755,exist_ok=True);s.protected(STAGE/folder)
    for name in TIMERS:
        timer_change((STAGE/('old-'+name)).read_bytes(),(STAGE/name).read_bytes())
    supported(s.command('systemctl','--version'))
    return s,package,old,host


def save(s, name, value, public=True):
    path=STAGE/'evidence'/name
    s.save(path,value,0o644 if public else 0o600)
    if public:path.chmod(0o644)


def authorize(s, expected, execution):
    outer=s.bound_request(expected)
    records=[r for r in s.metadata_repository().list_execution_metadata(s.KEY) if r.id==execution]
    require(outer.status.value=='executing' and len(records)==1 and records[0].status.value=='running'
            and records[0].executor_role.value=='operator' and records[0].executor_id==s.THREAD,
            'Actual separate Operator execution required')
    receipt=STAGE/'runtime-review.json';s.protected(receipt)
    require(json.loads(receipt.read_bytes())['activation_packet_sha256']==expected,'Exact authenticated review absent')


def review(s, package, expected):
    require(os.environ.get('SUDO_UID')=='1000' and os.environ.get('SUDO_USER')=='ark' and sys.stdin.isatty(),
            'Human local ark sudo terminal required')
    s.protected(s.MAPPING);require(s.sha(s.MAPPING)==s.MAPPING_SHA,'Identity mapping changed')
    mapping=json.loads(s.MAPPING.read_bytes())
    principal='unix-host:'+sha256(Path('/etc/machine-id').read_bytes()).hexdigest()+':uid:1000'
    require(pwd.getpwnam('ark').pw_uid==1000 and mapping['reviewer_principal']==principal,'Actual Reviewer differs')
    require(now()<datetime.fromisoformat(package['review_before']),'Bounded deployment review expired')
    engineering=s.metadata_repository().get_request(ENGINEERING)
    require(engineering.status.value=='completed' and engineering.requested_by==s.THREAD,'Engineering handoff incomplete')
    request=s.bound_request(expected)
    require(request.status.value in {'submitted','under_review'},'Request is not awaiting independent review')
    from dehps.agents.service import AgentRequestService
    from dehps.agents.roles import AgentRole
    service=AgentRequestService(s.metadata_repository(False))
    if request.status.value=='submitted':
        request=service.begin_review(s.KEY,reviewer_role=AgentRole.REVIEWER,reviewer_id=principal,environment='production')
    reason={'authentication':'genuine ark sudo terminal; owner delegated exact automatic repair/deployment review',
            'activation_packet_sha256':expected,'scope':'two timer templates only; existing worker/plan/scoped executions and deadlines retained',
            'original_approved_until':package['approved_until'],'no_new_model_admission':True}
    request=service.approve(s.KEY,reviewer_role=AgentRole.REVIEWER,reviewer_id=principal,environment='production',reason=reason)
    require(request.status.value=='approved','Actual approval failed')
    decisions=[d for d in s.metadata_repository().list_decisions(s.KEY) if d.decision_code=='request_approved']
    require(len(decisions)==1 and decisions[0].decided_by==principal and decisions[0].reason==reason,'Review readback differs')
    s.save(STAGE/'runtime-review.json',{'activation_packet_sha256':expected,'reviewer_principal':principal,
        'approved_until':package['approved_until'],'at':now().isoformat()})
    print('Exact timer-only Operator release approved; no model or service started.',flush=True)


def snapshot(s):
    baseline=json.loads((STAGE/'formal-baseline.json').read_bytes())
    return {'at':now().isoformat(),'files':{p:s.sha(Path(p)) for p in baseline['files']},
        'formal_timers':s.command('runuser','-u','ark','--','env','XDG_RUNTIME_DIR=/run/user/1000',
                                 'systemctl','--user','list-timers','--all','--no-pager')}


def quiet(s):
    for unit in UNITS:
        require(s.command('systemctl','show',unit+'.service','--property=ActiveState','--value')
                in {'inactive','failed'},'Historical service still active; wait or use approved quiesce')


def operate(s, package, old, host, action, expected, execution):
    authorize(s,expected,execution)
    if action=='quiesce':
        for unit in UNITS:s.command('systemctl','stop',unit+'.timer')
        for unit in UNITS:s.command('systemctl','stop',unit+'.service')
        save(s,'quiesced-'+now().strftime('%Y%m%dT%H%M%S%f')+'.json',{'at':now().isoformat(),'execution':execution})
    elif action.startswith('replay-'):
        quiet(s)
        domain=action.removeprefix('replay-');require(domain in {'learning','observer'},'Unexpected replay domain')
        host.check_replay_identity(s,domain)
        result=subprocess.run(host.replay_command(old,domain,prior=False),capture_output=True,text=True)
        stamp=now().strftime('%Y%m%dT%H%M%S%f')
        save(s,domain+'-replay-raw-'+stamp+'.json',{'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr},False)
        require(result.returncode==0,'Fixed-image read-only replay failed; private failure retained')
        data=json.loads(result.stdout)
        require(not data.get('task_errors') and data['plan_digest']==old['plans'][domain]
                and data['release_sha256']==old['workers'][domain]['release_sha256'],'Replay identity or task errors differ')
        summary={k:data.get(k) for k in ('run_id','plan_digest','release_sha256','control_plane','task_errors')}
        summary.update(action='replay-prefix',task_counts=dict(Counter(data['tasks'].values())),at=now().isoformat())
        save(s,domain+'-replay-'+stamp+'.json',summary);print(json.dumps(summary),flush=True)
    elif action=='install':
        quiet(s)
        save(s,'before.json',snapshot(s))
        for name in TIMERS:
            path=Path('/etc/systemd/system')/name;s.protected(path)
            require(path.read_bytes()==(STAGE/('old-'+name)).read_bytes(),'Installed timer changed; preserve and inspect')
        for name in TIMERS:
            path=Path('/etc/systemd/system')/name
            backup=STAGE/'rollback'/name
            if not backup.exists():backup.write_bytes(path.read_bytes());backup.chmod(0o444)
            temporary=path.with_suffix('.timer-defer-new')
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            with os.fdopen(fd,'wb') as stream:
                stream.write((STAGE/name).read_bytes());stream.flush();os.fsync(stream.fileno())
            temporary.replace(path)
        s.command('systemctl','daemon-reload')
        for unit in UNITS:
            require(s.command('systemctl','show',unit+'.timer','--property=DeferReactivation','--value')=='yes',
                    'Effective timer deferral not enabled')
        save(s,'installed.json',{'at':now().isoformat(),'operator_execution':execution,'packet_sha256':expected,
            'timers':{name:s.sha(Path('/etc/systemd/system')/name) for name in TIMERS}})
    elif action=='enable':
        require((STAGE/'evidence/installed.json').exists(),'Timer installation not recorded')
        for unit in UNITS:
            require(s.command('systemctl','show',unit+'.timer','--property=DeferReactivation','--value')=='yes','Timer setting differs')
            s.command('systemctl','enable','--now',unit+'.timer')
        save(s,'enabled-'+now().strftime('%Y%m%dT%H%M%S%f')+'.json',{'at':now().isoformat(),
            'timers':s.command('systemctl','list-timers','dehps-historical-*','--all','--no-pager')})
    elif action=='rollback':
        for unit in UNITS:s.command('systemctl','disable','--now',unit+'.timer')
        for unit in UNITS:s.command('systemctl','stop',unit+'.service')
        for name in TIMERS:
            path=Path('/etc/systemd/system')/name;s.protected(path)
            require(path.read_bytes() in ((STAGE/name).read_bytes(),(STAGE/('old-'+name)).read_bytes()),'Unreviewed timer mutation')
            path.write_bytes((STAGE/('old-'+name)).read_bytes())
        s.command('systemctl','daemon-reload')
        save(s,'rollback-'+now().strftime('%Y%m%dT%H%M%S%f')+'.json',{'at':now().isoformat(),'evidence_retained':True})
    else:raise ValueError('Unsupported bounded operation')


def main():
    require(len(sys.argv) in {3,4},'Exact action packet [execution] required')
    action,expected=sys.argv[1:3]
    s,package,old,host=setup(expected)
    if action=='review':
        require(len(sys.argv)==3,'Review cannot execute');review(s,package,expected)
    else:
        require(len(sys.argv)==4,'Separate Operator execution required')
        operate(s,package,old,host,action,expected,int(sys.argv[3]))


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Never expose credentials or connection repr in ordinary output.
        if os.geteuid()==0 and Path(__file__)==STAGE/'timer-host.py' and (STAGE/'evidence').is_dir():
            support=load('failure_support',SUPPORT)
            support.protected(STAGE/'evidence')
            save(support,'failure-'+now().strftime('%Y%m%dT%H%M%S%f')+'.json',
                 {'at':now().isoformat(),'error_type':type(error).__name__,'error':str(error)},False)
        print('Timer-only operation stopped; evidence retained. '+type(error).__name__,file=sys.stderr)
        if isinstance(error,ValueError):print(str(error),file=sys.stderr)
        sys.exit(1)
