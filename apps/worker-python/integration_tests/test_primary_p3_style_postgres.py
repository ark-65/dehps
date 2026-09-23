"""Real isolated PostgreSQL registration; synthetic canonical-source fixture."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

import psycopg
import pytest
from dehps.notifications.primary_style import mainline as style
from dehps.research_os.repository import PostgresResearchOSRepository


@pytest.mark.parametrize('kind', ['pre', 'post'])
def test_registered_chain_and_new_process_replay(tmp_path, monkeypatch, kind):
    dsn = os.environ.get('DEHPS_PRIMARY_STYLE_TEST_DSN')
    if not dsn:
        pytest.skip('requires a disposable PostgreSQL DSN')
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    assert info['dbname'] == 'dehps_execution_test_admin' and info['user'] == 'mail848_test_admin'
    # Every case has a fresh database; never reset failed task evidence in a
    # reused control plane merely to make a later run pass.
    database = 'style848_' + uuid.uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(database)))
    dsn = psycopg.conninfo.make_conninfo(dsn, dbname=database)
    monkeypatch.setenv('DEHPS_PRIMARY_STYLE_TEST_DSN', dsn)
    sys.path.insert(0, str(Path(__file__).parents[1] / 'tests'))
    from test_primary_p3_style import fixture_source, RECIPIENT
    source = fixture_source(kind)
    @contextmanager
    def connect():
        with psycopg.connect(dsn) as connection:
            yield connection
    repository = PostgresResearchOSRepository(connect); repository.ensure_schema()
    monkeypatch.setattr(style, 'load_source', lambda *a: source)
    try:
        live = repository.load_manifest(control_plane_key=style.PLANE).to_dict(include_digest=True)
    except style.ResearchOSValidationError:
        live = style.initial()
    payload, _ = style.build_additive_task_manifest(live_payload=live, new_tasks=style.tasks(source))
    repository.import_manifest(control_plane_key=style.PLANE, payload=payload, source='isolated-style-test')
    root = tmp_path
    supervisor = style.PresentationSupervisor(repository=repository, root_dir=root, recipient=RECIPIENT,
        git_commit='f' * 40, require_clean_tree=False)
    for key in style.keys(source['email']['issue'], kind).values():
        supervisor.run_once(task_key=key)
        assert supervisor.replay(task_key=key)['status'] == 'REPLAY_VERIFIED'
    email = style.consume(supervisor, source['email']['issue'], kind)
    assert email.text == source['email']['text'] and email.html == style.rendered(source)['body']['html']
    source_path = root / 'source.json'; source_path.write_text(json.dumps(source))
    before = repository.list_mainline_execution_events(control_plane_key=style.PLANE)
    before_files = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    script = '''
import json,os,sys
from pathlib import Path
from contextlib import contextmanager
import psycopg
from dehps.notifications.primary_style import mainline as s
from dehps.research_os.repository import PostgresResearchOSRepository
source=json.loads(Path(sys.argv[1]).read_bytes());root=Path(sys.argv[1]).parent
@contextmanager
def connect():
 with psycopg.connect(os.environ['DEHPS_PRIMARY_STYLE_TEST_DSN']) as c:
  c.execute('SET TRANSACTION READ ONLY');yield c
s.load_source=lambda *a:source
sup=s.PresentationSupervisor(repository=PostgresResearchOSRepository(connect),root_dir=root,recipient='reader@example.com',require_clean_tree=False)
email=s.consume(sup,source['email']['issue'],source['email']['kind'])
print(json.dumps({'status':'REPLAY_VERIFIED','html':email.html}))
'''
    replay = subprocess.run([sys.executable, '-c', script, str(source_path)], check=True, capture_output=True, text=True)
    assert json.loads(replay.stdout)['html'] == email.html
    assert repository.list_mainline_execution_events(control_plane_key=style.PLANE) == before
    assert {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before_files
