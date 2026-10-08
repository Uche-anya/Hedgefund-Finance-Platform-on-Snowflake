"""Bulk-load old OMS and custodian files; daily arrivals still use Snowpipe."""

from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.load_oms_snowpipe import connect

SAFE = re.compile(r'^[A-Za-z0-9_-]+$')

SOURCES = {
    'oms': dict(table='OMS_EVENTS', stage='OMS_EVENTS_STAGE', format='OMS_JSON',
                name='oms_events', daily='data/daily_oms', file='oms.jsonl',
                id_date='business_date'),
    'settlements': dict(table='SETTLEMENT_EVENTS', stage='SETTLEMENT_EVENTS_STAGE',
                        format='SETTLEMENT_JSON', name='settlement_events',
                        daily='data/daily_settlements', file='settlements.jsonl',
                        id_date='settlement_date'),
}


def saved_events(source, scenario):
    spec = SOURCES[source]
    expected = {}
    daily = ROOT / spec['daily'] / scenario
    for folder in sorted(path for path in daily.iterdir() if path.is_dir()):
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        raw = (folder / spec['file']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if manifest['files'][spec['file']] != digest:
            raise ValueError(f'Changed daily file: {folder}')
        delivery_id = manifest['delivery_id']
        if not SAFE.fullmatch(delivery_id):
            raise ValueError('Unsafe delivery ID')
        rows = [json.loads(line) for line in raw.splitlines()]
        if len(rows) != manifest['record_count']:
            raise ValueError(f'Changed daily row count: {folder}')
        expected[delivery_id] = {'digest': digest, 'count': len(rows),
                                 'event_ids': {row['event_id'] for row in rows}}
        if len(expected[delivery_id]['event_ids']) != len(rows):
            raise ValueError(f'Duplicate event ID: {folder}')
    return expected


def copy_file(cursor, source, manifest, folder, scenario):
    spec = SOURCES[source]
    file = folder / manifest['file']
    if hashlib.sha256(file.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError(f'Changed backfill package: {file}')
    local = file.resolve().as_posix().replace("'", "''")
    stage_path = f'backfill/{scenario}/v1'
    cursor.execute(f"PUT 'file:///{local}' "
                   f"@NORTHBRIDGE_DEV.RAW.{spec['stage']}/{stage_path}/ "
                   'AUTO_COMPRESS=TRUE OVERWRITE=FALSE')
    result = cursor.fetchone()
    if not result or str(result[6]).upper() not in ('UPLOADED', 'SKIPPED'):
        raise RuntimeError(f'PUT failed: {result}')
    staged_file = result[1]
    prefix = 'oms-' if source == 'oms' else 'settlement-'
    date_field = spec['id_date']
    fields = ("payload, source_system, scenario_id, delivery_id, "
              "source_file, source_row_number" if source == 'oms' else
              "payload, delivery_id, source_file, source_row_number")
    select = ('t.$1, t.$1:source_system::varchar, t.$1:scenario_id::varchar, '
              if source == 'oms' else 't.$1, ')
    select += (f"'{prefix}' || t.$1:scenario_id::varchar || '-' || "
               f"REPLACE(t.$1:{date_field}::varchar, '-', ''), "
               'METADATA$FILENAME, METADATA$FILE_ROW_NUMBER')
    cursor.execute(f'''
        COPY INTO NORTHBRIDGE_DEV.RAW.{spec['table']} ({fields})
        FROM (SELECT {select}
              FROM @NORTHBRIDGE_DEV.RAW.{spec['stage']}/{stage_path}/ t)
        FILES = ('{staged_file}')
        FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.{spec['format']}')
        ON_ERROR = ABORT_STATEMENT
        FORCE = FALSE
    ''')
    return cursor.fetchall()


def check_raw(cursor, source, expected, scenario):
    spec = SOURCES[source]
    scenario_filter = ('scenario_id' if source == 'oms'
                       else 'payload:scenario_id::varchar')
    cursor.execute(f'''
        select delivery_id, payload:event_id::varchar
        from NORTHBRIDGE_DEV.RAW.{spec['table']}
        where {scenario_filter} = %s
    ''', (scenario,))
    found = {}
    for delivery_id, event_id in cursor.fetchall():
        found.setdefault(delivery_id, []).append(event_id)
    if set(found) != set(expected):
        raise ValueError(f'{source}: RAW delivery dates differ from saved files')
    for delivery_id, saved in expected.items():
        rows = found[delivery_id]
        if len(rows) != saved['count'] or set(rows) != saved['event_ids']:
            raise ValueError(f'{source}: RAW events differ for {delivery_id}')
    return sum(len(rows) for rows in found.values())


def register(cursor, source, expected):
    spec = SOURCES[source]
    cursor.execute('''
        select delivery_id, manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES where source_name = %s
    ''', (spec['name'],))
    receipt_rows = cursor.fetchall()
    existing = {row[0]: row[1:] for row in receipt_rows}
    if len(existing) != len(receipt_rows):
        raise ValueError(f'Duplicate {spec["name"]} delivery receipts')
    for delivery_id, saved in expected.items():
        if delivery_id in existing and existing[delivery_id] != (
                saved['digest'], saved['count'], saved['count'], 'READY'):
            raise ValueError(f'Conflicting receipt for {delivery_id}')
    missing = [(delivery_id, item) for delivery_id, item in expected.items()
               if delivery_id not in existing]
    if not missing:
        return 0
    placeholders = ', '.join('(%s, %s)' for _ in missing)
    values = [value for delivery_id, item in missing
              for value in (delivery_id, item['digest'])]
    cursor.execute(f'''
        insert into NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
            (source_name, delivery_id, manifest_sha256, expected_rows,
             received_rows, delivery_status, first_loaded_at, last_loaded_at)
        select %s, e.delivery_id, e.digest, r.rows_received, r.rows_received,
               'READY', r.first_loaded, r.last_loaded
        from (values {placeholders}) as e(delivery_id, digest)
        join (
            select delivery_id, count(*) as rows_received,
                   min(loaded_at) as first_loaded, max(loaded_at) as last_loaded
            from NORTHBRIDGE_DEV.RAW.{spec['table']}
            group by delivery_id
        ) r on e.delivery_id = r.delivery_id
    ''', (spec['name'], *values))
    cursor.execute('''
        select delivery_id, manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES where source_name = %s
    ''', (spec['name'],))
    receipts = {row[0]: row[1:] for row in cursor.fetchall()}
    for delivery_id, saved in expected.items():
        if receipts.get(delivery_id) != (saved['digest'], saved['count'], saved['count'], 'READY'):
            raise ValueError(f'Incomplete receipt for {delivery_id}')
    return len(missing)


def run(scenario='sim-equity-2024-2026-v1'):
    if not SAFE.fullmatch(scenario):
        raise ValueError('Unsafe scenario ID')
    folder = ROOT / 'data/two_year_backfill' / scenario
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['scenario_id'] != scenario:
        raise ValueError('Backfill package belongs to another scenario')
    report = {'run_id': uuid4().hex, 'scenario_id': scenario,
              'started_at': datetime.now(timezone.utc).isoformat(),
              'status': 'RUNNING', 'sources': {}}
    report_folder = ROOT / 'data/ingestion_runs'
    report_folder.mkdir(parents=True, exist_ok=True)
    connection = None
    try:
        expected = {source: saved_events(source, scenario) for source in SOURCES}
        connection = connect('northbridge_two_year_backfill')
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            for source in SOURCES:
                copy_result = copy_file(cursor, source, manifest[source], folder, scenario)
                count = check_raw(cursor, source, expected[source], scenario)
                receipts = register(cursor, source, expected[source])
                report['sources'][source] = {'raw_rows': count, 'new_receipts': receipts,
                                             'copy_result': [list(row) for row in copy_result]}
                print(f'{source}: {count} RAW events, {receipts} new READY receipts')
        report['status'] = 'SUCCEEDED'
        return 0
    except Exception as error:
        report['status'] = 'FAILED'
        report['error'] = str(error)
        print(f'Backfill failed: {error}')
        return 1
    finally:
        if connection is not None:
            connection.close()
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        path = report_folder / f"two-year-backfill-{report['run_id']}.json"
        path.write_text(json.dumps(report, indent=2, default=str) + '\n', encoding='utf-8')
        print(f"Backfill {report['status']}. Record: {path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', default='sim-equity-2024-2026-v1')
    args = parser.parse_args()
    raise SystemExit(run(args.scenario))
