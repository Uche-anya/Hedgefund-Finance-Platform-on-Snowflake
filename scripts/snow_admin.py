"""Test the personal Snowflake connection or run a SQL file with a hidden login."""

import argparse
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SERVICE = 'northbridge/snowflake-cli/gxmgyta-fq45953'
USER = 'CHIGGZY'


def prepare_dbt_source(root):
    """Copy only deployable dbt source; leave local target and logs behind."""
    source = root / 'dbt'
    target = root / 'data' / 'dbt_deploy'
    data_root = (root / 'data').resolve()
    if target.resolve().parent != data_root:
        raise RuntimeError('Unsafe dbt deployment directory')
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in ('models', 'tests', 'seeds', 'macros'):
        shutil.copytree(source / name, target / name)
    for name in ('dbt_project.yml', 'dbt_projects_profiles.yml', 'env.yml'):
        shutil.copy2(source / name, target / name)
    return target


def credential_store():
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--file', type=Path, help='SQL file to execute instead of testing the connection')
    action.add_argument('--deploy-dbt', action='store_true',
                        help='Deploy dbt/ as the NORTHBRIDGE_DBT native project')
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--refresh-password', action='store_true', help='Prompt for a replacement password')
    options.add_argument('--forget-password', action='store_true', help='Delete the saved password and exit')
    args = parser.parse_args()
    if args.forget_password and (args.file or args.deploy_dbt):
        parser.error('--forget-password cannot be combined with another action')
    root = ROOT
    vault = credential_store()
    if args.forget_password:
        if vault.get_password(SERVICE, USER) is not None:
            vault.delete_password(SERVICE, USER)
        print('Saved administrator password removed from Windows Credential Manager.')
        return 0
    snow = root / '.venv/snowflake-cli/Scripts/snow.exe'
    if not snow.is_file():
        raise SystemExit('Snowflake CLI is missing. See snowflake/CLI.md.')

    command = [str(snow), 'connection', 'test']
    record = {'connection': 'northbridge_admin', 'operation': 'connection_test'}
    if args.file:
        sql_file = args.file.resolve()
        if not sql_file.is_file() or sql_file.suffix.lower() != '.sql':
            parser.error('--file must point to an existing SQL file')
        record.update(operation='sql_file', file=str(sql_file),
                      sha256=hashlib.sha256(sql_file.read_bytes()).hexdigest())
        command = [str(snow), 'sql', '--filename', str(sql_file), '--enhanced-exit-codes']
        print(f'Running SQL file: {sql_file}', flush=True)
    elif args.deploy_dbt:
        dbt_source = prepare_dbt_source(root)
        command = [
            str(snow), 'dbt', 'deploy', 'NORTHBRIDGE_DBT',
            '--source', str(dbt_source),
            '--default-target', 'dev',
            '--default-env', 'dev',
            '--dbt-version', '1.12.3',
            '--database', 'NORTHBRIDGE_DEV',
            '--schema', 'OPERATIONS',
            '--enhanced-exit-codes',
        ]
        record.update(operation='deploy_dbt', source=str(dbt_source))
        print('Deploying native dbt project: NORTHBRIDGE_DEV.OPERATIONS.NORTHBRIDGE_DBT',
              flush=True)
    command.extend(['--connection', 'northbridge_admin'])

    password = None if args.refresh_password else vault.get_password(SERVICE, USER)
    remember_password = not password
    if remember_password:
        password = getpass('Snowflake password for CHIGGZY (hidden; saved after success): ')
    else:
        print('Using the password saved in Windows Credential Manager.', flush=True)
    if not password:
        raise SystemExit('No password entered.')
    environment = os.environ.copy()
    variable = 'SNOWFLAKE_CONNECTIONS_NORTHBRIDGE_ADMIN_PASSWORD'
    environment[variable] = password
    environment['PYTHONUTF8'] = '1'
    del password
    print('Approve the Snowflake MFA push when it arrives.', flush=True)
    record['started_at_utc'] = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(command, cwd=root, env=environment)
        record['exit_code'] = result.returncode
        record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        folder = root / 'data/admin_runs'
        folder.mkdir(parents=True, exist_ok=True)
        report = folder / (uuid4().hex + '.json')
        report.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(f'CLI exit code: {result.returncode}. Run record: {report}')
        if result.returncode == 0 and remember_password:
            try:
                vault.set_password(SERVICE, USER, environment[variable])
                print('Password saved in Windows Credential Manager.')
            except Exception:
                print('The command succeeded, but saving the password failed. It will be requested again.')
        elif result.returncode != 0:
            print('No new password saved. If your password changed, use --refresh-password.')
        return result.returncode
    finally:
        environment.pop(variable, None)


if __name__ == '__main__':
    # Use the CLI environment, which already includes the Windows keyring backend.
    python = ROOT / '.venv/snowflake-cli/Scripts/python.exe'
    if Path(sys.executable).resolve() != python.resolve():
        if not python.is_file():
            raise SystemExit('Snowflake CLI environment is missing. See snowflake/CLI.md.')
        raise SystemExit(subprocess.run([str(python), str(Path(__file__).resolve()), *sys.argv[1:]]).returncode)
    raise SystemExit(main())
