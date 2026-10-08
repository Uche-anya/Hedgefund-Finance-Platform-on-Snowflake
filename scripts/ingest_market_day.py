"""Fetch one market close and land its price, OMS and due settlement files."""

import argparse
from datetime import date
from getpass import getpass
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_extraction.historical_prices import download
from data_extraction.prepare_daily_prices import prepare
from simulation.daily_oms import generate_next_day
from simulation.daily_settlements import generate as generate_settlements
from scripts.load_daily_prices import load as load_prices
from scripts.load_oms_snowpipe import load as load_oms
from scripts.load_settlement_snowpipe import load as load_settlements


CONFIG = ROOT / 'config/two_year_replay_v2.json'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def find_download(day, tickers):
    """Reuse one completed download, or resume one partial download."""
    base = ROOT / 'data/historical_prices'
    complete, partial = [], []
    for folder in base.iterdir():
        request = folder / 'request.json'
        if not request.is_file():
            continue
        saved = read_json(request)
        if saved.get('start') != day or saved.get('end') != day:
            continue
        if saved.get('symbols') != tickers:
            continue
        (complete if (folder / 'manifest.json').is_file() else partial).append(folder)
    if len(complete) > 1 or (not complete and len(partial) > 1):
        raise ValueError(f'Multiple price downloads for {day}; inspect them before retrying')
    if complete:
        return complete[0], False
    if partial:
        return partial[0], True
    return None, False


def previous_prices(day):
    """The last checked daily price package, if one exists."""
    base = ROOT / 'data/daily_prices'
    choices = []
    for manifest in base.glob('*/manifest.json'):
        saved = read_json(manifest)
        # A DEV correction is a separate close candidate, not the market feed
        # used to price the simulator's next trades.
        if saved.get('source_snapshot') and saved.get('valuation_date', '') < day:
            choices.append((saved['valuation_date'], manifest))
    if not choices:
        return None  # The first new day uses the fixed historical baseline.
    last_day = max(item[0] for item in choices)
    latest = [path for saved_day, path in choices if saved_day == last_day]
    if len(latest) != 1:
        raise ValueError(f'Multiple prior price packages for {last_day}')
    return latest[0]


def due_oms_days(scenario, day):
    base = ROOT / 'data/daily_oms' / scenario
    days = []
    for manifest in base.glob('*/manifest.json'):
        if read_json(manifest).get('settlement_due') == day:
            days.append(manifest.parent.name)
    return sorted(days)


def run(day, next_session, config_path=CONFIG, load=True):
    if date.fromisoformat(next_session) <= date.fromisoformat(day):
        raise ValueError('Next market session must follow the close date')
    config = read_json(config_path)
    snapshot, resume = find_download(day, config['tickers'])
    if snapshot is None or resume:
        key = os.environ.get('MASSIVE_API_KEY')
        if not key and sys.stdin.isatty():
            key = getpass('Massive API key (hidden): ')
        if not key:
            raise RuntimeError('Set MASSIVE_API_KEY for unattended runs; no complete price download exists')
        snapshot = download(ROOT / 'data/historical_prices', key,
                            symbols=config['tickers'], resume=snapshot if resume else None,
                            start=day, end=day)

    price_folder = prepare(snapshot, config_path)
    prior = previous_prices(day)
    if prior and read_json(prior)['valuation_date'] >= day:
        raise ValueError('Prior price package must precede this close')
    oms_folder = generate_next_day(config_path, day, next_session,
                                   previous_prices_manifest=prior)

    # Settlements due today come from earlier OMS deliveries, not today's fills.
    settlement_folders = []
    for oms_day in due_oms_days(config['scenario_id'], day):
        generate_settlements(config_path, oms_day=oms_day)
        settlement_folders.append(ROOT / 'data/daily_settlements' /
                                  config['scenario_id'] / day)

    if load:
        load_prices(price_folder)
        oms = read_json(oms_folder / 'manifest.json')
        if load_oms(oms_folder / 'oms.jsonl', oms['delivery_id']):
            raise RuntimeError('OMS Snowpipe delivery failed')
        for folder in dict.fromkeys(settlement_folders):
            settlement = read_json(folder / 'manifest.json')
            if load_settlements(folder / 'settlements.jsonl', settlement['delivery_id']):
                raise RuntimeError('Settlement Snowpipe delivery failed')
    print(f'{day}: price, OMS and due-settlement packages ready; loaded={load}')
    print('Close request and dbt Task still require a separate verified handoff.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--day', required=True, help='Market date, YYYY-MM-DD')
    parser.add_argument('--next-session', required=True, help='Next US equity session, YYYY-MM-DD')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--no-load', action='store_true', help='Prepare files without Snowflake calls')
    args = parser.parse_args()
    run(args.day, args.next_session, args.config.resolve(), not args.no_load)


if __name__ == '__main__':
    main()
