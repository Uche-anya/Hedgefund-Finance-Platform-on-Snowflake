"""Create four fictional settlement confirmations for the saved five-trade lesson."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from simulation.simulator import validate_execution


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = 'sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8'
INPUT = ROOT / 'data/simulator_historical' / SCENARIO
CUTOFF = '2025-01-07T22:00:00+00:00'
EXPECTED = [
    ('AAPL', 'BUY', '10', '243.48'),
    ('AMZN', 'SELL', '5', '224.08'),
    ('AAPL', 'BUY', '8', '243.55'),
    ('AMZN', 'BUY', '2', '224.26'),
    ('AAPL', 'SELL', '3', '243.31'),
]


def read_trades(folder):
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['scenario_id'] != SCENARIO or manifest['event_count'] != 5:
        raise ValueError('This settlement lesson requires the saved five-trade scenario')
    trades = []
    for name, digest in manifest['files'].items():
        if Path(name).name != name or not name.endswith('.jsonl'):
            raise ValueError('Expected a JSONL filename inside the scenario folder')
        raw = (folder / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f'Changed input: {name}')
        trade = json.loads(raw)
        validate_execution(trade)
        if (trade['scenario_id'] != SCENARIO
                or trade['business_date'] != '2025-01-06'
                or trade['settlement_due'] != '2025-01-07'
                or trade['account_id'] != 'SIM-ACCOUNT-01'
                or trade['currency'] != 'USD'):
            raise ValueError('Unexpected trade scope')
        trades.append(trade)
    trades.sort(key=lambda trade: trade['executed_at'])
    details = [(t['market_ticker'], t['side'], t['quantity'], t['execution_price'])
               for t in trades]
    if details != EXPECTED:
        raise ValueError('The five trade details differ from this lesson')
    for field in ('event_id', 'execution_id'):
        if len({trade[field] for trade in trades}) != 5:
            raise ValueError(f'Duplicate {field}')
    return trades


def make_confirmation(trade, index):
    amount = Decimal(trade['quantity']) * Decimal(trade['execution_price'])
    if trade['side'] == 'BUY':
        amount = -amount
    settled = datetime(2025, 1, 7, 17, tzinfo=timezone.utc) + timedelta(minutes=index)
    identifier = uuid5(NAMESPACE_URL, 'northbridge/settlement-lesson-001/' + trade['execution_id']).hex
    return {
        'schema_version': 1,
        'event_id': 'sim-settlement-' + identifier,
        'event_type': 'SETTLEMENT_CONFIRMED',
        'source_system': 'simulated_custodian',
        'scenario_id': SCENARIO,
        'is_simulated': True,
        'settlement_id': 'SIM-SETTLEMENT-' + identifier,
        'execution_id': trade['execution_id'],
        'fund_id': trade['fund_id'],
        'account_id': trade['account_id'],
        'broker_id': trade['broker_id'],
        'instrument_id': trade['instrument_id'],
        'side': trade['side'],
        'settled_quantity': trade['quantity'],
        'currency': trade['currency'],
        'cash_amount': str(amount),
        'settlement_date': '2025-01-07',
        'settled_at': settled.isoformat(),
        'published_at': (settled + timedelta(seconds=30)).isoformat(),
        'settlement_status': 'SETTLED',
    }


def produce_settlements(source=INPUT, output=ROOT / 'data/simulator_settlements'):
    trades = read_trades(source)
    confirmations = []
    unconfirmed = []
    for index, trade in enumerate(trades):
        # Withhold the Amazon buy confirmation. Do not invent a failure cause.
        if trade['market_ticker'] == 'AMZN' and trade['side'] == 'BUY':
            unconfirmed.append(trade['execution_id'])
            continue
        confirmations.append(make_confirmation(trade, index))

    delivery = uuid4().hex
    folder = output / delivery
    folder.mkdir(parents=True, exist_ok=False)
    files = {}
    for event in confirmations:
        path = folder / (event['event_id'] + '.jsonl')
        path.write_text(json.dumps(event) + '\n', encoding='utf-8')
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"Confirmed {event['side']} {event['settled_quantity']} "
              f"{event['instrument_id']}: USD {event['cash_amount']}")
    manifest = {
        'delivery_id': delivery,
        'scenario_id': SCENARIO,
        'is_simulated': True,
        'as_of': CUTOFF,
        'event_count': len(files),
        'files': files,
        'input_folder': str(source),
        'input_manifest_sha256': hashlib.sha256((source / 'manifest.json').read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'unconfirmed_execution_ids': unconfirmed,
        'assumptions': 'Full settlement, no fees; one confirmation withheld; no failure cause asserted',
        'source_note': 'Fictional custodian messages derived from OMS fixtures, not independent broker evidence',
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Four confirmations; Amazon BUY 2 has no confirmation by {CUTOFF}.')
    print(f'Saved settlement lesson: {folder}')
    return folder


if __name__ == '__main__':
    produce_settlements()
