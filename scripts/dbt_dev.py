"""Run dbt with the local encrypted key and Windows Credential Manager."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from dbt_key import KEY_PATH, USER, unlock_secret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['debug', 'build'], default='debug', nargs='?')
    parser.add_argument('--select', help='Optional dbt model selector, for example stg_executions')
    args = parser.parse_args()
    if args.select and args.command != 'build':
        parser.error('--select is only supported with build')

    root = Path(__file__).resolve().parent.parent
    executable = root / '.venv' / 'dbt' / 'Scripts' / 'dbt.exe'
    if not executable.exists():
        print('The project dbt environment is missing. See dbt/README.md.')
        return 2

    if not KEY_PATH.exists():
        print('Run scripts/dbt_key.py to prepare the encrypted key first.')
        return 2
    # dbt masks DBT_ENV_SECRET_* values. Nothing is prompted or written to .env.
    environment = os.environ.copy()
    environment.setdefault('NORTHBRIDGE_SNOWFLAKE_ACCOUNT', 'gxmgyta-fq45953')
    environment['NORTHBRIDGE_SNOWFLAKE_USER'] = USER
    environment['NORTHBRIDGE_DBT_KEY_PATH'] = str(KEY_PATH)
    environment.pop('DBT_ENV_SECRET_SNOWFLAKE_PASSWORD', None)
    environment['DBT_ENV_SECRET_DBT_KEY_PASSPHRASE'] = unlock_secret()
    command = [str(executable), args.command, '--project-dir', 'dbt', '--profiles-dir', 'dbt']
    if args.command == 'build':
        command.append('--fail-fast')
        if args.select:
            # Tests requiring unselected models wait for the full project build.
            command.extend(['--select', args.select, '--indirect-selection', 'cautious'])
    print('Connecting with the dedicated dbt key.')
    try:
        return subprocess.run(command, cwd=root, env=environment).returncode
    finally:
        environment.pop('DBT_ENV_SECRET_DBT_KEY_PASSPHRASE', None)


if __name__ == '__main__':
    raise SystemExit(main())
