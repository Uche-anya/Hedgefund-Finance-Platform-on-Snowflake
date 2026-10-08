"""Stage one custodian file and notify the settlement Snowpipe pipe."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ingest_key import USER
from scripts.load_oms_snowpipe import (ACCOUNT, HOST, connect, private_key,
                                       SAFE_DELIVERY)

PIPE = 'NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS_PIPE'
STAGE = 'NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS_STAGE'
TABLE = 'NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS'


def inspect_file(path):
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
              if line.strip()]
    if not events:
        raise ValueError('Settlement file is empty')
    ids = set()
    executions = set()
    for row in events:
        for field in ('event_id', 'execution_id', 'account_id', 'instrument_id',
                      'settlement_date', 'settled_at', 'published_at', 'cash_amount'):
            if not row.get(field):
                raise ValueError(f'Missing settlement {field}')
        if row['event_id'] in ids or row['execution_id'] in executions:
            raise ValueError('Duplicate settlement event or execution ID')
        ids.add(row['event_id'])
        executions.add(row['execution_id'])
        if (row.get('event_type') != 'SETTLEMENT_CONFIRMED'
                or row.get('source_system') != 'simulated_custodian'
                or row.get('settlement_status') != 'SETTLED'
                or row.get('currency') != 'USD'):
            raise ValueError('Unexpected settlement type, status or currency')
        amount = Decimal(row['cash_amount'])
        quantity = Decimal(row['settled_quantity'])
        if (not amount.is_finite() or not quantity.is_finite() or quantity <= 0
                or (row['side'] == 'BUY' and amount >= 0)
                or (row['side'] == 'SELL' and amount <= 0)):
            raise ValueError('Invalid settlement amount or quantity')
        if row['side'] not in ('BUY', 'SELL'):
            raise ValueError('Invalid settlement side')
        settled = datetime.fromisoformat(row['settled_at'].replace('Z', '+00:00'))
        published = datetime.fromisoformat(row['published_at'].replace('Z', '+00:00'))
        if settled.date().isoformat() != row['settlement_date'] or published < settled:
            raise ValueError('Settlement timestamps disagree')
    return len(events), hashlib.sha256(path.read_bytes()).hexdigest()


def wait_for_rows(cursor, delivery_id, expected, timeout):
    deadline = time.monotonic() + timeout
    while True:
        cursor.execute(f'SELECT COUNT(*) FROM {TABLE} WHERE delivery_id = %s', (delivery_id,))
        found = int(cursor.fetchone()[0])
        if found == expected:
            return
        if found > expected:
            raise ValueError(f'{delivery_id}: expected {expected}, found {found} rows')
        if time.monotonic() >= deadline:
            raise TimeoutError(f'{delivery_id}: only {found} of {expected} rows loaded')
        time.sleep(2)


def register(cursor, delivery_id, digest, count):
    cursor.execute('''
        select manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where source_name = 'settlement_events' and delivery_id = %s
    ''', (delivery_id,))
    saved = cursor.fetchall()
    if len(saved) > 1 or (saved and tuple(saved[0]) != (digest, count, count, 'READY')):
        raise ValueError(f'Conflicting settlement delivery receipt: {delivery_id}')
    if not saved:
        cursor.execute(f'''
            insert into NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
                (source_name, delivery_id, manifest_sha256, expected_rows,
                 received_rows, delivery_status, first_loaded_at, last_loaded_at)
            select 'settlement_events', %s, %s, %s, %s, 'READY',
                   min(loaded_at), max(loaded_at)
            from {TABLE} where delivery_id = %s
        ''', (delivery_id, digest, count, count, delivery_id))


def load(path, delivery_id, timeout=120):
    from snowflake.ingest import SimpleIngestManager, StagedFile

    path = path.resolve()
    if not path.is_file() or path.suffix != '.jsonl':
        raise ValueError('Expected a saved settlement .jsonl file')
    count, digest = inspect_file(path)
    if not SAFE_DELIVERY.fullmatch(delivery_id):
        raise ValueError('Invalid delivery ID')
    folder = path.parent
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest['delivery_id'] != delivery_id or manifest['record_count'] != count
            or manifest['files'].get(path.name) != digest):
        raise ValueError('Settlement file differs from manifest')
    report = {'load_id': uuid4().hex, 'delivery_id': delivery_id,
              'file_sha256': digest, 'expected_rows': count,
              'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING'}
    report_folder = ROOT / 'data/ingestion_runs'
    report_folder.mkdir(parents=True, exist_ok=True)
    report_path = report_folder / f"settlement-{report['load_id']}.json"
    connection = None
    try:
        connection = connect('northbridge_settlement_snowpipe')
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            local = path.as_posix().replace("'", "''")
            cursor.execute(f"PUT 'file:///{local}' @{STAGE}/{delivery_id}/ "
                           'AUTO_COMPRESS=TRUE OVERWRITE=FALSE')
            result = cursor.fetchone()
            if not result or str(result[6]).upper() not in ('UPLOADED', 'SKIPPED'):
                raise RuntimeError(f'Settlement PUT failed: {result}')
            staged = f'{delivery_id}/{result[1]}'
            manager = SimpleIngestManager(account=ACCOUNT, host=HOST,
                                          user=USER,
                                          pipe=PIPE, private_key=private_key())
            response = manager.ingest_files([StagedFile(staged, None)])
            if response.get('responseCode') != 'SUCCESS':
                raise RuntimeError(f'Snowpipe rejected {staged}: {response}')
            wait_for_rows(cursor, delivery_id, count, timeout)
            register(cursor, delivery_id, digest, count)
        report['status'] = 'SUCCEEDED'
        print(f'Snowpipe loaded {count} custodian confirmation(s) for {delivery_id}.')
        return 0
    except Exception as error:
        report['status'] = 'FAILED'
        report['error'] = str(error)
        print(f'Settlement ingestion failed: {error}')
        return 1
    finally:
        if connection is not None:
            connection.close()
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f"Ingestion {report['status']}. Record: {report_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--delivery-id', required=True)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    raise SystemExit(load(args.file, args.delivery_id, args.timeout))
