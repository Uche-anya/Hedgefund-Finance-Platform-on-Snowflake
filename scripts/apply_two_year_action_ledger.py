"""Build one provisional close from the current dividend review decisions."""

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

from fund_pipeline.action_restatement import apply_ledger
from scripts.preview_two_year_action_decision import CLOSE, load_review, read_csv, sha256
from simulation.daily_oms import write_once

OUTPUT = ROOT / 'data/two_year_close/review_ledgers'
REVIEW_DIR = ROOT / 'docs/action_reviews'
DIFFERENCE_COLUMNS = ('business_date', 'account_id', 'approved_event_ids',
                      'reviewed_nav_before_usd', 'reviewed_nav_after_usd', 'change_usd')


def csv_bytes(rows, columns):
    handle = StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode('utf-8')


def decision_paths(ledger):
    names = ledger.get('decision_files')
    if (ledger.get('schema_version') != 1
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ledger.get('ledger_id', ''))
            or not names or len(names) != len(set(names))):
        raise ValueError('Ledger needs a distinct version ID and decision files')
    paths = []
    for name in names:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(REVIEW_DIR) or path.suffix.lower() != '.json':
            raise ValueError(f'Decision file must be under docs/action_reviews: {name}')
        paths.append(path)
    return paths


def run(ledger_path):
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    paths = decision_paths(ledger)
    entries = []
    decisions = []
    starting_daily = None
    close_manifest = None
    for path in paths:
        (decision, event, daily, selected_entitlements, preview, amounts,
         queue_manifest, source_manifest) = load_review(path)
        if (ledger.get('scenario_id') != queue_manifest['scenario_id']
                or ledger.get('queue_sha256') != queue_manifest['queue_sha256']):
            raise ValueError('Ledger and decision queue refer to different snapshots')
        if starting_daily is None:
            starting_daily = daily
            close_manifest = source_manifest
        entries.append((decision, event, amounts))
        decisions.append({
            'decision_id': decision['decision_id'],
            'event_id': event['event_id'],
            'decision': decision['decision'],
            'file': str(path.relative_to(ROOT)).replace('\\', '/'),
            'sha256': sha256(path),
        })

    entitlements = read_csv(CLOSE / 'dividend_entitlements.csv')
    daily, reviewed_entitlements, differences, approved, held = apply_ledger(
        starting_daily, entitlements, entries)
    if (len(daily) != close_manifest['files']['daily.csv']['rows']
            or len(reviewed_entitlements)
               != close_manifest['files']['dividend_entitlements.csv']['rows']):
        raise ValueError('Decision ledger changed close or entitlement row counts')
    if not approved and (daily != starting_daily or reviewed_entitlements != entitlements):
        raise ValueError('Hold-only ledger changed the saved close')

    folder = OUTPUT / ledger['ledger_id']
    files = {}
    for name, rows, columns in (
            ('daily.csv', daily, list(starting_daily[0])),
            ('dividend_entitlements.csv', reviewed_entitlements, list(entitlements[0])),
            ('nav_differences.csv', differences, DIFFERENCE_COLUMNS)):
        body = csv_bytes(rows, columns)
        write_once(folder / name, body)
        files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(body).hexdigest()}
    result = {
        'scenario_id': ledger['scenario_id'],
        'status': 'PROVISIONAL_UNAPPROVED',
        'ledger_id': ledger['ledger_id'],
        'ledger_sha256': sha256(ledger_path),
        'source_close_manifest_sha256': sha256(CLOSE / 'manifest.json'),
        'source_queue_sha256': ledger['queue_sha256'],
        'decisions': decisions,
        'approved_event_ids': approved,
        'held_event_ids': held,
        'pending_event_count': close_manifest['review_split']['pending_event_ids'] - len(approved),
        'reviewed_event_count': close_manifest['review_split']['reviewed_event_ids'] + len(approved),
        'affected_market_days': len({row['business_date'] for row in differences}),
        'affected_account_day_rows': len(differences),
        'unchanged_source_files': {
            name: close_manifest['files'][name]['sha256']
            for name in ('positions.csv', 'security_transfers.csv')
        },
        'files': files,
        'limitations': ('Only review classification changes here. Cash, trades, prices and '
                        'illustrative NAV come from the saved close. Other pending events '
                        'and payment evidence gaps keep this provisional.'),
    }
    write_once(folder / 'manifest.json',
               (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(f"{len(approved)} approved, {len(held)} held; "
          f"{len(differences)} affected account-day rows")
    print(folder)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path,
                        default=ROOT / 'docs/action_reviews/decision_ledger.json')
    args = parser.parse_args()
    run(args.ledger.resolve())
