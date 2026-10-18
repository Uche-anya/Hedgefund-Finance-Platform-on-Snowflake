"""Create the TEST-only dbt key once; keep the private half out of Git."""

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".secrets" / "northbridge_ci_test.p8"
PUBLIC = ROOT / ".secrets" / "northbridge_ci_test.pub"


def create_key(private_path, public_path):
    if private_path.exists() or public_path.exists():
        raise SystemExit("Key already exists; refusing to replace it")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    public = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_path.write_text(base64.b64encode(public).decode("ascii"), encoding="ascii")
    print("Private key saved outside Git:", private_path)


def main():
    create_key(PRIVATE, PUBLIC)


if __name__ == "__main__":
    main()
