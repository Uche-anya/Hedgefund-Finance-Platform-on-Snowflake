"""Write dated OMS deliveries from saved market data. No Snowflake call here."""

import argparse
import csv
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import random
from uuid import NAMESPACE_URL, uuid5

from simulation.simulator import validate_execution

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def price_rows(path, tickers):
    prices = {}
    sessions = set()
    with path.open(newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            day = row['valuation_date']
            ticker = row['universe_ticker']
            if ticker == 'AAPL':
                sessions.add(day)
            if ticker not in tickers:
                continue
            key = (day, ticker)
            if key in prices:
                raise ValueError(f'Duplicate price for {ticker} on {day}')
            if (row['source_ticker'] != ticker or row['currency'] != 'USD'
                    or row['price_basis'] != 'unadjusted'):
                raise ValueError(f'Unsupported price row: {ticker} on {day}')
            close = Decimal(row['close_price'])
            if not close.is_finite() or close <= 0:
                raise ValueError(f'Invalid close: {ticker} on {day}')
            prices[key] = close
    return sorted(sessions), prices


def make_day(config, day, previous, following, prices):
    seed_text = f"{config['scenario_id']}/{day}/{config['seed']}"
    rng = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest(), 16))
    events = []
    for index in range(config['trades_per_day']):
        ticker = rng.choice(config['tickers'])
        account = config['accounts'][index % len(config['accounts'])]
        side = 'BUY' if index % 4 < 2 else 'SELL'
        method = config.get('sizing_method', 'shares_1_to_15')
        if method == 'shares_1_to_15':
            quantity = str(rng.randint(1, 15))
        offset_bps = rng.randint(-10, 10)
        reference = prices[(previous, ticker)]
        trade_price = (reference * (1 + Decimal(offset_bps) / 10000)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        if method == 'dollar_budget':
            low = int(config['min_trade_usd'])
            high = int(config['max_trade_usd'])
            budget = rng.randint(low, high)
            quantity = str(max(1, int(Decimal(budget) / reference)))
        stamp = uuid5(NAMESPACE_URL, f"{config['scenario_id']}/{day}/{index}").hex
        executed = datetime.fromisoformat(day + 'T15:00:00+00:00') + timedelta(minutes=index)
        event = {
            'schema_version': 1,
            'event_id': 'sim-event-' + stamp,
            'event_type': 'EXECUTION_REPORTED',
            'source_system': 'simulated_oms',
            'scenario_id': config['scenario_id'],
            'is_simulated': True,
            'occurred_at': executed.isoformat(),
            'published_at': (executed + timedelta(milliseconds=60)).isoformat(),
            'executed_at': executed.isoformat(),
            'business_date': day,
            'execution_id': 'SIM-EXEC-' + stamp,
            'execution_version': 1,
            'supersedes_event_id': None,
            'correction_reason': None,
            'order_id': 'SIM-ORDER-' + stamp,
            'fund_id': 'NORTHBRIDGE',
            'account_id': account,
            'broker_id': 'SIM-BROKER-01',
            'instrument_id': ticker + '.US',
            'market_ticker': ticker,
            'side': side,
            'quantity': quantity,
            'execution_price': str(trade_price),
            'currency': 'USD',
            'settlement_due': following,
            'execution_status': 'ACTIVE',
            'reference_price_date': previous,
            'reference_close_price': str(reference),
            'price_method': 'previous_close_with_fictional_offset',
            'price_offset_bps': offset_bps,
        }
        validate_execution(event)
        events.append(event)
    return events


def write_once(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f'Saved delivery changed: {path}')
    else:
        path.write_bytes(content)


def generate(config_path, output=ROOT / 'data/daily_oms', selected_day=None):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config['start_date'] > config['end_date']:
        raise ValueError('Start date follows end date')
    if not 1 <= config['trades_per_day'] <= 50:
        raise ValueError('Expected 1 to 50 trades per day')
    if (not config['tickers'] or len(config['tickers']) != len(set(config['tickers']))
            or not config['accounts'] or len(config['accounts']) != len(set(config['accounts']))):
        raise ValueError('Tickers and accounts must be nonempty and unique')
    method = config.get('sizing_method', 'shares_1_to_15')
    if method not in ('shares_1_to_15', 'dollar_budget'):
        raise ValueError(f'Unknown trade sizing method: {method}')
    if method == 'dollar_budget':
        low, high = config['min_trade_usd'], config['max_trade_usd']
        if not (isinstance(low, int) and isinstance(high, int) and 0 < low <= high):
            raise ValueError('Trade dollar limits must be positive whole dollars')
    price_path = ROOT / config['price_file']
    if sha256(price_path) != config['price_sha256']:
        raise ValueError('Price snapshot changed')
    sessions, prices = price_rows(price_path, set(config['tickers']))
    days = [day for day in sessions if config['start_date'] <= day <= config['end_date']]
    if not days or days[0] != config['start_date'] or days[-1] != config['end_date']:
        raise ValueError('Scenario endpoints must be saved market dates')
    if selected_day is not None:
        if selected_day not in days:
            raise ValueError(f'{selected_day} is not a selected market date')
        days = [selected_day]
    for day in days:
        place = sessions.index(day)
        if place == 0 or place == len(sessions) - 1:
            raise ValueError('Each trade date needs a previous price and next settlement date')
        previous, following = sessions[place - 1], sessions[place + 1]
        missing = [ticker for ticker in config['tickers'] if (previous, ticker) not in prices]
        if missing:
            raise ValueError(f'Missing prior close on {previous}: {missing}')
        events = make_day(config, day, previous, following, prices)
        delivery_id = f"oms-{config['scenario_id']}-{day.replace('-', '')}"
        folder = output / config['scenario_id'] / day
        payload = ''.join(json.dumps(event, sort_keys=True) + '\n' for event in events).encode()
        file = folder / 'oms.jsonl'
        manifest = {
            'delivery_id': delivery_id,
            'scenario_id': config['scenario_id'],
            'business_date': day,
            'reference_price_date': previous,
            'settlement_due': following,
            'source_system': 'simulated_oms',
            'is_simulated': True,
            'record_count': len(events),
            'price_snapshot_sha256': config['price_sha256'],
            'files': {'oms.jsonl': hashlib.sha256(payload).hexdigest()},
        }
        write_once(file, payload)
        write_once(folder / 'manifest.json',
                   (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
        print(f'{day}: {len(events)} fills, due {following}; {folder}')
    return days


def generate_next_day(config_path, day, settlement_due,
                      output=ROOT / 'data/daily_oms', previous_prices_manifest=None):
    """Append one new trade date after the saved price snapshot."""
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if day <= config['end_date'] or settlement_due <= day:
        raise ValueError('New trade date and settlement due must follow the saved run')
    if previous_prices_manifest:
        manifest_path = Path(previous_prices_manifest).resolve()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        price_path = manifest_path.parent / 'prices.csv'
        price_hash = sha256(price_path)
        if price_hash != manifest['files']['prices.csv']:
            raise ValueError('Previous daily price delivery changed')
        previous = manifest['valuation_date']
        sessions, prices = price_rows(price_path, set(config['tickers']))
        if sessions != [previous]:
            raise ValueError('Previous daily price file has the wrong date')
    else:
        price_path = ROOT / config['price_file']
        price_hash = config['price_sha256']
        if sha256(price_path) != price_hash:
            raise ValueError('Price snapshot changed')
        sessions, prices = price_rows(price_path, set(config['tickers']))
        previous = sessions[-1]
    if day <= previous:
        raise ValueError('New trade date must follow the last saved market close')
    missing = [ticker for ticker in config['tickers'] if (previous, ticker) not in prices]
    if missing:
        raise ValueError(f'Missing previous close on {previous}: {missing}')

    events = make_day(config, day, previous, settlement_due, prices)
    delivery_id = f"oms-{config['scenario_id']}-{day.replace('-', '')}"
    folder = output / config['scenario_id'] / day
    payload = ''.join(json.dumps(event, sort_keys=True) + '\n' for event in events).encode()
    manifest = {
        'delivery_id': delivery_id,
        'scenario_id': config['scenario_id'],
        'business_date': day,
        'reference_price_date': previous,
        'settlement_due': settlement_due,
        'source_system': 'simulated_oms',
        'is_simulated': True,
        'record_count': len(events),
        'price_snapshot_sha256': price_hash,
        'files': {'oms.jsonl': hashlib.sha256(payload).hexdigest()},
    }
    write_once(folder / 'oms.jsonl', payload)
    write_once(folder / 'manifest.json',
               (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    print(f'{day}: {len(events)} fills, due {settlement_due}; {folder}')
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_pilot.json')
    parser.add_argument('--day', help='Write only one business-day delivery')
    parser.add_argument('--next-day', help='Append a new day after the saved price snapshot')
    parser.add_argument('--settlement-due', help='Explicit due date for --next-day')
    parser.add_argument('--previous-prices-manifest', type=Path,
                        help='Checked prior-day price delivery for --next-day')
    args = parser.parse_args()
    if args.next_day:
        if args.day or not args.settlement_due:
            parser.error('--next-day needs --settlement-due and cannot use --day')
        generate_next_day(args.config.resolve(), args.next_day, args.settlement_due,
                          previous_prices_manifest=args.previous_prices_manifest)
    else:
        if args.settlement_due:
            parser.error('--settlement-due needs --next-day')
        generate(args.config.resolve(), selected_day=args.day)
