"""Check the saved Mastercard pilot against the rows actually loaded in RAW."""

import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.dividend_reconciliation import compare
from scripts.check_daily_oms_pilot import connect
from scripts.close_daily_pilot import saved_delivery
from simulation.daily_oms import write_once
from simulation.two_year_dividend_pilot import ACTION, CLOSE, OUTPUT, SCENARIO


def csv_rows(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def loaded(cursor, table, manifest_path, manifest, expected):
    cursor.execute(f'''
        select payload::varchar from NORTHBRIDGE_DEV.RAW.{table}
        where delivery_id = %s
    ''', (manifest['delivery_id'],))
    actual = [json.loads(row[0]) for row in cursor.fetchall()]
    if len(actual) != len(expected) or {row.get('event_id', row.get('record_id')): row
                                            for row in actual} != {
            row.get('event_id', row.get('record_id')): row for row in expected}:
        raise ValueError(f'RAW {table} differs from the saved delivery')
    cursor.execute('''
        select manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where delivery_id = %s
    ''', (manifest['delivery_id'],))
    receipt = cursor.fetchall()
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if (len(receipt) != 1 or receipt[0] !=
            (digest, len(expected), len(expected), 'READY')):
        raise ValueError(f'Missing READY receipt for {table}')
    return actual


def run():
    day = '2025-02-07'
    folder = OUTPUT / day
    pay_manifest, pay_saved = saved_delivery(folder / 'custodian', 'payments.jsonl')
    bank_manifest, bank_saved = saved_delivery(folder / 'bank', 'balances.jsonl')
    close_manifest = json.loads((CLOSE / 'manifest.json').read_text(encoding='utf-8'))
    for name, digest in (('daily.csv', pay_manifest['source_evidence']['daily_sha256']),
                         ('dividend_entitlements.csv', pay_manifest['source_evidence']['entitlements_sha256'])):
        if hashlib.sha256((CLOSE / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Close input changed: {name}')
    if (bank_manifest['source_evidence'] != pay_manifest['source_evidence']
            or close_manifest['scenario_id'] != SCENARIO):
        raise ValueError('Pilot sources disagree')
    approvals = ROOT / 'dbt/seeds/approved_corporate_actions.csv'
    if hashlib.sha256(approvals.read_bytes()).hexdigest() != pay_manifest['source_evidence']['approved_actions_sha256']:
        raise ValueError('Reviewed action seed changed')
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            payments = loaded(cursor, 'DIVIDEND_PAYMENT_EVENTS',
                              folder / 'custodian/manifest.json', pay_manifest, pay_saved)
            banks = loaded(cursor, 'BANK_CASH_STATEMENTS',
                           folder / 'bank/manifest.json', bank_manifest, bank_saved)
            cursor.execute('''
                select ticker, ex_dividend_date, pay_date, cash_amount
                from NORTHBRIDGE_DEV.DBT_DEV.STG_CORPORATE_ACTIONS
                where event_id = %s
            ''', (ACTION,))
            action = cursor.fetchall()
            if len(action) != 1 or action[0][0] != 'MA' or action[0][1].isoformat() != '2025-01-10' \
                    or action[0][2].isoformat() != day or str(action[0][3]) != '0.760000000000':
                raise ValueError('Live Mastercard action differs from reviewed pilot')
    finally:
        connection.close()
    entitlements = [row for row in csv_rows(CLOSE / 'dividend_entitlements.csv')
                    if row['event_id'] == ACTION]
    daily = {row['account_id']: row for row in csv_rows(CLOSE / 'daily.csv')
             if row['business_date'] == day}
    payment_by_account = {row['account_id']: row for row in payments}
    bank_by_account = {row['account_id']: row for row in banks}
    if (len(entitlements) != 2 or len(payment_by_account) != len(payments)
            or len(bank_by_account) != len(banks)
            or set(daily) != {row['account_id'] for row in entitlements}
            or set(payment_by_account) != set(daily) or set(bank_by_account) != set(daily)):
        raise ValueError('Pilot needs one entitlement, payment and bank row per account')
    results = [compare(row, payment_by_account[row['account_id']],
                       bank_by_account[row['account_id']],
                       daily[row['account_id']]['settled_cash_usd'])
               for row in sorted(entitlements, key=lambda item: item['account_id'])]
    status = ('PILOT_MATCHED_NOT_INDEPENDENT' if all(
        row['payment_status'] == row['bank_status'] == 'MATCHED' for row in results)
              else 'REVIEW_REQUIRED')
    report = {'scenario_id': SCENARIO, 'corporate_action_id': ACTION,
              'payment_date': day, 'status': status, 'accounts': results,
              'payment_delivery_id': pay_manifest['delivery_id'],
              'bank_delivery_id': bank_manifest['delivery_id'],
              'limitation': 'Both fictional feeds were generated from the provisional ledger. The full 500-day close still carries this receivable until payment handling is extended.'}
    write_once(folder / 'reconciliation_v2.json',
               (json.dumps(report, indent=2, sort_keys=True) + '\n').encode())
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    result = run()
    raise SystemExit(0 if result['status'] == 'PILOT_MATCHED_NOT_INDEPENDENT' else 1)
