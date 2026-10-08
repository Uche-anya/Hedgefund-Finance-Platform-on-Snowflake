"""Check the saved two-year inputs before loading or valuing the whole run."""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.close_daily_pilot import check_settlements, saved_delivery
from simulation.daily_oms import price_rows
from simulation.daily_settlements import read_trades


def audit(config_path=ROOT / 'config/two_year_replay.json'):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    price_file = ROOT / config['price_file']
    if hashlib.sha256(price_file.read_bytes()).hexdigest() != config['price_sha256']:
        raise ValueError('Saved price snapshot changed')
    sessions, prices = price_rows(price_file, set(config['tickers']))
    if len(sessions) != 500 or len(prices) != 500 * len(config['tickers']):
        raise ValueError('The 20-stock price matrix is incomplete')
    trade_days = sessions[1:-1]
    if trade_days[0] != config['start_date'] or trade_days[-1] != config['end_date']:
        raise ValueError('Trade dates differ from the full scenario config')

    oms_folder = ROOT / 'data/daily_oms' / scenario
    trades = read_trades(oms_folder)
    by_day = Counter(row['business_date'] for row in trades)
    if set(by_day) != set(trade_days) or set(by_day.values()) != {config['trades_per_day']}:
        raise ValueError('Missing or uneven OMS trade deliveries')
    if len({row['event_id'] for row in trades}) != len(trades):
        raise ValueError('Duplicate OMS event ID')
    for day in trade_days:
        manifest, saved = saved_delivery(oms_folder / day, 'oms.jsonl')
        if manifest['delivery_id'] != f"oms-{scenario}-{day.replace('-', '')}":
            raise ValueError(f'Unexpected OMS delivery ID: {day}')
        if {row['event_id'] for row in saved} != {
                row['event_id'] for row in trades if row['business_date'] == day}:
            raise ValueError(f'OMS file differs from scenario: {day}')

    settlement_days = sessions[2:]
    settlements = 0
    all_trades = {row['execution_id']: row for row in trades}
    for day in settlement_days:
        folder = ROOT / 'data/daily_settlements' / scenario / day
        manifest, rows = saved_delivery(folder, 'settlements.jsonl')
        if manifest['delivery_id'] != f"settlement-{scenario}-{day.replace('-', '')}":
            raise ValueError(f'Unexpected custodian delivery ID: {day}')
        check_settlements(day, rows, all_trades)
        settlements += len(rows)
    if settlements != len(trades):
        raise ValueError('Not every trade has a settlement confirmation')

    action_file = (ROOT / 'data/corporate_action_loads'
                   / '890be0cfdcf2151ebb4aab47f0d53cd9/actions.jsonl')
    with (ROOT / 'dbt/seeds/approved_corporate_actions.csv').open(newline='') as handle:
        approved = {row['event_id'] for row in csv.DictReader(handle)}
    actions = Counter()
    approved_count = 0
    with action_file.open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            event = record['event']
            day = event.get('ex_dividend_date', event.get('execution_date'))
            if event.get('ticker') in config['tickers'] and day and sessions[0] <= day <= sessions[-1]:
                actions[record['action_type']] += 1
                approved_count += event['id'] in approved

    report = {
        'scenario_id': scenario,
        'market_dates': len(sessions),
        'first_market_date': sessions[0],
        'last_market_date': sessions[-1],
        'trade_dates': len(trade_days),
        'oms_events': len(trades),
        'settlement_dates': len(settlement_days),
        'settlement_events': settlements,
        'accounts': len(config['accounts']),
        'possible_account_day_closes': len(sessions) * len(config['accounts']),
        'raw_corporate_action_candidates': dict(actions),
        'approved_action_ids_in_raw_candidates': approved_count,
        'accounting_ready': False,
        'note': 'Provider action candidates need identity and entitlement review; XOM successor holdings need an explicit transfer.',
    }
    path = ROOT / 'data' / f'{scenario}-source-audit.json'
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_replay.json')
    args = parser.parse_args()
    audit(args.config.resolve())
