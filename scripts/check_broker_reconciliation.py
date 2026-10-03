"""Compare Snowflake reconciliation exceptions with the simulator's hidden truth."""

from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from dbt_key import KEY_PATH, USER, unlock_secret


DELIVERY = 'sim-broker-42a53a52c3913f138bf0ba35'


def expected_exceptions(manifest):
    expected = set()
    status = {
        'WRONG_QUANTITY': 'QUANTITY_MISMATCH',
        'MISSING_FROM_BROKER': 'MISSING_AT_BROKER',
        'UNEXPECTED_ACCOUNT_POSITION': 'UNEXPECTED_AT_BROKER',
    }
    for row in manifest['synthetic_truth']:
        expected.add((
            row['account_id'], row['ticker'], status[row['label']],
            Decimal(row['expected_quantity']) if row['expected_quantity'] is not None else None,
            Decimal(row['reported_quantity']) if row['reported_quantity'] is not None else None,
        ))
    return expected


def main():
    folder = ROOT / 'data/broker_statements' / DELIVERY
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    expected = expected_exceptions(manifest)

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
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            cursor.execute('''
                select account_id, ticker, book_status, internal_quantity, broker_quantity
                from fct_position_reconciliation
                where book_status <> 'MATCHED'
            ''')
            actual = set(cursor.fetchall())
            if actual != expected:
                raise ValueError(f'Reconciliation differs from hidden truth: {actual ^ expected}')
            cursor.execute('''
                select distinct account_id
                from fct_position_reconciliation
                where timeliness_status = 'LATE'
            ''')
            late_accounts = {row[0] for row in cursor.fetchall()}
            if late_accounts != {'SIM-REPLAY-02'}:
                raise ValueError(f'Unexpected late-account result: {late_accounts}')
    finally:
        connection.close()
    print(f'{len(actual)} reconciliation exceptions match the simulator truth.')
    print('Late statement account matches the expected SLA breach: SIM-REPLAY-02.')


if __name__ == '__main__':
    main()
