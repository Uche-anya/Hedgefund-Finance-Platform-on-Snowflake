"""Prepare six more valuation days for the dividend lesson, without new trades."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.business_calendar import read_calendar
from simulation.multi_day import read_prices

BASE = 'sim-replay-406bbef8179cdbb0a3dd6df3'
CALENDAR = 'calendars/us_equities_2025_01_to_0207_v1.json'
CALENDAR_SHA256 = '897619d9437824bdc185be7d7c1bc9fb2c095eca771750dd1fcea20d2e8b28a2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / 'data/replays' / BASE
    manifest = json.loads((source / 'manifest.json').read_text())
    config = manifest['config']
    raw = (source / 'records.jsonl').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['files']['records.jsonl']:
        raise ValueError('Original replay has changed')
    if manifest['scenario_id'] != BASE or config['end_date'] != '2025-01-30':
        raise ValueError('Expected the saved January replay')
    calendar = read_calendar(ROOT / CALENDAR, CALENDAR_SHA256)['snapshot']
    old_calendar = read_calendar(ROOT / config['calendar'], config['calendar_sha256'])['snapshot']
    if calendar['days'][:len(old_calendar['days'])] != old_calendar['days']:
        raise ValueError('Extended calendar changed an existing day')
    open_days = [r['date'] for r in calendar['days'] if r['is_open']]
    added_days = [day for day in open_days if config['end_date'] < day <= '2025-02-07']
    if len(added_days) != 6 or added_days[-1] != '2025-02-07':
        raise ValueError('Expected six extra valuation days')
    price_file = ROOT / config['price_snapshot'] / 'prices.csv'
    if digest(price_file) != config['price_sha256']:
        raise ValueError('Saved prices changed')
    needed = {day for day in open_days if config['start_date'] <= day <= added_days[-1]}
    needed.add(open_days[open_days.index(config['start_date']) - 1])
    prices = read_prices(price_file, set(config['tickers']), needed)
    records = [json.loads(line) for line in raw.decode().splitlines()]
    sessions = [r['business_date'] for r in records if r['record_type'] == 'SESSION']
    expected_days = [d for d in open_days if config['start_date'] <= d <= config['end_date']]
    if sorted(sessions) != expected_days:
        raise ValueError('Original replay sessions do not match the calendar')
    additions = [dict(record_type='SESSION', scenario_id=BASE, business_date=day,
                      reference_date=open_days[open_days.index(day) - 1],
                      cutoff=day + 'T22:00:00+00:00', is_simulated=True,
                      source_system='saved_valuation_calendar') for day in added_days]
    # Preserve every original record, including its ID and existing settlement reports.
    extended = raw + (b'' if raw.endswith(b'\n') else b'\n')
    extended += ''.join(json.dumps(row) + '\n' for row in additions).encode()
    output_hash = hashlib.sha256(extended).hexdigest()
    folder = ROOT / 'data/replay_extensions' / output_hash[:32]
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / 'records.jsonl'
    if output.exists() and digest(output) != output_hash:
        raise ValueError('Existing extension changed; refusing to overwrite')
    output.write_bytes(extended)
    report = dict(status='PREPARED_NOT_LOADED', scenario_id=BASE,
                  delivery_id=output_hash[:32], base_replay=BASE,
                  base_manifest_sha256=digest(source / 'manifest.json'),
                  base_records_sha256=manifest['files']['records.jsonl'],
                  calendar=CALENDAR, calendar_sha256=CALENDAR_SHA256,
                  price_snapshot=config['price_snapshot'], price_sha256=config['price_sha256'],
                  added_days=added_days, added_price_rows=len(added_days) * len(config['tickers']),
                  checked_price_rows=len(prices), valuation_days=len(sessions) + len(added_days),
                  records=len(records) + len(additions), new_trades=0,
                  dividend_payment_confirmations=0,
                  files={'records.jsonl': output_hash},
                  note='Carry January positions forward. Payment handling must be built before loading this delivery.')
    (folder / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Added sessions: {", ".join(added_days)}')
    print(f'{len(config["tickers"])} stocks: all {report["added_price_rows"]} added closing prices present and valid.')
    print(f'{report["valuation_days"]} valuation days; original {len(records)} records preserved; no new trades.')
    print(f'Prepared extension: {folder}')
    print('Not loaded into Snowflake. Dividend payment handling is the next step.')


if __name__ == '__main__':
    main()
