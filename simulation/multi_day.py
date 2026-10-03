"""Build a reproducible January scenario from saved prices, without API calls."""

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import random
from uuid import NAMESPACE_URL, uuid5

from fund_pipeline.business_calendar import read_calendar
from simulation.simulator import validate_execution

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_settlement_day(day, config):
    following = date.fromisoformat(day) + timedelta(days=1)
    end = date.fromisoformat(config['settlement_calendar_end'])
    while following <= end:
        if following.weekday() < 5 and following.isoformat() not in config['settlement_closed_dates']:
            return following.isoformat()
        following += timedelta(days=1)
    raise ValueError('Settlement date is outside the configured calendar')


def read_prices(path, tickers, days):
    prices = {}
    with path.open(newline='', encoding='utf-8') as file:
        for row in csv.DictReader(file):
            key = (row['valuation_date'], row['universe_ticker'])
            if key[0] not in days or key[1] not in tickers:
                continue
            if key in prices:
                raise ValueError(f'Duplicate price: {key}')
            if (row['source_ticker'] != key[1] or row['currency'] != 'USD'
                    or row['price_basis'] != 'unadjusted'):
                raise ValueError(f'Unsupported price identity or basis: {key}')
            value = Decimal(row['close_price'])
            if not value.is_finite() or value <= 0:
                raise ValueError(f'Invalid price: {key}')
            prices[key] = value
    missing = [(day, ticker) for day in days for ticker in tickers if (day, ticker) not in prices]
    if missing:
        raise ValueError(f'Missing required price: {missing[0]}')
    return prices


def build_records(config, prices, open_days, scenario):
    days = [d for d in open_days if config['start_date'] <= d <= config['end_date']]
    if not days or config['start_date'] != days[0] or config['end_date'] != days[-1]:
        raise ValueError('Scenario endpoints must be open trading dates')
    if not set(config['no_trade_dates']).issubset(days):
        raise ValueError('No-trade dates must be inside the selected sessions')
    rng = random.Random(config['seed'])
    records = []
    for account in config['accounts']:
        records.append(dict(record_type='OPENING_CASH', scenario_id=scenario,
                            account_id=account, currency='USD', amount=config['opening_cash_usd'],
                            business_date=days[0], source_system='simulated_fund_setup', is_simulated=True))
    number = 0
    for day in days:
        previous = open_days[open_days.index(day) - 1]
        if previous >= day:
            raise ValueError('A prior trading date is required')
        records.append(dict(record_type='SESSION', scenario_id=scenario,
                            business_date=day, reference_date=previous,
                            cutoff=day + 'T22:00:00+00:00', is_simulated=True,
                            source_system='saved_valuation_calendar'))
        if day in config['no_trade_dates']:
            continue
        for index in range(config['trades_per_day']):
            number += 1
            ticker = rng.choice(config['tickers'])
            account = rng.choice(config['accounts'])
            side = rng.choice(['BUY', 'SELL'])
            quantity = str(rng.randint(1, 100))
            offset = rng.randint(-10, 10)
            reference = prices[(previous, ticker)]
            price = (reference * (1 + Decimal(offset) / 10000)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            identifier = uuid5(NAMESPACE_URL, f'{scenario}/{day}/{index}').hex
            executed = datetime.fromisoformat(day + 'T15:00:00+00:00') + timedelta(seconds=index * 60)
            due = next_settlement_day(day, config)
            event = dict(
                record_type='EXECUTION', schema_version=1,
                event_id='sim-event-' + identifier, execution_id='SIM-EXEC-' + identifier,
                order_id='SIM-ORDER-' + identifier, event_type='EXECUTION_REPORTED',
                execution_version=1, execution_status='ACTIVE', supersedes_event_id=None,
                correction_reason=None, source_system='simulated_oms', scenario_id=scenario,
                is_simulated=True, fund_id='NORTHBRIDGE', account_id=account,
                broker_id='SIM-BROKER-01', instrument_id=ticker + '.US', market_ticker=ticker,
                side=side, quantity=quantity, execution_price=str(price), currency='USD',
                business_date=day, settlement_due=due, executed_at=executed.isoformat(),
                occurred_at=executed.isoformat(), published_at=(executed + timedelta(milliseconds=60)).isoformat(),
                reference_price_date=previous, reference_close_price=str(reference),
                price_method='previous_close_with_fictional_offset', price_offset_bps=offset)
            validate_execution(event)
            records.append(event)
            # Controlled missing and delayed reports, not learned failure causes.
            if number % 97 == 0:
                continue
            settled = datetime.fromisoformat(due + 'T18:00:00+00:00') + timedelta(seconds=index)
            published = settled + timedelta(seconds=30)
            if number % 19 == 0:
                published = datetime.fromisoformat(next_settlement_day(due, config) + 'T09:00:00+00:00')
            amount = Decimal(quantity) * price * (-1 if side == 'BUY' else 1)
            records.append(dict(
                record_type='SETTLEMENT', scenario_id=scenario, is_simulated=True,
                event_id='sim-settlement-' + identifier, execution_id=event['execution_id'],
                account_id=account, instrument_id=event['instrument_id'], currency='USD',
                side=side, settled_quantity=quantity, cash_amount=str(amount),
                settlement_date=due, settled_at=settled.isoformat(), published_at=published.isoformat(),
                source_system='simulated_custodian'))
    return records


def generate(config_path, output=ROOT / 'data/replays'):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if not ('2025-01-02' <= config['start_date'] <= config['end_date'] <= '2025-01-30'):
        raise ValueError('This reviewed configuration supports January 2025 only')
    if not 1 <= config['trades_per_day'] <= 300:
        raise ValueError('Use 1 to 300 trades per trading day')
    for key in ('tickers', 'accounts'):
        if not config[key] or len(set(config[key])) != len(config[key]):
            raise ValueError(f'{key} must be nonempty and unique')
    opening = Decimal(config['opening_cash_usd'])
    if not opening.is_finite() or opening <= 0:
        raise ValueError('Opening cash must be positive')
    calendar_path = ROOT / config['calendar']
    calendar = read_calendar(calendar_path, config['calendar_sha256'])
    open_days = [d['date'] for d in calendar['snapshot']['days'] if d['is_open']]
    days = [d for d in open_days if config['start_date'] <= d <= config['end_date']]
    if not days or open_days.index(days[0]) == 0:
        raise ValueError('Need covered sessions and a prior reference date')
    price_file = ROOT / config['price_snapshot'] / 'prices.csv'
    if fingerprint(price_file) != config['price_sha256']:
        raise ValueError('Historical prices differ from the pinned snapshot')
    needed = set(days) | {open_days[open_days.index(day) - 1] for day in days}
    prices = read_prices(price_file, set(config['tickers']), needed)
    signature = fingerprint(config_path) + fingerprint(Path(__file__))
    scenario = 'sim-replay-' + hashlib.sha256(signature.encode()).hexdigest()[:24]
    folder = output / scenario
    if folder.exists():
        manifest = json.loads((folder / 'manifest.json').read_text())
        if fingerprint(folder / 'records.jsonl') != manifest['files']['records.jsonl']:
            raise ValueError('Saved replay changed; refusing to overwrite it')
        print(f'Reusing saved replay: {folder}')
        return folder
    records = build_records(config, prices, open_days, scenario)
    folder.mkdir(parents=True)
    file = folder / 'records.jsonl'
    with file.open('x', encoding='utf-8') as output_file:
        for record in records:
            output_file.write(json.dumps(record) + '\n')
    counts = dict(Counter(r['record_type'] for r in records))
    manifest = dict(scenario_id=scenario, delivery_id=scenario, is_simulated=True,
                    config=config, config_sha256=fingerprint(config_path),
                    script_sha256=fingerprint(Path(__file__)),
                    files={'records.jsonl': fingerprint(file)}, counts=counts,
                    assumptions='Zero opening holdings; USD equities; shorts allowed; no fees, corporate actions, borrow or margin accounting; not a strategy backtest')
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Saved {counts}: {folder}')
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/replay_january.json')
    args = parser.parse_args()
    generate(args.config.resolve())
