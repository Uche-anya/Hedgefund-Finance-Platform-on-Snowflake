"""Load the file-backed inputs selected by one controlled-run config."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from cryptography.hazmat.primitives import serialization

try:
    from scripts.ingest_key import KEY_PATH, USER, unlock_secret
except ModuleNotFoundError:
    from ingest_key import KEY_PATH, USER, unlock_secret


ROOT = Path(__file__).resolve().parents[1]
SAFE_NAME = re.compile(r'^[A-Za-z0-9_-]+$')
LOADERS = {
    'activity_events': ('records.jsonl', 'REPLAY_INPUTS', 'REPLAY_STAGE', 'REPLAY_JSON'),
    'broker_positions': ('positions.jsonl', 'BROKER_POSITIONS',
                         'BROKER_POSITIONS_STAGE', 'BROKER_POSITIONS_JSON'),
    'fx_rates': ('records.jsonl', 'FX_RATES', 'FX_RATES_STAGE', 'REFERENCE_JSON'),
    'treasury_rates': ('records.jsonl', 'TREASURY_RATES',
                       'TREASURY_RATES_STAGE', 'REFERENCE_JSON'),
    'fund_admin': ('events.jsonl', 'FUND_ADMIN_EVENTS', 'FUND_ADMIN_STAGE', 'REFERENCE_JSON'),
    'bank_cash': ('balances.jsonl', 'BANK_CASH_STATEMENTS',
                  'BANK_CASH_STAGE', 'REFERENCE_JSON'),
    'dividend_payments': ('payments.jsonl', 'DIVIDEND_PAYMENT_EVENTS',
                          'DIVIDEND_PAYMENT_STAGE', 'REFERENCE_JSON'),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deliveries(root, config_path):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    selected = []
    for source in config['inputs']:
        name = source['source_name']
        if name not in LOADERS:
            continue
        file_name, table, stage, file_format = LOADERS[name]
        manifest_path = (root / source['manifest']).resolve()
        if root.resolve() not in manifest_path.parents:
            raise ValueError(f'Manifest is outside the project: {name}')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest_delivery = manifest.get('delivery_id', manifest.get('load_id'))
        if manifest_delivery != source['delivery_id']:
            raise ValueError(f'{name} delivery ID differs from its manifest')
        path = manifest_path.parent / file_name
        if sha256(path) != manifest['files'][file_name]:
            raise ValueError(f'{name} file differs from its manifest')
        selected.append({
            'name': name,
            'delivery_id': source['delivery_id'],
            'path': path,
            'manifest_sha256': sha256(manifest_path),
            'expected_rows': int(source['expected_rows']),
            'table': table,
            'stage': stage,
            'format': file_format,
        })
    return selected


def connect():
    import snowflake.connector
    secret = unlock_secret()
    key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private_key = key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    connection = snowflake.connector.connect(
        account='gxmgyta-fq45953', user=USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_INGEST',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='RAW',
        autocommit=False,
        session_parameters={'QUERY_TAG': 'northbridge_daily_ingestion'})
    del private_key, key
    return connection


def load(cursor, item):
    delivery = item['delivery_id']
    for value in (delivery, item['table'], item['stage'], item['format']):
        if not SAFE_NAME.fullmatch(value):
            raise ValueError(f'Unsafe Snowflake name: {value}')
    local_path = item['path'].resolve().as_posix().replace("'", "''")
    cursor.execute(
        f"PUT 'file:///{local_path}' @NORTHBRIDGE_DEV.RAW.{item['stage']}/{delivery}/ "
        'AUTO_COMPRESS=TRUE OVERWRITE=FALSE')
    compressed = item['path'].name + '.gz'
    cursor.execute(f'''
        COPY INTO NORTHBRIDGE_DEV.RAW.{item['table']}
            (payload, delivery_id, source_file, source_row_number)
        FROM (
            SELECT t.$1, '{delivery}', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
            FROM @NORTHBRIDGE_DEV.RAW.{item['stage']}/{delivery}/ t
        )
        FILES = ('{compressed}')
        FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.{item['format']}')
        ON_ERROR = ABORT_STATEMENT
        FORCE = FALSE
    ''')
    copy_result = cursor.fetchall()
    cursor.execute(
        f'SELECT COUNT(*) FROM NORTHBRIDGE_DEV.RAW.{item["table"]} WHERE delivery_id = %s',
        (delivery,))
    rows = cursor.fetchone()[0]
    if rows != item['expected_rows']:
        raise ValueError(f"{item['name']} has {rows} rows; expected {item['expected_rows']}")
    cursor.execute(
        f'SELECT MIN(loaded_at), MAX(loaded_at) FROM NORTHBRIDGE_DEV.RAW.{item["table"]} '
        'WHERE delivery_id = %s', (delivery,))
    first_loaded, last_loaded = cursor.fetchone()
    cursor.execute('''
        select manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where source_name = %s and delivery_id = %s
    ''', (item['name'], delivery))
    saved = cursor.fetchall()
    evidence = (item['manifest_sha256'], item['expected_rows'], rows, 'READY')
    if len(saved) > 1 or (saved and tuple(saved[0]) != evidence):
        raise ValueError(f'Conflicting delivery registry entry: {item["name"]}/{delivery}')
    if not saved:
        cursor.execute('''
            insert into NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
                (source_name, delivery_id, manifest_sha256, expected_rows, received_rows,
                 delivery_status, first_loaded_at, last_loaded_at)
            values (%s, %s, %s, %s, %s, 'READY', %s, %s)
        ''', (item['name'], delivery, item['manifest_sha256'], item['expected_rows'],
              rows, first_loaded, last_loaded))
    return {'source': item['name'], 'delivery_id': delivery, 'verified_rows': rows,
            'copy_result': [list(row) for row in copy_result]}


def run(config_path, root=ROOT):
    inputs = deliveries(root, config_path)
    record = {'run_id': uuid4().hex, 'started_at': datetime.now(timezone.utc).isoformat(),
              'status': 'RUNNING', 'loads': []}
    folder = root / 'data/ingestion_runs'
    folder.mkdir(parents=True, exist_ok=True)
    report = folder / (record['run_id'] + '.json')
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            for item in inputs:
                result = load(cursor, item)
                record['loads'].append(result)
                print(f"{result['source']}: {result['verified_rows']} rows verified")
        connection.commit()
        record['status'] = 'SUCCEEDED'
        return 0
    except Exception as error:
        if connection is not None:
            connection.rollback()
        record['status'] = 'FAILED'
        record['error'] = str(error)
        print(f'Ingestion failed: {error}')
        return 1
    finally:
        if connection is not None:
            connection.close()
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        report.write_text(json.dumps(record, indent=2, default=str) + '\n', encoding='utf-8')
        print(f"Ingestion {record['status']}. Record: {report}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.config.resolve()))
