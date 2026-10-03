"""Compare Snowflake's multi-day output with an independent local calculation."""

import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.replay_control import calculate
from simulation.multi_day import read_prices
from dbt_key import KEY_PATH, USER, unlock_secret


def compare(cursor, table, key_columns, expected, scenario):
    fields = list(next(iter(expected.values())))
    columns = [*key_columns, *fields]
    # Table and column names are constants in this script; the scenario is bound.
    cursor.execute('select ' + ', '.join(columns) + ' from NORTHBRIDGE_DEV.DBT_DEV.' + table
                   + ' where scenario_id = %s', (scenario,))
    actual = {}
    for row in cursor.fetchall():
        key = tuple(str(v) for v in row[:len(key_columns)])
        if key in actual:
            raise ValueError(f'Duplicate output key in {table}: {key}')
        actual[key] = dict(zip(fields, row[len(key_columns):]))
    if set(actual) != set(expected):
        raise ValueError(f'Missing or extra output keys in {table}')
    for key in expected:
        for field in fields:
            if actual[key][field] != expected[key][field]:
                raise ValueError(f'{table}: {key}, {field} differs from the independent calculation')
    print(f'{table}: {len(actual)} rows match the independent Decimal calculation.')
    return len(actual)


def main():
    folder = ROOT / 'data/replays/sim-dividend-a48996d29c0473a090db3b9f'
    manifest = json.loads((folder / 'manifest.json').read_text())
    payload = (folder / 'records.jsonl').read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest['files']['records.jsonl']:
        raise ValueError('Replay input hash changed')
    config = manifest['config']
    price_file = ROOT / config['price_snapshot'] / 'prices.csv'
    if hashlib.sha256(price_file.read_bytes()).hexdigest() != config['price_sha256']:
        raise ValueError('Price snapshot hash changed')
    records = [json.loads(line) for line in payload.decode().splitlines()]
    days = {r['business_date'] for r in records if r['record_type'] == 'SESSION'}
    prices = read_prices(price_file, set(config['tickers']), days)
    # Independently reviewed terms, not values read back from the dbt result.
    # Scope and source evidence: docs/mastercard_dividend.md.
    dividends = [dict(ticker='MA', ex_date='2025-01-10', pay_date='2025-02-07', amount='0.76',
                      event_id='Ec6372be9137e6a822fd370e8f0738fc31cfb9db56ee95abb2ee9b45f3022db0b')]
    admin_file = ROOT / 'data/fund_admin/sim-admin-d4c87abd5740695f47b0bd8c/events.jsonl'
    admin_events = [json.loads(line) for line in admin_file.read_text(encoding='utf-8').splitlines()]
    positions, balances = calculate(records, prices, config['tickers'], dividends, admin_events)

    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    secret = unlock_secret()
    key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private_key = key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    connection = snowflake.connector.connect(
        account='gxmgyta-fq45953', user=USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_DBT_DEV', warehouse='COMPUTE_WH',
        database='NORTHBRIDGE_DEV', schema='DBT_DEV')
    del private_key, key
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            counts = {
                'positions': compare(cursor, 'FCT_DAILY_VALUATIONS',
                                     ['business_date', 'account_id', 'instrument_id'], positions, manifest['scenario_id']),
                'account_days': compare(cursor, 'FCT_DAILY_NAV',
                                        ['business_date', 'account_id'], balances, manifest['scenario_id'])}
    finally:
        connection.close()
    report = ROOT / 'data/replay_checks' / (uuid4().hex + '.json')
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps({'scenario_id': manifest['scenario_id'], 'status': 'PASS',
                                 'compared_rows': counts}, indent=2) + '\n')
    print(f'Check record: {report}')


if __name__ == '__main__':
    main()
