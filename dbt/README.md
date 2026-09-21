# First dbt slice

## Current authentication: key pair

Password/MFA authentication below is historical and has been replaced at the
user's request. Follow [KEY_AUTH.md](KEY_AUTH.md) for the current setup and commands.
The helper no longer prompts for a password. The user confirmed service-user
registration, key authentication, and the live build: 5 models and 40 tests passed.
See [VALUATION.md](VALUATION.md) for the current model build command.

The initial three-model walkthrough below is retained as learning history.

dbt Core runs on your computer; Snowflake executes its SQL.
This slice uses one selected simulated delivery, starting from zero holdings.
It is not yet a daily carry-forward calculation or approved reporting product.

## Models and checks

- `models/sources.yml` names the existing raw tables.
- `stg_executions` and `stg_allocations` are views preparing each source.
- `portfolio_holdings` is a table summing signed allocation quantities.
- `source()` refers to raw tables; `ref()` refers to another dbt model.
- The 20 data checks cover IDs, dates, sides, quantities, relationships,
  allocation totals, empty deliveries and this sample's expected holdings.

Identical business-record repeats within the selected delivery are removed.
Conflicting records with the same ID fail uniqueness tests. Raw metadata remains
available via the delivery ID and business IDs. Invalid dates/numbers become
NULL and fail tests. Quantities allow up to 29 integer and nine fractional
digits; excess precision is rejected rather than rounded.

## Run from the repository root in PowerShell

Installed in `.venv/dbt`: dbt-core 1.12.2 and dbt-snowflake 1.12.1.
To reinstall, create that environment with `python -m venv .venv/dbt`, then:

```powershell
.\.venv\dbt\Scripts\python.exe -m pip install -r requirements-dbt.txt
.\.venv\dbt\Scripts\dbt.exe parse --project-dir dbt --profiles-dir dbt --no-partial-parse
```

Before connecting, run `snowflake/06_dbt_access.sql` in Snowsight, in order.
It grants the current user a dedicated role with raw SELECT and CREATE TABLE/VIEW
in DBT_DEV. Other user roles are not revoked; the build disables secondary roles.
This is a developer login, not an unattended production service identity.

The user confirmed native username/password sign-in with MFA push approval.
Run this helper yourself in an interactive PowerShell terminal:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py debug
```

The helper uses account gxmgyta-fq45953 and user CHIGGZY from the supplied evidence;
NORTHBRIDGE_SNOWFLAKE_ACCOUNT and NORTHBRIDGE_SNOWFLAKE_USER can override them.
Enter your password at the hidden terminal prompt, then approve the MFA push.
Do not send the password in chat. It is passed to dbt through a child-process
DBT_ENV_SECRET variable, which dbt masks in logs, and is not written to a file.
This is interactive development authentication, not unattended Airflow setup.
No account-level MFA caching settings have been changed.

After debug succeeds and you have reviewed the models, run:

For the first lesson, build only executions and tests that reference only that
model. This avoids querying the allocations view before we have built it:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select stg_executions
```

The helper uses dbt's cautious indirect test selection for selected builds.
Expect one view and eight data checks. Cross-model checks remain pending until
the full build. Inspect NORTHBRIDGE_DEV.DBT_DEV.STG_EXECUTIONS after success:
SIM-E001 / AAPL.US / BUY / 10 and SIM-E002 / AMZN.US / SELL / 5, both 2025-01-06.

When ready to build all three models and all checks:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build
```

After a successful build, query NORTHBRIDGE_DEV.DBT_DEV.PORTFOLIO_HOLDINGS.
Expect 2025-01-06: GROWTH/AAPL.US = 10 and HEDGE/AMZN.US = -5.
Use build, not just run: tests are required. A failed build is not a current
usable result even if an older holdings table remains. Publication is separate.

## Evidence

The user supplied dbt debug output ending in Connection test OK and All checks
passed for CHIGGZY with NORTHBRIDGE_DBT_DEV using username_password_mfa. This
confirms authenticated connectivity; it does not prove model execution or tests.

Initial connection attempt: dbt debug accepted configuration and dependencies,
then reached Snowflake and returned error 390190 about the SAML identity-provider
account parameter. externalbrowser was the wrong choice for the user's confirmed
native password and MFA push login. The profile now uses username_password_mfa;
the subsequent authenticated debug check passed after the user ran it locally.
No models or data tests were executed by this connection check. The account
endpoint was reachable after enabling network access for the command.

The user confirmed two raw rows in each table. Offline dbt parse and dependency
checks passed; all eight model/singular-test SQL files also passed an offline
Snowflake-dialect parse using sqlglot. None of these prove live SQL execution.
Role selection and authenticated connectivity are confirmed by user evidence.
Model execution and data tests remain UNVERIFIED.
The Python reference independently checked the expected sample holdings.

Deferred: opening positions, cash/NAV, corrections, scheduling and publication.
Do not sum all raw history or treat this first-day model as daily closing holdings.

References:
- https://docs.getdbt.com/reference/commands/parse
- https://docs.getdbt.com/reference/commands/build
- https://docs.getdbt.com/docs/local/connect-data-platform/snowflake-setup
