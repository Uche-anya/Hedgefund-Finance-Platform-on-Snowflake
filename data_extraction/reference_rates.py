"""Download the ECB FX fix and US Treasury one-month rate for replay dates."""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / 'data/replays/sim-dividend-a48996d29c0473a090db3b9f'
ECB_URL = ('https://data-api.ecb.europa.eu/service/data/EXR/'
           'D.USD+GBP.EUR.SP00.A?startPeriod={start}&endPeriod={end}&format=csvdata')
TREASURY_URL = ('https://home.treasury.gov/resource-center/data-chart-center/'
                'interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value=2025')


def fetch(url):
    request = Request(url, headers={'User-Agent': 'NorthbridgeDataPipeline/1.0'})
    with urlopen(request, timeout=30) as response:
        return response.read(10_000_001)


def replay_dates():
    rows = (json.loads(line) for line in (REPLAY / 'records.jsonl').read_text(encoding='utf-8').splitlines())
    return sorted(row['business_date'] for row in rows if row['record_type'] == 'SESSION')


def parse_ecb(payload, dates):
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    required = {'TIME_PERIOD', 'OBS_VALUE', 'CURRENCY', 'CURRENCY_DENOM',
                'FREQ', 'EXR_TYPE', 'EXR_SUFFIX'}
    if not reader.fieldnames or not required <= set(reader.fieldnames):
        raise ValueError('ECB response is missing required columns')
    values = {}
    wanted = set(dates)
    for row in reader:
        if row['TIME_PERIOD'] not in wanted or row['CURRENCY'] not in ('USD', 'GBP'):
            continue
        if (row['CURRENCY_DENOM'], row['FREQ'], row['EXR_TYPE'], row['EXR_SUFFIX']) != ('EUR', 'D', 'SP00', 'A'):
            raise ValueError('Unexpected ECB rate definition')
        key = row['TIME_PERIOD'], row['CURRENCY']
        rate = Decimal(row['OBS_VALUE'])
        if key in values or not rate.is_finite() or rate <= 0:
            raise ValueError(f'Invalid or duplicate ECB observation: {key}')
        values[key] = rate
    expected = {(day, currency) for day in dates for currency in ('USD', 'GBP')}
    if set(values) != expected:
        missing = sorted(expected - set(values))
        raise ValueError(f'Missing ECB observation: {missing[0]}')
    return [
        {'rate_date': day, 'base_currency': 'EUR',
         'usd_per_eur': str(values[(day, 'USD')]),
         'gbp_per_eur': str(values[(day, 'GBP')]),
         'source_system': 'ECB_EXR'}
        for day in dates
    ]


def parse_treasury(payload, dates):
    root = ET.fromstring(payload)
    wanted = set(dates)
    values = {}
    for properties in root.iter():
        if properties.tag.rsplit('}', 1)[-1] != 'properties':
            continue
        row = {child.tag.rsplit('}', 1)[-1]: (child.text or '').strip() for child in properties}
        raw_day = row.get('NEW_DATE', '')[:10]
        if raw_day not in wanted:
            continue
        raw_rate = row.get('BC_1MONTH')
        if not raw_rate:
            raise ValueError(f'Missing one-month Treasury rate: {raw_day}')
        rate = Decimal(raw_rate)
        if raw_day in values or not rate.is_finite() or rate < 0:
            raise ValueError(f'Invalid or duplicate Treasury observation: {raw_day}')
        values[raw_day] = rate
    if set(values) != wanted:
        missing = sorted(wanted - set(values))
        raise ValueError(f'Missing Treasury observation: {missing[0]}')
    return [
        {'rate_date': day, 'tenor': '1M', 'annual_rate_percent': str(values[day]),
         'day_count_basis': 360, 'source_system': 'US_TREASURY'}
        for day in dates
    ]


def save_delivery(root, name, source_url, raw_name, raw, rows):
    content = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows).encode()
    delivery_id = name + '-' + hashlib.sha256(raw + content).hexdigest()[:24]
    folder = root / name / delivery_id
    if folder.exists():
        return folder
    temporary = root / name / ('.' + uuid4().hex)
    temporary.mkdir(parents=True)
    (temporary / raw_name).write_bytes(raw)
    (temporary / 'records.jsonl').write_bytes(content)
    manifest = {
        'delivery_id': delivery_id, 'source_url': source_url,
        'received_at_utc': datetime.now(timezone.utc).isoformat(),
        'record_count': len(rows), 'dates': [row['rate_date'] for row in rows],
        'files': {
            raw_name: hashlib.sha256(raw).hexdigest(),
            'records.jsonl': hashlib.sha256(content).hexdigest(),
        },
    }
    (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    temporary.rename(folder)
    return folder


def download(root=ROOT / 'data'):
    dates = replay_dates()
    ecb_url = ECB_URL.format(start=dates[0], end=dates[-1])
    ecb_raw = fetch(ecb_url)
    treasury_raw = fetch(TREASURY_URL)
    fx = save_delivery(root, 'fx_rates', ecb_url, 'ecb.csv', ecb_raw, parse_ecb(ecb_raw, dates))
    treasury = save_delivery(root, 'treasury_rates', TREASURY_URL, 'treasury.xml',
                             treasury_raw, parse_treasury(treasury_raw, dates))
    print(f'FX delivery: {fx}')
    print(f'Treasury delivery: {treasury}')
    return fx, treasury


if __name__ == '__main__':
    download()
