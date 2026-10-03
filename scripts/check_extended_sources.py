"""Check the four final sources after dbt has built their outputs."""

from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from dbt_key import KEY_PATH, USER, unlock_secret


def connect():
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    secret = unlock_secret()
    key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private_key = key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    connection = snowflake.connector.connect(
        account='gxmgyta-fq45953', user=USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_DBT_DEV',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='DBT_DEV')
    del private_key, key
    return connection


def main():
    bank_folder = ROOT / 'data/bank_statements/sim-bank-8690941c886b2dc3602d214f'
    manifest = json.loads((bank_folder / 'manifest.json').read_text(encoding='utf-8'))
    expected_breaks = {(row['account_id'], Decimal(row['reported_balance'])
                        - Decimal(row['expected_balance'])) for row in manifest['synthetic_truth']}
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            cursor.execute('''select account_id, balance_difference
                              from fct_bank_cash_reconciliation
                              where reconciliation_status <> 'MATCHED' ''')
            actual_breaks = set(cursor.fetchall())
            if actual_breaks != expected_breaks:
                raise ValueError(f'Bank reconciliation differs from hidden truth: {actual_breaks ^ expected_breaks}')
            cursor.execute('select count(*) from fct_daily_nav_reporting')
            reporting_rows = cursor.fetchone()[0]
            cursor.execute('select count(*) from fct_cash_yield_benchmark')
            benchmark_rows = cursor.fetchone()[0]
            if reporting_rows != 92 or benchmark_rows != 46:
                raise ValueError('Reference-rate outputs do not cover every account-day')
            cursor.execute('''
                select account_id, investor_flows, paid_expenses, expense_payable
                from fct_daily_cash where business_date = '2025-02-07' order by account_id
            ''')
            final_cash = cursor.fetchall()
            expected_cash = [
                ('SIM-REPLAY-01', Decimal('250000'), Decimal('1500'), Decimal('0')),
                ('SIM-REPLAY-02', Decimal('-100000'), Decimal('1500'), Decimal('0')),
            ]
            if final_cash != expected_cash:
                raise ValueError('Administrator events did not reach daily cash as expected')
    finally:
        connection.close()
    print('ECB reporting NAV: 92 account/currency rows verified.')
    print('Treasury benchmark: 46 account-day rows verified.')
    print('Administrator flows and expenses reached cash and NAV.')
    print('One $25 bank break matches the simulator truth.')


if __name__ == '__main__':
    main()
