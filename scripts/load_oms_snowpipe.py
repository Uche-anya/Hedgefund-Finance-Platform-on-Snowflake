"""Validate one OMS file, stage it and ask Snowpipe to load it."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from cryptography.hazmat.primitives import serialization


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.ingest_key import KEY_PATH, USER, unlock_secret
except ModuleNotFoundError:
    from ingest_key import KEY_PATH, USER, unlock_secret

from simulation.simulator import validate_execution

ACCOUNT = 'gxmgyta-fq45953'
HOST = ACCOUNT + '.snowflakecomputing.com'
PIPE = 'NORTHBRIDGE_DEV.RAW.OMS_EVENTS_PIPE'
STAGE = 'NORTHBRIDGE_DEV.RAW.OMS_EVENTS_STAGE'
SAFE_DELIVERY = re.compile(r'^[A-Za-z0-9_-]+$')


def inspect_file(path):
    digest = hashlib.sha256()
    event_ids = set()
    count = 0

    with path.open('rb') as raw_file:
        for raw_line in raw_file:
            digest.update(raw_line)
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError(f'Invalid JSON on line {count + 1}: {error}') from None
            validate_execution(event)
            event_id = event['event_id']
            if event_id in event_ids:
                raise ValueError(f'Duplicate event_id in file: {event_id}')
            event_ids.add(event_id)
            count += 1

    if count == 0:
        raise ValueError('OMS file contains no events')
    return count, digest.hexdigest()


def delivery_name(file_hash, supplied=None):
    value = supplied or 'oms-' + file_hash[:24]
    if not SAFE_DELIVERY.fullmatch(value):
        raise ValueError('delivery ID may contain only letters, digits, underscores and hyphens')
    return value


def private_key():
    secret = unlock_secret()
    key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode('ascii')
    del key
    return pem


def connect():
    import snowflake.connector

    pem = private_key()
    key = serialization.load_pem_private_key(pem.encode('ascii'), password=None)
    der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    del pem, key
    connection = snowflake.connector.connect(
        account=ACCOUNT,
        user=USER,
        private_key=der,
        authenticator='SNOWFLAKE_JWT',
        role='NORTHBRIDGE_INGEST',
        warehouse='COMPUTE_WH',
        database='NORTHBRIDGE_DEV',
        schema='RAW',
        session_parameters={'QUERY_TAG': 'northbridge_oms_snowpipe'},
    )
    del der
    return connection


def stage_file(cursor, path, delivery_id):
    local_path = path.resolve().as_posix().replace("'", "''")
    cursor.execute(
        f"PUT 'file:///{local_path}' @{STAGE}/{delivery_id}/ "
        'AUTO_COMPRESS=TRUE OVERWRITE=FALSE'
    )
    result = cursor.fetchone()
    if not result:
        raise RuntimeError('PUT returned no result')
    target = result[1]
    status = str(result[6]).upper()
    if status not in ('UPLOADED', 'SKIPPED'):
        raise RuntimeError(f'PUT failed with status {status}')
    return f'{delivery_id}/{target}'


def notify_pipe(staged_path, pem):
    try:
        from snowflake.ingest import SimpleIngestManager, StagedFile
    except ImportError:
        raise RuntimeError(
            'snowflake-ingest is missing; install requirements-dbt.txt'
        ) from None

    manager = SimpleIngestManager(
        account=ACCOUNT,
        host=HOST,
        user=USER,
        pipe=PIPE,
        private_key=pem,
    )
    response = manager.ingest_files([StagedFile(staged_path, None)])
    if response.get('responseCode') != 'SUCCESS':
        raise RuntimeError(f'Snowpipe rejected {staged_path}: {response}')
    return response


def wait_for_rows(cursor, delivery_id, expected_rows, timeout=120, pause=2):
    deadline = time.monotonic() + timeout
    while True:
        cursor.execute(
            'SELECT COUNT(*) FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS '
            'WHERE delivery_id = %s',
            (delivery_id,),
        )
        rows = int(cursor.fetchone()[0])
        if rows == expected_rows:
            return rows
        if rows > expected_rows:
            raise RuntimeError(
                f'{delivery_id} has {rows} rows; expected {expected_rows}'
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f'Snowpipe loaded {rows} of {expected_rows} rows within {timeout} seconds'
            )
        time.sleep(pause)


def register_delivery(cursor, delivery_id, file_hash, rows):
    cursor.execute('''
        select manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where source_name = 'oms_events' and delivery_id = %s
    ''', (delivery_id,))
    saved = cursor.fetchall()
    evidence = (file_hash, rows, rows, 'READY')
    if len(saved) > 1 or (saved and tuple(saved[0]) != evidence):
        raise ValueError(f'Conflicting delivery registry entry: oms_events/{delivery_id}')
    if saved:
        return
    cursor.execute('''
        insert into NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
            (source_name, delivery_id, manifest_sha256, expected_rows, received_rows,
             delivery_status, first_loaded_at, last_loaded_at)
        select 'oms_events', %s, %s, %s, %s, 'READY', min(loaded_at), max(loaded_at)
        from NORTHBRIDGE_DEV.RAW.OMS_EVENTS where delivery_id = %s
    ''', (delivery_id, file_hash, rows, rows, delivery_id))


def load(path, supplied_delivery=None, timeout=120):
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != '.jsonl':
        raise ValueError('OMS input must be a .jsonl file')

    expected_rows, file_hash = inspect_file(path)
    delivery_id = delivery_name(file_hash, supplied_delivery)
    report = {
        'load_id': uuid4().hex,
        'delivery_id': delivery_id,
        'source_file': str(path),
        'source_sha256': file_hash,
        'expected_rows': expected_rows,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'status': 'RUNNING',
    }
    folder = ROOT / 'data/ingestion_runs'
    folder.mkdir(parents=True, exist_ok=True)
    report_path = folder / f"oms-{report['load_id']}.json"
    connection = None

    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            staged_path = stage_file(cursor, path, delivery_id)
            report['staged_path'] = staged_path
            response = notify_pipe(staged_path, private_key())
            report['snowpipe_response'] = response
            report['loaded_rows'] = wait_for_rows(
                cursor, delivery_id, expected_rows, timeout=timeout
            )
            register_delivery(cursor, delivery_id, file_hash, report['loaded_rows'])
        report['status'] = 'SUCCEEDED'
        print(f"Snowpipe loaded {expected_rows} OMS event(s) for {delivery_id}.")
        return 0
    except Exception as error:
        report['status'] = 'FAILED'
        report['error'] = str(error)
        print(f'OMS ingestion failed: {error}')
        return 1
    finally:
        if connection is not None:
            connection.close()
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2, default=str) + '\n', encoding='utf-8')
        print(f"Ingestion {report['status']}. Record: {report_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--delivery-id')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error('--timeout must be at least one second')
    return load(args.file, args.delivery_id, args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
