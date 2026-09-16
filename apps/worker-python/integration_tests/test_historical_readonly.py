"""Actual CLI and SQL authority regression for the failed host prefix preflight."""
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg import sql
import pytest

from test_historical_continuation import domains, setup_prefix, install_contract
from historical_scenario import engine
from dehps.prediction.historical_learning import contract
from dehps.prediction.historical_learning.publisher import publish_observations
from dehps.execution.context import BoundaryError
from dehps.execution.release import Release, canonical
from dehps.prediction.historical_learning import operations


def rows(domains):
    result = {}
    for domain, fixture in domains.items():
        with psycopg.connect(fixture['admin']) as db:
            tables = db.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('execution_authority','execution_store','public') ORDER BY 1,2").fetchall()
            result[domain] = {'.'.join(t): db.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(*t))).fetchone()[0] for t in tables}
    return result


def files(domains):
    return {str(p): sha256(p.read_bytes()).hexdigest() for v in domains.values()
            for p in v['root'].rglob('*') if p.is_file()}


def preparation(domains, monkeypatch, tmp_path):
    release = Release(dict(schema='execution-release.v1', image_id='sha256:'+'a'*64,
        base_image_id='sha256:'+'b'*64, git_commit='c'*40, source_archive_sha256='d'*64,
        config_sha256='e'*64, entrypoint=['/usr/local/bin/python'],
        inventory={'python':'disposable fixture','packages':[]}, platform='linux/amd64'))
    c, key, configs, expected = setup_prefix(domains, monkeypatch, release.digest)
    readers = {}
    for domain, fixture in domains.items():
        binding = configs[domain]
        with psycopg.connect(fixture['admin']) as db:
            request = db.execute('SELECT request_id FROM execution_authority.executions WHERE id=%s',
                (binding['authorization']['execution_id'],)).fetchone()[0]
        inputs = fixture['root']/'inputs'
        (inputs/'execution.json').write_bytes(canonical({'request_id':request,'plan':binding['plan']}))
        (inputs/'release.json').write_bytes(canonical(release.payload))
        credentials = tmp_path/(domain+'-reader.json')
        credentials.write_bytes(canonical(asdict(fixture['clients']['operator'].database)))
        credentials.chmod(0o600)
        readers[domain] = dict(inputs=str(inputs),runtime_root=str(fixture['root']),
            reader_credentials=str(credentials), release_sha256=release.digest,
            code_root=str(Path(__file__).resolve().parents[3]))
    config = dict(schema='historical-continuation-preparation.v1',readers=readers,
        next_releases={'learning':'b'*64,'observer':'c'*64},
        original_approved_until=expected['original_approved_until'],budget_seconds=86400)
    path=tmp_path/'prepare.json';path.write_bytes(canonical(config));path.chmod(0o600)
    return path, config, expected, key


def test_actual_cli_keeps_identity_locks_and_cannot_write(domains, monkeypatch, tmp_path):
    path, config, expected, _ = preparation(domains, monkeypatch, tmp_path)
    before = rows(domains), files(domains)
    output = tmp_path/'candidate'
    python=os.environ.get('DEHPS_READONLY_TEST_PYTHON',sys.executable)
    command=[python,*(['-I','-B'] if 'DEHPS_READONLY_TEST_PYTHON' in os.environ else []),
             '-m','dehps.prediction.historical_learning.operations',
             'prepare-continuation','--config',str(path),'--output',str(output)]
    child=subprocess.run(command,capture_output=True,text=True,timeout=120)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout)['retained_count']==2
    assert (output/'continuation.json').read_bytes()==canonical(expected)
    reader=operations.reader_engine(config['readers']['learning'])
    with pytest.raises(BoundaryError,match='four authenticated read'):reader.run()
    with pytest.raises(BoundaryError,match='cannot prepare'):reader.store.artifacts.prepare(b'forbidden')
    with pytest.raises(BoundaryError,match='cannot write'):reader.store.artifacts.context.write_projection('status','x.json',{})
    forbidden=['SELECT execution_store.admit_plan(%s,%s,%s)',
        'SELECT execution_store.claim(%s,%s,%s,%s,%s)',
        'SELECT execution_store.commit_result(%s,%s,%s,%s,%s,%s,%s)',
        'SELECT execution_store.register_task(%s,%s,%s,%s)',
        'SELECT execution_store.record_mainline(%s,%s,%s,%s,%s)',
        'SELECT execution_authority.approve(%s,%s,%s,%s,%s)',
        'CREATE TEMP TABLE probe(value int)',
        'SELECT execution_authority.request_get(%s); SELECT 1',
        sql.SQL('SELECT execution_authority.request_get(%s)')]
    with reader.store.database.connect() as connection:
        for statement in forbidden:
            with pytest.raises(BoundaryError,match='four authenticated read'):
                connection.execute(statement,(1,))
    assert (rows(domains),files(domains))==before


def test_actual_root_reads_service_owned_domains_in_disposable_container(domains, monkeypatch, tmp_path):
    image=os.environ.get('DEHPS_READONLY_TEST_IMAGE')
    if not image:pytest.skip('requires explicit fixed disposable test image')
    path, config, expected, _=preparation(domains,monkeypatch,tmp_path)
    before=rows(domains),files(domains)
    # Only a disposable fixture and reviewed source enter the container. No
    # production mount, Docker socket, host root write or privileged mode.
    script=r'''
import json,os,shutil,subprocess,sys
from pathlib import Path
from hashlib import sha256
from dehps.execution.context import RunContext,BoundaryError
from dehps.prediction.historical_learning.readonly import ReadonlyContext
shutil.copytree('/fixture','/tmp/fixture')
root=Path('/tmp/fixture');config=json.loads((root/'prepare.json').read_bytes())
for domain,uid in [('learning',61010),('observer',61011)]:
    reader=config['readers'][domain]
    reader.update(inputs=str(root/domain/'inputs'),runtime_root=str(root/domain),
        reader_credentials=str(root/(domain+'-reader.json')),code_root='/source')
    for p in [root/domain,*(root/domain).rglob('*')]:os.chown(p,uid,uid)
    try:RunContext(root/domain,domain)
    except BoundaryError:pass
    else:raise AssertionError('generic writable owner guard weakened')
    ReadonlyContext(root/domain,domain)
    try:ReadonlyContext(root/domain,'observer' if domain=='learning' else 'learning')
    except BoundaryError:pass
    else:raise AssertionError('cross-domain service owner admitted')
def files():return {str(p):sha256(p.read_bytes()).hexdigest() for d in ('learning','observer') for p in (root/d).rglob('*') if p.is_file()}
before=files();path=root/'prepare.json';path.write_text(json.dumps(config));path.chmod(0o600)
child=subprocess.run([sys.executable,'-m','dehps.prediction.historical_learning.operations','prepare-continuation','--config',str(path),'--output',str(root/'candidate')],capture_output=True,text=True)
assert child.returncode==0,child.stderr
assert files()==before
assert (root/'candidate/continuation.json').read_bytes()==(root/'expected.json').read_bytes()
print(child.stdout.strip())
'''
    (tmp_path/'expected.json').write_bytes(canonical(expected))
    child=subprocess.run(['docker','run','--rm','--read-only','--network=host',
        '--label','org.dehps.scope=engineering-829-disposable-test','--user=0:0',
        '--cap-drop=ALL','--cap-add=CHOWN','--cap-add=DAC_OVERRIDE',
        '--security-opt=no-new-privileges','--tmpfs=/tmp:rw,nosuid,nodev,size=128m',
        '--mount',f'type=bind,src={tmp_path},dst=/fixture,readonly',
        '--mount',f'type=bind,src={Path(__file__).resolve().parents[3]},dst=/source,readonly',
        '--env','PYTHONPATH=/source/apps/worker-python','--env','PYTHONDONTWRITEBYTECODE=1',
        '--entrypoint=/usr/local/bin/python',image,'-c',script],capture_output=True,text=True,timeout=120)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout)['retained_count']==2
    assert (rows(domains),files(domains))==before


def test_publisher_reader_handles_committed_mixed_release_prefix(domains, monkeypatch, tmp_path):
    _, config, value, key = preparation(domains, monkeypatch, tmp_path)
    releases = {}
    for domain, reader in config['readers'].items():
        release = json.loads((Path(reader['inputs'])/'release.json').read_bytes())
        release['image_id']='sha256:'+'f'*64
        releases[domain] = Release(release)
        value['domains'][domain]['next_release_sha256'] = releases[domain].digest
    original=json.loads((domains['learning']['root']/'inputs/contract.json').read_bytes())
    configs=install_contract(domains,original,value)
    engine(configs['learning']).run()
    for domain, reader in config['readers'].items():
        with psycopg.connect(domains[domain]['admin']) as db:
            request=db.execute('SELECT request_id FROM execution_authority.executions WHERE id=%s',
                (configs[domain]['authorization']['execution_id'],)).fetchone()[0]
        inputs=Path(reader['inputs'])
        (inputs/'execution.json').write_bytes(canonical({'request_id':request,'plan':configs[domain]['plan']}))
        (inputs/'release.json').write_bytes(canonical(releases[domain].payload))
        reader['release_sha256']=releases[domain].digest
    before=rows(domains)
    producer=operations.reader_engine(config['readers']['learning'])
    target=contract.Inputs(domains['observer']['root']/'inputs',contract.digest(original))
    assert publish_observations(target,producer,key,approved_until=value['original_approved_until'])==[-1,902,903]
    assert rows(domains)==before
    observed=engine(configs['observer']);observed.run()
    assert '保留原版本 2 期' in (target.root/'reports/summary.md').read_text()
    before=rows(domains),files(domains)
    for domain, reader in config['readers'].items():
        operations.reader_engine({**reader,'domain':domain}).replay(require_complete=False)
    assert (rows(domains),files(domains))==before
