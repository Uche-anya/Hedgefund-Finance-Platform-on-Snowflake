"""Check the December 2025 PepsiCo candidate before a reviewer decides."""

import csv
from decimal import Decimal
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.preview_two_year_action_decision import preview_rows
from simulation.daily_oms import write_once

EVENT_ID = 'E1265d74c6ece2a1d84fe33404bceacb822de00c362e40caf43932720e9a586d4'
QUEUE = ROOT / 'data/two_year_action_review/v1'
CLOSE = ROOT / 'data/two_year_close/provisional_v2_review_split'
SOURCE = (ROOT / 'data/corporate_action_loads'
          / '890be0cfdcf2151ebb4aab47f0d53cd9/actions.jsonl')
ISSUER = ROOT / 'reference/dividend_issuer_evidence.csv'
NOTICES = ROOT / 'reference/dividend_ex_date_notices.csv'
DIMENSION = ROOT / 'dbt/seeds/dim_instrument.csv'
OUTPUT = ROOT / 'data/two_year_action_review/pep_2025-12-05_evidence_v1'
ACCOUNTS = ('SIM-REPLAY-01', 'SIM-REPLAY-02')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def one(rows, description):
    if len(rows) != 1:
        raise ValueError(f'Expected one {description}; found {len(rows)}')
    return rows[0]


def prior_holdings(position_rows, event, entitlements):
    prior = {}
    for account in ACCOUNTS:
        position = one([r for r in position_rows
                        if r['business_date'] == '2025-12-04'
                        and r['account_id'] == account
                        and r['security_id'] == event['security_id']],
                       f'prior-close PepsiCo position for {account}')
        entitlement = one([r for r in entitlements if r['account_id'] == account],
                          f'candidate entitlement for {account}')
        if (Decimal(position['quantity']) != Decimal(entitlement['opening_quantity'])
                or Decimal(position['quantity']) * Decimal(event['cash_per_share_usd'])
                   != Decimal(entitlement['gross_amount_usd'])
                or Decimal(event['cash_per_share_usd'])
                   >= Decimal(position['close_price_usd']) * Decimal('0.25')
                or entitlement['payment_status'] != 'NO_CONFIRMATION'):
            raise ValueError(f'Position and dividend candidate disagree for {account}')
        prior[account] = position['quantity']
    return prior


def csv_bytes(rows):
    handle = StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode('utf-8')


def prepare():
    queue_manifest = json.loads((QUEUE / 'manifest.json').read_text(encoding='utf-8'))
    close_manifest = json.loads((CLOSE / 'manifest.json').read_text(encoding='utf-8'))
    if (sha256(QUEUE / 'queue.csv') != queue_manifest['queue_sha256']
            or sha256(CLOSE / 'manifest.json')
               != queue_manifest['inputs_sha256']['close_manifest']
            or sha256(SOURCE) != queue_manifest['inputs_sha256']['provider_actions']
            or sha256(CLOSE / 'daily.csv')
               != close_manifest['files']['daily.csv']['sha256']
            or sha256(CLOSE / 'positions.csv')
               != close_manifest['files']['positions.csv']['sha256']
            or sha256(CLOSE / 'dividend_entitlements.csv')
               != close_manifest['files']['dividend_entitlements.csv']['sha256']):
        raise ValueError('Saved review or close changed')
    event = one([r for r in read_csv(QUEUE / 'queue.csv') if r['event_id'] == EVENT_ID],
                'pending PepsiCo event')
    if (event['review_status'] != 'PENDING' or event['ticker'] != 'PEP'
            or event['security_id'] != 'NB_EQ_0019'):
        raise ValueError('Wrong review event')

    provider = None
    with SOURCE.open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            if record['event']['id'] == EVENT_ID:
                if provider is not None:
                    raise ValueError('Duplicate provider event')
                provider = record['event']
    issuer = one([r for r in read_csv(ISSUER) if r['ticker'] == 'PEP'
                  and r['record_date'] == event['record_date']], 'issuer record')
    notice = one([r for r in read_csv(NOTICES) if r['ticker'] == 'PEP'
                  and r['record_date'] == event['record_date']], 'ex-date notice')
    identity = one([r for r in read_csv(DIMENSION)
                    if r['security_id'] == event['security_id']
                    and r['valid_from'] <= event['ex_dividend_date'] <= r['valid_to']],
                   'dated security identity')
    if (provider is None or provider['ticker'] != 'PEP'
            or provider['declaration_date'] != issuer['declared_date']
            or provider['record_date'] != issuer['record_date']
            or provider['pay_date'] != issuer['pay_date']
            or provider['ex_dividend_date'] != notice['ex_dividend_date']
            or notice['security_isin'] != 'US7134481081'
            or notice['venue'] != 'XFRA'
            or Decimal(str(provider['cash_amount'])) != Decimal(issuer['cash_per_share_usd'])
            or Decimal(event['cash_per_share_usd']) != Decimal(issuer['cash_per_share_usd'])
            or identity['ticker'] != 'PEP' or identity['primary_exchange'] != 'XNAS'
            or identity['share_class_figi'] != 'BBG001S695T1'):
        raise ValueError('Provider, issuer, exchange notice or identity disagree')
    entitlements = [r for r in read_csv(CLOSE / 'dividend_entitlements.csv')
                    if r['event_id'] == EVENT_ID]
    positions = prior_holdings(read_csv(CLOSE / 'positions.csv'), event, entitlements)
    preview, amounts = preview_rows(read_csv(CLOSE / 'daily.csv'), event,
                                    entitlements, {'decision': 'HOLD'})
    body = csv_bytes(preview)
    write_once(OUTPUT / 'conditional_nav.csv', body)
    result = {
        'event_id': EVENT_ID,
        'status': 'EVIDENCE_PREPARED_NOT_APPROVED',
        'provider_ex_date': event['ex_dividend_date'],
        'issuer_declared_date': issuer['declared_date'],
        'issuer_record_date': issuer['record_date'],
        'issuer_pay_date': issuer['pay_date'],
        'issuer_cash_per_share_usd': issuer['cash_per_share_usd'],
        'issuer_source_url': issuer['source_url'],
        'other_venue': notice['venue'],
        'other_venue_ex_date': notice['ex_dividend_date'],
        'other_venue_source_url': notice['source_url'],
        'us_ex_date_rule_url': 'https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/nasdaq-equity-11',
        'security_id': identity['security_id'],
        'share_class_figi': identity['share_class_figi'],
        'security_reference_as_of': '2025-01-10',
        'prior_close_date': '2025-12-04',
        'prior_close_shares': positions,
        'candidate_amount_usd_by_account': {k: str(v) for k, v in amounts.items()},
        'conditional_account_day_rows': len(preview),
        'conditional_market_days': len({r['business_date'] for r in preview}),
        'payment_status': 'NO_CONFIRMATION',
        'open_checks': ['US listing event-specific ex-date or approved rule policy',
                        'security identity on the event date',
                        'named reviewer of fictional account entitlement'],
        'input_sha256': {
            'queue': sha256(QUEUE / 'queue.csv'),
            'close_manifest': sha256(CLOSE / 'manifest.json'),
            'provider_actions': sha256(SOURCE),
            'issuer_evidence': sha256(ISSUER),
            'exchange_notices': sha256(NOTICES),
            'security_dimension': sha256(DIMENSION),
        },
        'conditional_nav_sha256': hashlib.sha256(body).hexdigest(),
    }
    write_once(OUTPUT / 'evidence.json',
               (json.dumps(result, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    print('PEP 2025-12-05: evidence prepared; no approval or cash confirmation')
    print('Prior-close shares:', positions)
    print('Candidate amounts:', result['candidate_amount_usd_by_account'])
    print(f"Conditional NAV rows: {len(preview)}")
    print(OUTPUT)
    return result


if __name__ == '__main__':
    prepare()
