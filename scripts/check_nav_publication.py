"""Verify the saved January NAV publication and its retry behaviour."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from publish_nav import code_version, connect, run_id


def main():
    config = json.loads((ROOT / 'config/nav_publication_january.json').read_text(encoding='utf-8'))
    run = run_id(config, code_version(ROOT))
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            cursor.execute('''
                select event_type, count(*)
                from pipeline_run_events where run_id = %s group by event_type
            ''', (run,))
            events = dict(cursor.fetchall())
            if events != {'STARTED': 1, 'SUCCEEDED': 1}:
                raise ValueError(f'Unexpected run events: {events}')
            cursor.execute('''
                select p.account_id, p.currency, p.published_nav, c.simplified_nav
                from nav_publications p
                join nav_candidates c
                  on p.scenario_id = c.scenario_id
                 and p.business_date = c.business_date
                 and p.account_id = c.account_id
                 and p.currency = c.currency
                where p.run_id = %s
                order by p.account_id
            ''', (run,))
            rows = cursor.fetchall()
            if len(rows) != 2 or any(row[2] != row[3] for row in rows):
                raise ValueError('Published NAV does not match the reviewed candidates')
            cursor.execute('''
                select count(*) from nav_restatements
                where replacement_publication_id in
                    (select publication_id from nav_publications where run_id = %s)
            ''', (run,))
            if cursor.fetchone()[0] != 0:
                raise ValueError('The first publication should not be a restatement')
    finally:
        connection.close()
    print(f'Publication verified: {run}')
    print('Two NAV rows, one STARTED event, one SUCCEEDED event and no restatement.')


if __name__ == '__main__':
    main()
