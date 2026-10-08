"""List the dividend events that need review before two-year NAV."""

import csv
from decimal import Decimal
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION_FILE = (ROOT / 'data/corporate_action_loads'
               / '890be0cfdcf2151ebb4aab47f0d53cd9/actions.jsonl')
OUTPUT = ROOT / 'data/two_year_dividend_review.csv'


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def prepare():
    config = json.loads((ROOT / 'config/two_year_replay.json').read_text(encoding='utf-8'))
    tickers = set(config['tickers'])
    dimension = read_csv(ROOT / 'dbt/seeds/dim_instrument.csv')
    approved = {row['event_id'] for row in
                read_csv(ROOT / 'dbt/seeds/approved_corporate_actions.csv')}
    rows = []
    with ACTION_FILE.open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            if record['action_type'] != 'dividends':
                continue
            event = record['event']
            ticker = event.get('ticker')
            ex_date = event.get('ex_dividend_date')
            if ticker not in tickers or not ex_date or not (
                    '2024-09-23' <= ex_date <= '2026-09-21'):
                continue
            matched = [item for item in dimension if item['ticker'] == ticker
                       and item['valid_from'] <= ex_date <= item['valid_to']]
            if len(matched) != 1:
                raise ValueError(f'No unique security identity for {ticker} on {ex_date}')
            amount = Decimal(str(event['cash_amount']))
            if (not amount.is_finite() or amount <= 0 or event.get('currency') != 'USD'
                    or not event.get('pay_date') or event['pay_date'] < ex_date):
                raise ValueError(f'Invalid dividend dates, currency or amount: {event["id"]}')
            rows.append({
                'event_id': event['id'],
                'ticker': ticker,
                'security_id': matched[0]['security_id'],
                'ex_dividend_date': ex_date,
                'record_date': event.get('record_date', ''),
                'pay_date': event['pay_date'],
                'cash_per_share_usd': str(amount),
                'distribution_type': event.get('distribution_type', ''),
                'identity_status': record['identity_status'],
                'source_file': record['source_file'],
                'source_row_number': record['source_row_number'],
                'review_status': 'APPROVED_IN_SEED' if event['id'] in approved else 'PENDING',
            })
    rows.sort(key=lambda row: (row['ex_dividend_date'], row['ticker'], row['event_id']))
    if len({row['event_id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate provider dividend event ID')
    fieldnames = list(rows[0])
    with OUTPUT.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    pending = sum(row['review_status'] == 'PENDING' for row in rows)
    print(f'{len(rows)} dividend candidates; {pending} pending, {len(rows)-pending} already in approval seed')
    print(OUTPUT)
    return rows


if __name__ == '__main__':
    prepare()
