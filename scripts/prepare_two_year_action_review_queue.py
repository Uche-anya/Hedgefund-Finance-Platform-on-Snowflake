"""Rank pending dividend events by the dollars exposed in the v2 fund."""

import csv
from decimal import Decimal
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simulation.daily_oms import write_once

CLOSE = ROOT / 'data/two_year_close/provisional_v2_review_split'
REVIEW = ROOT / 'data/two_year_dividend_review.csv'
SOURCE = (ROOT / 'data/corporate_action_loads'
          / '890be0cfdcf2151ebb4aab47f0d53cd9/actions.jsonl')
OUTPUT = ROOT / 'data/two_year_action_review/v1'
ACCOUNTS = ('SIM-REPLAY-01', 'SIM-REPLAY-02')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def ranked_row(action, entitlements):
    if (action['review_status'] != 'PENDING' or len(entitlements) != len(ACCOUNTS)
            or {row['account_id'] for row in entitlements} != set(ACCOUNTS)):
        raise ValueError(f'Wrong account coverage or review state: {action["event_id"]}')
    by_account = {row['account_id']: row for row in entitlements}
    amounts = []
    for account in ACCOUNTS:
        row = by_account[account]
        if (row['event_id'] != action['event_id']
                or row['security_id'] != action['security_id']
                or row['ex_dividend_date'] != action['ex_dividend_date']
                or row['pay_date'] != action['pay_date']
                or row['review_status'] != 'PENDING'
                or row['payment_status'] != 'NO_CONFIRMATION'
                or Decimal(row['cash_per_share_usd']) != Decimal(action['cash_per_share_usd'])):
            raise ValueError(f'Entitlement differs from provider review: {action["event_id"]}')
        amount = Decimal(row['gross_amount_usd'])
        if amount != Decimal(row['opening_quantity']) * Decimal(action['cash_per_share_usd']):
            raise ValueError(f'Shares times rate differs from entitlement: {action["event_id"]}')
        amounts.append(amount)
    long_cash = sum((max(amount, 0) for amount in amounts), Decimal(0))
    short_cash = sum((max(-amount, 0) for amount in amounts), Decimal(0))
    gross = sum((abs(amount) for amount in amounts), Decimal(0))
    return {
        'event_id': action['event_id'], 'ticker': action['ticker'],
        'security_id': action['security_id'],
        'ex_dividend_date': action['ex_dividend_date'],
        'record_date': action['record_date'], 'pay_date': action['pay_date'],
        'cash_per_share_usd': action['cash_per_share_usd'],
        'distribution_type': action['distribution_type'],
        'identity_status': action['identity_status'],
        'source_file': action['source_file'],
        'source_row_number': action['source_row_number'],
        'account_01_opening_shares': by_account[ACCOUNTS[0]]['opening_quantity'],
        'account_01_signed_amount_usd': str(amounts[0]),
        'account_02_opening_shares': by_account[ACCOUNTS[1]]['opening_quantity'],
        'account_02_signed_amount_usd': str(amounts[1]),
        'possible_long_receipts_usd': str(long_cash),
        'possible_short_payments_usd': str(short_cash),
        'net_candidate_impact_usd': str(long_cash - short_cash),
        'gross_absolute_exposure_usd': str(gross),
        'review_status': 'PENDING',
        'decision': 'NOT_DECIDED',
    }


def csv_bytes(rows):
    output = StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode('utf-8')


def prepare():
    close_manifest = json.loads((CLOSE / 'manifest.json').read_text(encoding='utf-8'))
    entitlement_file = CLOSE / 'dividend_entitlements.csv'
    if (close_manifest['scenario_id'] != 'sim-equity-2024-2026-v2'
            or close_manifest['review_split']['pending_event_ids'] != 143
            or digest(entitlement_file) != close_manifest['files']['dividend_entitlements.csv']['sha256']):
        raise ValueError('Wrong or changed two-year close')
    review_rows = read_csv(REVIEW)
    review = {row['event_id']: row for row in review_rows}
    if len(review) != len(review_rows):
        raise ValueError('Repeated event ID in review file')
    source = {}
    with SOURCE.open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            event_id = record['event']['id']
            if event_id in review:
                if event_id in source:
                    raise ValueError(f'Repeated source event: {event_id}')
                source[event_id] = record
    if set(source) != set(review):
        raise ValueError('Provider source and review file cover different events')
    entitlements = {}
    for row in read_csv(entitlement_file):
        entitlements.setdefault(row['event_id'], []).append(row)
    if set(entitlements) != set(review):
        raise ValueError('Close entitlements and review file cover different events')

    queue = []
    for event_id, action in review.items():
        record = source[event_id]
        event = record['event']
        if (record['action_type'] != 'dividends'
                or event['ticker'] != action['ticker']
                or event['ex_dividend_date'] != action['ex_dividend_date']
                or event['record_date'] != action['record_date']
                or event['pay_date'] != action['pay_date']
                or event['distribution_type'] != action['distribution_type']
                or record['identity_status'] != action['identity_status']
                or Decimal(str(event['cash_amount'])) != Decimal(action['cash_per_share_usd'])
                or record['source_file'] != action['source_file']
                or str(record['source_row_number']) != action['source_row_number']):
            raise ValueError(f'Provider event differs from review file: {event_id}')
        if action['review_status'] == 'PENDING':
            queue.append(ranked_row(action, entitlements[event_id]))
        elif action['review_status'] != 'APPROVED_IN_SEED':
            raise ValueError(f'Unknown review status: {event_id}')
    queue.sort(key=lambda row: (-Decimal(row['gross_absolute_exposure_usd']),
                                row['ex_dividend_date'], row['event_id']))
    if len(queue) != 143:
        raise ValueError('Expected 143 pending dividend events')
    body = csv_bytes(queue)
    write_once(OUTPUT / 'queue.csv', body)
    active = sum(Decimal(row['gross_absolute_exposure_usd']) > 0 for row in queue)
    summary = {
        'scenario_id': close_manifest['scenario_id'],
        'status': 'PRIORITIZED_NOT_APPROVED',
        'accounts': list(ACCOUNTS),
        'pending_events': len(queue),
        'events_with_exposure': active,
        'events_without_exposure': len(queue) - active,
        'rank_method': 'sum of absolute account amounts, so opposing accounts do not cancel',
        'gross_absolute_exposure_usd': str(sum(
            (Decimal(row['gross_absolute_exposure_usd']) for row in queue), Decimal(0))),
        'net_candidate_impact_usd': str(sum(
            (Decimal(row['net_candidate_impact_usd']) for row in queue), Decimal(0))),
        'top_event_id': queue[0]['event_id'],
        'inputs_sha256': {
            'close_manifest': digest(CLOSE / 'manifest.json'),
            'entitlements': digest(entitlement_file),
            'review_file': digest(REVIEW),
            'provider_actions': digest(SOURCE),
            'approval_seed': digest(ROOT / 'dbt/seeds/approved_corporate_actions.csv'),
        },
        'queue_sha256': hashlib.sha256(body).hexdigest(),
    }
    write_once(OUTPUT / 'manifest.json',
               (json.dumps(summary, indent=2, sort_keys=True) + '\n').encode())
    print(f"{len(queue)} pending actions: {active} with exposure, {len(queue)-active} without")
    print('Highest exposure:', queue[0]['ticker'], queue[0]['ex_dividend_date'],
          queue[0]['gross_absolute_exposure_usd'])
    print(OUTPUT)
    return queue, summary


if __name__ == '__main__':
    prepare()
