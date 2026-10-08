"""Save counts and fingerprints for one development dbt close build."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_daily_readiness import connect


QUERIES = {
    'nav': '''
        select count(*), min(business_date), max(business_date),
               sum(reviewed_nav_usd),
               hash_agg(hash(scenario_id, business_date, account_id,
                             settled_cash_usd, trade_receivable_usd,
                             trade_payable_usd, net_market_value_usd,
                             reviewed_dividend_receivable_usd,
                             reviewed_short_dividend_payable_usd,
                             reviewed_nav_usd, illustrative_nav_usd))
        from NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_NAV_DAILY
        where scenario_id = %s and business_date <= %s
    ''',
    'positions': '''
        select count(*), min(business_date), max(business_date),
               sum(market_value_usd),
               hash_agg(hash(scenario_id, business_date, account_id,
                             security_id, quantity, close_price_usd,
                             market_value_usd))
        from NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_POSITIONS_DAILY
        where scenario_id = %s and business_date <= %s
    ''',
}


def fingerprint(cursor, request_id):
    cursor.execute('''
        select scenario_id, business_date, request_status, expected_input_count
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
        where request_id = %s
    ''', (request_id,))
    rows = cursor.fetchall()
    if len(rows) != 1 or rows[0][2] != 'CANDIDATE':
        raise ValueError('Expected one registered candidate close')
    scenario, day, _, input_count = rows[0]
    cursor.execute('''
        select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS
        where request_id = %s
    ''', (request_id,))
    if cursor.fetchone()[0] != input_count:
        raise ValueError('Close input registration is incomplete')
    result = {}
    for name, sql in QUERIES.items():
        cursor.execute(sql, (scenario, day))
        count, first, last, total, digest = cursor.fetchone()
        result[name] = {
            'rows': count,
            'first_date': str(first),
            'last_date': str(last),
            'value_sum': str(total),
            'hash_agg': str(digest),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            result = fingerprint(cursor, args.request_id)
    finally:
        connection.close()
    record = {
        'request_id': args.request_id,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'results': result,
    }
    folder = ROOT / 'data/close_results'
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / (args.request_id + '_' + uuid4().hex + '.json')
    output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    print(f'Fingerprint: {output}')


if __name__ == '__main__':
    main()
