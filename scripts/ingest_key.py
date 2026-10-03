"""Create or verify the encrypted private key used by the local ingestion user."""

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
KEY_PATH = ROOT / '.secrets' / 'ingest_private_key.p8'
SERVICE = 'northbridge/ingest/gxmgyta-fq45953'
USER = 'NORTHBRIDGE_INGEST_LOCAL'


def vault():
    return WinVaultKeyring()


def unlock_secret():
    value = vault().get_password(SERVICE, USER)
    if not value:
        raise RuntimeError('No ingestion-key secret found. Run scripts/ingest_key.py.')
    return value


def write_access_sql(public_key):
    sql = f"""-- Generated public key only. The private key stays in .secrets.
USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS NORTHBRIDGE_INGEST;
GRANT ROLE NORTHBRIDGE_INGEST TO ROLE SYSADMIN;

CREATE USER IF NOT EXISTS {USER}
    TYPE = SERVICE
    DEFAULT_ROLE = NORTHBRIDGE_INGEST
    DEFAULT_WAREHOUSE = COMPUTE_WH
    DEFAULT_NAMESPACE = NORTHBRIDGE_DEV.RAW;
ALTER USER {USER} SET RSA_PUBLIC_KEY = '{public_key}';
GRANT ROLE NORTHBRIDGE_INGEST TO USER {USER};

GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE NORTHBRIDGE_INGEST;
GRANT USAGE ON DATABASE NORTHBRIDGE_DEV TO ROLE NORTHBRIDGE_INGEST;
GRANT USAGE ON SCHEMA NORTHBRIDGE_DEV.RAW TO ROLE NORTHBRIDGE_INGEST;

GRANT SELECT, INSERT ON TABLE NORTHBRIDGE_DEV.RAW.REPLAY_INPUTS TO ROLE NORTHBRIDGE_INGEST;
GRANT SELECT, INSERT ON TABLE NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS TO ROLE NORTHBRIDGE_INGEST;
GRANT READ, WRITE ON STAGE NORTHBRIDGE_DEV.RAW.REPLAY_STAGE TO ROLE NORTHBRIDGE_INGEST;
GRANT READ, WRITE ON STAGE NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS_STAGE TO ROLE NORTHBRIDGE_INGEST;
GRANT USAGE ON FILE FORMAT NORTHBRIDGE_DEV.RAW.REPLAY_JSON TO ROLE NORTHBRIDGE_INGEST;
GRANT USAGE ON FILE FORMAT NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS_JSON TO ROLE NORTHBRIDGE_INGEST;
"""
    target = ROOT / 'snowflake' / '27_ingest_key_access.sql'
    target.write_text(sql, encoding='utf-8')
    return target


def setup():
    secret_store = vault()
    if KEY_PATH.exists():
        key = serialization.load_pem_private_key(
            KEY_PATH.read_bytes(), password=unlock_secret().encode())
    else:
        if secret_store.get_password(SERVICE, USER):
            raise RuntimeError('Ingestion key secret exists but the key file is missing')
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
    restored = serialization.load_pem_private_key(
        KEY_PATH.read_bytes(), password=unlock_secret().encode())
    if restored.public_key().public_numbers() != key.public_key().public_numbers():
        raise RuntimeError('Ingestion private key and saved secret do not match')
    target = write_access_sql(public)
    print('Encrypted ingestion key and Windows Credential Manager secret verified.')
    print(f'Bootstrap SQL: {target}')


if __name__ == '__main__':
    setup()
