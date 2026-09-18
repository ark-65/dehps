"""Exact-package host handoff. Stage as protected root-owned bytes before use.

review requires ark's real local sudo terminal. install requires a separately
recorded Operator execution. Neither owner chat text nor a principal string is
accepted as Reviewer authentication. No formal service or mail action exists.
"""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import grp
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess
import sys
import time

OLD = Path('/opt/dehps/releases/historical-learning-v1-d9c9899-r2')
OLD_CONFIG = Path('/etc/dehps/historical')
PRIOR = Path('/opt/dehps/releases/historical-continuation-831')
PRIOR_CONFIG = Path('/etc/dehps/historical-continuation-831')
CURRENT_PUBLISHER_CONFIG = Path('/etc/dehps/historical-source-refresh-20260917/publisher.json')
STAGE = Path('/opt/dehps/releases/historical-chained-continuation-837')
CONFIG = Path('/etc/dehps/historical-chained-continuation-837')
PUB = Path('/opt/dehps/releases/historical-chained-publisher-837')
UNITS = ['dehps-historical-publisher', 'dehps-historical-worker@learning', 'dehps-historical-worker@observer']


def now():return datetime.now(timezone.utc)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def bootstrap(expected):
    # The staging entry has already verified this file and the support hashes.
    package = json.loads((STAGE/'activation-packet.json').read_bytes())
    for name, identity in package['retained_helpers'].items():
        path = OLD/name
        if path.is_symlink() or sha256(path.read_bytes()).hexdigest() != identity:
            raise ValueError('Retained host helper differs: '+name)
    support = load('continuation_support', OLD/'operator-support.py')
    support.STAGE, support.CONFIG, support.PUB = STAGE, CONFIG, PUB
    support.KEY = package['operator_request_key']
    support.ENGINEERING = 'engineering-historical-chained-continuation-20260918-v1'
    package = support.packet(expected)
    support.require(os.geteuid() == 0, 'Actual host administrator authentication required')
    support.require(Path(__file__) == STAGE/'continuation-host.py', 'Protected staged entry required')
    support.protected(Path(__file__))
    for name in package['retained_helpers']:support.protected(OLD/name)
    installer = load('retained_installer', OLD/'install-activation.py');installer.s = support
    reviewer = load('retained_reviewer', OLD/'review-activation.py');reviewer.s = support
    original_save = support.save
    def save(path, value, mode=0o600):
        original_save(path, value, mode)
        if mode == 0o644:path.chmod(mode)
    support.save = save
    return support, package, installer, reviewer


def prepare_request(s, package, domain):
    """New narrow logins; existing identities and schema remain untouched."""
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.types.json import Jsonb
    folder = CONFIG/domain;folder.mkdir(mode=0o700,exist_ok=True)
    marker = folder/'admission-prepared.json'
    plan = json.loads((STAGE/(domain+'-plan.json')).read_bytes())
    release = package['workers'][domain]['release_sha256']
    if marker.exists():
        saved = s.private(marker)
        with s.admin_connection(domain) as db:
            actual = db.execute('SELECT payload,release_sha256,content_sha256,requester FROM execution_authority.requests WHERE id=%s',
                                (saved['request_id'],)).fetchone()
        s.require(actual == (plan,release,saved['content_sha256'],s.THREAD), 'Existing continuation admission differs')
        return saved
    engineer = 'dehps_control_'+domain+'_hist837_engineer'
    operator = 'dehps_control_'+domain+'_hist837_operator'
    passwords = {engineer:secrets.token_urlsafe(48), operator:secrets.token_urlsafe(48)}
    with s.admin_connection(domain) as db:
        s.require(not db.execute('SELECT 1 FROM pg_roles WHERE rolname=ANY(%s)',([engineer,operator],)).fetchone(),
                  'Unrecorded existing continuation role; preserve and inspect')
        for role,request,execute in [(engineer,True,False),(operator,False,True)]:
            db.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS')
                       .format(sql.Identifier(role),sql.Literal(passwords[role])))
            db.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier('dehps_control_'+domain),sql.Identifier(role)))
            db.execute(sql.SQL('GRANT USAGE ON SCHEMA execution_authority TO {}').format(sql.Identifier(role)))
            db.execute('INSERT INTO execution_authority.identities(login_oid,login_name,principal,control_plane,can_request,can_review,can_execute) SELECT oid,rolname,%s,%s,%s,false,%s FROM pg_roles WHERE rolname=%s',
                       (s.THREAD,domain,request,execute,role))
            signatures = ['request_get(bigint)'] + (['request_create(jsonb,text,text)'] if request else
                ['begin_execution(bigint,text,text,text)','reauthorize(bigint,text,text)'])
            for signature in signatures:
                db.execute(sql.SQL('GRANT EXECUTE ON FUNCTION execution_authority.{} TO {}').format(sql.SQL(signature),sql.Identifier(role)))
        db.execute(sql.SQL('GRANT USAGE ON SCHEMA execution_store TO {}').format(sql.Identifier(operator)))
        for signature in ['register_task(bigint,text,text,jsonb)','read_result(bigint)','claim(bigint,bigint,text,text,integer)',
            'renew(bigint,uuid,bigint,text,text,integer)','fail(bigint,uuid,bigint,text,text,text)',
            'commit_result(bigint,uuid,bigint,text,text,text,bigint)','admit_plan(bigint,text,text)',
            'read_plan(text)','mainline_context(bigint)','record_mainline(bigint,bigint,text,text,jsonb)']:
            db.execute(sql.SQL('GRANT EXECUTE ON FUNCTION execution_store.{} TO {}').format(sql.SQL(signature),sql.Identifier(operator)))
    params = conninfo_to_dict(s.private(s.CONTROL/domain/'admin-host.json')['dsn'])
    try:
        with psycopg.connect(**{**params,'user':engineer,'password':passwords[engineer]}) as db:
            s.require(db.execute('SELECT session_user').fetchone()[0] == engineer, 'Engineering login differs')
            request = db.execute('SELECT execution_authority.request_create(%s,%s,%s)',
                (Jsonb(plan),release,'Exact retained-prefix continuation after Engineering837')).fetchone()[0]
            value = db.execute('SELECT execution_authority.request_get(%s)',(request,)).fetchone()[0]
    finally:
        with s.admin_connection(domain) as db:
            db.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(engineer)))
    operator_params = {**params,'user':operator,'password':passwords[operator]}
    s.save(folder/'operator-host.json',{'dsn':make_conninfo(**operator_params),'database':'dehps_control_'+domain,'role':operator})
    s.save(folder/'operator.json',{'dsn':make_conninfo(**{**operator_params,'host':'/run/dehps-postgres','port':'5432'}),
                                 'database':'dehps_control_'+domain,'role':operator})
    saved = {'domain':domain,'request_id':request,'content_sha256':value['content_sha256'],
             'release_sha256':release,'requester':value['requester']}
    s.save(marker,saved)
    return saved


def publisher(s, package, installer):
    if not PUB.exists():
        unpack = STAGE/'unpack';unpack.mkdir(exist_ok=True)
        installer.unpack_publisher(STAGE/'publisher-host.tar.gz',unpack,package['publisher_files'])
        candidate = unpack/'historical-publisher'
        for p in [candidate,*candidate.rglob('*')]:
            os.chown(p,0,0,follow_symlinks=False)
            if not p.is_symlink():p.chmod((p.stat().st_mode & 0o777) & ~0o022)
        candidate.rename(PUB);unpack.rmdir()
    for name,item in package['publisher_files'].items():
        p = PUB/name
        s.require((p.is_symlink() and os.readlink(p)==item['symlink']) if 'symlink' in item else s.sha(p)==item['sha256'],
                  'Fixed continuation publisher differs: '+name)


def prefix_check(s, package):
    # Reader allows four authenticated read APIs with identity locks; replay is a
    # separate deployment proof. Neither command invokes run/fit or repairs SQL.
    config = {'schema':'historical-continuation-preparation.v2','readers':{},
        'next_releases':{d:v['release_sha256'] for d,v in package['workers'].items()},
        'original_approved_until':package['approved_until'],'budget_seconds':86400}
    for domain in ('learning','observer'):
        config['readers'][domain] = {'inputs':'/opt/dehps/inputs/historical-continuation-831-'+domain,
            'runtime_root':'/var/lib/dehps/control-'+domain,'release_sha256':package['prior_workers'][domain]['release_sha256'],
            'reader_credentials':str(PRIOR_CONFIG/domain/'operator-host.json'),'code_root':str(PUB/'source')}
    s.save(STAGE/'prefix-reader.json',config)
    output = STAGE/'evidence'/('prefix-check-'+now().strftime('%Y%m%dT%H%M%S%f'))
    s.command('/usr/bin/flock','--exclusive','/run/dehps/historical/learning.lock',
        '/usr/bin/flock','--exclusive','/run/dehps/historical/observer.lock',
        str(PUB/'venv/bin/python'),'-I','-m','dehps.prediction.historical_learning.operations',
        'prepare-continuation','--config',str(STAGE/'prefix-reader.json'),'--output',str(output))
    s.require((output/'continuation.json').read_bytes() == (STAGE/'continuation.json').read_bytes(),
              'Live registered prefix differs from exact reviewed continuation; preserve and prepare a new packet')


def snapshot(s):
    baseline = json.loads((STAGE/'formal-baseline.json').read_bytes())
    return {'at':now().isoformat(),'files':{p:s.sha(Path(p)) for p in baseline['files']},
        'timers':s.command('runuser','-u','ark','--','env','XDG_RUNTIME_DIR=/run/user/1000','systemctl','--user','list-timers','--all','--no-pager')}


def check_replay_identity(s, domain):
    service = 'dehps-'+domain
    uid = {'learning':61010, 'observer':61011}[domain]
    account = pwd.getpwnam(service)
    s.require(account.pw_uid == uid and account.pw_gid == uid
              and grp.getgrnam(service).gr_gid == uid, 'Replay service UID/primary GID differs')
    raw = s.command('systemctl','show','dehps-historical-worker@'+domain+'.service',
                    '--property=User','--property=Group','--property=SupplementaryGroups')
    actual = dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    s.require(actual == {'User':service,'Group':service,'SupplementaryGroups':'docker'},
              'Replay must match existing canonical service identity and supplementary group')


def replay_command(package, domain, *, prior):
    """The retained launcher requires the actual non-root runtime UID."""
    stage = PRIOR if prior else STAGE
    config = PRIOR_CONFIG if prior else CONFIG
    inputs = '/opt/dehps/inputs/historical-'+('continuation-831-' if prior else 'chained-continuation-837-')+domain
    worker = package['prior_workers' if prior else 'workers'][domain]
    return ['runuser','-u','dehps-'+domain,'-g','dehps-'+domain,'-G','docker','--','env',
        'DOCKER_HOST=unix:///var/run/docker.sock',
        'DOCKER_CONFIG=/opt/dehps/releases/control-refactor-r5/docker-client',
        '/usr/bin/flock','--exclusive','/run/dehps/historical/'+domain+'.lock',
        '/usr/bin/python3.14','-I','-B','/opt/dehps/releases/historical-publisher/launcher/launch.py','run',
        '--descriptor',str(stage/(domain+'-release.json')),'--release-sha256',worker['release_sha256'],
        '--runtime-root','/var/lib/dehps/control-'+domain,'--control-domain',domain,'--inputs',inputs,
        '--credentials',str(config/domain/'operator.json'),'--network','none',
        '--database-socket','/run/dehps/'+domain+'-postgres-socket','--action','replay-prefix']


def review(s, package, installer, reviewer, expected):
    s.require(os.environ.get('SUDO_UID')=='1000' and os.environ.get('SUDO_USER')=='ark' and sys.stdin.isatty(),
              'Human local ark sudo terminal required')
    s.protected(s.MAPPING);s.require(s.sha(s.MAPPING)==s.MAPPING_SHA, 'Installed identity mapping changed')
    mapping=json.loads(s.MAPPING.read_bytes())
    principal='unix-host:'+sha256(Path('/etc/machine-id').read_bytes()).hexdigest()+':uid:1000'
    s.require(pwd.getpwnam('ark').pw_uid==1000 and mapping['reviewer_principal']==principal, 'Actual ark Reviewer differs')
    for domain in ('learning','observer'):check_replay_identity(s,domain)
    original=s.private(OLD_CONFIG/'admission-window.json')
    s.require(original['approved_until']==package['approved_until'] and now()<datetime.fromisoformat(package['review_before']),
              'Original expiry or time-bound deployment packet differs; no extension')
    engineering=s.metadata_repository().get_request(s.ENGINEERING)
    s.require(engineering.status.value=='completed' and engineering.requested_by==s.THREAD, 'Engineering handoff incomplete')
    outer=s.bound_request(expected)
    s.require(outer.status.value in {'submitted','under_review','approved','executing'}, 'Operator request not reviewable')
    (STAGE/'evidence').mkdir(mode=0o755,exist_ok=True);(STAGE/'evidence').chmod(0o755);(STAGE/'rollback').mkdir(exist_ok=True)
    publisher(s,package,installer)
    receipt=CONFIG/'runtime-review.json'
    if not receipt.exists():
        prefix_check(s,package)
        print('已核验全部已提交历史记录和连续接续包。仅批准这份精确接续计划；原30天截止不变，新续批最多24小时。',flush=True)
        from dehps.agents.service import AgentRequestService
        from dehps.agents.roles import AgentRole
        approvals=[reviewer.approve_runtime(prepare_request(s,package,d),principal,datetime.fromisoformat(package['approved_until']))
                   for d in ('learning','observer')]
        service=AgentRequestService(s.metadata_repository(False))
        if outer.status.value=='submitted':outer=service.begin_review(s.KEY,reviewer_role=AgentRole.REVIEWER,reviewer_id=principal,environment='production')
        if outer.status.value=='under_review':
            outer=service.approve(s.KEY,reviewer_role=AgentRole.REVIEWER,reviewer_id=principal,environment='production',
                reason={'authentication':'actual ark sudo authentication, owner-delegated exact packet review, and independent scoped authenticated Reviewer sessions',
                        'activation_packet_sha256':expected,'continuation_sha256':package['continuation_sha256'],
                        'runtime_approvals':approvals,'original_approved_until':package['approved_until'],
                        'continuation_budget_seconds':86400,'no_model_started':True,'no_mail_sent':True})
        s.require(outer.status.value=='approved','Outer runtime approval differs')
        s.save(receipt,{'activation_packet_sha256':expected,'reviewer_principal':principal,
            'approved_until':package['approved_until'],'activated_at':original['activated_at'],'runtime_approvals':approvals},0o644)
    else:
        saved=json.loads(receipt.read_bytes());s.protected(receipt)
        s.require(saved['activation_packet_sha256']==expected and saved['reviewer_principal']==principal, 'Existing review differs')
    print('真实运行审批已登记；等待当前Codex任务登记独立Operator执行。无需重复审批。',flush=True)
    until=time.monotonic()+3600
    while time.monotonic()<until:
        outer=s.bound_request(expected)
        if outer.status.value=='executing':
            active=[x for x in s.metadata_repository().list_execution_metadata(s.KEY)
                    if x.status.value=='running' and x.executor_role.value=='operator' and x.executor_id==s.THREAD]
            s.require(len(active)==1,'Actual Operator execution differs')
            s.command('systemd-run','--quiet','--collect','--unit=dehps-historical-continuation-'+str(active[0].id),
                '--service-type=exec','--property=RuntimeMaxSec=25h','--property=UMask=0077',
                sys.executable,'-I','-B',str(STAGE/'continuation-host.py'),'install',expected,str(active[0].id))
            print('部署与验收已交接后台服务，可关闭终端。进度：'+str(STAGE/'evidence/progress.json'),flush=True);return
        s.require(outer.status.value=='approved','Operator approval no longer active')
        time.sleep(5)
    print('等待执行登记超时，审批保留。重新运行相同入口继续，不延长期限。',flush=True)


def new_inputs(s, installer, package, domain):
    uid=61010 if domain=='learning' else 61011
    old=Path('/opt/dehps/inputs/historical-continuation-831-'+domain)
    root=Path('/opt/dehps/inputs/historical-chained-continuation-837-'+domain)
    if not root.exists():
        shutil.copytree(old,root,symlinks=True,
            ignore=lambda path,names: {'formal-cgroups','execution.json','release.json','dispatch.json','continuation.json'} if Path(path)==old else set())
        installer.copy_tree_permissions(root,61010,uid)
    prepared=s.private(CONFIG/domain/'admission-prepared.json')
    for name,value in [('continuation.json',json.loads((STAGE/'continuation.json').read_bytes())),
        ('release.json',json.loads((STAGE/(domain+'-release.json')).read_bytes())),
        ('execution.json',{'schema':'execution-input.v1','request_id':prepared['request_id'],
                          'plan':json.loads((STAGE/(domain+'-plan.json')).read_bytes())})]:
        installer.exact_file(root/name,s.canonical(value),0o440,0,uid)
    mount=root/'formal-cgroups';mount.mkdir(exist_ok=True)
    unit=s.command('systemd-escape','--path','--suffix=mount',str(mount))
    text='[Unit]\nAfter=user@1000.service\nRequires=user@1000.service\n[Mount]\nWhat=/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice\nWhere='+str(mount)+'\nType=none\nOptions=bind,ro\n[Install]\nWantedBy=multi-user.target\n'
    installer.exact_file(Path('/etc/systemd/system')/unit,text.encode())
    folder=CONFIG/domain;os.chown(folder,0,uid);folder.chmod(0o750)
    credential=folder/'operator.json';os.chown(credential,uid,uid);credential.chmod(0o600)
    env='DEHPS_RELEASE_DESCRIPTOR='+str(STAGE/(domain+'-release.json'))+'\nDEHPS_RELEASE_SHA256='+package['workers'][domain]['release_sha256']+'\n'
    installer.exact_file(folder/'release.env',env.encode(),0o640,0,uid)
    text=('[Unit]\nRequiresMountsFor='+str(mount)+'\n[Service]\nEnvironmentFile='+str(folder/'release.env')+
        '\nExecStart=\nExecStart=/usr/bin/flock --exclusive --no-fork /run/dehps/historical/'+domain+'.lock '+
        '/usr/bin/python3.14 -I -B /opt/dehps/releases/historical-publisher/launcher/launch.py run '+
        '--descriptor ${DEHPS_RELEASE_DESCRIPTOR} --release-sha256 ${DEHPS_RELEASE_SHA256} '+
        '--runtime-root /var/lib/dehps/control-'+domain+' --control-domain '+domain+' --inputs '+str(root)+
        ' --credentials '+str(credential)+' --network none --database-socket /run/dehps/'+domain+'-postgres-socket --action run\n')
    installer.exact_file(Path('/etc/systemd/system')/('dehps-historical-worker@'+domain+'.service.d/zzzz-chained-continuation-837.conf'),text.encode())
    return root,unit


def busy(s, unit):
    state=s.command('systemctl','show',unit+'.service','-p','ActiveState','--value')
    s.require(state!='failed','Historical service failed: '+unit)
    return state in {'active','activating','deactivating','reloading'}


def dispatch(s, installer, last_publish, observer_pending):
    publishing=busy(s,UNITS[0]);observing=busy(s,UNITS[2])
    if not publishing and not observing:
        # A finished publication must reach its consumer before another export.
        if observer_pending:
            installer.start_worker('observer');observer_pending=False
        elif time.monotonic()-last_publish>=900:
            s.command('systemctl','start','--no-block',UNITS[0]+'.service')
            last_publish=time.monotonic();observer_pending=True
    if not busy(s,UNITS[1]):installer.start_worker('learning')
    return last_publish,observer_pending


def install(s, package, installer, expected, execution):
    outer=s.bound_request(expected)
    active=[x for x in s.metadata_repository().list_execution_metadata(s.KEY) if x.id==execution]
    s.require(outer.status.value=='executing' and len(active)==1 and active[0].status.value=='running'
              and active[0].executor_role.value=='operator' and active[0].executor_id==s.THREAD,'Actual Operator admission absent')
    review=json.loads((CONFIG/'runtime-review.json').read_bytes());s.protected(CONFIG/'runtime-review.json')
    s.require(review['activation_packet_sha256']==expected and now()<datetime.fromisoformat(package['approved_until']), 'Runtime review absent/expired')
    for domain,uid in [('learning',61010),('observer',61011)]:
        check_replay_identity(s,domain)
        s.require(json.loads(s.command('docker','image','inspect',package['workers'][domain]['image_id']))[0]['Id']==package['workers'][domain]['image_id'], 'Fixed image absent')
    publisher(s,package,installer)
    baseline=STAGE/'evidence/before.json'
    if baseline.exists():before=json.loads(baseline.read_bytes())
    else:
        before=snapshot(s);s.save(baseline,before,0o644)
    # Pause only the independent historical chain. Immutable SQL/objects and all
    # formal P3/V11/mail units remain untouched, including on preflight failure.
    for unit in UNITS:s.command('systemctl','stop',unit+'.timer')
    for unit in UNITS:s.command('systemctl','stop',unit+'.service')
    prefix_check(s,package)
    # Retained environments verify their own records in fresh processes.
    for domain in ('learning','observer'):
        result=subprocess.run(replay_command(package,domain,prior=True),capture_output=True,text=True)
        s.save(STAGE/'evidence'/(domain+'-prior-replay.json'),{'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr},0o644)
        s.require(result.returncode==0,'Retained fixed-release replay failed')
    roots={};mounts=[]
    for domain in ('learning','observer'):
        roots[domain],unit=new_inputs(s,installer,package,domain);mounts.append(unit)
    pub_config=json.loads(CURRENT_PUBLISHER_CONFIG.read_bytes())
    s.require(pub_config['approved_until']==package['approved_until'],'Publisher original expiry differs')
    pub_config.update(learning_inputs=str(roots['learning']),observer_inputs=str(roots['observer']))
    pub_config['producer_reader']={**pub_config['producer_reader'],'inputs':str(roots['learning']),
        'release_sha256':package['workers']['learning']['release_sha256'],'code_root':str(PUB/'source')}
    installer.private_write(CONFIG/'publisher.json',pub_config)
    text=('[Service]\nExecStartPre=\nExecStart=\nExecStart=/usr/bin/flock --exclusive --no-fork /run/dehps/historical/observer.lock '+
        str(PUB/'venv/bin/python')+' -I -m dehps.prediction.historical_learning.operations publish --config '+str(CONFIG/'publisher.json')+
        '\nReadWritePaths='+str(roots['learning'])+' '+str(roots['observer'])+'\nReadOnlyPaths='+str(CONFIG)+'\n')
    old_dropin=Path('/etc/systemd/system/dehps-historical-publisher.service.d/formal-idle.conf')
    if old_dropin.exists():installer.exact_file(STAGE/'rollback/formal-idle.conf',old_dropin.read_bytes(),0o400)
    installer.exact_file(Path('/etc/systemd/system/dehps-historical-publisher.service.d/zzzz-chained-continuation-837.conf'),text.encode())
    executions={d:installer.begin(d,package) for d in ('learning','observer')}
    for domain in ('learning','observer'):
        env=Path('/etc/dehps/control')/domain/'reader.env'
        backup=STAGE/'rollback'/(domain+'-reader.env')
        if not backup.exists():installer.exact_file(backup,env.read_bytes(),0o400)
        binding={'root':'/status','controlPlane':domain,'planDigest':package['plans'][domain],
            'releaseSha256':package['workers'][domain]['release_sha256'],'executionId':executions[domain],
            'requestId':s.private(CONFIG/domain/'admission-prepared.json')['request_id'],'maxAgeSeconds':1200}
        temporary=env.with_suffix('.continuation-new');temporary.write_text('DEHPS_EXECUTION_STATUS_SOURCES='+json.dumps([binding],separators=(',',':'))+'\n')
        os.chown(temporary,0,61010 if domain=='learning' else 61011);temporary.chmod(0o640);temporary.replace(env)
    s.command('systemctl','daemon-reload')
    for unit in mounts:s.command('systemctl','enable','--now',unit)
    for domain in ('learning','observer'):
        unit='dehps-control-status@'+domain+'.service';s.command('systemctl','stop',unit)
        cid=Path('/run/dehps-'+domain+'-status-control/container.id')
        if cid.exists():
            identity=cid.read_text().strip()
            import re
            s.require(re.fullmatch('[0-9a-f]{64}',identity), 'Unexpected status container ID')
            check=subprocess.run(['docker','container','inspect','--format','{{.Id}}',identity],capture_output=True,text=True)
            s.require(check.returncode!=0 and 'no such' in check.stderr.lower(), 'Prior status container is still present')
            installer.exact_file(STAGE/'rollback'/(domain+'-'+identity+'.cid'),cid.read_bytes(),0o400);cid.unlink()
        s.command('systemctl','start',unit)
    s.save(STAGE/'evidence/runtime-identities.json',{'outer_request':outer.id,'outer_execution':execution,
        'scoped_executions':executions,'continuation_sha256':package['continuation_sha256'],'workers':package['workers'],
        'original_approved_until':package['approved_until']},0o644)
    # No dispatch was copied: first canonical admission waits for new source
    # validation. Once both plans exist, the publisher can bridge their reports.
    for domain in ('learning','observer'):s.command('systemctl','start','dehps-historical-worker@'+domain+'.service')
    s.command('systemctl','start','dehps-historical-publisher.service')
    installer.start_worker('learning')
    anchor=STAGE/'evidence/acceptance-anchor.json'
    if not anchor.exists():s.save(anchor,{'started_at':now().isoformat()},0o644)
    started=datetime.fromisoformat(json.loads(anchor.read_bytes())['started_at'])
    from datetime import timedelta
    deadline=min(started+timedelta(seconds=package['budget_seconds']),datetime.fromisoformat(package['approved_until']))
    last_publish=time.monotonic();witnessed=False;observer_pending=True
    while now()<deadline:
        outer=s.bound_request(expected)
        s.require(outer.status.value=='executing', 'Operator execution withdrawn')
        state={d:installer.progress(d) for d in ('learning','observer')}
        for domain,p in state.items():
            s.require(p.get('phase')!='failed' and not p.get('task_errors'),'Continuation runtime error: '+domain)
            if p.get('capability_progress'):
                s.require(p['release_sha256']==package['workers'][domain]['release_sha256'] and p['plan_digest']==package['plans'][domain], 'Runtime identity drift')
        lp=state['learning'].get('capability_progress',{});op=state['observer'].get('capability_progress',{})
        s.require('HISTORICAL_BATCH_BUDGET_EXHAUSTED' not in state['learning'].get('wait_reasons',{}).values(), 'Finite continuation budget exhausted')
        # Consume registered progress before starting a process which projects STARTING.
        if not witnessed and lp.get('continuation',{}).get('new_committed_count',0)>=2 and op.get('continuation',{}).get('new_committed_count',0)>=2:
            for issue in package['first_new_issues']:
                report=s.command('runuser','-u','dehps-observer','--','cat',str(roots['observer']/'reports'/(issue+'.md')))
                s.require('HISTORICAL_RECONSTRUCTION' in report,'Independent report unreadable or mislabeled')
                installer.exact_file(STAGE/'evidence'/(issue+'.md'),(report+'\n').encode())
            s.save(STAGE/'evidence/two-new-issue-witness.json',{'issues':package['first_new_issues'],
                'runs':{d:p['run_id'] for d,p in state.items()},'registered_independent_observations':True,
                'old_prefix_count':package['retained_count'],'external_delivery':False},0o644)
            for unit in UNITS:s.command('systemctl','enable','--now',unit+'.timer')
            witnessed=True
        status={'at':now().isoformat(),'first_two_witnessed':witnessed,**state}
        target=STAGE/'evidence/progress.json';temporary=target.with_suffix('.new')
        temporary.write_bytes(s.canonical(status));temporary.chmod(0o644);temporary.replace(target)
        if lp.get('batch_summary_registered') and op.get('batch_summary_registered'):
            s.require(witnessed,'Full batch requires independent witness')
            s.save(STAGE/'evidence/batch-complete-awaiting-replay.json',status,0o644)
            break
        last_publish,observer_pending=dispatch(s,installer,last_publish,observer_pending)
        time.sleep(30)
    else:raise RuntimeError('Bounded acceptance window ended; retained progress and errors preserved')
    # Full-batch replay is mandatory; use existing locks and new exact releases.
    for domain in ('learning','observer'):
        result=subprocess.run(replay_command(package,domain,prior=False),capture_output=True,text=True)
        s.save(STAGE/'evidence'/(domain+'-new-replay.json'),{'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr},0o644)
        s.require(result.returncode==0,'New fixed-release readonly replay failed')
    after=snapshot(s);s.save(STAGE/'evidence/after.json',after,0o644)
    changed=[p for p,h in before['files'].items() if after['files'][p]!=h]
    s.save(STAGE/'evidence/acceptance.json',{'new_two_witnessed':witnessed,'batch_complete':True,'replay_verified':True,
        'formal_changed_files':changed,'mail_sent_by_acceptance':False,'requires_formal_readonly_review':bool(changed)},0o644)
    s.require(not changed,'Formal bytes changed during long run; retain evidence and inspect legitimate timer activity before acceptance')


def main():
    if len(sys.argv) not in (3,4) or sys.argv[1] not in {'review','install'}:raise ValueError('Exact review/install invocation required')
    s,package,installer,reviewer=bootstrap(sys.argv[2])
    if sys.argv[1]=='review':review(s,package,installer,reviewer,sys.argv[2])
    else:install(s,package,installer,sys.argv[2],int(sys.argv[3]))


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Preserve private credentials: no traceback locals or connection repr.
        import stat
        directory=STAGE/'evidence'
        if os.geteuid()==0 and directory.is_dir() and all(
            p.lstat().st_uid==0 and not stat.S_ISLNK(p.lstat().st_mode) and not p.lstat().st_mode & 0o022
            for p in (directory,*directory.parents)):
            failure=directory/('failure-'+now().strftime('%Y%m%dT%H%M%S%f')+'.json')
            fd=os.open(failure,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump({'at':now().isoformat(),'error_type':type(error).__name__,'error':str(error)},stream)
                stream.flush();os.fsync(stream.fileno())
        print('Historical continuation stopped; original evidence retained. '+type(error).__name__,file=sys.stderr)
        if isinstance(error,ValueError):print(str(error),file=sys.stderr)
        raise SystemExit(1) from None
