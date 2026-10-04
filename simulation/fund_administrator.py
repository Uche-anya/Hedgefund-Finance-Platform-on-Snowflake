"""Produce fictional investor-flow and expense records from reviewed inputs."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def produce(config_path=ROOT / 'config/fund_admin_january.json', output=ROOT / 'data/fund_admin',
            input_root=ROOT):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    replay = input_root / config['source_replay']
    replay_manifest = json.loads((replay / 'manifest.json').read_text(encoding='utf-8'))
    valid_accounts = set(replay_manifest['config']['accounts'])
    replay_records = [json.loads(line) for line in
                      (replay / 'records.jsonl').read_text(encoding='utf-8').splitlines()]
    valid_dates = {row['business_date'] for row in replay_records if row['record_type'] == 'SESSION'}
    records = []
    for number, item in enumerate(config['events'], 1):
        amount = Decimal(item['amount'])
        if item['account_id'] not in valid_accounts or item['event_date'] not in valid_dates:
            raise ValueError('Administrator event is outside the reviewed replay')
        if item['event_type'] == 'EXPENSE' and (amount <= 0 or item.get('payment_date') not in valid_dates):
            raise ValueError('Expense amount and payment date are required')
        if item['event_type'] == 'INVESTOR_SUBSCRIPTION' and amount <= 0:
            raise ValueError('Subscription must be positive')
        if item['event_type'] == 'INVESTOR_REDEMPTION' and amount >= 0:
            raise ValueError('Redemption must be negative')
        key = f"{replay_manifest['scenario_id']}/{number}/{item['event_type']}"
        records.append({
            'record_id': 'SIM-ADMIN-' + hashlib.sha256(key.encode()).hexdigest()[:24],
            'scenario_id': replay_manifest['scenario_id'], 'source_system': 'simulated_fund_administrator',
            'is_simulated': True, **item,
        })
    body = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in records).encode()
    signature = config_path.read_bytes() + Path(__file__).read_bytes() + body
    delivery_id = 'sim-admin-' + hashlib.sha256(signature).hexdigest()[:24]
    folder = output / delivery_id
    if folder.exists():
        return folder
    folder.mkdir(parents=True)
    data_file = folder / 'events.jsonl'
    data_file.write_bytes(body)
    manifest = {
        'delivery_id': delivery_id, 'scenario_id': replay_manifest['scenario_id'],
        'record_count': len(records), 'is_simulated': True,
        'source_replay': config['source_replay'], 'config_sha256': sha256(config_path),
        'files': {'events.jsonl': sha256(data_file)},
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Fund administrator delivery: {folder}')
    return folder


if __name__ == '__main__':
    produce()
