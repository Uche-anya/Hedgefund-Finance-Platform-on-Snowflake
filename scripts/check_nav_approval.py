"""Confirm the publisher and reviewer calculate the same NAV candidate hash."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from publish_nav import candidate_hash, connect


def main():
    day = '2025-02-07'
    scenario = 'sim-replay-406bbef8179cdbb0a3dd6df3'
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            cursor.execute('''
                select scenario_id, business_date, account_id, currency,
                       simplified_nav, calculation_basis
                from nav_candidates
                where business_date = %s::date and scenario_id = %s
                order by account_id, currency
            ''', (day, scenario))
            rows = cursor.fetchall()
            local_hash = candidate_hash(rows)
            cursor.execute('''
                select candidate_hash
                from nav_review_candidates
                where business_date = %s::date and scenario_id = %s
            ''', (day, scenario))
            saved_hash = cursor.fetchone()[0]
            if local_hash != saved_hash:
                raise ValueError(f'Candidate hash mismatch: {local_hash} != {saved_hash}')
    finally:
        connection.close()
    print(f'Candidate hash matches for {len(rows)} NAV rows: {local_hash}')


if __name__ == '__main__':
    main()
