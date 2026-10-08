"""Compare the pending dividend queue with issuer records already checked by hand."""

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

QUEUE = ROOT / 'data/two_year_action_review/v1'
SOURCE = (ROOT / 'data/corporate_action_loads'
          / '890be0cfdcf2151ebb4aab47f0d53cd9/actions.jsonl')
EVIDENCE = ROOT / 'reference/dividend_issuer_evidence.csv'
DIMENSION = ROOT / 'dbt/seeds/dim_instrument.csv'
OUTPUT = ROOT / 'data/two_year_action_triage/v1'


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


def compare(provider, issuer):
    if issuer is None:
        return 'NO_ISSUER_EVIDENCE', '', ''
    missing = []
    if not issuer['declared_date']:
        missing.append('declaration_date')
    if not issuer['ex_dividend_date']:
        missing.append('ex_dividend_date')
    different = []
    for provider_name, issuer_name in (
            ('record_date', 'record_date'),
            ('pay_date', 'pay_date'),
            ('declaration_date', 'declared_date'),
            ('ex_dividend_date', 'ex_dividend_date')):
        if issuer[issuer_name] and provider.get(provider_name, '') != issuer[issuer_name]:
            different.append(provider_name)
    if Decimal(str(provider['cash_amount'])) != Decimal(issuer['cash_per_share_usd']):
        different.append('cash_amount')
    if different:
        return 'ISSUER_CONFLICT', ','.join(different), ','.join(missing)
    return ('PARTIAL_ISSUER_MATCH' if missing else 'ISSUER_FIELDS_MATCH',
            '', ','.join(missing))


def triage():
    manifest = json.loads((QUEUE / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest['status'] != 'PRIORITIZED_NOT_APPROVED'
            or sha256(QUEUE / 'queue.csv') != manifest['queue_sha256']
            or sha256(SOURCE) != manifest['inputs_sha256']['provider_actions']):
        raise ValueError('Review queue or provider snapshot has changed')
    queue = read_csv(QUEUE / 'queue.csv')
    if len(queue) != manifest['pending_events'] or len({r['event_id'] for r in queue}) != len(queue):
        raise ValueError('Pending event count or IDs changed')

    issuer_rows = read_csv(EVIDENCE)
    issuer = {}
    for row in issuer_rows:
        key = row['ticker'], row['record_date']
        if key in issuer or not row['source_url'].startswith('https://'):
            raise ValueError(f'Duplicate or unsourced issuer record: {key}')
        issuer[key] = row

    dimension = read_csv(DIMENSION)
    wanted = {row['event_id'] for row in queue}
    source = {}
    with SOURCE.open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            event_id = record['event']['id']
            if event_id in wanted:
                if event_id in source:
                    raise ValueError(f'Duplicate provider event: {event_id}')
                source[event_id] = record
    if set(source) != wanted:
        raise ValueError('Queue event missing from provider snapshot')

    results = []
    used_evidence = set()
    for row in queue:
        record = source[row['event_id']]
        event = record['event']
        if (record['action_type'] != 'dividends'
                or event['ticker'] != row['ticker']
                or event['record_date'] != row['record_date']
                or event['pay_date'] != row['pay_date']
                or event['ex_dividend_date'] != row['ex_dividend_date']
                or Decimal(str(event['cash_amount'])) != Decimal(row['cash_per_share_usd'])
                or row['review_status'] != 'PENDING'):
            raise ValueError(f'Queue differs from source: {row["event_id"]}')
        identities = [d for d in dimension if d['ticker'] == row['ticker']
                      and d['valid_from'] <= row['ex_dividend_date'] <= d['valid_to']]
        if len(identities) != 1 or identities[0]['security_id'] != row['security_id']:
            raise ValueError(f'Security identity changed: {row["event_id"]}')
        key = row['ticker'], row['record_date']
        evidence = issuer.get(key)
        if evidence:
            used_evidence.add(key)
        status, conflicts, unverified = compare(event, evidence)
        results.append({
            'event_id': row['event_id'], 'ticker': row['ticker'],
            'ex_dividend_date': row['ex_dividend_date'],
            'record_date': row['record_date'],
            'pay_date': row['pay_date'],
            'cash_per_share_usd': row['cash_per_share_usd'],
            'gross_absolute_exposure_usd': row['gross_absolute_exposure_usd'],
            'issuer_check': status, 'conflicting_fields': conflicts,
            'issuer_fields_not_verified': unverified,
            'provider_declared_date': event.get('declaration_date', ''),
            'issuer_declared_date': evidence['declared_date'] if evidence else '',
            'issuer_cash_per_share_usd': evidence['cash_per_share_usd'] if evidence else '',
            'issuer_source_url': evidence['source_url'] if evidence else '',
            'review_decision': 'PENDING',
        })
    if used_evidence != set(issuer):
        raise ValueError(f'Issuer evidence does not match a pending event: {set(issuer)-used_evidence}')
    body = csv_bytes(results)
    write_once(OUTPUT / 'triage.csv', body)
    counts = {status: sum(r['issuer_check'] == status for r in results)
              for status in ('NO_ISSUER_EVIDENCE', 'PARTIAL_ISSUER_MATCH',
                             'ISSUER_FIELDS_MATCH', 'ISSUER_CONFLICT')}
    summary = {
        'scenario_id': manifest['scenario_id'],
        'status': 'ISSUER_TRIAGE_NOT_APPROVAL',
        'pending_events': len(results),
        'counts': counts,
        'issuer_evidence_exposure_usd': str(sum(
            (Decimal(r['gross_absolute_exposure_usd']) for r in results
             if r['issuer_check'] != 'NO_ISSUER_EVIDENCE'), Decimal(0))),
        'input_sha256': {'queue': sha256(QUEUE / 'queue.csv'),
                         'provider_actions': sha256(SOURCE),
                         'issuer_evidence': sha256(EVIDENCE),
                         'security_dimension': sha256(DIMENSION)},
        'triage_sha256': hashlib.sha256(body).hexdigest(),
    }
    write_once(OUTPUT / 'manifest.json',
               (json.dumps(summary, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    print(f"{len(results)} pending events checked: {counts}")
    print(OUTPUT / 'triage.csv')
    return results, summary


if __name__ == '__main__':
    triage()
