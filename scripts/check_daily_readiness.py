"""Check one provisional close against its saved files and Snowflake RAW."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import dbt_key


def connect():
    import snowflake.connector

    secret = dbt_key.unlock_secret()
    key = serialization.load_pem_private_key(
        dbt_key.KEY_PATH.read_bytes(), password=secret.encode())
    private_key = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    return snowflake.connector.connect(
        account='gxmgyta-fq45953', user=dbt_key.USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_DBT_DEV',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='DBT_DEV',
        session_parameters={'QUERY_TAG': 'northbridge_daily_readiness'})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(root, name, filename):
    path = (root / name).resolve()
    if root.resolve() not in path.parents:
        raise ValueError('Manifest must be inside the project')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    file = path.parent / filename
    file_hash = digest(file)
    if manifest['files'][filename] != file_hash:
        raise ValueError(f'{filename} changed after packaging')
    return manifest, file, file_hash


def saved_inputs(root, request):
    day = request['business_date']
    scenario = request['scenario_id']
    cutoff = datetime.fromisoformat(request['cutoff_at'].replace('Z', '+00:00'))
    if cutoff.tzinfo is None or cutoff.utcoffset() != timezone.utc.utcoffset(cutoff):
        raise ValueError('Cutoff must be in UTC')

    oms, oms_file, oms_hash = package(root, request['oms_manifest'], 'oms.jsonl')
    if (oms['business_date'] != day or oms['scenario_id'] != scenario
            or oms['delivery_id'] is None):
        raise ValueError('OMS manifest is for another close')
    events = [json.loads(line) for line in oms_file.read_text(encoding='utf-8').splitlines()
              if line.strip()]
    ids = [event['event_id'] for event in events]
    executions = [event['execution_id'] for event in events]
    if (len(events) != oms['record_count'] or len(ids) != len(set(ids))
            or len(executions) != len(set(executions))):
        raise ValueError('OMS file count, event IDs or execution IDs are wrong')
    for event in events:
        published = datetime.fromisoformat(event['published_at'].replace('Z', '+00:00'))
        if (event['scenario_id'] != scenario or event['business_date'] != day
                or published > cutoff):
            raise ValueError('OMS event is outside the requested close')

    prices, price_file, price_hash = package(root, request['price_manifest'], 'prices.csv')
    with price_file.open(newline='', encoding='utf-8') as handle:
        bars = list(csv.DictReader(handle))
    tickers = [row['universe_ticker'] for row in bars]
    required = request['required_tickers']
    if (prices['valuation_date'] != day or len(bars) != prices['record_count']
            or len(tickers) != len(set(tickers))
            or len(required) != len(set(required))
            or set(tickers) != set(required)):
        raise ValueError('Price date, count or ticker set is wrong')
    for bar in bars:
        if (bar['valuation_date'] != day or bar['currency'] != 'USD'
                or bar['price_basis'] != 'unadjusted'
                or Decimal(bar['close_price']) <= 0):
            raise ValueError('Invalid daily close price')

    selected = {
        'scenario_id': scenario, 'business_date': day,
        'cutoff_at': cutoff.isoformat(),
        'required_tickers': sorted(required),
        'oms': {'delivery_id': oms['delivery_id'], 'sha256': oms_hash,
                'rows': len(events), 'event_ids': sorted(ids),
                'execution_ids': sorted(executions)},
        'daily_prices': {'delivery_id': prices['delivery_id'], 'sha256': price_hash,
                         'rows': len(bars),
                         'closes': {row['universe_ticker']: row['close_price'] for row in bars}},
    }
    if prices.get('replaces_delivery_id'):
        selected['daily_prices']['replaces_delivery_id'] = prices['replaces_delivery_id']
    # The same request always gets the same ID. New file bytes get a new ID.
    value = json.dumps(selected, sort_keys=True, separators=(',', ':')).encode()
    selected['request_id'] = hashlib.sha256(value).hexdigest()[:24]
    return selected


def check_receipt(cursor, source, item):
    cursor.execute('''
        select manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where source_name = %s and delivery_id = %s
    ''', (source, item['delivery_id']))
    rows = cursor.fetchall()
    expected = (item['sha256'], item['rows'], item['rows'], 'READY')
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise ValueError(f'{source}/{item["delivery_id"]}: receipt missing or changed')


def check_raw(cursor, selected):
    day = selected['business_date']
    scenario = selected['scenario_id']
    check_receipt(cursor, 'oms_events', selected['oms'])
    check_receipt(cursor, 'daily_prices', selected['daily_prices'])

    # Read every event for this scenario and date, including a second delivery.
    cursor.execute('''
        select delivery_id, payload:event_id::varchar,
               payload:execution_id::varchar, payload:published_at::varchar,
               payload:execution_status::varchar
        from NORTHBRIDGE_DEV.RAW.OMS_EVENTS
        where scenario_id = %s and payload:business_date::varchar = %s
    ''', (scenario, day))
    events = cursor.fetchall()
    ids = [row[1] for row in events]
    executions = [row[2] for row in events]
    if (len(events) != selected['oms']['rows']
            or sorted(ids) != selected['oms']['event_ids']
            or sorted(executions) != selected['oms']['execution_ids']
            or len(ids) != len(set(ids))
            or len(executions) != len(set(executions))):
        raise ValueError('RAW OMS has missing, extra or repeated events')
    cutoff = datetime.fromisoformat(selected['cutoff_at'])
    for delivery, _, _, published_at, status in events:
        published = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        if (delivery != selected['oms']['delivery_id'] or status != 'ACTIVE'
                or published > cutoff):
            raise ValueError('RAW OMS delivery, status or cutoff differs')

    prices = selected['daily_prices']
    price_filter = 'and delivery_id = %s' if prices.get('replaces_delivery_id') else ''
    cursor.execute(f'''
        select delivery_id, universe_ticker, currency, price_basis, close_price
        from NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
        where valuation_date = %s {price_filter}
    ''', (day, prices['delivery_id']) if price_filter else (day,))
    bars = cursor.fetchall()
    tickers = [row[1] for row in bars]
    if (len(bars) != prices['rows'] or len(tickers) != len(set(tickers))
            or set(tickers) != set(prices['closes'])):
        raise ValueError('RAW prices have missing, extra or repeated tickers')
    for delivery, ticker, currency, basis, close in bars:
        if (delivery != prices['delivery_id'] or currency != 'USD'
                or basis != 'unadjusted'
                or Decimal(close) != Decimal(prices['closes'][ticker])):
            raise ValueError(f'RAW price differs for {ticker}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding='utf-8'))
    selected = saved_inputs(ROOT, request)
    record = {'attempt_id': uuid4().hex, 'request_id': selected['request_id'],
              'scenario_id': selected['scenario_id'],
              'business_date': selected['business_date'],
              'cutoff_at': selected['cutoff_at'],
              'oms_delivery_id': selected['oms']['delivery_id'],
              'oms_sha256': selected['oms']['sha256'],
              'oms_rows': selected['oms']['rows'],
              'price_delivery_id': selected['daily_prices']['delivery_id'],
              'price_sha256': selected['daily_prices']['sha256'],
              'price_rows': selected['daily_prices']['rows'],
              'started_at': datetime.now(timezone.utc).isoformat(),
              'status': 'RUNNING'}
    folder = ROOT / 'data/daily_close_checks'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (record['attempt_id'] + '.json')
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            check_raw(cursor, selected)
        record['status'] = 'READY'
        print(f"READY {selected['business_date']} | request {selected['request_id']}")
        print(f"OMS {selected['oms']['rows']} events; prices {selected['daily_prices']['rows']} bars")
        return 0
    except Exception as error:
        record['status'] = 'FAILED'
        record['error'] = str(error)
        print(f'Daily close is not ready: {error}')
        return 1
    finally:
        if connection is not None:
            connection.close()
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(f'Check record: {path}')


if __name__ == '__main__':
    raise SystemExit(main())
