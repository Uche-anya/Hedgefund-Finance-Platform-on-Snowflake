"""Exercise interrupted-attempt recovery in the development ledger."""

from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.register_close_request import connect
from scripts.run_pinned_close import acquire_lock, recover_interrupted

REQUEST_ID = '5d1f1abedf4cbe14e6a6cef3'


def main():
    lock = connect()
    ledger = None
    attempt_id = 'SIMULATED_INTERRUPTION_' + uuid4().hex
    try:
        acquire_lock(lock)
        ledger = connect()
        with ledger.cursor() as cursor:
            cursor.execute('''
                select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
                where attempt_status = 'RUNNING'
            ''')
            if cursor.fetchone()[0]:
                raise ValueError('A close attempt is already running')
            cursor.execute('''
                insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
                    (attempt_id, request_id, started_at, attempt_status, error_message)
                values (%s, %s, %s, 'RUNNING', 'Simulated interrupted runner test')
            ''', (attempt_id, REQUEST_ID, datetime.now(timezone.utc)))
        ledger.commit()

        with ledger.cursor() as cursor:
            recovered = recover_interrupted(cursor)
            cursor.execute('''
                select attempt_status from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
                where attempt_id = %s
            ''', (attempt_id,))
            status = cursor.fetchone()[0]
        ledger.commit()
        if recovered != 1 or status != 'INTERRUPTED':
            raise ValueError(f'Unexpected recovery: {recovered} rows, {status}')
        print(f'Simulated attempt {attempt_id}: RUNNING -> INTERRUPTED')
    finally:
        if ledger is not None:
            ledger.close()
        lock.rollback()
        lock.close()


if __name__ == '__main__':
    main()
