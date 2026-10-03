"""Generate five fictional January 6 trades using saved January 3 closing prices."""

import csv
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

from simulation.simulator import create_execution, save_event


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae'
TRADE_DATE = '2025-01-06'
REFERENCE_DATE = '2025-01-03'
# Ticker, side, shares, fictional price movement from the previous close.
# A basis point is 0.01%; these offsets are scenario assumptions, not measured spreads.
TRADES = (
    ('AAPL', 'BUY', '10', 5),
    ('AMZN', 'SELL', '5', -5),
    ('AAPL', 'BUY', '8', 8),
    ('AMZN', 'BUY', '2', 3),
    ('AAPL', 'SELL', '3', -2),
)


def reference_prices(payload):
    rows = csv.DictReader(io.StringIO(payload.decode('utf-8')))
    prices = {}
    for row in rows:
        ticker = row['universe_ticker']
        if row['valuation_date'] != REFERENCE_DATE or ticker not in ('AAPL', 'AMZN'):
            continue
        if ticker in prices:
            raise ValueError(f'Duplicate reference price for {ticker}')
        if row['source_ticker'] != ticker or row['currency'] != 'USD' or row['price_basis'] != 'unadjusted':
            raise ValueError(f'Unexpected reference details for {ticker}')
        value = Decimal(row['close_price'])
        if not value.is_finite() or value <= 0:
            raise ValueError(f'Invalid reference price for {ticker}')
        prices[ticker] = value
    if set(prices) != {'AAPL', 'AMZN'}:
        raise ValueError('Both January 3 reference prices are required; no stale-price fallback')
    return prices


def make_event(ticker, side, quantity, offset_bps, reference, scenario, index):
    price = (reference * (Decimal(1) + Decimal(offset_bps) / Decimal(10000)))
    price = price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    # The original lesson supplies January 6 timestamps and January 7 settlement.
    event = create_execution(ticker + '.US', side, quantity, str(price), index * 2)
    event.update(
        scenario_id=scenario,
        market_ticker=ticker,
        price_method='previous_close_with_fictional_offset',
        reference_price_date=REFERENCE_DATE,
        reference_close_price=str(reference),
        price_offset_bps=offset_bps,
    )
    return event


def produce_trades(snapshot=SNAPSHOT, output=ROOT / 'data/simulator_historical'):
    manifest_file = snapshot / 'manifest.json'
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    payload = (snapshot / 'prices.csv').read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != manifest['output_sha256']['prices.csv']:
        raise ValueError('prices.csv differs from its saved manifest')
    prices = reference_prices(payload)
    scenario = 'sim-historical-' + uuid4().hex
    folder = output / scenario
    files = {}
    for index, (ticker, side, quantity, offset) in enumerate(TRADES):
        event = make_event(ticker, side, quantity, offset, prices[ticker], scenario, index)
        path = save_event(event, folder)
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{side} {quantity} {ticker} at fictional USD {event['execution_price']} "
              f"| previous close {prices[ticker]}")
    record = {
        'scenario_id': scenario, 'is_simulated': True, 'business_date': TRADE_DATE,
        'reference_date': REFERENCE_DATE, 'price_snapshot': str(snapshot),
        'price_file_sha256': digest,
        'price_manifest_sha256': hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'event_count': len(files), 'files': files,
        'assumptions': 'Fixed January 6 lesson; shorts allowed; offsets invented; no exchange fill reconstruction',
        'identity_note': 'AAPL.US and AMZN.US are legacy simulator labels, not verified permanent security IDs',
    }
    (folder / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(f'Saved five fictional events: {folder}')
    return folder


if __name__ == '__main__':
    produce_trades()
