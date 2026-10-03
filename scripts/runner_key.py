"""Create or verify the encrypted private key used by the pipeline runner."""

import base64
import csv
import io
from pathlib import Path
import secrets
import subprocess

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from keyring.backends.Windows import WinVaultKeyring


ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = ROOT / '.secrets' / 'runner_private_key.p8'
SERVICE = 'northbridge/runner/gxmgyta-fq45953'
USER = 'NORTHBRIDGE_RUNNER_LOCAL'


def vault():
    return WinVaultKeyring()


def unlock_secret():
    value = vault().get_password(SERVICE, USER)
    if not value:
        raise RuntimeError('No runner-key secret found. Run scripts/runner_key.py.')
    return value


def setup():
    secret_store = vault()
    if KEY_PATH.exists():
        key = serialization.load_pem_private_key(
            KEY_PATH.read_bytes(), password=unlock_secret().encode())
    else:
        if secret_store.get_password(SERVICE, USER):
            raise RuntimeError('Runner secret exists but its private key is missing')
        KEY_PATH.parent.mkdir(exist_ok=True)
        identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
        sid = next(csv.reader(io.StringIO(identity.strip())))[1]
        subprocess.run([
            'icacls', str(KEY_PATH.parent), '/inheritance:r', '/grant:r',
            f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F',
        ], check=True, capture_output=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        secret = secrets.token_urlsafe(48)
        KEY_PATH.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(secret.encode())))
        secret_store.set_password(SERVICE, USER, secret)

    public = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    sql = f"""-- Generated public key only. The private key stays in .secrets.
USE ROLE ACCOUNTADMIN;

CREATE USER IF NOT EXISTS {USER}
    TYPE = SERVICE
    DEFAULT_ROLE = NORTHBRIDGE_RUNNER
    DEFAULT_WAREHOUSE = COMPUTE_WH
    DEFAULT_NAMESPACE = NORTHBRIDGE_DEV.OPERATIONS;
ALTER USER {USER} SET RSA_PUBLIC_KEY = '{public}';
GRANT ROLE NORTHBRIDGE_RUNNER TO USER {USER};

DESCRIBE USER {USER};
"""
    target = ROOT / 'snowflake' / '32_runner_key_access.sql'
    target.write_text(sql, encoding='utf-8')
    restored = serialization.load_pem_private_key(
        KEY_PATH.read_bytes(), password=unlock_secret().encode())
    if restored.public_key().public_numbers() != key.public_key().public_numbers():
        raise RuntimeError('Runner private key and saved secret do not match')
    print('Encrypted runner key and Windows Credential Manager secret verified.')
    print(f'Registration SQL: {target}')


if __name__ == '__main__':
    setup()
