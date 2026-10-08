"""Compare five saved OMS files with what Snowpipe put in Snowflake RAW."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives import serialization
from scripts import dbt_key

SCENARIO = 'sim-equity-2024-2026-v1'
DAYS = ('2024-09-24', '2024-09-25', '2024-09-26', '2024-09-27', '2024-09-30')


def connect():
    import snowflake.connector
    secret = dbt_key.unlock_secret()
    key = serialization.load_pem_private_key(
        dbt_key.KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private_key = key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    return snowflake.connector.connect(
        account='gxmgyta-fq45953', user=dbt_key.USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_DBT_DEV',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='DBT_DEV')


def expected(day):
    folder = ROOT / 'data/daily_oms' / SCENARIO / day
    manifest = json.loads((folder / 'manifest.json').read_text())
    raw = (folder / 'oms.jsonl').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['files']['oms.jsonl']:
        raise ValueError(f'Saved OMS file changed: {day}')
    events = [json.loads(line) for line in raw.splitlines()]
    if len(events) != manifest['record_count']:
        raise ValueError(f'Manifest row count differs: {day}')
    return manifest, {event['event_id'] for event in events}


def check():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            total = 0
            for day in DAYS:
                manifest, saved = expected(day)
                cursor.execute('''
                    select payload:event_id::varchar, payload:business_date::varchar,
                           source_system
                    from NORTHBRIDGE_DEV.RAW.OMS_EVENTS
                    where scenario_id = %s and delivery_id = %s
                ''', (SCENARIO, manifest['delivery_id']))
                loaded = cursor.fetchall()
                ids = [row[0] for row in loaded]
                if (len(ids) != len(saved) or set(ids) != saved
                        or any(row[1] != day or row[2] != 'simulated_oms' for row in loaded)):
                    raise ValueError(f'RAW rows differ from saved delivery: {day}')
                cursor.execute('''
                    select expected_rows, received_rows, delivery_status
                    from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
                    where source_name = 'oms_events' and delivery_id = %s
                ''', (manifest['delivery_id'],))
                receipt = cursor.fetchall()
                if receipt != [(len(saved), len(saved), 'READY')]:
                    raise ValueError(f'Delivery receipt is not READY: {day}')
                total += len(ids)
                print(f'{day}: {len(ids)} OMS fills, READY')
            print(f'{total} saved fills match Snowpipe RAW rows across {len(DAYS)} days.')
    finally:
        connection.close()


if __name__ == '__main__':
    check()
