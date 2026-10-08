"""Save the fictional opening capital and matching bank statement."""

import hashlib
import json
import argparse
from pathlib import Path

from simulation.daily_oms import ROOT, price_rows, write_once


def save(folder, filename, delivery_id, scenario, rows, opening_day):
    body = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode()
    manifest = {
        'delivery_id': delivery_id,
        'scenario_id': scenario,
        'business_date': opening_day,
        'is_simulated': True,
        'record_count': len(rows),
        'files': {filename: hashlib.sha256(body).hexdigest()},
    }
    write_once(folder / filename, body)
    write_once(folder / 'manifest.json',
               (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())


def generate(config_path=ROOT / 'config/two_year_pilot.json',
             output=ROOT / 'data/daily_opening'):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    sessions, _ = price_rows(ROOT / config['price_file'], set())
    first = config['start_date']
    if first not in sessions or sessions.index(first) == 0:
        raise ValueError('Opening needs a saved market date before the first trade')
    opening_day = sessions[sessions.index(first) - 1]
    amount = f"{int(config.get('opening_cash_usd_per_account', 5000000))}.00"
    admin = []
    bank = []
    for account in config['accounts']:
        key = scenario + '/' + opening_day + '/' + account
        stamp = hashlib.sha256(key.encode()).hexdigest()[:24]
        admin.append({
            'record_id': 'SIM-ADMIN-OPEN-' + stamp,
            'scenario_id': scenario, 'source_system': 'simulated_fund_administrator',
            'is_simulated': True, 'event_type': 'INVESTOR_SUBSCRIPTION',
            'event_date': opening_day, 'account_id': account,
            'currency': 'USD', 'amount': amount,
        })
        bank.append({
            'record_id': 'SIM-BANK-OPEN-' + stamp,
            'statement_id': 'SIM-BANK-OPEN-' + opening_day.replace('-', ''),
            'scenario_id': scenario, 'source_system': 'simulated_bank',
            'is_simulated': True, 'statement_date': opening_day,
            'account_id': account, 'currency': 'USD',
            'closing_balance': amount,
            'published_at': opening_day + 'T23:00:00+00:00',
        })
    folder = output / scenario / opening_day
    admin_id = f"sim-admin-open-{scenario}-{opening_day.replace('-', '')}"
    bank_id = f"sim-bank-open-{scenario}-{opening_day.replace('-', '')}"
    save(folder / 'fund_admin', 'events.jsonl', admin_id, scenario, admin, opening_day)
    save(folder / 'bank_cash', 'balances.jsonl', bank_id, scenario, bank, opening_day)
    load_config = {'inputs': [
        {'source_name': 'fund_admin', 'delivery_id': admin_id,
         'manifest': str((folder / 'fund_admin/manifest.json').relative_to(ROOT)).replace('\\', '/'),
         'expected_rows': len(admin)},
        {'source_name': 'bank_cash', 'delivery_id': bank_id,
         'manifest': str((folder / 'bank_cash/manifest.json').relative_to(ROOT)).replace('\\', '/'),
         'expected_rows': len(bank)},
    ]}
    write_once(folder / 'load_config.json',
               (json.dumps(load_config, indent=2, sort_keys=True) + '\n').encode())
    print(f'{opening_day}: {len(admin)} investor subscriptions and {len(bank)} bank balances')
    print(f'Opening deliveries: {folder}')
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_pilot.json')
    args = parser.parse_args()
    generate(args.config.resolve())
