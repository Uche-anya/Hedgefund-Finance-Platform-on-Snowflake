"""Compare two saved DEV close versions without rebuilding dbt."""

import argparse
from collections import defaultdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.register_close_request import connect


def request_details(cursor, request_id):
    cursor.execute('''
        select r.scenario_id, r.business_date, r.model_sha256, r.seed_sha256,
               o.supersedes_request_id, o.nav_rows, o.position_rows
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS r
        join NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS o
          on r.request_id = o.request_id
        where r.request_id = %s
    ''', (request_id,))
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise ValueError(f'Expected one saved close: {request_id}')
    return rows[0]


def input_differences(cursor, old, new):
    cursor.execute('''
        select source_name, delivery_id
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS
        where request_id = %s
    ''', (old,))
    previous = set(cursor.fetchall())
    cursor.execute('''
        select source_name, delivery_id
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS
        where request_id = %s
    ''', (new,))
    current = set(cursor.fetchall())
    return sorted(previous - current), sorted(current - previous)


def changed_rows(cursor, old, new, kind, amount_field):
    cursor.execute(f'''
        with old as (
            select business_date, account_id, coalesce(security_id, '') as security_id,
                   row_data, row_data:{amount_field}::number(38, 12) as amount
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
            where request_id = %s and record_type = %s
        ), new as (
            select business_date, account_id, coalesce(security_id, '') as security_id,
                   row_data, row_data:{amount_field}::number(38, 12) as amount
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
            where request_id = %s and record_type = %s
        )
        select coalesce(old.business_date, new.business_date),
               coalesce(old.account_id, new.account_id),
               coalesce(old.security_id, new.security_id),
               old.amount, new.amount, new.amount - old.amount,
               old.row_data is null, new.row_data is null
        from old full outer join new
          on old.business_date = new.business_date
         and old.account_id = new.account_id
         and old.security_id = new.security_id
        where old.row_data is null or new.row_data is null
           or hash(old.row_data) <> hash(new.row_data)
        order by 1, 2, 3
    ''', (old, kind, new, kind))
    return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original')
    parser.add_argument('corrected')
    args = parser.parse_args()
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            original = request_details(cursor, args.original)
            corrected = request_details(cursor, args.corrected)
            if original[:4] != corrected[:4]:
                raise ValueError('Date, scenario, model or seed differs')
            if corrected[4] != args.original:
                raise ValueError('Corrected result does not supersede original')
            removed, added = input_differences(cursor, args.original, args.corrected)
            nav = changed_rows(cursor, args.original, args.corrected,
                               'NAV', 'REVIEWED_NAV_USD')
            positions = changed_rows(cursor, args.original, args.corrected,
                                     'POSITION', 'MARKET_VALUE_USD')
    finally:
        connection.close()
    print(f'Original {args.original}: {original[5]} NAV, {original[6]} positions')
    print(f'Corrected {args.corrected}: {corrected[5]} NAV, {corrected[6]} positions')
    print(f'Removed input: {removed}')
    print(f'Added input: {added}')
    print(f'Changed NAV rows: {len(nav)}')
    for day, account, _, before, after, delta, missing_old, missing_new in nav:
        print(f'  {day} {account}: {before} -> {after} (change {delta})')
    print(f'Changed position rows: {len(positions)}')
    for day, account, security, before, after, delta, missing_old, missing_new in positions:
        print(f'  {day} {account} {security}: {before} -> {after} (change {delta})')
    if (len(removed) != 1 or len(added) != 1
            or removed[0][0] != 'daily_prices' or added[0][0] != 'daily_prices'
            or not nav or not positions
            or any(row[0] != corrected[1] or row[6] or row[7]
                   for row in nav + positions)):
        raise ValueError('Correction changed unexpected inputs, dates or row keys')
    position_change = defaultdict(int)
    for day, account, security, before, after, delta, _, _ in positions:
        position_change[day, account] += delta
    for day, account, _, before, after, delta, _, _ in nav:
        if delta != position_change[day, account]:
            raise ValueError('NAV change differs from the position-value change')


if __name__ == '__main__':
    main()
