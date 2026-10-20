"""Write Snowflake service-user SQL using the local public keys."""

import base64
from pathlib import Path


SECRETS = Path(__file__).resolve().parents[1] / ".secrets"


def public_key(name):
    value = (SECRETS / (name + ".pub")).read_text(encoding="ascii").strip()
    base64.b64decode(value, validate=True)
    return value


def main():
    users = (
        ("NORTHBRIDGE_INGEST_PROD", "northbridge_ingest_prod", "RAW"),
        ("NORTHBRIDGE_RELEASE_PROD", "northbridge_release_prod", "DBT_PROD"),
    )
    lines = ["USE ROLE SECURITYADMIN;"]
    for user, key_name, schema in users:
        role = "NORTHBRIDGE_INGEST_PROD" if schema == "RAW" else "NORTHBRIDGE_DBT_PROD"
        lines.append(
            "CREATE USER IF NOT EXISTS {} TYPE = SERVICE RSA_PUBLIC_KEY = '{}' "
            "DEFAULT_ROLE = {} DEFAULT_WAREHOUSE = COMPUTE_WH "
            "DEFAULT_NAMESPACE = NORTHBRIDGE_PROD.{};".format(
                user, public_key(key_name), role, schema
            )
        )
        lines.append("GRANT ROLE {} TO USER {};".format(role, user))
    path = SECRETS / "prod_users.sql"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Prepared", path)


if __name__ == "__main__":
    main()
