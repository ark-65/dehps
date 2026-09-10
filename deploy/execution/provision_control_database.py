"""Install the reviewed control schema into an empty, explicitly identified DB.

Trusted administrator operation, never a runtime migration or approval endpoint.
Login credentials are provisioned separately to their actual owners. In
particular this installer neither generates a Reviewer secret nor approves a
request. A successful installation is not deployment/research approval.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict


SCHEMA_FILES = (
    'infra/postgres/init/002_research_os.sql',
    'apps/worker-python/dehps/execution/migrations/001_authority.sql',
    'apps/worker-python/dehps/execution/migrations/002_store.sql',
    'apps/worker-python/dehps/execution/migrations/003_mainline.sql',
)
AUTHORITY = {
    'engineer': ('request_create(jsonb,text,text)', 'request_get(bigint)'),
    'reviewer': ('request_get(bigint)', 'approve(bigint,text,text,timestamptz,text)', 'revoke(bigint)'),
    'operator': ('request_get(bigint)', 'begin_execution(bigint,text,text,text)',
                 'reauthorize(bigint,text,text)'),
}
STORE = (
    'register_task(bigint,text,text,jsonb)', 'read_result(bigint)',
    'claim(bigint,bigint,text,text,integer)', 'renew(bigint,uuid,bigint,text,text,integer)',
    'fail(bigint,uuid,bigint,text,text,text)',
    'commit_result(bigint,uuid,bigint,text,text,text,bigint)',
    'admit_plan(bigint,text,text)', 'read_plan(text)', 'mainline_context(bigint)',
    'record_mainline(bigint,bigint,text,text,jsonb)',
)


def validate_spec(spec: dict, source: Path) -> dict[str, str]:
    if (set(spec) != {'schema', 'database', 'system_identifier', 'domain', 'principals', 'sql_sha256'}
            or spec['schema'] != 'dehps-control-database-install.v1'
            or spec['domain'] not in {'learning', 'observer'}
            or not re.fullmatch(r'dehps_control_[a-z][a-z0-9_]{0,24}', spec['database'])
            or not re.fullmatch(r'[0-9]{1,20}', spec['system_identifier'])):
        raise ValueError('closed independent control database specification required')
    principals = spec['principals']
    if (set(principals) != set(AUTHORITY)
            or any(not isinstance(p, str) or not 1 <= len(p) <= 200 for p in principals.values())
            or principals['reviewer'] in {principals['engineer'], principals['operator']}):
        raise ValueError('Reviewer must be a distinct administrator-verified principal')
    if set(spec['sql_sha256']) != set(SCHEMA_FILES):
        raise ValueError('exact schema file inventory required')
    if not source.is_absolute() or source.resolve() != source:
        raise ValueError('canonical schema source required')
    contents = {}
    for relative in SCHEMA_FILES:
        path = source / relative
        if path.resolve() != path or not path.is_file():
            raise ValueError('regular schema file required')
        data = path.read_bytes()
        if sha256(data).hexdigest() != spec['sql_sha256'][relative]:
            raise ValueError(f'reviewed schema bytes differ: {relative}')
        contents[relative] = data.decode('utf-8')
    return contents


def install(admin_dsn: str, spec: dict, source: Path) -> dict:
    contents = validate_spec(spec, source)
    if any(key.startswith('PG') and value for key, value in os.environ.items()):
        raise ValueError('remove ambient libpq configuration before installing')
    connection = conninfo_to_dict(admin_dsn)
    required = {'host', 'port', 'user', 'password', 'dbname'}
    if (not required <= set(connection) or not all(connection[k] for k in required)
            or set(connection) - (required | {'sslmode', 'sslrootcert'})
            or connection['dbname'] != spec['database']):
        raise ValueError('explicit administrator connection to the reviewed database required')
    database = spec['database']
    owner = database + '_owner'
    roles = {kind: database + '_' + kind for kind in AUTHORITY}
    # CREATE ROLE and all schema/grant changes are transactional. Any failure
    # leaves this existing empty database and all roles as they were before.
    with psycopg.connect(admin_dsn, connect_timeout=5) as admin:
        actual = admin.execute('SELECT current_database(),system_identifier::text FROM pg_control_system()').fetchone()
        if actual != (database, spec['system_identifier']):
            raise ValueError('actual database cluster identity differs from reviewed target')
        if admin.execute("SELECT 1 FROM pg_namespace WHERE nspname IN ('execution_authority','execution_store')").fetchone():
            raise ValueError('existing execution schema: installation never overwrites or resumes implicitly')
        occupied = admin.execute("""SELECT
            EXISTS (SELECT 1 FROM pg_class WHERE relnamespace='public'::regnamespace)
            OR EXISTS (SELECT 1 FROM pg_proc WHERE pronamespace='public'::regnamespace)
            OR EXISTS (SELECT 1 FROM pg_type WHERE typnamespace='public'::regnamespace)
            OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspname NOT IN ('public','information_schema')
                       AND nspname NOT LIKE 'pg\\_%' ESCAPE '\\')""").fetchone()[0]
        if occupied:
            raise ValueError('empty control database required')
        ownership = admin.execute('''SELECT pg_get_userbyid(datdba)=current_user,datacl IS NULL
            FROM pg_database WHERE datname=current_database()''').fetchone()
        if ownership != (True, True):
            raise ValueError('new database owned by this administrator with untouched ACL required')
        if admin.execute('SELECT 1 FROM pg_roles WHERE rolname=ANY(%s)', ([owner, *roles.values()],)).fetchone():
            raise ValueError('existing deployment role: installation never reassigns an identity')
        admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(database)))
        admin.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
        for role in [owner, *roles.values()]:
            admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS').format(sql.Identifier(role)))
        admin.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO {}').format(sql.Identifier(database), sql.Identifier(owner)))
        admin.execute(sql.SQL('GRANT USAGE,CREATE ON SCHEMA public TO {}').format(sql.Identifier(owner)))
        admin.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(owner)))
        for relative in SCHEMA_FILES:
            admin.execute(contents[relative])
        admin.execute('RESET ROLE')
        admin.execute(sql.SQL('REVOKE CREATE ON DATABASE {} FROM {}').format(sql.Identifier(database), sql.Identifier(owner)))
        admin.execute(sql.SQL('REVOKE CREATE ON SCHEMA public FROM {}').format(sql.Identifier(owner)))
        for kind, role in roles.items():
            admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(database), sql.Identifier(role)))
            admin.execute('''INSERT INTO execution_authority.identities
                (login_oid,login_name,principal,control_plane,can_request,can_review,can_execute)
                SELECT oid,rolname,%s,%s,%s,%s,%s FROM pg_roles WHERE rolname=%s''',
                (spec['principals'][kind], spec['domain'], kind == 'engineer',
                 kind == 'reviewer', kind == 'operator', role))
            admin.execute(sql.SQL('GRANT USAGE ON SCHEMA execution_authority TO {}').format(sql.Identifier(role)))
            for signature in AUTHORITY[kind]:
                admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION execution_authority.{} TO {}').format(sql.SQL(signature), sql.Identifier(role)))
        operator = sql.Identifier(roles['operator'])
        admin.execute(sql.SQL('GRANT USAGE ON SCHEMA execution_store TO {}').format(operator))
        for signature in STORE:
            admin.execute(sql.SQL('GRANT EXECUTE ON FUNCTION execution_store.{} TO {}').format(sql.SQL(signature), operator))
        if (admin.execute('SELECT count(*) FROM execution_authority.approvals').fetchone()[0]
                or admin.execute('SELECT count(*) FROM execution_authority.executions').fetchone()[0]):
            raise ValueError('installation must not create approvals or executions')
    return {'schema': 'dehps-control-database-install-result.v1', 'database': database,
            'system_identifier': spec['system_identifier'], 'owner': owner, 'roles': roles,
            'spec_sha256': sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'status': 'INSTALLED_LOGINS_DISABLED', 'request_approvals_created': 0,
            'runtime_executions_created': 0}


def private_json(path: Path) -> dict:
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('canonical private credential file required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('administrator credentials must be private and owned by the caller')
        value = json.load(stream)
    if set(value) != {'dsn'}:
        raise ValueError('closed administrator credential record required')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admin-credentials', required=True, type=Path)
    parser.add_argument('--spec', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(install(private_json(args.admin_credentials)['dsn'],
                             json.loads(args.spec.read_bytes()), args.source_root), sort_keys=True))
