"""Real PostgreSQL coordinator -> actual file -> separate credential-free HTTP API."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psycopg
import pytest

from mainline_scenario import coordinator
from test_execution_mainline import mainline, child, RELEASE, records


def api(config, **changed_binding):
    root = Path(__file__).resolve().parents[3]
    binding = dict(root=config['root'],controlPlane='learning',
                   planDigest=config['plan']['canonical']['manifest']['digest'],releaseSha256=RELEASE,
                   executionId=config['authorization']['execution_id'],maxAgeSeconds=60)
    binding.update(changed_binding)
    node = subprocess.check_output(['node','-p','process.execPath'],text=True).strip()
    result = subprocess.run([node,'--import','tsx','test/helpers/execution-status-http.ts'],
                            cwd=root/'apps/api',env={'PATH':os.defpath,'DEHPS_EXECUTION_STATUS_SOURCES':json.dumps([binding])},
                            check=True,capture_output=True,text=True,timeout=20)
    return json.loads(result.stdout)


def test_real_execution_consumed_by_http_without_database_credentials(mainline):
    config,admin_dsn,_=mainline
    assert api(config)['reason']=='MISSING'
    completed=child(config,'normal')
    assert completed.returncode==0,completed.stderr
    status_path=Path(config['root'])/'learning/status/execution.json'
    before=(status_path.read_bytes(),status_path.stat().st_mtime_ns,records(admin_dsn))
    response=api(config)
    assert response['status']=='COMPLETED'
    assert response['runId']==json.loads(completed.stdout)['run_id']
    assert response['executionId']==config['authorization']['execution_id']
    assert response['durableCompletionVerified'] is False
    assert response['tasks']=={'consume':'completed','source':'completed'}
    assert api(config,releaseSha256='d'*64)['reason']=='IDENTITY_MISMATCH'
    assert api(config,planDigest='d'*64)['reason']=='IDENTITY_MISMATCH'
    assert api(config,executionId=config['authorization']['execution_id']+1)['reason']=='IDENTITY_MISMATCH'
    replayed=child(config,'replay');assert replayed.returncode==0,replayed.stderr
    assert (status_path.read_bytes(),status_path.stat().st_mtime_ns,records(admin_dsn))==before
    # Force a real authenticated admission failure; committed records stay intact,
    # but an earlier completed projection must not hide the new failed process.
    with psycopg.connect(admin_dsn) as admin:
        admin.execute('UPDATE execution_authority.identities SET active=false WHERE login_name=%s',(config['role'],))
    failed=child(config,'normal');assert failed.returncode!=0
    response=api(config)
    assert response['status']=='FAILED'
    assert response['runId']!=json.loads(completed.stdout)['run_id']
    assert records(admin_dsn)==before[2]
    print(json.dumps({'canonical_run_id':json.loads(completed.stdout)['run_id'],'failed_run_id':response['runId'],
                      'http_status':response['status'],'durable_records_unchanged':True}))


def test_recovery_verifier_failure_replaces_previous_success_projection(mainline):
    config,admin_dsn,_=mainline
    successful=child(config,'normal');assert successful.returncode==0,successful.stderr
    before=records(admin_dsn)
    engine=coordinator(config)
    def reject(*args):
        raise ValueError('verification intentionally rejects stored bytes')
    engine.store.verifiers={'fixture-graph.v1':reject}
    with pytest.raises(ValueError,match='verification intentionally'):
        engine.run()
    assert api(config)['status']=='FAILED'
    assert records(admin_dsn)==before


def test_live_lease_heartbeat_keeps_http_projection_fresh(mainline):
    config,_,_=mainline
    config_file=Path(config['root'])/'heartbeat-config.json'
    config_file.write_text(json.dumps(config));config_file.chmod(0o600)
    process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('mainline_scenario.py')),
                              str(config_file),'status_heartbeat'],
                             env={'PATH':os.defpath,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),
                                  'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        status=Path(config['root'])/'learning/status/execution.json'
        updates=set()
        deadline=time.monotonic()+10
        while time.monotonic()<deadline and process.poll() is None:
            if status.exists():
                payload=json.loads(status.read_bytes())['payload']
                if payload['phase']=='running':
                    updates.add(payload['updated_at'])
                    if len(updates)>=4:
                        break
            time.sleep(0.03)
        assert len(updates)>=4, 'no live projection heartbeat'
        assert api(config,maxAgeSeconds=1)['status']=='RUNNING'
        stdout,stderr=process.communicate(timeout=10)
        assert process.returncode==0,stderr
        assert api(config)['status']=='COMPLETED'
    finally:
        if process.poll() is None:
            process.kill();process.communicate(timeout=10)
