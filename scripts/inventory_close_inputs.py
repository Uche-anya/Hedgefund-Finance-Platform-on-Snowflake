"""List the saved inputs for one two-year close. Does not write to Snowflake."""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'fb25ddd9838840488e4c8b971ff7e0ae'
ACTION_LOAD = '890be0cfdcf2151ebb4aab47f0d53cd9'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def jsonl_count(path):
    with path.open(encoding='utf-8') as handle:
        return sum(bool(line.strip()) for line in handle)


def package(root, manifest_path, file_name, source_name, row_field='record_count'):
    manifest_path = (root / manifest_path).resolve()
    if root.resolve() not in manifest_path.parents:
        raise ValueError(f'Manifest outside repository: {manifest_path}')
    manifest = read_json(manifest_path)
    file_path = manifest_path.parent / file_name
    actual_hash = sha256(file_path)
    if manifest['files'][file_name] != actual_hash:
        raise ValueError(f'File changed since packaging: {file_path}')
    rows = jsonl_count(file_path) if file_path.suffix == '.jsonl' else None
    if rows is not None and rows != manifest[row_field]:
        raise ValueError(f'Row count changed since packaging: {file_path}')
    return {
        'source_name': source_name,
        'delivery_id': manifest['delivery_id'],
        'file_sha256': actual_hash,
        'receipt_sha256': (sha256(manifest_path)
                           if source_name in ('fund_admin', 'dividend_payments')
                           else actual_hash),
        'expected_rows': manifest[row_field],
        'manifest': manifest_path.relative_to(root).as_posix(),
    }


def dated_packages(root, folder, scenario, last_day, file_name, source_name):
    base = root / 'data' / folder / scenario
    chosen = []
    for day_folder in sorted(base.iterdir()):
        if not day_folder.is_dir() or date.fromisoformat(day_folder.name) > last_day:
            continue
        item = package(root, day_folder / 'manifest.json', file_name, source_name)
        manifest = read_json(day_folder / 'manifest.json')
        if manifest['scenario_id'] != scenario:
            raise ValueError(f'Wrong scenario: {day_folder}')
        chosen.append(item)
    return chosen


def daily_price_packages(root, last_day, current_manifest):
    """Keep every earlier provider close and the explicitly chosen current close."""
    current_path = root / current_manifest
    current = read_json(current_path)
    if current['valuation_date'] != last_day.isoformat():
        raise ValueError('Current price package has the wrong date')
    chosen = [package(root, current_manifest, 'prices.csv', 'daily_prices')]
    prior_dates = set()
    for manifest_path in sorted((root / 'data/daily_prices').glob('*/manifest.json')):
        saved = read_json(manifest_path)
        day = saved.get('valuation_date', '')
        if day >= last_day.isoformat() or not saved.get('source_snapshot'):
            continue
        if day in prior_dates:
            raise ValueError(f'Multiple provider price packages for {day}')
        prior_dates.add(day)
        chosen.append(package(root, manifest_path.relative_to(root),
                              'prices.csv', 'daily_prices'))
    return chosen


def code_hash(root, paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode() + b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def selection_id(selection):
    keys = ('scenario_id', 'business_date', 'cutoff_at',
            'model_sha256', 'seed_sha256', 'inputs')
    packed = json.dumps({key: selection[key] for key in keys},
                        sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(packed).hexdigest()[:24]


def inventory(root, request):
    scenario = request['scenario_id']
    last_day = date.fromisoformat(request['business_date'])
    cutoff = datetime.fromisoformat(request['cutoff_at'].replace('Z', '+00:00'))
    if cutoff.utcoffset() != timezone.utc.utcoffset(cutoff):
        raise ValueError('Close cutoff must be UTC')

    inputs = []
    inputs += dated_packages(root, 'daily_oms', scenario, last_day,
                             'oms.jsonl', 'oms_events')
    inputs += dated_packages(root, 'daily_settlements', scenario, last_day,
                             'settlements.jsonl', 'settlement_events')
    inputs.append(package(root, 'data/daily_opening/' + scenario +
                          '/2024-09-23/fund_admin/manifest.json',
                          'events.jsonl', 'fund_admin'))
    inputs.append(package(root, 'data/dividend_payment_pilot/' + scenario +
                          '/2025-02-07/custodian/manifest.json',
                          'payments.jsonl', 'dividend_payments'))
    inputs += daily_price_packages(root, last_day, request['price_manifest'])

    baseline_path = root / 'data/assembled_prices' / BASELINE
    baseline = read_json(baseline_path / 'manifest.json')
    baseline_hash = sha256(baseline_path / 'prices.csv')
    if baseline['output_sha256']['prices.csv'] != baseline_hash:
        raise ValueError('Historical price baseline changed')
    inputs.append({
        'source_name': 'historical_prices', 'delivery_id': BASELINE,
        'file_sha256': baseline_hash, 'receipt_sha256': None,
        'expected_rows': baseline['row_count'],
        'manifest': (baseline_path / 'manifest.json').relative_to(root).as_posix(),
    })

    actions_path = root / 'data/corporate_action_loads' / ACTION_LOAD
    actions = read_json(actions_path / 'manifest.json')
    for file_name, source_name, count_field in (
            ('actions.jsonl', 'corporate_actions', 'actions'),
            ('reviews.jsonl', 'corporate_action_reviews', 'reviews')):
        file_path = actions_path / file_name
        digest = sha256(file_path)
        if digest != actions['files'][file_name] or jsonl_count(file_path) != actions[count_field]:
            raise ValueError(f'Corporate-action load changed: {file_path}')
        inputs.append({
            'source_name': source_name, 'delivery_id': ACTION_LOAD,
            'file_sha256': digest, 'receipt_sha256': None,
            'expected_rows': actions[count_field],
            'manifest': (actions_path / 'manifest.json').relative_to(root).as_posix(),
        })

    keys = [(item['source_name'], item['delivery_id']) for item in inputs]
    if len(keys) != len(set(keys)):
        raise ValueError('Same source delivery selected twice')
    inputs.sort(key=lambda item: (item['source_name'], item['delivery_id']))
    model_paths = [root / 'dbt/dbt_project.yml',
                   *root.glob('dbt/models/**/*.sql'),
                   *root.glob('dbt/models/**/*.yml'),
                   *root.glob('dbt/macros/**/*.sql'),
                   *root.glob('dbt/tests/**/*.sql')]
    seed_paths = list(root.glob('dbt/seeds/*.csv'))
    selection = {
        'scenario_id': scenario,
        'business_date': last_day.isoformat(),
        'cutoff_at': cutoff.isoformat(),
        'model_sha256': code_hash(root, model_paths),
        'seed_sha256': code_hash(root, seed_paths),
        'inputs': inputs,
    }
    selection['request_id'] = selection_id(selection)
    selection['summary'] = dict(sorted(Counter(item['source_name'] for item in inputs).items()))
    selection['status'] = 'LOCAL_INVENTORY_ONLY'
    return selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    request = read_json(args.request)
    selected = inventory(ROOT, request)
    output = ROOT / 'data/close_input_inventory' / (selected['request_id'] + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(selected, indent=2) + '\n', encoding='utf-8')
    print(f"Close {selected['business_date']}: {selected['request_id']}")
    for name, count in selected['summary'].items():
        print(f'{name}: {count} delivery(s)')
    print(f'Local inventory: {output}')
    print('Snowflake receipts and RAW row counts still need verification.')


if __name__ == '__main__':
    main()
