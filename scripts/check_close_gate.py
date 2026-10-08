"""Read the Snowflake gate for one selected development close."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.register_close_request import connect


def gate(cursor, request_id):
    cursor.execute('''
        select build_gate, publication_gate, expected_input_count,
               selected_inputs, verified_inputs, legacy_gaps, bad_inputs
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_GATE
        where request_id = %s
    ''', (request_id,))
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise ValueError('Expected one registered close gate result')
    return rows[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request_id')
    args = parser.parse_args()
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            build, publication, expected, selected, verified, legacy, bad = gate(
                cursor, args.request_id)
            print(f'{args.request_id}: build {build}; publication {publication}')
            print(f'Inputs: {selected}/{expected} selected; '
                  f'{verified} verified; {legacy} legacy gaps; {bad} bad')
            if bad:
                cursor.execute('''
                    select source_name, delivery_id, input_status,
                           raw_rows, expected_rows, receipt_count
                    from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUT_AUDIT
                    where request_id = %s
                      and input_status not in ('VERIFIED', 'LEGACY_GAP')
                    order by source_name, delivery_id
                ''', (args.request_id,))
                for row in cursor.fetchall()[:10]:
                    print(row)
            return 0 if build == 'BUILDABLE' else 1
    finally:
        connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
