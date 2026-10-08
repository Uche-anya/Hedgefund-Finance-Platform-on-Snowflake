"""Save one fictional Mastercard payment and matching bank statement for v2."""

import csv
from decimal import Decimal
import hashlib
import json

from simulation.daily_oms import ROOT, write_once

SCENARIO = 'sim-equity-2024-2026-v2'
ACTION = 'Ec6372be9137e6a822fd370e8f0738fc31cfb9db56ee95abb2ee9b45f3022db0b'
CLOSE = ROOT / 'data/two_year_close/provisional_v2'
OUTPUT = ROOT / 'data/dividend_payment_pilot' / SCENARIO


def saved_csv(name, manifest):
    path = CLOSE / name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest['files'][name]['sha256']:
        raise ValueError(f'Close input changed: {name}')
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle)), digest


def save(folder, filename, delivery_id, day, rows, evidence):
    body = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
    manifest = {
        'delivery_id': delivery_id, 'scenario_id': SCENARIO,
        'business_date': day, 'is_simulated': True,
        'record_count': len(rows), 'files': {filename: hashlib.sha256(body).hexdigest()},
        'source_evidence': evidence,
        'note': 'Both fictional feeds were generated from the same provisional ledger; this is not independent bank or custodian evidence.',
    }
    write_once(folder / filename, body)
    write_once(folder / 'manifest.json',
               (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    return manifest


def generate():
    close_manifest = json.loads((CLOSE / 'manifest.json').read_text(encoding='utf-8'))
    if close_manifest['scenario_id'] != SCENARIO or close_manifest['status'] != 'PROVISIONAL_UNAPPROVED':
        raise ValueError('Wrong provisional close')
    approvals = ROOT / 'dbt/seeds/approved_corporate_actions.csv'
    with approvals.open(newline='', encoding='utf-8') as handle:
        approved = {row['event_id'] for row in csv.DictReader(handle)}
    if ACTION not in approved:
        raise ValueError('Mastercard event is not in the reviewed action seed')
    entitlements, entitlement_hash = saved_csv('dividend_entitlements.csv', close_manifest)
    daily, daily_hash = saved_csv('daily.csv', close_manifest)
    selected = [row for row in entitlements if row['event_id'] == ACTION]
    if len(selected) != 2 or {row['account_id'] for row in selected} != {
            'SIM-REPLAY-01', 'SIM-REPLAY-02'}:
        raise ValueError('Expected one Mastercard entitlement per account')
    dates = {(row['ex_dividend_date'], row['pay_date'], row['security_id'],
              row['cash_per_share_usd'], row['review_status']) for row in selected}
    if dates != {('2025-01-10', '2025-02-07', 'NB_EQ_0012',
                  '0.760000000000', 'APPROVED_IN_SEED')}:
        raise ValueError('Reviewed Mastercard action differs from this pilot')
    day = '2025-02-07'
    balances = {row['account_id']: Decimal(row['settled_cash_usd']) for row in daily
                if row['business_date'] == day}
    if set(balances) != {row['account_id'] for row in selected}:
        raise ValueError('Missing base cash on payment date')

    payments, bank = [], []
    for row in sorted(selected, key=lambda item: item['account_id']):
        account = row['account_id']
        amount = Decimal(row['opening_quantity']) * Decimal(row['cash_per_share_usd'])
        if amount <= 0 or amount != Decimal(row['gross_amount_usd']):
            raise ValueError(f'Unmatched positive entitlement for {account}')
        amount = amount.quantize(Decimal('0.01'))
        stamp = hashlib.sha256(f'{SCENARIO}/{ACTION}/{account}'.encode()).hexdigest()[:24]
        payments.append({
            'schema_version': 1, 'event_id': 'sim-dividend-payment-' + stamp,
            'event_type': 'DIVIDEND_PAYMENT_CONFIRMED',
            'scenario_id': SCENARIO, 'source_system': 'simulated_custodian',
            'is_simulated': True, 'corporate_action_id': ACTION,
            'account_id': account, 'instrument_id': 'MA.US', 'currency': 'USD',
            'cash_amount': str(amount), 'settlement_date': day,
            'settled_at': day + 'T18:00:00+00:00',
            'published_at': day + 'T18:01:00+00:00',
        })
        bank.append({
            'record_id': 'SIM-BANK-DIV-' + stamp,
            'statement_id': 'SIM-BANK-DIV-' + day.replace('-', ''),
            'scenario_id': SCENARIO, 'statement_date': day,
            'account_id': account, 'currency': 'USD',
            'closing_balance': str(balances[account] + amount),
            'published_at': day + 'T23:00:00+00:00',
            'source_system': 'simulated_bank', 'is_simulated': True,
        })
    evidence = {'daily_sha256': daily_hash, 'entitlements_sha256': entitlement_hash,
                'approved_actions_sha256': hashlib.sha256(approvals.read_bytes()).hexdigest()}
    folder = OUTPUT / day
    payment_id = 'sim-dividend-payment-v2-' + day.replace('-', '')
    bank_id = 'sim-bank-dividend-v2-' + day.replace('-', '')
    save(folder / 'custodian', 'payments.jsonl', payment_id, day, payments, evidence)
    save(folder / 'bank', 'balances.jsonl', bank_id, day, bank, evidence)
    config = {'inputs': [
        {'source_name': 'dividend_payments', 'delivery_id': payment_id,
         'manifest': str((folder / 'custodian/manifest.json').relative_to(ROOT)).replace('\\', '/'),
         'expected_rows': len(payments)},
        {'source_name': 'bank_cash', 'delivery_id': bank_id,
         'manifest': str((folder / 'bank/manifest.json').relative_to(ROOT)).replace('\\', '/'),
         'expected_rows': len(bank)},
    ]}
    write_once(folder / 'load_config.json',
               (json.dumps(config, indent=2, sort_keys=True) + '\n').encode())
    print(f'{day}: two fictional Mastercard receipts and two bank balances')
    print(folder)
    return folder


if __name__ == '__main__':
    generate()
