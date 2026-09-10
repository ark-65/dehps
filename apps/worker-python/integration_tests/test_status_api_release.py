"""Actual canonical projection -> different host UID -> read-only deployed API."""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

import psycopg
import pytest

from test_execution_mainline import mainline, child, RELEASE, records


def docker(*args, input=None, check=True):
    return subprocess.run(['docker', *args], input=input, text=True, capture_output=True,
                          check=check, timeout=90)


def test_private_projection_consumed_without_write_or_database_access(mainline, tmp_path):
    image = os.environ['DEHPS_STATUS_API_TEST_IMAGE']
    assert image.startswith('sha256:') or '@sha256:' in image
    config, admin_dsn, _ = mainline
    result = child(config, 'normal')
    assert result.returncode == 0, result.stderr
    original = Path(config['root']) / 'learning/status/execution.json'
    before = records(admin_dsn)
    projection = tmp_path / 'private-status'
    projection.mkdir(mode=0o700)
    uid = 65531 if os.getuid() != 65531 else 65530
    binding = dict(root='/status', controlPlane='learning',
                   planDigest=config['plan']['canonical']['manifest']['digest'],
                   releaseSha256=RELEASE, executionId=config['authorization']['execution_id'],
                   maxAgeSeconds=60)

    def helper(script, data=None):
        return docker('run', '--rm', '-i', '--network=none', '--user=0:0',
                      '--mount', f'type=bind,src={projection},dst=/projection',
                      '--entrypoint', 'node', image, '-e', script, input=data)

    def publish():
        # Test relocation only: production directly mounts the canonical status
        # directory. Preserve canonical bytes and original timestamps in payload.
        helper(f"const f=require('fs');const d=f.readFileSync(0);"
               f"f.writeFileSync('/projection/new.json',d,{{mode:0o600}});"
               f"f.chownSync('/projection/new.json',{uid},{uid});"
               "f.renameSync('/projection/new.json','/projection/execution.json');"
               f"f.chownSync('/projection',{uid},{uid});", original.read_text())

    container = None
    try:
        publish()
        assert projection.stat().st_uid == uid != os.getuid()
        started = docker('run', '-d', '--read-only', '--cap-drop=ALL',
                         '--security-opt=no-new-privileges', '--user', f'{uid}:{uid}',
                         '-p', '127.0.0.1::3000', '--mount',
                         f'type=bind,src={projection},dst=/status/learning/status,readonly',
                         '-e', 'DEHPS_EXECUTION_STATUS_SOURCES=' + json.dumps([binding]), image)
        container = started.stdout.strip()
        info = json.loads(docker('inspect', container).stdout)[0]
        port = info['NetworkSettings']['Ports']['3000/tcp'][0]
        assert port['HostIp'] == '127.0.0.1'
        assert len(info['Mounts']) == 1 and info['Mounts'][0]['RW'] is False
        url = f"http://127.0.0.1:{port['HostPort']}/execution-status/learning"

        def read():
            with urlopen(url, timeout=2) as response:
                return json.load(response)

        deadline = time.monotonic() + 30
        while True:
            try:
                value = read()
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise AssertionError(docker('logs', container).stdout)
                time.sleep(0.1)
        assert value['status'] == 'COMPLETED'
        assert value['runId'] == json.loads(result.stdout)['run_id']
        assert value['durableCompletionVerified'] is False
        probe = r'''
const f=require('fs');
let denied=false;
try{f.writeFileSync('/status/learning/status/execution.json','corrupt');}
catch(e){if(e.code!=='EROFS')throw e;denied=true;}
if(!denied)throw Error('status writable');
for(const p of ['/runtime','/run/dehps-credentials.json','/var/run/docker.sock','/home/ark/workspace/dehps/.env'])
  if(f.existsSync(p))throw Error('unexpected authority mount: '+p);
console.log(JSON.stringify({uid:process.getuid(),statusWrite:'EROFS',credentials:false}));
'''
        boundary = json.loads(docker('exec', container, 'node', '-e', probe).stdout)
        assert boundary['uid'] == uid
        other_uid = uid - 1
        denied = docker('exec', '--user', f'{other_uid}:{other_uid}', container,
                        'node', '-e', "try{require('fs').readFileSync('/status/learning/status/execution.json');"
                        "process.exit(2)}catch(e){if(e.code!=='EACCES')throw e}")
        assert denied.returncode == 0
        # The mounted directory, not an inode snapshot, must expose a later
        # canonical failure instead of continuing to serve an earlier success.
        with psycopg.connect(admin_dsn) as admin:
            admin.execute('UPDATE execution_authority.identities SET active=false WHERE login_name=%s',
                          (config['role'],))
        failed = child(config, 'normal')
        assert failed.returncode != 0
        publish()
        assert read()['status'] == 'FAILED'
        assert records(admin_dsn) == before
        print(json.dumps({'canonical_run_id': value['runId'], 'consumer_uid': uid,
                          'host_uid': os.getuid(), 'kernel': boundary,
                          'subsequent_status': 'FAILED', 'durable_records_unchanged': True}))
    finally:
        if container:
            docker('rm', '-f', container)
        helper(f"const f=require('fs');for(const n of f.readdirSync('/projection'))"
               f"f.chownSync('/projection/'+n,{os.getuid()},{os.getgid()});"
               f"f.chownSync('/projection',{os.getuid()},{os.getgid()});")


@pytest.mark.parametrize('uid,secret,message', [
    ('0:0', False, 'non-root UID'),
    ('65531:65531', True, 'no credentials'),
])
def test_deployed_status_entry_rejects_authority(uid, secret, message):
    image = os.environ['DEHPS_STATUS_API_TEST_IMAGE']
    binding = dict(root='/status', controlPlane='learning', planDigest='a'*64,
                   releaseSha256='b'*64, executionId=1, maxAgeSeconds=60)
    args = ['run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--user', uid, '-e',
            'DEHPS_EXECUTION_STATUS_SOURCES=' + json.dumps([binding])]
    if secret:
        args += ['-e', 'DB_PASSWORD=disposable-test-only']
    result = docker(*args, image, check=False)
    assert result.returncode != 0 and message in result.stderr
