"""Prove a second DEV close writer cannot take the Snowflake lock."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.register_close_request import connect
from scripts.run_pinned_close import acquire_lock


def main():
    first = connect()
    second = connect()
    try:
        acquire_lock(first)
        try:
            acquire_lock(second)
        except Exception as error:
            second.rollback()
            if 'lock' not in str(error).lower():
                raise
            print('Second writer was blocked by the Snowflake close lock.')
        else:
            raise AssertionError('Second writer acquired a lock held by another session')
        first.rollback()
        acquire_lock(second)
        print('Lock became available after the first transaction rolled back.')
        second.rollback()

        marker = 'SIMULATED_TASK_LEASE'
        with first.cursor() as cursor:
            cursor.execute('''
                update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                set lease_owner = %s
                where lock_name = 'DAILY_CLOSE' and lease_owner is null
            ''', (marker,))
            if cursor.rowcount != 1:
                raise ValueError('Close already has a Task owner')
        first.commit()
        try:
            try:
                acquire_lock(second)
            except ValueError as error:
                second.rollback()
                if 'Task' not in str(error):
                    raise
                print('Local runner refused a Task-owned close.')
            else:
                raise AssertionError('Local runner ignored the Task owner')
        finally:
            with first.cursor() as cursor:
                cursor.execute('''
                    update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                    set lease_owner = null
                    where lock_name = 'DAILY_CLOSE' and lease_owner = %s
                ''', (marker,))
            first.commit()
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()


if __name__ == '__main__':
    main()
