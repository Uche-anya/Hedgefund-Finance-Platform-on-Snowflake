# Local Snowflake CLI

The CLI has its own Python environment at .venv/snowflake-cli. Its version is
pinned in requirements-snowflake-cli.txt. To recreate the environment:

```powershell
python -m venv .venv/snowflake-cli
.\.venv\snowflake-cli\Scripts\python.exe -m pip install -r requirements-snowflake-cli.txt
.\.venv\snowflake-cli\Scripts\snow.exe --version
```

The environment's Scripts directory is added to this Windows user's PATH.
Open a fresh PowerShell window after installation. If using a terminal inside
VS Code, restart VS Code so it picks up the PATH change. Then run:

```powershell
snow --version
snow --help
```

The full executable path above also works immediately from the project root.
Moving the project requires updating the PATH entry and recreating the venv.

Installing the CLI does not configure a Snowflake connection or grant database
permissions. The existing dbt key uses NORTHBRIDGE_DBT_DEV; the setup scripts
require a separate connection authorised for their administrator roles.

[Official installation instructions](https://docs.snowflake.com/en/developer-guide/snowflake-cli/installation/installation)

## Personal setup connection

The named connection northbridge_admin uses account gxmgyta-fq45953, user
CHIGGZY, role SYSADMIN, warehouse COMPUTE_WH and NORTHBRIDGE_DEV.RAW.
Authentication is USERNAME_PASSWORD_MFA. No password is saved in its config,
and the default connection is unchanged. The name itself grants no privileges.

From the project root, run:

```powershell
python scripts/snow_admin.py
```

On first use, enter the Snowflake password at the hidden prompt and approve
the MFA push. After a successful command the helper saves the password in
Windows Credential Manager under northbridge/snowflake-cli/gxmgyta-fq45953,
user CHIGGZY. Later runs retrieve it automatically. It stays out of the CLI
config, command arguments, project files and shell history. The helper supplies
it to the CLI through the child process environment. MFA may still be required.
The helper uses the CLI's Python environment for its Windows keyring backend.
The existing dbt key connection is unchanged.

The user subsequently supplied Status OK for CHIGGZY using SYSADMIN.
To execute a SQL file with the same hidden password prompt:

```powershell
python scripts/snow_admin.py --file snowflake/12_historical_prices.sql
```

The helper records the filename, fingerprint, timestamps and CLI exit code in
data/admin_runs/. These records contain no passwords or console output. Exit code 0
means the CLI completed successfully; on failure, earlier DDL statements may
already have succeeded. Script 12 creates storage and grants, without loading
prices. The user confirmed exit code 0 for setup and the subsequent price load.

To replace a changed password, run `python scripts/snow_admin.py --refresh-password`.
It replaces the credential only after success. To remove it without connecting,
run `python scripts/snow_admin.py --forget-password`. A failed SQL command does
not erase an existing saved password or automatically rerun SQL.

The password-storage workflow is tested with a mock vault. The user confirmed
the successful load printed the Credential Manager password-saved message.
