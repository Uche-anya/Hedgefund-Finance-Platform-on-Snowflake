"""Write dated fictional custodian confirmations for saved OMS fills."""

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from simulation.daily_oms import ROOT, write_once
from simulation.simulator import validate_execution


def read_trades(folder, selected_day=None):
    trades = []
    folders = [folder / selected_day] if selected_day else sorted(folder.iterdir())
    for day_folder in folders:
        if not day_folder.is_dir():
            continue
        manifest = json.loads((day_folder / 'manifest.json').read_text(encoding='utf-8'))
        raw = (day_folder / 'oms.jsonl').read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['files']['oms.jsonl']:
            raise ValueError(f'OMS file changed: {day_folder}')
        events = [json.loads(line) for line in raw.splitlines()]
        if len(events) != manifest['record_count']:
            raise ValueError(f'OMS count changed: {day_folder}')
        for event in events:
            validate_execution(event)
            if event['scenario_id'] != manifest['scenario_id'] or event['business_date'] != manifest['business_date']:
                raise ValueError(f'OMS event differs from manifest: {day_folder}')
        trades.extend(events)
    if len({row['execution_id'] for row in trades}) != len(trades):
        raise ValueError('Duplicate execution ID across OMS deliveries')
    return trades


def confirmation(trade, index):
    amount = Decimal(trade['quantity']) * Decimal(trade['execution_price'])
    if trade['side'] == 'BUY':
        amount = -amount
    due = trade['settlement_due']
    settled = datetime.fromisoformat(due + 'T18:00:00+00:00') + timedelta(seconds=index)
    stamp = uuid5(NAMESPACE_URL, trade['scenario_id'] + '/settlement/' + trade['execution_id']).hex
    return {
        'schema_version': 1,
        'event_id': 'sim-settlement-' + stamp,
        'event_type': 'SETTLEMENT_CONFIRMED',
        'source_system': 'simulated_custodian',
        'scenario_id': trade['scenario_id'],
        'is_simulated': True,
        'settlement_id': 'SIM-SETTLEMENT-' + stamp,
        'execution_id': trade['execution_id'],
        'fund_id': trade['fund_id'],
        'account_id': trade['account_id'],
        'broker_id': trade['broker_id'],
        'instrument_id': trade['instrument_id'],
        'side': trade['side'],
        'settled_quantity': trade['quantity'],
        'currency': trade['currency'],
        'cash_amount': str(amount),
        'settlement_date': due,
        'settled_at': settled.isoformat(),
        'published_at': (settled + timedelta(seconds=30)).isoformat(),
        'settlement_status': 'SETTLED',
    }


def generate(config_path=ROOT / 'config/two_year_pilot.json',
             oms_root=ROOT / 'data/daily_oms', output=ROOT / 'data/daily_settlements',
             oms_day=None):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    trades = read_trades(oms_root / scenario, selected_day=oms_day)
    by_day = {}
    for trade in trades:
        by_day.setdefault(trade['settlement_due'], []).append(trade)
    for day, due_trades in sorted(by_day.items()):
        events = [confirmation(trade, index) for index, trade in
                  enumerate(sorted(due_trades, key=lambda row: row['execution_id']))]
        folder = output / scenario / day
        payload = ''.join(json.dumps(event, sort_keys=True) + '\n' for event in events).encode()
        delivery_id = f"settlement-{scenario}-{day.replace('-', '')}"
        manifest = {
            'delivery_id': delivery_id,
            'scenario_id': scenario,
            'settlement_date': day,
            'source_system': 'simulated_custodian',
            'is_simulated': True,
            'record_count': len(events),
            'files': {'settlements.jsonl': hashlib.sha256(payload).hexdigest()},
            'source_execution_ids': sorted(trade['execution_id'] for trade in due_trades),
            'source_note': 'Fictional custodian feed derived from saved OMS fills; not independent evidence',
        }
        write_once(folder / 'settlements.jsonl', payload)
        write_once(folder / 'manifest.json',
                   (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
        print(f'{day}: {len(events)} settlements; {folder}')
    return sorted(by_day)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_pilot.json')
    parser.add_argument('--oms-day', help='Confirm trades from one saved OMS delivery')
    args = parser.parse_args()
    generate(args.config.resolve(), oms_day=args.oms_day)
