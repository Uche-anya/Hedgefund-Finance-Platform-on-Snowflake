"""Put the first twelve pending dividends and their evidence in one review file."""

import csv
from datetime import date
from decimal import Decimal
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simulation.daily_oms import write_once

QUEUE = ROOT / 'data/two_year_action_review/v1'
TRIAGE = ROOT / 'data/two_year_action_triage/v1'
NOTICES = ROOT / 'reference/dividend_ex_date_notices.csv'
OUTPUT = ROOT / 'data/two_year_action_review/top12_evidence_v1'
NYSE_RULE = 'https://www.nyse.com/trade/ex-date-dividends'
NASDAQ_RULE = 'https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/nasdaq-equity-11'


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


def make_review(queue_row, triage_row, notice):
    if (queue_row['event_id'] != triage_row['event_id']
            or queue_row['ticker'] != triage_row['ticker']
            or queue_row['record_date'] != triage_row['record_date']
            or queue_row['ex_dividend_date'] != triage_row['ex_dividend_date']
            or queue_row['pay_date'] != triage_row['pay_date']
            or queue_row['review_status'] != 'PENDING'
            or triage_row['review_decision'] != 'PENDING'
            or triage_row['issuer_check'] not in ('PARTIAL_ISSUER_MATCH', 'ISSUER_CONFLICT')):
        raise ValueError(f'Review files disagree: {queue_row["event_id"]}')
    event_date = date.fromisoformat(queue_row['record_date'])
    if (event_date.weekday() >= 5
            or queue_row['ex_dividend_date'] != queue_row['record_date']
            or Decimal(queue_row['cash_per_share_usd']) <= 0):
        raise ValueError(f'Ordinary ex-date rule cannot be assumed: {queue_row["event_id"]}')
    rule = NASDAQ_RULE if queue_row['ticker'] == 'PEP' else NYSE_RULE
    notice_date = notice['ex_dividend_date'] if notice else ''
    if notice and notice_date != queue_row['ex_dividend_date']:
        raise ValueError(f'Exchange notice differs from provider: {queue_row["event_id"]}')
    if triage_row['issuer_check'] == 'ISSUER_CONFLICT':
        recommendation = 'HOLD_DECLARATION_CONFLICT'
    else:
        recommendation = 'AWAITING_REVIEW'
    return {
        'event_id': queue_row['event_id'],
        'ticker': queue_row['ticker'],
        'record_date': queue_row['record_date'],
        'provider_ex_dividend_date': queue_row['ex_dividend_date'],
        'issuer_check': triage_row['issuer_check'],
        'conflicting_fields': triage_row['conflicting_fields'],
        'issuer_source_url': triage_row['issuer_source_url'],
        'us_ex_date_rule_url': rule,
        'other_venue': notice['venue'] if notice else '',
        'other_venue_ex_date': notice_date,
        'other_venue_notice_url': notice['source_url'] if notice else '',
        'account_01_opening_shares': queue_row['account_01_opening_shares'],
        'account_01_signed_amount_usd': queue_row['account_01_signed_amount_usd'],
        'account_02_opening_shares': queue_row['account_02_opening_shares'],
        'account_02_signed_amount_usd': queue_row['account_02_signed_amount_usd'],
        'gross_absolute_exposure_usd': queue_row['gross_absolute_exposure_usd'],
        'recommendation': recommendation,
        'approved': 'NO',
    }


def prepare():
    queue_manifest = json.loads((QUEUE / 'manifest.json').read_text(encoding='utf-8'))
    triage_manifest = json.loads((TRIAGE / 'manifest.json').read_text(encoding='utf-8'))
    if (sha256(QUEUE / 'queue.csv') != queue_manifest['queue_sha256']
            or sha256(TRIAGE / 'triage.csv') != triage_manifest['triage_sha256']
            or triage_manifest['input_sha256']['queue'] != queue_manifest['queue_sha256']):
        raise ValueError('Review input changed')
    queue = read_csv(QUEUE / 'queue.csv')[:12]
    triage = {r['event_id']: r for r in read_csv(TRIAGE / 'triage.csv')}
    notices = {}
    for row in read_csv(NOTICES):
        key = row['ticker'], row['record_date']
        if key in notices or not row['source_url'].startswith('https://'):
            raise ValueError(f'Duplicate or unsourced exchange notice: {key}')
        notices[key] = row
    if len(queue) != 12:
        raise ValueError('Expected twelve priority events')
    reviews = []
    used_notices = set()
    for row in queue:
        key = row['ticker'], row['record_date']
        notice = notices.get(key)
        if notice:
            used_notices.add(key)
        reviews.append(make_review(row, triage[row['event_id']], notice))
    if used_notices != set(notices):
        raise ValueError(f'Exchange notice not matched to priority event: {set(notices)-used_notices}')
    body = csv_bytes(reviews)
    write_once(OUTPUT / 'review.csv', body)
    summary = {
        'status': 'RESEARCH_PACKET_NOT_APPROVAL',
        'events': len(reviews),
        'issuer_conflicts': sum(r['recommendation'] == 'HOLD_DECLARATION_CONFLICT'
                                for r in reviews),
        'other_venue_ex_date_notices': len(used_notices),
        'approved_events': 0,
        'gross_absolute_exposure_usd': str(sum(
            (Decimal(r['gross_absolute_exposure_usd']) for r in reviews), Decimal(0))),
        'input_sha256': {
            'queue': sha256(QUEUE / 'queue.csv'),
            'triage': sha256(TRIAGE / 'triage.csv'),
            'exchange_notices': sha256(NOTICES),
        },
        'review_sha256': hashlib.sha256(body).hexdigest(),
    }
    write_once(OUTPUT / 'manifest.json',
               (json.dumps(summary, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    print(f"{len(reviews)} reviewed: {summary['issuer_conflicts']} conflicts, "
          f"{summary['other_venue_ex_date_notices']} other-venue ex-date notices, 0 approved")
    print(OUTPUT / 'review.csv')
    return reviews, summary


if __name__ == '__main__':
    prepare()
