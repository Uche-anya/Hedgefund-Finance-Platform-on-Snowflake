"""Publish the missing Amazon confirmation a day after its reported settlement."""

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from simulation.settlement_simulator import INPUT, ROOT, SCENARIO, make_confirmation, read_trades


def late_confirmation(trades):
    matches = [t for t in trades if t['market_ticker'] == 'AMZN' and t['side'] == 'BUY']
    if len(matches) != 1:
        raise ValueError('Expected exactly one Amazon buy')
    event = make_confirmation(matches[0], 3)
    # The message reports settlement on Jan 7, but is published on Jan 8.
    event['published_at'] = '2025-01-08T09:00:00+00:00'
    return event


def produce_late_confirmation(source=INPUT, output=ROOT / 'data/simulator_settlements'):
    event = late_confirmation(read_trades(source))
    delivery = uuid4().hex
    folder = output / delivery
    folder.mkdir(parents=True, exist_ok=False)
    file = folder / (event['event_id'] + '.jsonl')
    file.write_text(json.dumps(event) + '\n', encoding='utf-8')
    manifest = {
        'delivery_id': delivery, 'scenario_id': SCENARIO, 'is_simulated': True,
        'event_count': 1,
        'files': {file.name: hashlib.sha256(file.read_bytes()).hexdigest()},
        'input_folder': str(source),
        'input_manifest_sha256': hashlib.sha256((source / 'manifest.json').read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'as_of': '2025-01-08T10:00:00+00:00',
        'assumption': 'Late publication of a fictional Jan 7 full settlement, not late payment',
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f"Reported settlement: {event['settled_at']}; published: {event['published_at']}")
    print(f"Amazon BUY 2: USD {event['cash_amount']}")
    print(f'Saved late confirmation: {folder}')
    return folder


if __name__ == '__main__':
    produce_late_confirmation()
