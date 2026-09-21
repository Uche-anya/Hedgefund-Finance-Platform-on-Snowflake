"""Local encrypted dbt key; the unlock secret lives in Windows Credential Manager."""

import base64
import csv
import io
from pathlib import Path
import secrets
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from keyring.backends.Windows import WinVaultKeyring

ROOT = Path(__file__).resolve().parent.parent
KEY_PATH = ROOT / '.secrets' / 'dbt_private_key.p8'
SERVICE = 'northbridge/dbt/gxmgyta-fq45953'
USER = 'NORTHBRIDGE_DBT_LOCAL'


def unlock_secret():
    value = WinVaultKeyring().get_password(SERVICE, USER)
    if not value:
        raise RuntimeError('No dbt key secret found for this Windows user. Run scripts/dbt_key.py.')
    return value


def setup():
    vault = WinVaultKeyring()
    if KEY_PATH.exists():
        key = serialization.load_pem_private_key(
            KEY_PATH.read_bytes(), password=unlock_secret().encode()
        )
    else:
        if vault.get_password(SERVICE, USER):
            raise RuntimeError('A key secret already exists but the key file is missing. Stop and recover it.')
        KEY_PATH.parent.mkdir(exist_ok=True)
        identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
        sid = next(csv.reader(io.StringIO(identity.strip())))[1]
        # Limit the new secrets folder to this Windows user and SYSTEM.
        subprocess.run([
            'icacls', str(KEY_PATH.parent), '/inheritance:r', '/grant:r',
            f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F',
        ], check=True, capture_output=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        secret = secrets.token_urlsafe(48)
        encrypted = key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(secret.encode()),
        )
        vault.set_password(SERVICE, USER, secret)
        with KEY_PATH.open('xb') as handle:
            handle.write(encrypted)

    public = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )).decode()
    sql = (
        '-- Public key only. Run once in Snowsight. Stop if the user already exists.\n'
        'USE ROLE ACCOUNTADMIN;\n\n'
        f'CREATE USER {USER}\n'
        '    TYPE = SERVICE\n'
        f"    RSA_PUBLIC_KEY = '{public}'\n"
        "    DEFAULT_ROLE = 'NORTHBRIDGE_DBT_DEV'\n"
        "    DEFAULT_WAREHOUSE = 'COMPUTE_WH';\n\n"
        f'GRANT ROLE NORTHBRIDGE_DBT_DEV TO USER {USER};\n\n'
        f'DESCRIBE USER {USER};\n'
    )
    target = ROOT / 'snowflake' / '07_dbt_key_access.sql'
    target.write_text(sql, encoding='utf-8')
    # Verify the encrypted file and vault secret match, without exposing either.
    restored = serialization.load_pem_private_key(
        KEY_PATH.read_bytes(), password=unlock_secret().encode()
    )
    assert restored.public_key().public_numbers() == key.public_key().public_numbers()
    print('Encrypted key and Windows Credential Manager secret verified.')
    print('Public-key registration SQL:', target)
    print('Snowflake registration and connection are still pending.')


if __name__ == '__main__':
    setup()
