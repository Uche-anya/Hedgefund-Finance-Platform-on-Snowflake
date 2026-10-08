"""Show what one dividend decision would do to the saved daily NAV."""

import argparse
import csv
from decimal import Decimal
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simulation.daily_oms import write_once

QUEUE = ROOT / 'data/two_year_action_review/v1'
CLOSE = ROOT / 'data/two_year_close/provisional_v2_review_split'
OUTPUT = ROOT / 'data/two_year_action_review/decisions'
ACCOUNTS = ('SIM-REPLAY-01', 'SIM-REPLAY-02')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def csv_bytes(rows):
    handle = StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode('utf-8')


def check_decision(decision, event):
    if (decision.get('schema_version') != 1
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', decision.get('decision_id', ''))
            or decision.get('event_id') != event['event_id']
            or decision.get('decision') not in ('HOLD', 'APPROVE')
            or not decision.get('reason') or not decision.get('recorded_by')
            or event['review_status'] != 'PENDING'):
        raise ValueError('Decision is incomplete or refers to a different pending event')
    if decision['decision'] == 'APPROVE':
        required = ('issuer_notice', 'ex_date_source', 'security_identity',
                    'account_eligibility')
        evidence = decision.get('evidence', {})
        if (not decision.get('reviewer') or
                any(not evidence.get(item) for item in required)):
            raise ValueError('Approval needs a reviewer and evidence for the event and accounts')


def preview_rows(daily, event, entitlements, decision):
    amounts = {}
    for row in entitlements:
        if (row['event_id'] != event['event_id'] or row['review_status'] != 'PENDING'
                or row['payment_status'] != 'NO_CONFIRMATION'
                or row['security_id'] != event['security_id']
                or row['ex_dividend_date'] != event['ex_dividend_date']
                or row['pay_date'] != event['pay_date']
                or Decimal(row['cash_per_share_usd']) != Decimal(event['cash_per_share_usd'])):
            raise ValueError('Saved entitlement differs from the review queue')
        account = row['account_id']
        if account in amounts:
            raise ValueError('Repeated account entitlement')
        amount = Decimal(row['gross_amount_usd'])
        if amount != Decimal(row['opening_quantity']) * Decimal(row['cash_per_share_usd']):
            raise ValueError('Entitlement shares times rate does not equal its amount')
        amounts[account] = amount
    if set(amounts) != set(ACCOUNTS):
        raise ValueError('Missing account entitlement')

    rows = []
    seen = set()
    for day in daily:
        key = (day['business_date'], day['account_id'])
        if key in seen or day['account_id'] not in amounts:
            raise ValueError('Repeated or unknown account-day close')
        seen.add(key)
        base = Decimal(day['nav_excluding_pending_actions_usd'])
        pending = Decimal(day['pending_candidate_impact_usd'])
        if base + pending != Decimal(day['illustrative_nav_usd']):
            raise ValueError(f'Close does not reconcile: {key}')
        if day['business_date'] < event['ex_dividend_date']:
            continue
        amount = amounts[day['account_id']]
        approved_nav = base + amount
        remaining_pending = pending - amount
        if approved_nav + remaining_pending != Decimal(day['illustrative_nav_usd']):
            raise ValueError(f'Approval preview does not reconcile: {key}')
        is_approved = decision['decision'] == 'APPROVE'
        rows.append({
            'business_date': day['business_date'], 'account_id': day['account_id'],
            'reviewed_nav_before_usd': str(base),
            'pending_impact_before_usd': str(pending),
            'decision_nav_usd': str(approved_nav if is_approved else base),
            'decision_pending_impact_usd': str(remaining_pending if is_approved else pending),
            'nav_if_approved_usd': str(approved_nav),
            'pending_impact_if_approved_usd': str(remaining_pending),
            'nav_change_if_approved_usd': str(amount),
            'illustrative_nav_usd': day['illustrative_nav_usd'],
        })
    if not rows or len(seen) != len(daily):
        raise ValueError('No affected close rows or duplicate close rows')
    return rows, amounts


def load_review(decision_path):
    decision = json.loads(decision_path.read_text(encoding='utf-8'))
    queue_manifest = json.loads((QUEUE / 'manifest.json').read_text(encoding='utf-8'))
    close_manifest = json.loads((CLOSE / 'manifest.json').read_text(encoding='utf-8'))
    if (decision.get('queue_sha256') != queue_manifest['queue_sha256']
            or sha256(QUEUE / 'queue.csv') != queue_manifest['queue_sha256']
            or sha256(CLOSE / 'manifest.json') != queue_manifest['inputs_sha256']['close_manifest']
            or sha256(ROOT / 'dbt/seeds/approved_corporate_actions.csv')
               != queue_manifest['inputs_sha256']['approval_seed']
            or queue_manifest['scenario_id'] != close_manifest['scenario_id']
            or close_manifest['status'] != 'PROVISIONAL_UNAPPROVED'):
        raise ValueError('Decision inputs have changed; rebuild the queue first')

    events = [row for row in read_csv(QUEUE / 'queue.csv')
              if row['event_id'] == decision.get('event_id')]
    if len(events) != 1:
        raise ValueError('Event is not in the pending review queue')
    event = events[0]
    check_decision(decision, event)
    daily_file = CLOSE / 'daily.csv'
    entitlement_file = CLOSE / 'dividend_entitlements.csv'
    if (sha256(daily_file) != close_manifest['files']['daily.csv']['sha256']
            or sha256(entitlement_file) != close_manifest['files']['dividend_entitlements.csv']['sha256']
            or sha256(entitlement_file) != queue_manifest['inputs_sha256']['entitlements']):
        raise ValueError('Saved close files have changed')
    daily = read_csv(daily_file)
    entitlements = [row for row in read_csv(entitlement_file)
                    if row['event_id'] == event['event_id']]
    if len(daily) != close_manifest['files']['daily.csv']['rows']:
        raise ValueError('Wrong number of close rows')
    rows, amounts = preview_rows(daily, event, entitlements, decision)
    if (amounts[ACCOUNTS[0]] != Decimal(event['account_01_signed_amount_usd'])
            or amounts[ACCOUNTS[1]] != Decimal(event['account_02_signed_amount_usd'])):
        raise ValueError('Review queue amounts differ from the saved entitlements')
    return decision, event, daily, entitlements, rows, amounts, queue_manifest, close_manifest


def run(decision_path):
    (decision, event, daily, entitlements, rows, amounts,
     queue_manifest, close_manifest) = load_review(decision_path)
    body = csv_bytes(rows)
    folder = OUTPUT / decision['decision_id']
    result = {
        'decision_id': decision['decision_id'], 'event_id': event['event_id'],
        'decision': decision['decision'], 'scenario_id': queue_manifest['scenario_id'],
        'status': 'PREVIEW_ONLY_NOT_PUBLISHED',
        'affected_market_days': len({row['business_date'] for row in rows}),
        'affected_account_day_rows': len(rows),
        'approval_delta_usd_by_account': {account: str(amounts[account]) for account in ACCOUNTS},
        'actual_decision_changes_nav': decision['decision'] == 'APPROVE',
        'decision_sha256': sha256(decision_path),
        'queue_sha256': queue_manifest['queue_sha256'],
        'close_manifest_sha256': sha256(CLOSE / 'manifest.json'),
        'preview_sha256': hashlib.sha256(body).hexdigest(),
        'note': 'Approval preview reclassifies the existing candidate accrual. It does not verify payment or publish NAV.',
    }
    write_once(folder / 'preview.csv', body)
    write_once(folder / 'manifest.json',
               (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(f"{decision['decision']}: {len(rows)} affected account-day rows")
    print('If approved:', result['approval_delta_usd_by_account'])
    print(folder)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decision', type=Path,
                        default=ROOT / 'docs/action_reviews/cvx_2026-05-19.json')
    args = parser.parse_args()
    run(args.decision.resolve())
