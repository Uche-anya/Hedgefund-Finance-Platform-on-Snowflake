"""Run Northbridge Terraform with credentials kept outside the repository."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TF_DIR = ROOT / 'terraform' / 'snowflake'
SERVICE = 'northbridge/snowflake-cli/gxmgyta-fq45953'
USER = 'CHIGGZY'
PLAN_FILE = 'northbridge.tfplan'


def saved_password():
    from keyring.backends.Windows import WinVaultKeyring

    password = WinVaultKeyring().get_password(SERVICE, USER)
    if not password:
        raise SystemExit(
            'No saved Snowflake password. Run scripts/snow_admin.py first.'
        )
    return password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('terraform_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.terraform_args:
        parser.error('provide a Terraform command, for example: plan')

    terraform = shutil.which('terraform')
    if not terraform:
        raise SystemExit('Terraform is not installed or is not on PATH.')

    terraform_args = list(args.terraform_args)
    if terraform_args == ['plan']:
        terraform_args.append(f'-out={PLAN_FILE}')
    elif terraform_args == ['apply']:
        terraform_args.append(PLAN_FILE)

    environment = os.environ.copy()
    environment['TF_CLOUD_ORGANIZATION'] = 'northbridge-fund-anya'
    environment['TF_WORKSPACE'] = 'northbridge-snowflake'
    environment['SNOWFLAKE_PASSWORD'] = saved_password()

    command = [terraform, f'-chdir={TF_DIR}', *terraform_args]
    print('Using HCP workspace: northbridge-fund-anya/northbridge-snowflake')
    print('Using the Snowflake password saved in Windows Credential Manager.')
    print('Terraform command:', ' '.join(terraform_args))
    print('Approve a Snowflake MFA notification if one arrives.', flush=True)
    try:
        return subprocess.run(command, cwd=ROOT, env=environment).returncode
    finally:
        environment.pop('SNOWFLAKE_PASSWORD', None)


if __name__ == '__main__':
    python = ROOT / '.venv' / 'snowflake-cli' / 'Scripts' / 'python.exe'
    if Path(sys.executable).resolve() != python.resolve():
        if not python.is_file():
            raise SystemExit('Snowflake CLI environment is missing.')
        command = [str(python), str(Path(__file__).resolve()), *sys.argv[1:]]
        raise SystemExit(subprocess.run(command, cwd=ROOT).returncode)
    raise SystemExit(main())
