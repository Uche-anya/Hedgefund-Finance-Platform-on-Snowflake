"""Create a local development key for the dbt service user once."""

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / ".secrets" / "northbridge_dbt.p8"
PUBLIC = ROOT / ".secrets" / "northbridge_dbt.pub"


def main():
    if KEY.exists() or PUBLIC.exists():
        raise SystemExit("dbt key already exists; refusing to replace it")
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    KEY.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    PUBLIC.write_text(base64.b64encode(public).decode("ascii"), encoding="ascii")
    print("Private key saved to", KEY)
    print("Public key saved to", PUBLIC)


if __name__ == "__main__":
    main()
