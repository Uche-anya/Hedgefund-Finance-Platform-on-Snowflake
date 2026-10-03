"""Compare staged corporate actions with the saved events and reviewed decisions."""
import csv
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data_extraction.review_bny_dividends import SNAPSHOT
from data_extraction.repair_bny_history import checked_file
from dbt_key import KEY_PATH, USER, unlock_secret


def main():
    manifest = json.loads((SNAPSHOT / 'manifest.json').read_text())
    expected = {}
    for kind in ('splits', 'dividends'):
        raw = checked_file(SNAPSHOT / (kind + '.jsonl'), manifest[kind]['sha256'])
        for line in raw.decode().splitlines():
            event = json.loads(line)['event']
            expected[event['id']] = {'event': event, 'kind': kind, 'decision': 'NEEDS_REVIEW', 'ids': [event['id']]}
    for folder, name, hash_field in [
        ('0a2042dd095e4a348a1dd75064a87658', 'bny_decisions.csv', 'decision_sha256'),
        ('26e32fc523e24ab08a0c479c0369e423', 'dividend_pair_decisions.csv', 'output_sha256')]:
        path = ROOT / 'data/corporate_action_reviews' / folder
        evidence = json.loads((path / 'manifest.json').read_text())
        raw = checked_file(path / name, evidence[hash_field])
        for row in csv.DictReader(raw.decode().splitlines()):
            if row['decision'] == 'EXCLUDED_FROM_BANK':
                del expected[row['event_id']]
            else:
                expected[row['event_id']]['decision'] = row['decision']
    path = ROOT / 'data/corporate_action_reviews/33fbc11bbd4740e5905b49cbcc3060b4'
    evidence = json.loads((path / 'manifest.json').read_text())
    replacement = json.loads(checked_file(path / 'tel_reviewed_event.json', evidence['output_sha256']))
    ids = [r['event']['id'] for r in replacement['source_records']]
    for event_id in ids:
        del expected[event_id]
    expected[replacement['reviewed_event_id']] = {'event': replacement['event'], 'kind': 'dividends',
        'decision': 'ONE_CASH_ENTITLEMENT', 'ids': ids}

    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    secret = unlock_secret()
    key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    connection = snowflake.connector.connect(account='gxmgyta-fq45953', user=USER, private_key=private,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_DBT_DEV', warehouse='COMPUTE_WH',
        database='NORTHBRIDGE_DEV', schema='DBT_DEV')
    del key, private
    fields = ['ticker', 'ex_dividend_date', 'execution_date', 'record_date', 'pay_date',
              'declaration_date', 'currency', 'cash_amount', 'split_from', 'split_to',
              'distribution_type', 'adjustment_type']
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            cursor.execute('select event_id, action_type, review_decision, source_event_ids, ' + ', '.join(fields)
                           + ' from stg_corporate_actions')
            seen = set()
            for row in cursor.fetchall():
                event_id, kind, decision, source_ids = row[:4]
                if event_id in seen or event_id not in expected:
                    raise ValueError('Duplicate or unexpected output ID')
                seen.add(event_id)
                wanted = expected[event_id]
                if kind != wanted['kind'] or decision != wanted['decision'] or sorted(json.loads(source_ids)) != sorted(wanted['ids']):
                    raise ValueError(f'Review or provenance mismatch: {event_id}')
                for field, value in zip(fields, row[4:]):
                    original = wanted['event'].get(field)
                    if field in ('cash_amount', 'split_from', 'split_to'):
                        original = Decimal(str(original)) if original is not None else None
                    elif value is not None:
                        value = str(value)
                    if value != original:
                        raise ValueError(f'Value mismatch: {event_id}, {field}')
            if seen != set(expected):
                raise ValueError('Missing output events')
            # An excess-precision value must be rejected, not rounded to one.
            cursor.execute("select case when regexp_like('1.0000000000001', '^[0-9]{1,26}([.][0-9]{1,12})?$') then try_to_decimal('1.0000000000001',38,12) end")
            if cursor.fetchone()[0] is not None:
                raise ValueError('Excess precision was not rejected')
            print(f'PASS: {len(seen)} events match saved inputs, decisions, source IDs and typed fields exactly.')
            print('PASS: excess decimal precision is rejected.')
    finally:
        connection.close()


if __name__ == '__main__':
    main()
