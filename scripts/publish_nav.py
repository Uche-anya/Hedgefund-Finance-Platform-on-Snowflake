"""Append a reviewed NAV snapshot to Snowflake's publication ledger."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def code_version(root):
    files = [root / 'dbt/dbt_project.yml']
    files.extend(sorted((root / 'dbt/models').rglob('*')))
    files.extend(sorted((root / 'dbt/tests').rglob('*')))
    files.extend(sorted((root / 'dbt/seeds').rglob('*')))
    digest = hashlib.sha256()
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run_id(config, version):
    values = [config['business_date'], config['scenario_id'],
              config['replay_delivery_id'], config['price_delivery_id'],
              config['broker_delivery_id'], version]
    return 'nav-run-' + hashlib.sha256('|'.join(values).encode()).hexdigest()[:24]


def publication_id(run, account, currency):
    return 'nav-pub-' + hashlib.sha256(f'{run}|{account}|{currency}'.encode()).hexdigest()[:24]


def candidate_hash(rows):
    parts = []
    for scenario, day, account, currency, nav, basis in rows:
        parts.append('|'.join((account, currency, str(nav), basis)))
    return hashlib.sha256('||'.join(parts).encode()).hexdigest()


def connect():
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    from publisher_key import KEY_PATH, USER, unlock_secret
    secret = unlock_secret()
    key = serialization.load_pem_private_key(KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private_key = key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    connection = snowflake.connector.connect(
        account='gxmgyta-fq45953', user=USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_NAV_PUBLISHER',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='OPERATIONS',
        session_parameters={'QUERY_TAG': 'northbridge_nav_publication'})
    del private_key, key
    return connection


def event(cursor, run, kind, config, version, details):
    cursor.execute('''
        insert into pipeline_run_events
        (event_id, run_id, event_type, business_date, replay_delivery_id,
         price_delivery_id, broker_delivery_id, code_version, details)
        select %s, %s, %s, %s::date, %s, %s, %s, %s, parse_json(%s)
    ''', (uuid4().hex, run, kind, config['business_date'],
          config['replay_delivery_id'], config['price_delivery_id'],
          config['broker_delivery_id'], version, json.dumps(details)))


def publish(config_path, restatement_reason=None, approved_by=None):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    version = code_version(ROOT)
    run = run_id(config, version)
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            cursor.execute('select count(*) from nav_publications where run_id = %s', (run,))
            saved_count = cursor.fetchone()[0]
            if saved_count:
                print(f'Run already published with {saved_count} NAV rows: {run}')
                cursor.execute('''
                    select account_id, currency, published_nav
                    from nav_publications where run_id = %s order by account_id, currency
                ''', (run,))
                for account, currency, nav in cursor.fetchall():
                    print(f'  {account} {currency}: {nav}')
                return run

            event(cursor, run, 'STARTED', config, version, {'config': config_path.name})
            connection.commit()

            cursor.execute('''
                select position_exceptions, late_records
                from broker_reconciliation_summary where statement_date = %s::date
            ''', (config.get('broker_statement_date', config['business_date']),))
            control = cursor.fetchone()
            if control is None:
                raise ValueError('No broker reconciliation is available for the publication date')
            if control[0] and not config.get('exception_review_note'):
                raise ValueError('Position exceptions require an exception review note')

            cursor.execute('''
                select scenario_id, business_date, account_id, currency,
                       simplified_nav, calculation_basis
                from nav_candidates
                where business_date = %s::date and scenario_id = %s
                order by account_id, currency
            ''', (config['business_date'], config['scenario_id']))
            candidates = cursor.fetchall()
            if not candidates:
                raise ValueError('No NAV candidates found')

            digest = candidate_hash(candidates)
            cursor.execute('''
                select approval_id
                from nav_approvals
                where business_date = %s::date and scenario_id = %s
                  and candidate_hash = %s and decision = 'APPROVED'
                qualify row_number() over (order by reviewed_at desc, approval_id desc) = 1
            ''', (config['business_date'], config['scenario_id'], digest))
            approval = cursor.fetchone()
            if approval is None:
                raise ValueError('No recorded approval matches the current NAV candidate')
            approval_id = approval[0]

            cursor.execute('''
                select publication_id, account_id, currency, published_nav
                from current_nav_publications where business_date = %s::date
            ''', (config['business_date'],))
            previous = {(row[1], row[2]): row for row in cursor.fetchall()}
            changed = []
            for row in candidates:
                old = previous.get((row[2], row[3]))
                if old and Decimal(old[3]) != Decimal(row[4]):
                    changed.append((row, old))
            if changed and (not restatement_reason or not approved_by):
                raise ValueError('Changed published NAV requires a reason and approver')

            publications = []
            for scenario, day, account, currency, nav, basis in candidates:
                pub = publication_id(run, account, currency)
                cursor.execute('''
                    insert into nav_publications
                    (publication_id, run_id, scenario_id, business_date, account_id,
                     currency, published_nav, calculation_basis, replay_delivery_id,
                     price_delivery_id, broker_delivery_id, code_version, exception_review_note,
                     approval_id)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (pub, run, scenario, day, account, currency, nav, basis,
                      config['replay_delivery_id'], config['price_delivery_id'],
                      config['broker_delivery_id'], version,
                      config.get('exception_review_note'), approval_id))
                publications.append((account, currency, pub, Decimal(nav)))

            for row, old in changed:
                account, currency = row[2], row[3]
                replacement = next(item[2] for item in publications
                                   if item[0] == account and item[1] == currency)
                revised = Decimal(row[4])
                original = Decimal(old[3])
                restatement = 'nav-restatement-' + uuid4().hex
                cursor.execute('''
                    insert into nav_restatements
                    (restatement_id, original_publication_id, replacement_publication_id,
                     business_date, account_id, currency, original_nav, revised_nav,
                     nav_difference, reason, approved_by)
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (restatement, old[0], replacement, row[1], account, currency,
                      original, revised, revised - original, restatement_reason, approved_by))

            event(cursor, run, 'SUCCEEDED', config, version,
                  {'nav_rows': len(publications), 'position_exceptions': control[0],
                   'late_records': control[1], 'restatements': len(changed)})
            connection.commit()
            print(f'Published {len(publications)} immutable NAV rows: {run}')
            for account, currency, publication, nav in publications:
                print(f'  {account} {currency}: {nav} ({publication})')
            print(f'Reconciliation review recorded: {control[0]} exceptions, {control[1]} late records.')
            return run
    except Exception as error:
        connection.rollback()
        try:
            with connection.cursor() as cursor:
                event(cursor, run, 'FAILED', config, version, {'error': str(error)})
            connection.commit()
        except Exception:
            connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path,
                        default=ROOT / 'config/nav_publication_january.json')
    parser.add_argument('--restatement-reason')
    parser.add_argument('--approved-by')
    args = parser.parse_args()
    publish(args.config.resolve(), args.restatement_reason, args.approved_by)
