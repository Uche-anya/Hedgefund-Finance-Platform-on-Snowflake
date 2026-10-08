"""Make a clearly simulated one-cent AAPL price correction for the DEV pilot."""

import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'data/daily_prices/d0aa06f1b5f04633b6e5fbe3da38a241'


def main():
    old = json.loads((ORIGINAL / 'manifest.json').read_text(encoding='utf-8'))
    with (ORIGINAL / 'prices.csv').open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    changed = [row for row in rows if row['universe_ticker'] == 'AAPL']
    if len(changed) != 1:
        raise ValueError('Expected exactly one AAPL bar')
    row = changed[0]
    before = Decimal(row['close_price'])
    row['close_price'] = str(before + Decimal('0.01'))
    row['source_system'] = 'simulated_price_correction'
    row['input_file'] = 'correction_pilot/2026-09-22/AAPL'

    import io
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    content = output.getvalue().encode('utf-8')
    digest = hashlib.sha256(content).hexdigest()
    folder = ROOT / 'data/daily_prices' / ('correction_' + digest[:24])
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / 'prices.csv'
    if file.exists() and file.read_bytes() != content:
        raise ValueError('Correction package folder already has different bytes')
    file.write_bytes(content)
    manifest = {
        'delivery_id': 'daily-prices-correction-' + digest[:24],
        'valuation_date': old['valuation_date'],
        'record_count': len(rows),
        'files': {'prices.csv': digest},
        'replaces_delivery_id': old['delivery_id'],
        'is_simulated': True,
        'correction_reason': 'DEV-only one-cent AAPL close correction test',
    }
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n',
                                          encoding='utf-8')
    request = json.loads((ROOT / 'config/daily_close_20260922.json').read_text(
        encoding='utf-8'))
    request['price_manifest'] = (folder / 'manifest.json').relative_to(ROOT).as_posix()
    output_request = ROOT / 'config/daily_close_20260922_correction.json'
    output_request.write_text(json.dumps(request, indent=2) + '\n', encoding='utf-8')
    print(f'AAPL close: {before} -> {row["close_price"]} (simulated)')
    print(f'Correction package: {folder}')
    print(f'Close request: {output_request}')


if __name__ == '__main__':
    main()
