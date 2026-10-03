"""Produce a fictional prime-broker position statement for reconciliation."""

from collections import defaultdict
import csv
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closing_positions(records, statement_date):
    positions = defaultdict(Decimal)
    for row in records:
        if row.get('record_type') != 'EXECUTION' or row['business_date'] > statement_date:
            continue
        quantity = Decimal(row['quantity'])
        if row['side'] == 'SELL':
            quantity = -quantity
        positions[(row['account_id'], row['market_ticker'])] += quantity
    return dict(positions)


def apply_exceptions(positions, config):
    result = dict(positions)
    labels = []
    for item in config['quantity_adjustments']:
        key = (item['account_id'], item['ticker'])
        if key not in result:
            raise ValueError(f'Quantity-adjustment target is absent: {key}')
        before = result[key]
        result[key] += Decimal(item['change'])
        labels.append({**item, 'expected_quantity': str(before),
                       'reported_quantity': str(result[key])})
    for item in config['omitted_positions']:
        key = (item['account_id'], item['ticker'])
        if key not in result:
            raise ValueError(f'Omitted-position target is absent: {key}')
        expected = result.pop(key)
        labels.append({**item, 'expected_quantity': str(expected),
                       'reported_quantity': None})
    for item in config['extra_positions']:
        key = (item['account_id'], item['ticker'])
        if key in result:
            raise ValueError(f'Extra-position target already exists: {key}')
        result[key] = Decimal(item['quantity'])
        labels.append({**item, 'expected_quantity': None,
                       'reported_quantity': item['quantity']})
    return result, labels


def read_instruments(path, statement_date):
    day = date.fromisoformat(statement_date)
    instruments = {}
    with path.open(newline='', encoding='utf-8') as file:
        for row in csv.DictReader(file):
            if date.fromisoformat(row['valid_from']) <= day <= date.fromisoformat(row['valid_to']):
                if row['ticker'] in instruments:
                    raise ValueError(f"Overlapping instrument mapping: {row['ticker']}")
                instruments[row['ticker']] = row
    return instruments


def statement_rows(positions, instruments, config, scenario_id):
    rows = []
    for account, ticker in sorted(positions):
        if ticker not in instruments:
            raise ValueError(f'No instrument mapping for {ticker}')
        if account not in config['published_at_by_account']:
            raise ValueError(f'No publication time for {account}')
        instrument = instruments[ticker]
        statement_key = f"{scenario_id}/{config['statement_date']}/{account}"
        statement_id = 'SIM-STMT-' + hashlib.sha256(statement_key.encode()).hexdigest()[:24]
        record_key = statement_key + '/' + instrument['share_class_figi']
        rows.append({
            'schema_version': 1,
            'record_type': 'BROKER_POSITION',
            'record_id': 'SIM-BROKER-POS-' + hashlib.sha256(record_key.encode()).hexdigest()[:24],
            'statement_id': statement_id,
            'statement_date': config['statement_date'],
            'position_basis': config['position_basis'],
            'fund_id': 'NORTHBRIDGE',
            'broker_id': 'SIM-PRIME-BROKER-01',
            'account_id': account,
            'broker_instrument_id': instrument['share_class_figi'],
            'ticker': ticker,
            'currency': instrument['currency'],
            'quantity': str(positions[(account, ticker)]),
            'published_at': config['published_at_by_account'][account],
            'source_system': 'simulated_prime_broker',
            'is_simulated': True,
        })
    return rows


def produce(config_path=ROOT / 'config/broker_statement_january.json',
            output=ROOT / 'data/broker_statements'):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    replay = ROOT / config['source_replay']
    manifest_path = replay / 'manifest.json'
    records_path = replay / 'records.jsonl'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if fingerprint(records_path) != manifest['files']['records.jsonl']:
        raise ValueError('Replay records differ from their saved manifest')
    if not (manifest['config']['start_date'] <= config['statement_date']
            <= manifest['config']['end_date']):
        raise ValueError('Statement date is outside the replay')

    records = [json.loads(line) for line in records_path.read_text(encoding='utf-8').splitlines()]
    positions = closing_positions(records, config['statement_date'])
    positions, labels = apply_exceptions(positions, config)
    instruments = read_instruments(ROOT / 'dbt/seeds/dim_instrument.csv', config['statement_date'])
    rows = statement_rows(positions, instruments, config, manifest['scenario_id'])

    signature = fingerprint(records_path) + fingerprint(config_path) + fingerprint(Path(__file__))
    delivery_id = 'sim-broker-' + hashlib.sha256(signature.encode()).hexdigest()[:24]
    folder = output / delivery_id
    data_file = folder / 'positions.jsonl'
    if folder.exists():
        saved = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        if fingerprint(data_file) != saved['files']['positions.jsonl']:
            raise ValueError('Saved broker delivery changed; refusing to overwrite it')
        print(f'Reusing saved broker statement: {folder}')
        return folder

    folder.mkdir(parents=True)
    with data_file.open('x', encoding='utf-8') as file:
        for row in rows:
            file.write(json.dumps(row) + '\n')
    output_manifest = {
        'delivery_id': delivery_id,
        'scenario_id': manifest['scenario_id'],
        'statement_date': config['statement_date'],
        'position_basis': config['position_basis'],
        'expected_by': config['expected_by'],
        'is_simulated': True,
        'record_count': len(rows),
        'account_count': len({row['account_id'] for row in rows}),
        'source_replay': config['source_replay'],
        'source_records_sha256': fingerprint(records_path),
        'config_sha256': fingerprint(config_path),
        'script_sha256': fingerprint(Path(__file__)),
        'files': {'positions.jsonl': fingerprint(data_file)},
        'synthetic_truth': labels,
        'source_note': 'Fictional broker feed calculated separately from dbt; not independent real-world evidence.',
    }
    (folder / 'manifest.json').write_text(json.dumps(output_manifest, indent=2) + '\n', encoding='utf-8')
    late = sorted(account for account, timestamp in config['published_at_by_account'].items()
                  if timestamp > config['expected_by'])
    print(f"Saved {len(rows)} broker positions for {config['statement_date']}.")
    print(f"Injected {len(labels)} labelled exceptions; late accounts: {', '.join(late)}")
    print(f'Broker delivery: {folder}')
    return folder


if __name__ == '__main__':
    produce()
