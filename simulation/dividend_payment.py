"""Add one fictional Mastercard cash receipt to the prepared February replay."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = '34cb5c585ab65e1742f610e64e577aed'
ACTION = 'Ec6372be9137e6a822fd370e8f0738fc31cfb9db56ee95abb2ee9b45f3022db0b'


def generate():
    source = ROOT / 'data/replay_extensions' / EXTENSION
    extension = json.loads((source / 'manifest.json').read_text())
    raw = (source / 'records.jsonl').read_bytes()
    if hashlib.sha256(raw).hexdigest() != extension['files']['records.jsonl']:
        raise ValueError('Prepared replay changed')
    base = ROOT / 'data/replays' / extension['base_replay']
    original_manifest = (base / 'manifest.json').read_bytes()
    if hashlib.sha256(original_manifest).hexdigest() != extension['base_manifest_sha256']:
        raise ValueError('Original replay manifest changed')
    config = json.loads(original_manifest)['config']
    config.update(end_date='2025-02-07', calendar=extension['calendar'],
                  calendar_sha256=extension['calendar_sha256'])
    config['no_trade_dates'] += extension['added_days']
    payment = dict(record_type='DIVIDEND_PAYMENT', schema_version=1,
                   scenario_id=extension['scenario_id'], is_simulated=True,
                   event_id='sim-dividend-MA-20250207-account02-v1',
                   corporate_action_id=ACTION, account_id='SIM-REPLAY-02',
                   broker_id='SIM-BROKER-01', instrument_id='MA.US', currency='USD',
                   cash_amount='254.60', business_date='2025-02-07',
                   settled_at='2025-02-07T18:00:00+00:00',
                   published_at='2025-02-07T18:01:00+00:00',
                   source_system='simulated_custodian')
    output = raw + (b'' if raw.endswith(b'\n') else b'\n')
    output += (json.dumps(payment) + '\n').encode()
    fingerprint = hashlib.sha256(output).hexdigest()
    delivery = 'sim-dividend-' + fingerprint[:24]
    folder = ROOT / 'data/replays' / delivery
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'records.jsonl'
    if path.exists() and path.read_bytes() != output:
        raise ValueError('Existing payment replay changed; refusing to overwrite')
    path.write_bytes(output)
    manifest = dict(delivery_id=delivery, scenario_id=extension['scenario_id'],
                    config=config, files={'records.jsonl': fingerprint},
                    base_extension=EXTENSION, base_extension_sha256=hashlib.sha256(raw).hexdigest(),
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    counts=dict(OPENING_CASH=2, SESSION=23, EXECUTION=3200,
                                SETTLEMENT=3168, DIVIDEND_PAYMENT=1),
                    assumptions='One fictional gross MA receipt; short payment unconfirmed; no new trades after January 30.')
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(delivery)
    print(f'Saved fictional receipt of USD 254.60: {folder}')
    return folder


if __name__ == '__main__':
    generate()
