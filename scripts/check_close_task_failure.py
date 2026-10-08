"""Verify the deliberate DEV Task failure left no running close or lease."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.register_close_request import connect

REQUEST_ID = '5d1f1abedf4cbe14e6a6cef3'


def main():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                select name, state, error_message
                from table(NORTHBRIDGE_DEV.INFORMATION_SCHEMA.TASK_HISTORY(
                    SCHEDULED_TIME_RANGE_START => dateadd('hour', -1, current_timestamp()),
                    RESULT_LIMIT => 100
                ))
                where database_name = 'NORTHBRIDGE_DEV'
                  and schema_name = 'OPERATIONS'
                  and name in ('CLOSE_PILOT_GATE', 'CLOSE_PILOT_DBT',
                               'CLOSE_PILOT_CAPTURE', 'CLOSE_PILOT_FINALIZER')
                order by scheduled_time desc
            ''')
            latest = {}
            for name, state, error in cursor.fetchall():
                latest.setdefault(name, state)
            print('Latest Task states:', latest)
            if latest.get('CLOSE_PILOT_DBT') != 'FAILED' or \
                    latest.get('CLOSE_PILOT_FINALIZER') != 'SUCCEEDED':
                raise ValueError('Failure drill has not finalized')

            cursor.execute('''
                select attempt_status from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
                where request_id = %s order by started_at desc limit 1
            ''', (REQUEST_ID,))
            status = cursor.fetchone()[0]
            cursor.execute('''
                select lease_owner from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                where lock_name = 'DAILY_CLOSE'
            ''')
            lease = cursor.fetchone()[0]
            print(f'Latest attempt: {status}; lease owner: {lease}')
            if status != 'FAILED' or lease is not None:
                raise ValueError('Failed run still owns the close')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
