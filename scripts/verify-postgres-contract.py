#!/usr/bin/env python3
"""hub 데이터베이스 역할 계약을 빈 PostgreSQL/PostGIS 에서 검사한다.

검사하는 것:
  - 역할 SQL(scripts/database-roles.sql)로 만든 migrator 가 실제 리비전을
    두 번 돌려도 같은 결과가 나온다(멱등).
  - runtime 역할로 기동 계약 검사·예보 적재·금지 구역 CRUD 가 된다.
  - runtime 은 DDL·소유 역할 전환·다른 데이터 읽기가 42501 로 막힌다.
  - migrator 는 hub_data 안에서만 DDL 을 할 수 있다.

대상은 로컬의 빈 DB(이름이 contract_ 로 시작)만 허용한다. 컨테이너를 띄우거나
지우지 않고, 외부 공급자를 부르지 않는다. 운영자 접속 정보는 환경변수로만 받는다.
서비스 간 격리(다른 서비스 스키마와의 경계)는 map-project-infra 의 통합 검사가 맡는다.
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parents[1]
ROLES_SQL = ROOT / 'scripts' / 'database-roles.sql'
PHASE = 'initialization'
REPORT = None


def execute(args, env, cwd=None):
    global PHASE
    PHASE = args[2] if len(args) > 2 and args[1] == '-m' else Path(args[0]).name
    completed = subprocess.run(args, env=env, cwd=cwd, capture_output=True, text=True, timeout=900)
    if completed.returncode:
        # 오류 본문에는 접속 정보·SQL 인자가 섞일 수 있어 분류와 지문만 남긴다.
        classes = sorted(set(re.findall(r"(?:psycopg(?:\.errors)?|sqlalchemy\.exc)\.([A-Za-z][A-Za-z0-9_]{0,80})", completed.stderr)))
        safe_lines = [line[:200] for line in completed.stderr.splitlines() if re.fullmatch(r"Hub [A-Za-z0-9 _;:=(),.-]{1,190}", line)]
        details = dict(phase=PHASE, exit=completed.returncode, error_classes=classes, safe_messages=safe_lines[-3:], stderr_sha256=hashlib.sha256(completed.stderr.encode()).hexdigest())
        raise RuntimeError(json.dumps(details))


def base_env():
    return {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'TMPDIR', 'SSL_CERT_FILE')}


def denied(conn, statement):
    try:
        conn.execute(statement)
    except psycopg.Error as error:
        if error.sqlstate != '42501':
            raise RuntimeError('unexpected SQLSTATE ' + str(error.sqlstate)) from None
    else:
        raise RuntimeError('forbidden operation accepted')


async def worker(source, dsn):
    """runtime 역할로 접속해 앱 코드 경로를 그대로 돌린다."""
    global PHASE
    PHASE = 'hub_imports'
    sys.path.insert(0, str(source))
    os.environ['HUB_DATABASE_URL'] = dsn.replace('postgresql://', 'postgresql+psycopg://')
    from map_project_hub.db.hub_db import get_hub_db, dispose_hub_db
    from map_project_hub.db.schema_contract import validate_runtime_schema
    from map_project_hub.db import forecast_repo, admin_ops_repo
    try:
        PHASE = 'hub_schema_guard'
        await validate_runtime_schema(get_hub_db())
        PHASE = 'hub_kma_upsert_and_region_query'
        kst = timezone(timedelta(hours=9))
        base = datetime.now(kst).replace(minute=0, second=0, microsecond=0)
        fcst = base + timedelta(hours=1)
        item = dict(fcstDate=fcst.strftime('%Y%m%d'), fcstTime=fcst.strftime('%H%M'), category='TMP', fcstValue='22')
        assert await forecast_repo.upsert_short_term_items(60, 127, base, [item]) == 1
        item['fcstValue'] = '23'
        assert await forecast_repo.upsert_short_term_items(60, 127, base + timedelta(minutes=1), [item]) == 1
        rows, _ = await forecast_repo.fetch_short_term_range(60, 127, fcst.date(), fcst.date())
        assert len(rows) == 1 and rows[0]['fcst_value'] == '23'
        assert not (await forecast_repo.fetch_short_term_range(61, 127, fcst.date(), fcst.date()))[0]
        PHASE = 'hub_postgis_sequence_crud'
        zone = dict(type='Polygon', coordinates=[[[127, 37], [127.001, 37], [127.001, 37.001], [127, 37]]])
        created = await admin_ops_repo.create_forbidden_zone('contract-fixture', 'synthetic', zone)
        zid = created['zone_id']
        assert (await admin_ops_repo.get_forbidden_zone(zid))['name'] == 'contract-fixture'
        assert (await admin_ops_repo.update_forbidden_zone(zid, 'contract-updated', 'synthetic', zone))['name'] == 'contract-updated'
        assert await admin_ops_repo.delete_forbidden_zone(zid)
        assert await admin_ops_repo.get_forbidden_zone(zid) is None
        await forecast_repo.housekeeping_expire()
    finally:
        await dispose_hub_db()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT, help='hub 레포 경로(기본: 이 스크립트가 있는 레포)')
    parser.add_argument('--python', default=sys.executable, help='hub 의존성이 설치된 파이썬')
    parser.add_argument('--operator-dsn-env', default='HUB_CONTRACT_FIXTURE_DSN')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    global REPORT
    REPORT = args.output
    if args.worker:
        asyncio.run(worker(args.source, os.environ['HUB_CONTRACT_RUNTIME_DSN']))
        return
    if not args.output:
        parser.error('--output is required')
    dsn = os.environ[args.operator_dsn_env]
    cfg = conninfo_to_dict(dsn)
    if cfg.get('host') not in ('127.0.0.1', 'localhost', '::1') or not cfg.get('dbname', '').startswith('contract_'):
        raise RuntimeError('only a local explicitly named contract_* empty fixture database is allowed')
    source = args.source.resolve()
    results = {'environment': 'isolated PostgreSQL fixture', 'started_utc': datetime.now(timezone.utc).isoformat(), 'checks': {},
               'source': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()}
    env = base_env()
    for key, value in cfg.items():
        if key in ('host', 'port', 'dbname', 'user', 'password'):
            env[{'dbname': 'PGDATABASE'}.get(key, 'PG' + key.upper())] = value

    def psql(path):
        execute(['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-f', str(path)], env)

    roles_sql = source / 'scripts' / 'database-roles.sql'
    with psycopg.connect(dsn, autocommit=True) as operator:
        assert operator.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p')").fetchone()[0] == 0
        results['postgres_version'] = operator.execute('SHOW server_version').fetchone()[0]
        assert results['postgres_version'].startswith('17.')
        operator.execute('CREATE EXTENSION postgis')
        results['postgis_version'] = operator.execute('SELECT postgis_full_version()').fetchone()[0]
        operator.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        # 다른 서비스가 public 에 둔 데이터를 흉내 낸다. hub 역할은 읽지 못해야 하고, 끝까지 남아 있어야 한다.
        operator.execute('CREATE TABLE public.contract_sentinel (id integer primary key, value text)')
        operator.execute("INSERT INTO public.contract_sentinel VALUES (1,'synthetic-preserved')")
        psql(roles_sql)
        passwords = {role: secrets.token_urlsafe(24) for role in ('map_hub_migrator', 'map_hub_runtime')}
        for role, password in passwords.items():
            operator.execute(sql.SQL('ALTER ROLE {} PASSWORD {}').format(sql.Identifier(role), sql.Literal(password)))

        def role_dsn(role, sqlalchemy=False):
            from sqlalchemy.engine import URL
            uri = URL.create('postgresql+psycopg' if sqlalchemy else 'postgresql', username=role, password=passwords[role],
                             host=cfg['host'], port=int(cfg.get('port', 5432)), database=cfg['dbname'])
            return uri.render_as_string(hide_password=False)

        child = base_env()
        child['HUB_MIGRATION_DATABASE_URL'] = role_dsn('map_hub_migrator', True)
        command = [args.python, '-m', 'map_project_hub.db.migrate']
        # 빈 DB 의 첫 리비전은 스키마가 있어도 DB CREATE 권한을 확인한다. 그 한 번만 주고 바로 거둔다.
        operator.execute(sql.SQL('GRANT CREATE ON DATABASE {} TO map_hub_owner').format(sql.Identifier(cfg['dbname'])))
        try:
            execute(command, child, source)
        finally:
            operator.execute(sql.SQL('REVOKE CREATE ON DATABASE {} FROM map_hub_owner').format(sql.Identifier(cfg['dbname'])))
        execute(command, child, source)
        results['checks']['hub_real_migrations_idempotent'] = 'PASS'
        psql(roles_sql)
        child = base_env()
        child['HUB_CONTRACT_RUNTIME_DSN'] = role_dsn('map_hub_runtime')
        execute([args.python, str(Path(__file__).resolve()), '--worker', '--source', str(source)], child)
        results['checks']['hub_runtime_schema_and_repository_crud'] = 'PASS'
        forbidden = ['CREATE TABLE hub_data.contract_forbidden(id int)',
                     'ALTER TABLE hub_data.short_term_forecast ADD COLUMN forbidden int',
                     'DROP TABLE hub_data.short_term_forecast',
                     'UPDATE hub_data.region_grid SET lv1=lv1',
                     'SET ROLE map_hub_owner',
                     'CREATE TABLE public.contract_forbidden(id int)',
                     'SELECT * FROM public.contract_sentinel']
        with psycopg.connect(role_dsn('map_hub_runtime'), autocommit=True) as conn:
            for statement in forbidden:
                denied(conn, statement)
        results['checks']['map_hub_runtime_42501_count'] = len(forbidden)
        results['checks']['map_hub_runtime_temporary_privilege'] = operator.execute("SELECT has_database_privilege('map_hub_runtime',current_database(),'TEMP')").fetchone()[0]
        with psycopg.connect(role_dsn('map_hub_migrator'), autocommit=True) as conn:
            conn.execute('SET ROLE map_hub_owner')
            conn.execute('CREATE TABLE hub_data.contract_migrator_probe(id int)')
            conn.execute('DROP TABLE hub_data.contract_migrator_probe')
            for statement in ['CREATE TABLE public.contract_forbidden(id int)', 'CREATE SCHEMA contract_forbidden', 'SELECT * FROM public.contract_sentinel']:
                denied(conn, statement)
        results['checks']['hub_migrator_scoped_ddl_and_42501'] = 'PASS'
        assert operator.execute('SELECT value FROM public.contract_sentinel WHERE id=1').fetchone()[0] == 'synthetic-preserved'
        results['checks']['sentinel_preserved'] = 'PASS'
    results['status'] = 'PASS'
    results['completed_utc'] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    print('Hub isolated database contract PASS')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        failure = {'status': 'FAIL', 'phase': PHASE, 'error_class': type(error).__name__, 'utc': datetime.now(timezone.utc).isoformat()}
        if isinstance(error, RuntimeError):
            try:
                failure['diagnostic'] = json.loads(str(error))
            except (ValueError, TypeError):
                if re.fullmatch(r"[A-Za-z0-9 _;:=(),.-]{1,200}", str(error)):
                    failure['safe_message'] = str(error)
        if REPORT:
            REPORT.write_text(json.dumps(failure, indent=2) + '\n')
        print('Hub isolated database contract FAIL: ' + type(error).__name__ + ' phase=' + PHASE, file=sys.stderr)
        raise SystemExit(1) from None
