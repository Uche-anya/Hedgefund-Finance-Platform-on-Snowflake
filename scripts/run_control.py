"""Register a controlled run in Snowflake and record each pipeline step."""

import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
RUNNER_KEY_PATH = ROOT / '.secrets' / 'runner_private_key.p8'
RUNNER_USER = 'NORTHBRIDGE_RUNNER_LOCAL'


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_count(manifest):
    if 'record_count' in manifest:
        return int(manifest['record_count'])
    if 'row_count' in manifest:
        return int(manifest['row_count'])
    if 'counts' in manifest:
        return sum(int(value) for value in manifest['counts'].values())
    if 'actions' in manifest and 'reviews' in manifest:
        return int(manifest['actions']) + int(manifest['reviews'])
    raise ValueError('Manifest has no supported row count')


def code_version(root):
    paths = [root / 'dbt/dbt_project.yml', root / 'scripts/load_daily_inputs.py',
             root / 'scripts/dbt_dev.py', root / 'scripts/run_control.py']
    for folder in ('dbt/models', 'dbt/tests', 'dbt/seeds'):
        paths.extend(sorted((root / folder).rglob('*')))
    digest = hashlib.sha256()
    for path in paths:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def read_config(path, root=ROOT):
    config = json.loads(path.read_text(encoding='utf-8'))
    if config.get('run_mode') not in ('DAILY', 'REPLAY'):
        raise ValueError('run_mode must be DAILY or REPLAY')
    date.fromisoformat(config['business_date'])
    datetime.fromisoformat(config['calculation_cutoff'].replace('Z', '+00:00'))
    if not config.get('inputs'):
        raise ValueError('Run has no inputs')

    names = set()
    checked = []
    for item in config['inputs']:
        name = item['source_name']
        if name in names:
            raise ValueError(f'Duplicate source name: {name}')
        names.add(name)
        manifest_path = (root / item['manifest']).resolve()
        if root.resolve() not in manifest_path.parents:
            raise ValueError(f'Manifest is outside the project: {name}')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        delivery = item['delivery_id']
        stated_delivery = manifest.get('delivery_id', manifest.get('load_id'))
        if stated_delivery is None:
            stated_delivery = manifest_path.parent.name
        if stated_delivery != delivery:
            raise ValueError(f'{name} delivery ID differs from its manifest')
        rows = manifest_count(manifest)
        if rows != int(item['expected_rows']):
            raise ValueError(f'{name} has {rows} manifest rows; expected {item["expected_rows"]}')
        checked.append({
            'source_name': name,
            'delivery_id': delivery,
            'manifest_sha256': file_hash(manifest_path),
            'expected_rows': rows,
        })

    config['checked_inputs'] = sorted(checked, key=lambda value: value['source_name'])
    config['code_version'] = code_version(root)
    identity = {
        'run_mode': config['run_mode'],
        'business_date': config['business_date'],
        'calculation_cutoff': config['calculation_cutoff'],
        'scenario_id': config.get('scenario_id'),
        'code_version': config['code_version'],
        'inputs': config['checked_inputs'],
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()
    config['run_id'] = 'northbridge-run-' + hashlib.sha256(encoded).hexdigest()[:24]
    config['_config_path'] = str(path.resolve())
    return config


def connect():
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    try:
        from scripts.runner_key import unlock_secret
    except ModuleNotFoundError:
        from runner_key import unlock_secret
    secret = unlock_secret()
    key = serialization.load_pem_private_key(
        RUNNER_KEY_PATH.read_bytes(), password=secret.encode())
    del secret
    private_key = key.private_bytes(serialization.Encoding.DER,
                                    serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
    connection = snowflake.connector.connect(
        account='gxmgyta-fq45953', user=RUNNER_USER, private_key=private_key,
        authenticator='SNOWFLAKE_JWT', role='NORTHBRIDGE_RUNNER',
        warehouse='COMPUTE_WH', database='NORTHBRIDGE_DEV', schema='OPERATIONS',
        autocommit=False,
        session_parameters={'QUERY_TAG': 'northbridge_run_control'})
    del private_key, key
    return connection


def register(cursor, config):
    run_id = config['run_id']
    cursor.execute('select count(*) from runs where run_id = %s', (run_id,))
    count = cursor.fetchone()[0]
    if count > 1:
        raise ValueError(f'Duplicate run definition in Snowflake: {run_id}')
    if count == 0:
        cursor.execute('''
            insert into runs
            (run_id, run_mode, business_date, calculation_cutoff, scenario_id, code_version)
            select %s, %s, %s::date, %s::timestamp_tz, %s, %s
        ''', (run_id, config['run_mode'], config['business_date'],
              config['calculation_cutoff'], config.get('scenario_id'), config['code_version']))
        for item in config['checked_inputs']:
            cursor.execute('''
                insert into run_inputs
                (run_id, source_name, delivery_id, manifest_sha256, expected_rows)
                select %s, %s, %s, %s, %s
            ''', (run_id, item['source_name'], item['delivery_id'],
                  item['manifest_sha256'], item['expected_rows']))
        return True

    cursor.execute('''
        select source_name, delivery_id, manifest_sha256, expected_rows
        from run_inputs where run_id = %s order by source_name
    ''', (run_id,))
    saved = [dict(source_name=row[0], delivery_id=row[1], manifest_sha256=row[2],
                  expected_rows=int(row[3])) for row in cursor.fetchall()]
    if saved != config['checked_inputs']:
        raise ValueError(f'Saved inputs differ for existing run: {run_id}')
    return False


def next_attempt(cursor, run_id):
    cursor.execute('select coalesce(max(attempt_number), 0) + 1 from run_events where run_id = %s',
                   (run_id,))
    return int(cursor.fetchone()[0])


def event(cursor, run_id, attempt, step, event_type, details=None):
    cursor.execute('''
        insert into run_events
        (event_id, run_id, attempt_number, step_name, event_type, details)
        select %s, %s, %s, %s, %s, parse_json(%s)
    ''', (uuid4().hex, run_id, attempt, step, event_type,
          json.dumps(details or {}, sort_keys=True)))


def commands(config, root=ROOT):
    python = root / '.venv/dbt/Scripts/python.exe'
    if not python.is_file():
        raise FileNotFoundError('The dbt Python environment is missing')
    executable = str(python)
    variables = json.dumps(config['dbt_vars'], separators=(',', ':'))
    return [
        ('load_inputs', [executable, 'scripts/load_daily_inputs.py',
                         '--config', config['_config_path']]),
        ('dbt_build', [executable, 'scripts/dbt_dev.py', 'build',
                       '--exclude', 'tag:fixture', '--vars', variables]),
        ('check_financials', [executable, 'scripts/check_replay.py']),
        ('check_positions', [executable, 'scripts/check_broker_reconciliation.py']),
        ('check_extended_sources', [executable, 'scripts/check_extended_sources.py']),
    ]


def run(config_path, register_only=False, root=ROOT):
    config = read_config(config_path, root)
    connection = connect()
    run_id = config['run_id']
    attempt = None
    try:
        with connection.cursor() as cursor:
            cursor.execute('use secondary roles none')
            created = register(cursor, config)
            connection.commit()
            print(('Registered' if created else 'Found') + f' run: {run_id}')
            if register_only:
                return 0
            attempt = next_attempt(cursor, run_id)
            event(cursor, run_id, attempt, 'pipeline', 'STARTED')
            connection.commit()
            for name, command in commands(config, root):
                print(f'\n{name}', flush=True)
                event(cursor, run_id, attempt, name, 'STARTED')
                connection.commit()
                result = subprocess.run(command, cwd=root)
                status = 'SUCCEEDED' if result.returncode == 0 else 'FAILED'
                event(cursor, run_id, attempt, name, status,
                      {'exit_code': result.returncode})
                connection.commit()
                if result.returncode:
                    event(cursor, run_id, attempt, 'pipeline', 'FAILED',
                          {'failed_step': name, 'exit_code': result.returncode})
                    connection.commit()
                    return result.returncode
            event(cursor, run_id, attempt, 'pipeline', 'SUCCEEDED')
            connection.commit()
            print(f'Controlled run succeeded: {run_id}, attempt {attempt}')
            return 0
    except KeyboardInterrupt:
        try:
            if attempt is not None:
                with connection.cursor() as cursor:
                    event(cursor, run_id, attempt, 'pipeline', 'INTERRUPTED')
                    connection.commit()
        finally:
            return 130
    except Exception as error:
        connection.rollback()
        if attempt is not None:
            with connection.cursor() as cursor:
                event(cursor, run_id, attempt, 'pipeline', 'FAILED', {'error': str(error)})
                connection.commit()
        raise
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path,
                        default=ROOT / 'config/controlled_replay_february.json')
    parser.add_argument('--register-only', action='store_true')
    args = parser.parse_args()
    return run(args.config.resolve(), args.register_only)


if __name__ == '__main__':
    raise SystemExit(main())
