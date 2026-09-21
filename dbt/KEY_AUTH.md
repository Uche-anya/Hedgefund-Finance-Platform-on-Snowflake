# Password-free dbt on this Windows computer

dbt now uses an encrypted RSA key and a dedicated Snowflake SERVICE user,
NORTHBRIDGE_DBT_LOCAL. The registration SQL grants NORTHBRIDGE_DBT_DEV only;
no admin role is granted. The user's ordinary CHIGGZY login and MFA are unchanged.

## One-time Snowflake setup

The encrypted private key is prepared in `.secrets/dbt_private_key.p8` and ignored
by Git. Its generated unlock secret is in Windows Credential Manager, under
service `northbridge/dbt/gxmgyta-fq45953`, username `NORTHBRIDGE_DBT_LOCAL`.
The key folder is owned by the Windows user UCHE and restricted to that user
and SYSTEM. Local key decryption using the stored secret was verified.

1. Open `snowflake/07_dbt_key_access.sql` and run it in Snowsight in order.
   It contains only the public key. It creates a service user and grants the
   existing project role. Stop if CREATE USER says the user already exists;
   do not overwrite an existing user's authentication. The role from
   `06_dbt_access.sql` must already exist.
2. Run the connection check from the project root in your normal PowerShell:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py debug
```

Expect Connection test OK and All checks passed. No password prompt or MFA push
is needed for this key login. No Snowflake password is stored by this setup.

3. After connection success, build the first model:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select stg_executions
```

Expect one view and eight tests. Allocation and holdings checks wait until the
full build. Run `scripts/dbt_dev.py build` without --select for the full project
when ready. Both commands use the Python executable shown above.

## How it works

The private key signs the connection request; Snowflake checks the signature
against the public key registered on the dedicated service user. The private key
is not sent to Snowflake. The helper retrieves the unlock secret from the Windows
vault and passes it through a DBT_ENV_SECRET child-process variable, masked by dbt.
It does not save the secret in `.env` or a project configuration file.

Applications running under your Windows identity can use the stored credential.
This is local secret storage, not a production secret manager. Airflow on another
host needs separately provisioned credentials. Key rotation is still future work.
An administrator can revoke this login with:

```sql
ALTER USER NORTHBRIDGE_DBT_LOCAL SET DISABLED = TRUE;
```

## Reproducibility and recovery

`scripts/dbt_key.py` creates the local encrypted key and public registration SQL.
It reuses an existing decryptable key rather than rotating it. It refuses to
replace a vault secret when the private file is missing. Run it using the project
Python and the same Windows login. Do not copy private files into source control.
If setup fails halfway through, inspect file/vault state before retrying.

The first attempt inside the sandbox could not access a Windows credential
session. Setup then succeeded under UCHE; folder ownership and permissions were
corrected before key creation. No private key or unlock secret was printed.

Live service-user registration, key authentication and model builds are pending.
Earlier password/MFA debug success does not establish key-authentication success.

References:
- https://docs.snowflake.com/en/user-guide/key-pair-auth
- https://docs.snowflake.com/en/sql-reference/sql/create-user
- https://docs.getdbt.com/reference/dbt-jinja-functions/env_var#secrets
