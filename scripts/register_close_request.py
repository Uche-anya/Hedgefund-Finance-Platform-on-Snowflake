"""Record one verified close selection in the Snowflake development account."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.inventory_close_inputs import selection_id
from scripts.snow_admin import SERVICE, USER, credential_store


def checked_files(inventory_path, check_path):
    selected = json.loads(inventory_path.read_text(encoding='utf-8'))
    check = json.loads(check_path.read_text(encoding='utf-8'))
    if selected['request_id'] != selection_id(selected):
        raise ValueError('Inventory content differs from its request ID')
    if check['request_id'] != selected['request_id']:
        raise ValueError('Snowflake check belongs to another request')
    if check['errors'] or check['raw_deliveries'] != len(selected['inputs']):
        raise ValueError('Snowflake RAW or receipt comparison failed')
    gaps = sorted(f'{item["source_name"]}/{item["delivery_id"]}: no original delivery receipt'
                  for item in selected['inputs'] if item['receipt_sha256'] is None)
    if check['receipt_gaps'] != gaps:
        raise ValueError('Receipt gaps differ from the inventory')
    checked_at = datetime.fromisoformat(check['checked_at'])
    if datetime.now(timezone.utc) - checked_at > timedelta(minutes=30):
        raise ValueError('Snowflake check is older than 30 minutes; rerun it')
    return selected, checked_at


def connect():
    import snowflake.connector

    password = credential_store().get_password(SERVICE, USER)
    if not password:
        raise ValueError('No saved Snowflake admin password; run scripts/snow_admin.py')
    return snowflake.connector.connect(
        account='gxmgyta-fq45953', user=USER, password=password,
        authenticator='username_password_mfa', role='SYSADMIN',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='OPERATIONS',
        autocommit=False,
        session_parameters={'QUERY_TAG': 'northbridge_close_registration'})


def input_rows(selected):
    request_id = selected['request_id']
    for item in selected['inputs']:
        evidence = ('RECEIPT_VERIFIED' if item['receipt_sha256']
                    else 'LEGACY_RAW_COUNT_ONLY')
        yield (request_id, item['source_name'], item['delivery_id'],
               item['file_sha256'], item['receipt_sha256'],
               item['expected_rows'], item['expected_rows'], evidence)


def registered_inputs(cursor, request_id):
    cursor.execute('''
        select request_id, source_name, delivery_id, file_sha256,
               receipt_sha256, expected_rows, verified_raw_rows, evidence_status
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS
        where request_id = %s
    ''', (request_id,))
    return sorted(tuple(row) for row in cursor.fetchall())


def register(cursor, selected, checked_at):
    request_id = selected['request_id']
    expected = sorted(input_rows(selected))
    cursor.execute('''
        select scenario_id, business_date::varchar, model_sha256,
               seed_sha256, expected_input_count, request_status
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
        where request_id = %s
    ''', (request_id,))
    previous = cursor.fetchall()
    wanted = (selected['scenario_id'], selected['business_date'],
              selected['model_sha256'], selected['seed_sha256'],
              len(expected), 'CANDIDATE')
    if len(previous) > 1 or (previous and tuple(previous[0]) != wanted):
        raise ValueError('Conflicting or duplicate close request')
    if previous:
        if registered_inputs(cursor, request_id) != expected:
            raise ValueError('Registered close inputs differ from saved selection')
        return 'already registered'

    cursor.execute('''
        insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
            (request_id, scenario_id, business_date, cutoff_at,
             model_sha256, seed_sha256, expected_input_count,
             request_status, raw_verified_at)
        values (%s, %s, %s, %s, %s, %s, %s, 'CANDIDATE', %s)
    ''', (request_id, selected['scenario_id'], selected['business_date'],
          datetime.fromisoformat(selected['cutoff_at']),
          selected['model_sha256'], selected['seed_sha256'], len(expected),
          checked_at))
    cursor.executemany('''
        insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS
            (request_id, source_name, delivery_id, file_sha256,
             receipt_sha256, expected_rows, verified_raw_rows, evidence_status)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', expected)
    if registered_inputs(cursor, request_id) != expected:
        raise ValueError('Close inputs differed after insert')
    return 'registered'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--snowflake-check', type=Path, required=True)
    args = parser.parse_args()
    selected, checked_at = checked_files(args.inventory, args.snowflake_check)
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            result = register(cursor, selected, checked_at)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print(f'{selected["request_id"]}: {result} as CANDIDATE')
    print('Three legacy inputs have count evidence only; this is not a READY daily close.')


if __name__ == '__main__':
    main()
