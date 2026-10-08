"""Compare a saved close inventory with Snowflake RAW and delivery receipts."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_daily_readiness import connect


def raw_counts(cursor, selected):
    scenario = selected['scenario_id']
    day = selected['business_date']
    lookup = {item['source_name']: item['delivery_id'] for item in selected['inputs']
              if item['source_name'] in ('historical_prices', 'corporate_actions')}
    daily_price_ids = [item['delivery_id'] for item in selected['inputs']
                       if item['source_name'] == 'daily_prices']
    if not daily_price_ids:
        raise ValueError('No daily price delivery selected')
    price_slots = ', '.join('%s' for _ in daily_price_ids)
    queries = {
        'oms_events': (
            "select delivery_id, count(*) from NORTHBRIDGE_DEV.RAW.OMS_EVENTS "
            "where scenario_id = %s and try_to_date(payload:business_date::varchar) <= %s "
            "group by delivery_id", (scenario, day)),
        'settlement_events': (
            "select delivery_id, count(*) from NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS "
            "where payload:scenario_id::varchar = %s "
            "and try_to_date(payload:settlement_date::varchar) <= %s "
            "group by delivery_id", (scenario, day)),
        'historical_prices': (
            "select delivery_id, count(*) from NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES "
            "where delivery_id = %s group by delivery_id",
            (lookup['historical_prices'],)),
        'daily_prices': (
            "select delivery_id, count(*) from NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES "
            f"where valuation_date <= %s and delivery_id in ({price_slots}) "
            "group by delivery_id", (day, *daily_price_ids)),
        'fund_admin': (
            "select delivery_id, count(*) from NORTHBRIDGE_DEV.RAW.FUND_ADMIN_EVENTS "
            "where payload:scenario_id::varchar = %s "
            "and try_to_date(payload:event_date::varchar) <= %s group by delivery_id",
            (scenario, day)),
        'dividend_payments': (
            "select delivery_id, count(*) from NORTHBRIDGE_DEV.RAW.DIVIDEND_PAYMENT_EVENTS "
            "where payload:scenario_id::varchar = %s "
            "and try_to_date(payload:settlement_date::varchar) <= %s group by delivery_id",
            (scenario, day)),
        'corporate_actions': (
            "select load_id, count(*) from NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS "
            "where load_id = %s group by load_id", (lookup['corporate_actions'],)),
        'corporate_action_reviews': (
            "select load_id, count(*) from NORTHBRIDGE_DEV.RAW.CORPORATE_ACTION_REVIEWS "
            "where load_id = %s group by load_id", (lookup['corporate_actions'],)),
    }
    found = {}
    for source, (sql, params) in queries.items():
        cursor.execute(sql, params)
        for delivery, count in cursor.fetchall():
            found[source, delivery] = count
    return found


def receipt_rows(cursor):
    cursor.execute('''
        select source_name, delivery_id, manifest_sha256,
               expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where source_name in ('oms_events', 'settlement_events', 'daily_prices',
                              'fund_admin', 'dividend_payments')
    ''')
    found = {}
    duplicates = []
    for source, delivery, digest, expected, received, status in cursor.fetchall():
        key = (source, delivery)
        if key in found:
            duplicates.append(key)
        found[key] = (digest, expected, received, status)
    return found, duplicates


def compare(selected, raw, receipts, duplicates):
    expected = {(item['source_name'], item['delivery_id']): item
                for item in selected['inputs']}
    errors = []
    gaps = []
    for key, item in expected.items():
        count = raw.get(key)
        if count != item['expected_rows']:
            errors.append(f'{key[0]}/{key[1]}: RAW {count}, saved {item["expected_rows"]}')
        receipt_hash = item['receipt_sha256']
        if receipt_hash is None:
            gaps.append(f'{key[0]}/{key[1]}: no original delivery receipt')
            continue
        saved_receipt = receipts.get(key)
        wanted = (receipt_hash, item['expected_rows'], item['expected_rows'], 'READY')
        if saved_receipt != wanted:
            errors.append(f'{key[0]}/{key[1]}: receipt missing or different')
    for key in raw.keys() - expected.keys():
        errors.append(f'{key[0]}/{key[1]}: unselected RAW delivery')
    for key in duplicates:
        if key in expected:
            errors.append(f'{key[0]}/{key[1]}: duplicate receipt')
    return sorted(errors), sorted(gaps)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    args = parser.parse_args()
    selected = json.loads(args.inventory.read_text(encoding='utf-8'))
    if selected.get('status') != 'LOCAL_INVENTORY_ONLY':
        raise ValueError('Expected a locally verified inventory')
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            raw = raw_counts(cursor, selected)
            receipts, duplicates = receipt_rows(cursor)
    finally:
        connection.close()
    errors, gaps = compare(selected, raw, receipts, duplicates)
    totals = Counter()
    for (source, _), count in raw.items():
        totals[source] += count
    result = {
        'request_id': selected['request_id'],
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'selected_deliveries': len(selected['inputs']),
        'raw_deliveries': len(raw),
        'raw_rows_by_source': dict(sorted(totals.items())),
        'errors': errors, 'receipt_gaps': gaps,
    }
    output = ROOT / 'data/close_input_inventory' / (selected['request_id'] + '_snowflake.json')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Selected {result['selected_deliveries']} deliveries; RAW has {result['raw_deliveries']}.")
    print(f"RAW/count/receipt errors: {len(errors)}; original receipt gaps: {len(gaps)}")
    for issue in (errors + gaps)[:10]:
        print(issue)
    print(f'Full check: {output}')
    return 1 if errors or gaps else 0


if __name__ == '__main__':
    raise SystemExit(main())
