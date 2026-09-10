"""An installed learning image uses only a private PostgreSQL Unix socket."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import socket as unix_sockets
import subprocess
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from dehps.execution.authority import AuthorityClient
from dehps.execution.context import BoundaryError, RunContext
from dehps.execution.database import DatabaseBinding
from dehps.execution.release import canonical, launch
from dehps.prediction.learning_plan import build_plan
from test_control_database_install import ROOT, installer, control_database_target
from test_execution_mainline import records
from test_learning_execution import learning_packet, synthetic
from test_learning_release import learning_release


def wait_for_socket(details):
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(make_conninfo(**details),connect_timeout=1) as connection:
                # Don't admit the official entrypoint's temporary init server.
                if connection.execute("SELECT split_part(pg_read_file('postmaster.pid'),chr(10),1)").fetchone() == ('1',):
                    return
        except psycopg.OperationalError:
            pass
        time.sleep(0.1)
    raise AssertionError('socket test database startup timed out')


@pytest.fixture(params=['image-default', 'dedicated-uid'])
def socket_target(tmp_path, request):
    # CI starts a separate socket-only server from its actual labelled test
    # image. Never add a mount, restart or alter the existing server.
    existing = json.loads(subprocess.check_output(['docker','inspect',
        os.environ['DEHPS_EXECUTION_TEST_CONTAINER']],text=True))[0]
    assert existing['Config']['Labels'].get('dehps.execution-test') == 'true'
    root = tmp_path/'socket-postgres'; root.mkdir(mode=0o755)
    socket = root/'socket'; socket.mkdir(mode=0o750)
    password = uuid4().hex
    nonce = uuid4().hex
    dedicated = request.param == 'dedicated-uid'
    uid = 61012
    assert not dedicated or uid != os.getuid()
    extra = []
    entry = ['--entrypoint','/bin/sh',existing['Image'],'-ec',
             f'chown postgres:{os.getgid()} /socket; chmod 2750 /socket; exec /usr/local/bin/docker-entrypoint.sh "$@"',
             '--']
    secret_args = ['--env','POSTGRES_PASSWORD='+password]

    def ownership(owner):
        # Only this disposable fixture mount is exposed to the setup helper.
        subprocess.run(['docker','run','--rm','--network=none','--user=0:0',
            '--mount',f'type=bind,src={root},dst=/fixture','--entrypoint','/bin/sh',
            existing['Image'],'-ec',
            f'chown -R {owner}:{os.getgid()} /fixture/data /fixture/socket /fixture/admin-password; '
            'chmod 2750 /fixture/socket; chmod 700 /fixture/data; chmod 600 /fixture/admin-password'],
            check=True,capture_output=True)

    if dedicated:
        data = root/'data'; data.mkdir(mode=0o700)
        secret = root/'admin-password'; secret.write_text(password); secret.chmod(0o600)
        ownership(uid)
        extra = ['--user',f'{uid}:{os.getgid()}', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                 '--mount',f'type=bind,src={data},dst=/var/lib/postgresql/data',
                 '--mount',f'type=bind,src={secret},dst=/run/control-admin-password,readonly']
        secret_args = ['--env','POSTGRES_PASSWORD_FILE=/run/control-admin-password']
        entry = [existing['Image']]
    container = subprocess.check_output(['docker','run','-d',
        '--label','dehps.execution-test=true','--label','dehps.socket-test='+nonce,
        '--network=none','--mount',f'type=bind,src={socket},dst=/socket',
        '--env','POSTGRES_USER=execution_test_admin','--env','POSTGRES_DB=dehps_execution_test_admin',
        *secret_args,'--env','POSTGRES_INITDB_ARGS=--auth-local=scram-sha-256',
        *extra,*entry,'postgres','-c','listen_addresses=',
        '-c','unix_socket_directories=/var/run/postgresql,/socket','-c','unix_socket_permissions=0770'],text=True).strip()
    details = {'host':str(socket),'port':'5432','dbname':'dehps_execution_test_admin',
               'user':'execution_test_admin','password':password}
    try:
        wait_for_socket(details)
        info = json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0]
        assert info['HostConfig']['NetworkMode'] == 'none' and not info['NetworkSettings']['Ports']
        if dedicated:
            assert info['Config']['User'] == f'{uid}:{os.getgid()}'
            assert socket.stat().st_uid == (root/'data').stat().st_uid == uid
            assert socket.stat().st_gid == os.getgid()
            assert subprocess.check_output(['docker','exec',container,'id','-u'],text=True).strip() == str(uid)
            process_status = subprocess.check_output(['docker','exec',container,'cat','/proc/1/status'],text=True)
            assert 'CapEff:\t0000000000000000' in process_status
            assert 'NoNewPrivs:\t1' in process_status
        with control_database_target(details) as value:
            yield (*value,container)
    finally:
        info = json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0]
        assert info['Config']['Labels'].get('dehps.socket-test') == nonce
        subprocess.run(['docker','stop',container],check=True,capture_output=True)
        (root/'postgres.log').write_bytes(subprocess.check_output(['docker','logs',container],stderr=subprocess.STDOUT))
        subprocess.run(['docker','rm','--volumes',container],check=True,capture_output=True)
        if dedicated:
            ownership(os.getuid())


def test_networkless_learning_runs_and_replays_through_installed_socket_database(
        socket_target, learning_packet, learning_release, tmp_path):
    spec, admin_dsn, details, database_container = socket_target
    socket = Path(details['host'])
    assert socket.is_absolute(), 'this test must use the dedicated Unix socket PostgreSQL fixture'
    installed = installer.install(admin_dsn, spec, ROOT)
    clients = {}
    with psycopg.connect(admin_dsn) as admin:
        assert admin.execute("SELECT inet_server_addr(),current_setting('listen_addresses')").fetchone() == (None, '')
        assert admin.execute("SELECT current_setting('fsync'),current_setting('synchronous_commit')").fetchone() == ('on','on')
        assert all(row[0] == 'scram-sha-256' for row in admin.execute("SELECT auth_method FROM pg_hba_file_rules WHERE type='local'").fetchall())
        for kind, role in installed['roles'].items():
            password = uuid4().hex
            admin.execute(sql.SQL('ALTER ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
            dsn = make_conninfo(**{**details,'dbname':spec['database'],'user':role,'password':password})
            clients[kind] = AuthorityClient(DatabaseBinding(dsn,spec['database'],role))
    # Isolated fixture approval only. This is not independent production review.
    packet_root, digest, scientific = learning_packet
    directory = tmp_path/'inputs'; shutil.copytree(packet_root,directory)
    runtime = tmp_path/'runtime'; runtime.mkdir(mode=0o700)
    plan = build_plan(inputs_sha256=digest,scientific_contract_sha256=scientific)
    release = learning_release
    request = clients['engineer'].request(plan.payload,release.digest)
    content = clients['reviewer'].get(request)['content_sha256']
    clients['reviewer'].approve(request,content,release.digest,datetime.now(timezone.utc)+timedelta(hours=1))
    (directory/'release.json').write_bytes(canonical(release.payload))
    (directory/'execution.json').write_bytes(canonical({'schema':'execution-input.v1','request_id':request,'plan':plan.payload}))
    db = clients['operator'].database
    credentials = tmp_path/'credentials.json'
    connection = {**conninfo_to_dict(db.dsn),'host':'/run/dehps-postgres'}
    credentials.write_bytes(canonical({'dsn':make_conninfo(**connection),'database':db.database,'role':db.role}))
    credentials.chmod(0o600)
    context = RunContext(runtime,'learning')
    args = dict(inputs=directory,credentials=credentials,network='none',database_socket=socket,timeout=1800)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(launch,release,release.digest,context,action='run',**args)
        transport = None
        deadline = time.monotonic() + 60
        while not future.done() and time.monotonic() < deadline:
            ids = subprocess.check_output(['docker','ps','--no-trunc','--filter',
                'label=org.dehps.launch','--format','{{.ID}}'],text=True).split()
            for container in ids:
                info = json.loads(subprocess.check_output(['docker','inspect',container],text=True))[0]
                mounts = {m['Destination']:m for m in info['Mounts']}
                if mounts.get('/runtime',{}).get('Source') != str(runtime): continue
                assert info['HostConfig']['NetworkMode'] == 'none'
                assert info['Config']['User'] == f'{os.getuid()}:{os.getgid()}'
                assert mounts['/run/dehps-postgres']['Source'] == str(socket)
                assert mounts['/run/dehps-postgres']['RW'] is False
                probe = subprocess.check_output(['docker','exec',container,'/usr/local/bin/python','-I','-c',
                    "import os,json; from pathlib import Path; print(json.dumps({'uid':os.getuid(),'interfaces':sorted(p.name for p in Path('/sys/class/net').iterdir()),'socket_mount_readonly':bool(os.statvfs('/run/dehps-postgres').f_flag & os.ST_RDONLY)}))"],text=True)
                transport = json.loads(probe)
                assert transport == {'uid':os.getuid(),'interfaces':['lo'],'socket_mount_readonly':True}
                break
            if transport is not None: break
            time.sleep(0.05)
        first = future.result(timeout=1800)
    assert transport is not None, 'actual running worker transport was not inspected'
    assert first.returncode == 0, first.stderr.decode()
    result = json.loads(first.stdout)
    assert len(result['artifacts']) == 5 and set(result['tasks'].values()) == {'completed'}
    before = records(admin_dsn)
    status = runtime/'learning/status/execution.json'
    before_status = status.read_bytes(),status.stat().st_mtime_ns
    # Recreate the real socket after a server restart. A stale socket-file bind
    # would fail here; this exercises the retained directory mount and database.
    subprocess.run(['docker','restart',database_container],check=True,capture_output=True)
    wait_for_socket(details)
    assert records(admin_dsn) == before
    replay = launch(release,release.digest,context,action='replay',**args)
    assert replay.returncode == 0, replay.stderr.decode()
    replayed = json.loads(replay.stdout)
    assert replayed['run_id'] != result['run_id']
    assert replayed['artifacts'] == result['artifacts']
    assert replayed['manifest_digest'] == result['manifest_digest']
    assert before['execution_store.commits'] == before['public.research_os_mainline_artifacts'] == 5
    assert records(admin_dsn) == before
    assert (status.read_bytes(),status.stat().st_mtime_ns) == before_status
    with pytest.raises(BoundaryError,match='disabled IP networking'):
        launch(release,release.digest,context,action='run',**{**args,'network':'dehps-unapproved-network'})
    untrusted = tmp_path/'runtime-owned-socket'; untrusted.mkdir(mode=0o750)
    with unix_sockets.socket(unix_sockets.AF_UNIX,unix_sockets.SOCK_STREAM) as fake:
        fake.bind(str(untrusted/'.s.PGSQL.5432'))
        with pytest.raises(BoundaryError,match='PostgreSQL-owned'):
            launch(release,release.digest,context,action='run',**{**args,'database_socket':untrusted})
    assert records(admin_dsn) == before
    print(json.dumps({'release':release.digest,'transport':'private Unix socket','network':'none',
                      'run_id':result['run_id'],'replay_run_id':replayed['run_id'],
                      'manifest_digest':result['manifest_digest'],'commits':5,'replay_writes':0,
                      'kernel_transport':transport,'database_restarted':True,
                      'database_uid':socket.stat().st_uid}))
