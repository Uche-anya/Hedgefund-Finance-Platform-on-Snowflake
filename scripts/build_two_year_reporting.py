"""Build local exploratory BI tables from a versioned review ledger close."""

import argparse
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.two_year_reporting import make_reporting_rows
from scripts.preview_two_year_action_decision import read_csv, sha256
from simulation.daily_oms import write_once

LEDGER_DIR = ROOT / 'data/two_year_close/review_ledgers'
SOURCE_CLOSE = ROOT / 'data/two_year_close/provisional_v2_review_split'
SECURITIES = ROOT / 'dbt/seeds/dim_instrument.csv'
OUTPUT = ROOT / 'data/two_year_reporting'


def csv_bytes(rows):
    handle = StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode('utf-8')


def run(ledger_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ledger_id):
        raise ValueError('Invalid ledger ID')
    folder = LEDGER_DIR / ledger_id
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    source_manifest = json.loads((SOURCE_CLOSE / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest['ledger_id'] != ledger_id
            or manifest['scenario_id'] != 'sim-equity-2024-2026-v2'
            or manifest['status'] != 'PROVISIONAL_UNAPPROVED'
            or manifest['source_close_manifest_sha256'] != sha256(SOURCE_CLOSE / 'manifest.json')):
        raise ValueError('Wrong or changed review-ledger close')
    daily_file = folder / 'daily.csv'
    position_file = SOURCE_CLOSE / 'positions.csv'
    if (sha256(daily_file) != manifest['files']['daily.csv']['sha256']
            or sha256(position_file) != manifest['unchanged_source_files']['positions.csv']
            or sha256(position_file) != source_manifest['files']['positions.csv']['sha256']):
        raise ValueError('Daily close or position source has changed')
    daily = read_csv(daily_file)
    positions = read_csv(position_file)
    instruments = read_csv(SECURITIES)
    if (len(daily) != manifest['files']['daily.csv']['rows']
            or len(positions) != source_manifest['files']['positions.csv']['rows']):
        raise ValueError('Close row counts differ from their manifests')

    account_rows, position_rows = make_reporting_rows(
        daily, positions, instruments, manifest['scenario_id'], ledger_id)
    result_dir = OUTPUT / ledger_id
    files = {}
    for name, rows in (('account_day.csv', account_rows),
                       ('position_day.csv', position_rows)):
        body = csv_bytes(rows)
        write_once(result_dir / name, body)
        files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(body).hexdigest()}
    report = {
        'scenario_id': manifest['scenario_id'], 'ledger_id': ledger_id,
        'status': 'EXPLORATORY_PROVISIONAL',
        'grain': {
            'account_day.csv': 'scenario_id + ledger_id + business_date + account_id',
            'position_day.csv': 'scenario_id + ledger_id + business_date + account_id + security_id',
        },
        'market_days': len({row['business_date'] for row in account_rows}),
        'accounts': sorted({row['account_id'] for row in account_rows}),
        'inputs_sha256': {
            'ledger_manifest': sha256(folder / 'manifest.json'),
            'daily_close': sha256(daily_file),
            'positions': sha256(position_file),
            'instrument_seed': sha256(SECURITIES),
        },
        'files': files,
        'limitations': ('Exploratory exposure and NAV comparisons only. Pending corporate '
                        'actions, incomplete cash evidence, borrow fees and tax prevent '
                        'published performance or investor reporting.'),
    }
    write_once(result_dir / 'manifest.json',
               (json.dumps(report, indent=2, sort_keys=True) + '\n').encode())
    print(f"{len(account_rows)} account days, {len(position_rows)} position days")
    print(result_dir)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger-id', default='TWO_YEAR_REVIEW_001')
    args = parser.parse_args()
    run(args.ledger_id)
