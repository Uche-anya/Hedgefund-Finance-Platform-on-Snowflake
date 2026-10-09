"""Run Snowflake CLI with the password kept in Windows Credential Manager."""

import argparse
from getpass import getpass
import os
from pathlib import Path
import subprocess

from keyring.backends.Windows import WinVaultKeyring


ROOT = Path(__file__).resolve().parents[1]
SNOW = ROOT / '.venv' / 'cli' / 'Scripts' / 'snow.exe'
CONFIG = ROOT / '.secrets' / 'snowflake_cli.toml'
SERVICE = 'northbridge/snowflake-cli/gxmgyta-fq45953'
USER = 'CHIGGZY'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, help='run a SQL file')
    parser.add_argument('--query', help='run one SQL statement')
    args = parser.parse_args()
    if args.file and args.query:
        parser.error('use --file or --query, not both')
    if args.file and (not args.file.is_file() or args.file.suffix.lower() != '.sql'):
        parser.error('--file must point to an existing .sql file')
    if not SNOW.is_file() or not CONFIG.is_file():
        parser.error('Snowflake CLI or its local config is missing')

    vault = WinVaultKeyring()
    password = vault.get_password(SERVICE, USER)
    new_password = password is None
    if new_password:
        password = getpass('Snowflake password for CHIGGZY: ')
    if not password:
        parser.error('no password available')

    command = [str(SNOW), '--config-file', str(CONFIG)]
    if args.file:
        command += ['sql', '--enable-templating', 'NONE',
                    '--filename', str(args.file.resolve()),
                    '--connection', 'northbridge_admin', '--enhanced-exit-codes']
    elif args.query:
        command += ['sql', '--enable-templating', 'NONE', '--query', args.query,
                    '--connection', 'northbridge_admin', '--enhanced-exit-codes']
    else:
        command += ['connection', 'test', '--connection', 'northbridge_admin']

    env = os.environ.copy()
    env['SNOWFLAKE_CONNECTIONS_NORTHBRIDGE_ADMIN_PASSWORD'] = password
    del password
    print('Connecting as CHIGGZY. Approve the MFA push if Snowflake sends one.', flush=True)
    result = subprocess.run(command, env=env)
    if result.returncode == 0 and new_password:
        vault.set_password(SERVICE, USER,
                           env['SNOWFLAKE_CONNECTIONS_NORTHBRIDGE_ADMIN_PASSWORD'])
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
