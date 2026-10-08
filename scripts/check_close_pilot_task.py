"""Show the latest manual close Task graph and compare its output to the saved close."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fingerprint_close import fingerprint
from scripts.register_close_request import connect

REQUEST_ID = '5d1f1abedf4cbe14e6a6cef3'


def main():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                select name, state, scheduled_time, completed_time, error_message
                from table(NORTHBRIDGE_DEV.INFORMATION_SCHEMA.TASK_HISTORY(
                    SCHEDULED_TIME_RANGE_START => dateadd('hour', -2, current_timestamp()),
                    RESULT_LIMIT => 100
                ))
                where database_name = 'NORTHBRIDGE_DEV'
                  and schema_name = 'OPERATIONS'
                  and name in ('CLOSE_PILOT_GATE', 'CLOSE_PILOT_DBT',
                               'CLOSE_PILOT_CAPTURE', 'CLOSE_PILOT_FINALIZER')
                order by scheduled_time desc
            ''')
            rows = cursor.fetchall()
            latest = {}
            for name, state, scheduled, completed, error in rows[:12]:
                print(f'{name}: {state} | {scheduled} | {completed}')
                if error:
                    print(error[:500])
                latest.setdefault(name, state)
            if latest != {'CLOSE_PILOT_DBT': 'SUCCEEDED',
                          'CLOSE_PILOT_GATE': 'SUCCEEDED',
                          'CLOSE_PILOT_CAPTURE': 'SUCCEEDED',
                          'CLOSE_PILOT_FINALIZER': 'SUCCEEDED'}:
                raise ValueError('Latest manual Task graph did not succeed')

            cursor.execute('''
                select lease_owner from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                where lock_name = 'DAILY_CLOSE'
            ''')
            lease = cursor.fetchone()[0]
            if lease is not None:
                raise ValueError(f'Close lease was not released: {lease}')

            cursor.execute('''
                select attempt_id, attempt_status
                from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
                where request_id = %s
                order by started_at desc limit 2
            ''', (REQUEST_ID,))
            attempts = cursor.fetchall()
            print('Latest close attempts:', attempts)
            if not attempts or attempts[0][1] not in ('MATCHED', 'SAVED'):
                raise ValueError('Task did not record a completed close attempt')

            cursor.execute('''
                select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
                where request_id = %s
            ''', (REQUEST_ID,))
            headers = cursor.fetchone()[0]
            if headers != 1:
                raise ValueError(f'Expected one saved close header, got {headers}')
            cursor.execute('''
                select record_type, count(*)
                from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
                where request_id = %s group by record_type
            ''', (REQUEST_ID,))
            row_counts = dict(cursor.fetchall())
            print('Saved result rows:', row_counts)
            if row_counts != {'NAV': 1002, 'POSITION': 19574}:
                raise ValueError('Saved close rows changed during the retry')

            cursor.execute('''
                select nav_rows, nav_total, nav_hash,
                       position_rows, position_total, position_hash
                from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
                where request_id = %s
            ''', (REQUEST_ID,))
            saved = cursor.fetchall()
            if len(saved) != 1:
                raise ValueError('Expected one saved close result')
            current = fingerprint(cursor, REQUEST_ID)
            actual = (current['nav']['rows'], current['nav']['value_sum'],
                      current['nav']['hash_agg'], current['positions']['rows'],
                      current['positions']['value_sum'], current['positions']['hash_agg'])
            matches = tuple(map(str, saved[0])) == tuple(map(str, actual))
            print(f'Shared dbt output matches saved candidate: {matches}')
            if not matches:
                raise ValueError('Task output differs from saved candidate')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
