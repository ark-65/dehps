"""Exact-package Operator handoff; genuine ark review is a separate action.

No new SQL identities, grants, tables or algorithm changes. Existing disabled
Engineering/Reviewer logins are authenticated for one bounded session then
returned to NOLOGIN/PASSWORD NULL, as in the retained host authentication flow.
"""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys

STAGE = Path('/opt/dehps/releases/historical-returns-846')
CONFIG = Path('/etc/dehps/historical-returns-846')
INPUTS = Path('/opt/dehps/inputs/historical-returns-846')
RUNTIME = Path('/var/lib/dehps/historical-returns-846')
UNITS = ('dehps-historical-result-post-mail',)
DROPIN = Path('/etc/systemd/system/dehps-historical-result-post-mail.service.d/30-returns-846.conf')
OLD = Path('/opt/dehps/releases/historical-learning-v1-d9c9899-r2')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()


def protected(path):
    for p in (path,*path.parents):
        v=p.lstat();require(not stat.S_ISLNK(v.st_mode) and v.st_uid==0 and not v.st_mode & 0o022,'protected release required')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def require_active_execution(records, execution, requester, request_id):
    # Repository returns typed metadata objects, not the adapter's JSON view.
    require(any(x.id==execution and x.request_id==request_id and x.status.value=='running'
                and x.executor_role.value=='operator' and x.executor_id==requester and x.environment=='production'
                for x in records), 'actual Operator execution differs')


def checked(expected,execution):
    require(os.geteuid()==0,'authenticated host administrator required')
    raw=(STAGE/'package.json').read_bytes();require(sha256(raw).hexdigest()==expected,'package digest differs')
    p=json.loads(raw)
    for name,identity in p['files'].items():
        path=STAGE/name;require(path.is_relative_to(STAGE) and '..' not in Path(name).parts,'package path escaped')
        protected(path);require(sha256(path.read_bytes()).hexdigest()==identity,'fixed file differs: '+name)
    for path,identity in p['retained_helpers'].items():
        protected(Path(path));require(sha256(Path(path).read_bytes()).hexdigest()==identity,'retained helper changed')
    support=load('mail_operator_support',OLD/'operator-support.py')
    repo=support.metadata_repository();request=repo.get_request(p['operator_request_key'])
    require(request.status.value=='executing' and request.requested_by==support.THREAD
            and request.payload['scope']['activation_packet_sha256']==expected,'exact active Operator request required')
    records=repo.list_execution_metadata(p['operator_request_key'])
    require_active_execution(records,execution,support.THREAD,request.id)
    require(repo.get_request('engineering-historical-mail-returns-20260923-v1').status.value=='completed','Engineering846 not accepted')
    require(datetime.now(timezone.utc)<datetime.fromisoformat(p['approved_until']),'original bounded expiry reached')
    return p,support


def write(path,data,mode=0o600,uid=0,gid=0):
    if path.exists():
        require(path.read_bytes()==data,'existing file differs; preserve: '+str(path));return
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as f:
        f.write(data);os.fchown(f.fileno(),uid,gid);f.flush();os.fsync(f.fileno())
    d=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(d)
    finally:os.close(d)


def command(*args):
    r=subprocess.run(args,capture_output=True,text=True)
    require(r.returncode==0,'bounded command failed: '+str(args[:3])+' '+r.stderr[-500:])
    return r.stdout


def install_files(p,expected):
    for path,uid,gid,mode in [(CONFIG,0,0,0o700),(INPUTS,0,61011,0o2750),(RUNTIME,61011,61011,0o700),
            (Path(p['paths']['reports']),0,1000,0o2750),(Path(p['paths']['ledger']).parent,0,0,0o700),
            (Path(p['paths']['evidence']),0,0,0o700),(Path(p['paths']['lock']).parent,0,0,0o700)]:
        path.mkdir(parents=True,exist_ok=True);os.chown(path,uid,gid);path.chmod(mode)
    for sub in ('sources','errors'):
        path=INPUTS/sub;path.mkdir(exist_ok=True);os.chown(path,0,61011);path.chmod(0o2750)
    write(INPUTS/'contract.json',(STAGE/'contract.json').read_bytes(),0o640,0,61011)
    write(INPUTS/'release.json',(STAGE/'release.json').read_bytes(),0o640,0,61011)
    old=Path('/etc/dehps/historical-chained-continuation-837/observer')
    write(CONFIG/'operator-host.json',(old/'operator-host.json').read_bytes())
    write(CONFIG/'operator.json',(old/'operator.json').read_bytes(),0o600,61011,61011)
    # The launcher needs traverse permission, while every host secret stays0600.
    CONFIG.chmod(0o711)
    require((CONFIG/'signing-key.json').exists(),'separately staged private signing key missing')
    cfg={'schema':'historical-mail-host.v1','package':str(STAGE/'package.json'),'package_sha256':expected,
        'inputs':str(INPUTS),'runtime':str(RUNTIME),'credentials':str(CONFIG/'operator-host.json'),
        'worker_credentials':str(CONFIG/'operator.json'),'key':str(CONFIG/'signing-key.json'),
        'source_credentials':'/etc/dehps/historical/source-reader.json','source_root':'/opt/dehps/inputs/historical-source',
        'readers':{'original_config':'/etc/dehps/historical-mail-842/config.json'},
        **{k:p['paths'][k] for k in ('ledger','reports','evidence','lock','formal_cgroups')}}
    write(CONFIG/'config.json',canonical(cfg))
    print('Additive return package installed; existing scheduled services unchanged; no mail sent.')


def admission(p,s):
    require(os.environ.get('SUDO_UID')=='1000' and os.environ.get('SUDO_USER')=='ark' and sys.stdin.isatty(),
            'genuine delegated ark local authentication required')
    mapping=json.loads(s.MAPPING.read_bytes());principal='unix-host:'+sha256(Path('/etc/machine-id').read_bytes()).hexdigest()+':uid:1000'
    require(sha256(s.MAPPING.read_bytes()).hexdigest()==s.MAPPING_SHA and mapping['reviewer_principal']==principal,'actual Reviewer mapping differs')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict
    from psycopg.types.json import Jsonb
    engine='dehps_control_observer_hist837_engineer';reviewer='dehps_control_observer_reviewer'
    plan=json.loads((STAGE/'plan.json').read_bytes());saved=CONFIG/'runtime-admission.json'
    params=conninfo_to_dict(s.private(s.CONTROL/'observer/admin-host.json')['dsn'])
    if saved.exists():
        item=json.loads(saved.read_bytes())
    else:
        password=secrets.token_urlsafe(48)
        with s.admin_connection('observer') as db:
            actual=db.execute('''SELECT i.principal,i.control_plane,i.can_request,i.can_review,i.can_execute,r.rolcanlogin,r.rolpassword IS NULL
                FROM execution_authority.identities i JOIN pg_authid r ON r.oid=i.login_oid WHERE i.login_name=%s''',(engine,)).fetchone()
            require(actual==(s.THREAD,'observer',True,False,False,False,True),'existing Engineering identity differs')
        try:
            with s.admin_connection('observer') as db:db.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(engine),sql.Literal(password)))
            with psycopg.connect(**{**params,'user':engine,'password':password}) as db:
                require(db.execute('SELECT session_user').fetchone()[0]==engine,'Engineering login authentication differs')
                rid=db.execute('SELECT execution_authority.request_create(%s,%s,%s)',(Jsonb(plan),p['release_sha256'],'Exact independently approved additive historical returns plan')).fetchone()[0]
                item=db.execute('SELECT execution_authority.request_get(%s)',(rid,)).fetchone()[0]
            write(saved,canonical(item))
        finally:
            with s.admin_connection('observer') as db:db.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(engine)))
            password=None
    require(item['payload']==plan and item['release_sha256']==p['release_sha256'],'prepared admission differs')
    with s.admin_connection('observer') as db:
        actual=db.execute('''SELECT i.principal,i.can_review,i.can_request,i.can_execute,r.rolcanlogin,r.rolpassword IS NULL
            FROM execution_authority.identities i JOIN pg_authid r ON r.oid=i.login_oid WHERE i.login_name=%s''',(reviewer,)).fetchone()
        require(actual==(principal,True,False,False,False,True),'existing Reviewer identity differs')
        previous=db.execute('SELECT to_jsonb(a) FROM execution_authority.approvals a WHERE request_id=%s',(item['id'],)).fetchone()
    if previous:
        require(previous[0]['content_sha256']==item['content_sha256'] and previous[0]['release_sha256']==p['release_sha256']
                and datetime.fromisoformat(previous[0]['expires_at'])==datetime.fromisoformat(p['approved_until']), 'prior approval differs; never extend')
    else:
        password=secrets.token_urlsafe(48)
        try:
            with s.admin_connection('observer') as db:db.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(reviewer),sql.Literal(password)))
            with psycopg.connect(**{**params,'user':reviewer,'password':password}) as db:
                require(db.execute('SELECT session_user').fetchone()[0]==reviewer,'Reviewer authentication differs')
                db.execute('SELECT execution_authority.approve(%s,%s,%s,%s,%s)',(item['id'],item['content_sha256'],p['release_sha256'],
                    datetime.fromisoformat(p['approved_until']),'Genuine delegated ark approval: same recipient/time, enhanced post reports and one 2026110 resend, original expiry retained'))
        finally:
            with s.admin_connection('observer') as db:db.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(reviewer)))
            password=None
    write(CONFIG/'review-receipt.json',canonical({'request_id':item['id'],'content_sha256':item['content_sha256'],
        'release_sha256':p['release_sha256'],'reviewer':principal,'expires_at':p['approved_until']}))
    print('Exact observer-domain mail plan approved through authenticated Reviewer; no workload or mail executed.')


def activate(p):
    item=json.loads((CONFIG/'runtime-admission.json').read_bytes());require((CONFIG/'review-receipt.json').exists(),'runtime approval missing')
    write(INPUTS/'execution.json',canonical({'schema':'execution-input.v1','request_id':item['id'],'plan':item['payload']}),0o640,0,61011)
    # Preparation and fresh-process replay are read/compute only: no SMTP.
    result=json.loads(command('/opt/dehps/releases/historical-chained-publisher-837/venv/bin/python','-I','-B',str(STAGE/'runner.py'),'prepare'))
    require(result.get('status')=='VERIFIED' and result.get('registered_reports',0)>0,
            'first registered readable return report missing; existing scheduled command unchanged')
    command('/opt/dehps/releases/historical-chained-publisher-837/venv/bin/python','-I','-B',str(STAGE/'runner.py'),'replay')
    # Stop only the independent post unit while switching its reviewed command.
    name=UNITS[0];command('systemctl','stop',name+'.timer');command('systemctl','stop',name+'.service')
    DROPIN.parent.mkdir(parents=True,exist_ok=True)
    write(DROPIN,(STAGE/'30-returns-846.conf').read_bytes(),0o644)
    command('systemctl','daemon-reload');command('systemctl','enable','--now',name+'.timer')
    print('Enhanced post consumer activated on the original 15-minute timer; original pre-mail and Formal P3 unchanged.')


def main():
    action,expected,execution=sys.argv[1:];p,s=checked(expected,int(execution))
    if action=='install':install_files(p,expected)
    elif action=='admit':admission(p,s)
    elif action=='activate':activate(p)
    elif action=='send':
        print(command('/opt/dehps/releases/historical-chained-publisher-837/venv/bin/python','-I','-B',str(STAGE/'runner.py'),'post'))
    elif action=='rollback':
        name=UNITS[0];command('systemctl','stop',name+'.timer');command('systemctl','stop',name+'.service')
        # A future enhanced send has no legacy sent row. Blindly restoring the old
        # automatic consumer could duplicate it, so rollback pauses only post mail.
        command('systemctl','disable',name+'.timer')
        if DROPIN.exists():write(STAGE/'evidence/rollback-dropin.conf',DROPIN.read_bytes())
        print('Independent post mail paused; all evidence retained. Pre-mail, training and Formal P3 unchanged; reconcile new ledger before restoring old post consumer.')
    else:raise ValueError('unsupported bounded Operator action')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        import traceback
        path=STAGE/'evidence'/('operator-failure-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.txt')
        try:write(path,traceback.format_exc().encode())
        except Exception:pass
        print('Bounded mail operation stopped; evidence retained. '+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1) from None
