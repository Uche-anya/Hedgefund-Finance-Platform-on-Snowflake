"""Build one selected development close and keep its result in Snowflake."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fingerprint_close import fingerprint
from scripts.inventory_close_inputs import code_hash
from scripts.register_close_request import connect


def acquire_lock(connection):
    with connection.cursor() as cursor:
        cursor.execute('ALTER SESSION SET LOCK_TIMEOUT = 0')
        cursor.execute('BEGIN')
        cursor.execute('''
            update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
            set touched_at = current_timestamp()
            where lock_name = 'DAILY_CLOSE' and lease_owner is null
        ''')
        if cursor.rowcount != 1:
            raise ValueError('Close lock is held by a Snowflake Task')


def current_code_hashes():
    models = [ROOT / 'dbt/dbt_project.yml',
              *ROOT.glob('dbt/models/**/*.sql'),
              *ROOT.glob('dbt/models/**/*.yml'),
              *ROOT.glob('dbt/macros/**/*.sql'),
              *ROOT.glob('dbt/tests/**/*.sql')]
    seeds = list(ROOT.glob('dbt/seeds/*.csv'))
    return code_hash(ROOT, models), code_hash(ROOT, seeds)


def recover_interrupted(cursor):
    cursor.execute('''
        update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
        set finished_at = current_timestamp(), attempt_status = 'INTERRUPTED',
            error_message = 'Previous runner ended before finishing; inspect dbt logs'
        where attempt_status = 'RUNNING'
    ''')
    return cursor.rowcount


def start_attempt(cursor, request_id, attempt_id):
    cursor.execute('''
        select g.build_gate, g.bad_inputs, g.legacy_gaps,
               r.model_sha256, r.seed_sha256
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_GATE g
        join NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS r
          on g.request_id = r.request_id
        where g.request_id = %s
    ''', (request_id,))
    requests = cursor.fetchall()
    if len(requests) != 1 or requests[0][0] != 'BUILDABLE':
        raise ValueError('Snowflake close gate is BLOCKED')
    if (requests[0][3], requests[0][4]) != current_code_hashes():
        raise ValueError('Local dbt code or seed differs from the pinned request')
    cursor.execute('''
        insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
            (attempt_id, request_id, started_at, attempt_status)
        values (%s, %s, %s, 'RUNNING')
    ''', (attempt_id, request_id, datetime.now(timezone.utc)))


def record_blocked(cursor, request_id, attempt_id, error):
    now = datetime.now(timezone.utc)
    cursor.execute('''
        insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
            (attempt_id, request_id, started_at, finished_at,
             attempt_status, error_message)
        values (%s, %s, %s, %s, 'BLOCKED', %s)
    ''', (attempt_id, request_id, now, now, str(error)[:1000]))


def saved_result(cursor, request_id):
    cursor.execute('''
        select supersedes_request_id, nav_rows, nav_total, nav_hash,
               position_rows, position_total, position_hash
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
        where request_id = %s
    ''', (request_id,))
    rows = cursor.fetchall()
    if len(rows) > 1:
        raise ValueError('Duplicate saved close results')
    return rows[0] if rows else None


def result_tuple(result):
    nav = result['nav']
    positions = result['positions']
    return (str(nav['rows']), nav['value_sum'], nav['hash_agg'],
            str(positions['rows']), positions['value_sum'], positions['hash_agg'])


def save_result(cursor, request_id, attempt_id, supersedes):
    result = fingerprint(cursor, request_id)
    found = saved_result(cursor, request_id)
    values = result_tuple(result)
    if found:
        if found[0] != supersedes:
            raise ValueError('Rerun names a different predecessor')
        if tuple(str(value) for value in found[1:]) != values:
            raise ValueError('Rerun changed a saved close result')
        cursor.execute('''
            select record_type, count(*)
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
            where request_id = %s group by record_type
        ''', (request_id,))
        counts = dict(cursor.fetchall())
        if counts != {'NAV': result['nav']['rows'],
                      'POSITION': result['positions']['rows']}:
            raise ValueError('Saved close rows are incomplete')
        return result, 'MATCHED'

    if supersedes:
        cursor.execute('''
            select r.scenario_id, r.business_date, r.model_sha256, r.seed_sha256
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS r
            join NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS o
              on r.request_id = o.request_id
            where r.request_id = %s
        ''', (supersedes,))
        previous = cursor.fetchall()
        cursor.execute('''
            select scenario_id, business_date, model_sha256, seed_sha256
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
            where request_id = %s
        ''', (request_id,))
        current = cursor.fetchall()
        if len(previous) != 1 or len(current) != 1 or previous[0] != current[0]:
            raise ValueError('Original result must have the same date and dbt code')
    cursor.execute('''
        insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
            (request_id, supersedes_request_id, attempt_id,
             nav_rows, nav_total, nav_hash, position_rows, position_total,
             position_hash, result_status)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'CANDIDATE')
    ''', (request_id, supersedes, attempt_id, *values))

    for record_type, table, security in (
            ('NAV', 'FCT_ACCOUNT_NAV_DAILY', 'cast(null as varchar)'),
            ('POSITION', 'FCT_ACCOUNT_POSITIONS_DAILY', 'security_id')):
        cursor.execute(f'''
            insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
                (request_id, record_type, business_date, account_id,
                 security_id, row_data)
            select %s, '{record_type}', business_date, account_id,
                   {security}, object_construct_keep_null(*)
            from NORTHBRIDGE_DEV.DBT_DEV.{table}
            where scenario_id = (
                select scenario_id from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
                where request_id = %s
            ) and business_date <= (
                select business_date from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
                where request_id = %s
            )
        ''', (request_id, request_id, request_id))
    cursor.execute('''
        select record_type, count(*)
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
        where request_id = %s group by record_type
    ''', (request_id,))
    counts = dict(cursor.fetchall())
    if counts != {'NAV': result['nav']['rows'],
                  'POSITION': result['positions']['rows']}:
        raise ValueError('Captured row counts differ from the dbt result')
    return result, 'SAVED'


def finish_attempt(cursor, attempt_id, status, error=None):
    cursor.execute('''
        update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
        set finished_at = %s, attempt_status = %s, error_message = %s
        where attempt_id = %s and attempt_status = 'RUNNING'
    ''', (datetime.now(timezone.utc), status, error, attempt_id))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--supersedes-request-id')
    args = parser.parse_args()
    attempt_id = uuid4().hex
    lock_connection = connect()
    connection = None
    started = False
    try:
        acquire_lock(lock_connection)
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            recovered = recover_interrupted(cursor)
        connection.commit()
        with connection.cursor() as cursor:
            start_attempt(cursor, args.request_id, attempt_id)
        connection.commit()
        started = True
        if recovered:
            print(f'Marked {recovered} earlier attempt(s) INTERRUPTED')

        command = [sys.executable, 'scripts/dbt_dev.py', 'build',
                   '--select', '+fct_account_nav_daily',
                   '--exclude', 'tag:fixture',
                   '--vars', f'close_request_id: {args.request_id}']
        if subprocess.run(command, cwd=ROOT).returncode:
            raise RuntimeError('dbt build failed')

        with connection.cursor() as cursor:
            result, status = save_result(cursor, args.request_id, attempt_id,
                                         args.supersedes_request_id)
            finish_attempt(cursor, attempt_id, status)
        connection.commit()
        print(f'{args.request_id}: {status} ({result["nav"]["rows"]} NAV rows, '
              f'{result["positions"]["rows"]} position rows)')
        print(f'Attempt: {attempt_id}')
    except Exception as error:
        if connection is not None:
            connection.rollback()
            with connection.cursor() as cursor:
                if started:
                    finish_attempt(cursor, attempt_id, 'FAILED', str(error)[:1000])
                else:
                    record_blocked(cursor, args.request_id, attempt_id, error)
            connection.commit()
        raise
    finally:
        if connection is not None:
            connection.close()
        lock_connection.rollback()
        lock_connection.close()


if __name__ == '__main__':
    main()
