"""Produce a fictional bank closing-balance statement independently from dbt."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_balances(replay_records, admin_records, cutoff):
    balances = defaultdict(Decimal)
    for row in replay_records:
        kind = row['record_type']
        if kind == 'OPENING_CASH':
            balances[row['account_id']] += Decimal(row['amount'])
        elif kind in ('SETTLEMENT', 'DIVIDEND_PAYMENT'):
            settled = datetime.fromisoformat(row['settled_at'])
            published = datetime.fromisoformat(row['published_at'])
            if settled <= cutoff and published <= cutoff:
                balances[row['account_id']] += Decimal(row['cash_amount'])
    for row in admin_records:
        if row['event_type'].startswith('INVESTOR_') and row['event_date'] <= cutoff.date().isoformat():
            balances[row['account_id']] += Decimal(row['amount'])
        elif row['event_type'] == 'EXPENSE' and row['payment_date'] <= cutoff.date().isoformat():
            balances[row['account_id']] -= Decimal(row['amount'])
    return balances


def produce(config_path=ROOT / 'config/bank_statement_february.json',
            output=ROOT / 'data/bank_statements'):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    replay = ROOT / config['source_replay']
    admin = ROOT / config['source_admin']
    replay_manifest = json.loads((replay / 'manifest.json').read_text(encoding='utf-8'))
    admin_manifest = json.loads((admin / 'manifest.json').read_text(encoding='utf-8'))
    replay_records = [json.loads(line) for line in (replay / 'records.jsonl').read_text().splitlines()]
    admin_records = [json.loads(line) for line in (admin / 'events.jsonl').read_text().splitlines()]
    balances = expected_balances(replay_records, admin_records, datetime.fromisoformat(config['cutoff']))
    truth = []
    for adjustment in config['adjustments']:
        account = adjustment['account_id']
        expected = balances[account]
        balances[account] += Decimal(adjustment['amount'])
        truth.append({**adjustment, 'expected_balance': str(expected),
                      'reported_balance': str(balances[account])})
    rows = []
    for account, balance in sorted(balances.items()):
        key = f"{replay_manifest['scenario_id']}/{config['statement_date']}/{account}/USD"
        rows.append({
            'record_id': 'SIM-BANK-' + hashlib.sha256(key.encode()).hexdigest()[:24],
            'statement_id': 'SIM-BANK-STMT-' + hashlib.sha256(key.rsplit('/', 2)[0].encode()).hexdigest()[:24],
            'scenario_id': replay_manifest['scenario_id'], 'statement_date': config['statement_date'],
            'account_id': account, 'currency': 'USD', 'closing_balance': str(balance),
            'published_at': config['published_at'], 'source_system': 'simulated_bank',
            'is_simulated': True,
        })
    body = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows).encode()
    signature = config_path.read_bytes() + Path(__file__).read_bytes() + body
    delivery_id = 'sim-bank-' + hashlib.sha256(signature).hexdigest()[:24]
    folder = output / delivery_id
    if folder.exists():
        return folder
    folder.mkdir(parents=True)
    data_file = folder / 'balances.jsonl'
    data_file.write_bytes(body)
    manifest = {
        'delivery_id': delivery_id, 'scenario_id': replay_manifest['scenario_id'],
        'statement_date': config['statement_date'], 'expected_by': config['expected_by'],
        'record_count': len(rows), 'is_simulated': True,
        'source_replay_sha256': sha256(replay / 'records.jsonl'),
        'source_admin_sha256': sha256(admin / 'events.jsonl'),
        'files': {'balances.jsonl': sha256(data_file)}, 'synthetic_truth': truth,
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Bank statement delivery: {folder}')
    return folder


if __name__ == '__main__':
    produce()
