"""Send a checked, versioned two-year reporting extract to Snowflake."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

from scripts.load_daily_inputs import connect


ROOT = Path(__file__).resolve().parents[1]
SAFE_ID = re.compile(r'^[A-Za-z0-9_-]+$')
FILES = {'account_day': 'account_day.csv', 'position_day': 'position_day.csv'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(folder):
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    ledger_id = manifest['ledger_id']
    if not SAFE_ID.fullmatch(ledger_id) or folder.name != ledger_id:
        raise ValueError('Ledger ID and folder must match and contain only safe characters')
    if manifest['status'] != 'EXPLORATORY_PROVISIONAL':
        raise ValueError('Unexpected reporting status')

    output = folder / 'snowflake'
    output.mkdir(exist_ok=True)
    prepared = []
    for record_type, name in FILES.items():
        source = folder / name
        evidence = manifest['files'][name]
        if digest(source) != evidence['sha256']:
            raise ValueError(f'{name} differs from its manifest')
        destination = output / (record_type + '.jsonl')
        rows = 0
        with source.open(newline='', encoding='utf-8') as incoming, \
                destination.open('w', encoding='utf-8', newline='\n') as outgoing:
            for row in csv.DictReader(incoming):
                if row['ledger_id'] != ledger_id or row['scenario_id'] != manifest['scenario_id']:
                    raise ValueError(f'{name} contains a different scenario or ledger')
                outgoing.write(json.dumps(row, separators=(',', ':')) + '\n')
                rows += 1
        if rows != evidence['rows']:
            raise ValueError(f'{name} has {rows} rows; manifest expects {evidence["rows"]}')
        prepared.append((record_type, destination, rows))
    return manifest, digest(manifest_path), prepared


def load(folder):
    manifest, manifest_hash, prepared = prepare(folder)
    ledger_id = manifest['ledger_id']
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            cursor.execute('''
                SELECT DISTINCT manifest_sha256
                FROM NORTHBRIDGE_DEV.RAW.TWO_YEAR_REPORTING
                WHERE ledger_id = %s
            ''', (ledger_id,))
            saved_hashes = {row[0] for row in cursor.fetchall()}
            if saved_hashes and saved_hashes != {manifest_hash}:
                raise ValueError('This ledger ID was loaded with a different manifest')

            for record_type, path, expected in prepared:
                local_path = path.resolve().as_posix().replace("'", "''")
                cursor.execute(
                    f"PUT 'file:///{local_path}' "
                    f"@NORTHBRIDGE_DEV.RAW.TWO_YEAR_REPORTING_STAGE/{ledger_id}/ "
                    'AUTO_COMPRESS=TRUE OVERWRITE=FALSE')
                cursor.execute(f'''
                    COPY INTO NORTHBRIDGE_DEV.RAW.TWO_YEAR_REPORTING
                        (record_type, payload, ledger_id, manifest_sha256,
                         source_file, source_row_number)
                    FROM (
                        SELECT '{record_type}', t.$1, '{ledger_id}', '{manifest_hash}',
                               METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
                        FROM @NORTHBRIDGE_DEV.RAW.TWO_YEAR_REPORTING_STAGE/{ledger_id}/ t
                    )
                    FILES = ('{path.name}.gz')
                    FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.REFERENCE_JSON')
                    ON_ERROR = ABORT_STATEMENT
                    FORCE = FALSE
                ''')
                cursor.execute('''
                    SELECT COUNT(*), COUNT(DISTINCT source_row_number)
                    FROM NORTHBRIDGE_DEV.RAW.TWO_YEAR_REPORTING
                    WHERE ledger_id = %s AND record_type = %s
                      AND manifest_sha256 = %s
                ''', (ledger_id, record_type, manifest_hash))
                count, distinct_rows = cursor.fetchone()
                if (count, distinct_rows) != (expected, expected):
                    raise ValueError(f'{record_type}: expected {expected} unique rows, found {count}')
                print(f'{record_type}: {count} rows verified for {ledger_id}')
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger_id', nargs='?', default='TWO_YEAR_REVIEW_003')
    args = parser.parse_args()
    folder = ROOT / 'data' / 'two_year_reporting' / args.ledger_id
    load(folder)
