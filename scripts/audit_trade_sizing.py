"""Value saved simulated trades locally before sending a new scenario to Snowflake."""

import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.two_year_close import calculate
from scripts.close_daily_pilot import saved_delivery
from simulation.daily_oms import price_rows


def run(config_path):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    sessions, source_prices = price_rows(ROOT / config['price_file'], set(config['tickers']))
    first = sessions.index(config['start_date'])
    last = sessions.index(config['end_date'])
    if first == 0 or last + 1 >= len(sessions):
        raise ValueError('Need opening and final settlement market dates')
    days = sessions[first - 1:last + 2]
    prices = {day: {ticker: source_prices[(day, ticker)] for ticker in config['tickers']}
              for day in days}
    identities = {(day, ticker): ticker for day in days for ticker in config['tickers']}
    trades = defaultdict(list)
    settlements = defaultdict(list)
    oms_root = ROOT / 'data/daily_oms' / scenario
    due_root = ROOT / 'data/daily_settlements' / scenario
    for day in sessions[first:last + 1]:
        manifest, rows = saved_delivery(oms_root / day, 'oms.jsonl')
        if manifest['scenario_id'] != scenario or len(rows) != config['trades_per_day']:
            raise ValueError(f'Wrong OMS delivery: {day}')
        trades[day] = rows
    for day in sessions[first + 1:last + 2]:
        manifest, rows = saved_delivery(due_root / day, 'settlements.jsonl')
        if manifest['scenario_id'] != scenario:
            raise ValueError(f'Wrong settlement delivery: {day}')
        settlements[day] = rows

    opening = Decimal(config['opening_cash_usd_per_account'])
    daily, positions, _, _ = calculate(
        days, {account: opening for account in config['accounts']},
        prices, identities, trades, settlements, {}, {})
    gross = defaultdict(Decimal)
    for row in positions:
        gross[(row['business_date'], row['account_id'])] += abs(Decimal(row['market_value_usd']))
    trade_values = [Decimal(row['quantity']) * Decimal(row['execution_price'])
                    for rows in trades.values() for row in rows]
    exposure = [gross[(row['business_date'], row['account_id'])]
                / Decimal(row['illustrative_nav_usd']) for row in daily]
    cash = [Decimal(row['settled_cash_usd']) for row in daily]
    nav = [Decimal(row['illustrative_nav_usd']) for row in daily]
    report = {
        'scenario_id': scenario,
        'status': 'LOCAL_SIZING_CHECK_ONLY',
        'market_dates': len(days), 'trade_dates': last - first + 1,
        'trades': len(trade_values), 'settlements': sum(map(len, settlements.values())),
        'account_day_rows': len(daily),
        'trade_notional_usd': {'min': str(min(trade_values)),
                               'median': str(statistics.median(trade_values)),
                               'max': str(max(trade_values))},
        'gross_exposure_pct_of_nav': {
            'median': str(round(statistics.median(exposure) * 100, 2)),
            'max': str(round(max(exposure) * 100, 2)),
        },
        'minimum_settled_cash_usd': str(min(cash)),
        'minimum_nav_before_dividends_usd': str(min(nav)),
        'passes_sizing_guardrails': min(cash) > 0 and min(nav) > 0 and max(exposure) <= Decimal('1.5'),
        'limitations': 'Uses ticker-level prices for sizing only; omits corporate actions, borrow fees, dividends and daily bank evidence.',
    }
    out = ROOT / 'data' / f'{scenario}-sizing-audit.json'
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_replay_v2.json')
    args = parser.parse_args()
    result = run(args.config.resolve())
    raise SystemExit(0 if result['passes_sizing_guardrails'] else 1)
