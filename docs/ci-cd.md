# Environments and releases

The scheduled producer and Snowflake tasks process each market day's **data**.
CI checks a proposed **code** change. These are different runs: passing CI
does not mean a daily close was delivered or validated.

| Environment | Job | Current state |
| --- | --- | --- |
| `NORTHBRIDGE_DEV` | Develop and operate the current daily close | RAW deliveries, native dbt project and scheduled tasks are running |
| `NORTHBRIDGE_TEST` | Check candidate dbt code on isolated inputs | October 16 RAW fixture, dbt models and TEST-only service user; local and native dbt builds passed |
| `NORTHBRIDGE_PROD` | Intended destination for an approved release | Database, schemas and roles only; no daily data, dbt project or tasks |

## What CI does

Pull requests run Python tests and parse the dbt project for DEV, TEST and
PROD. Parsing catches configuration errors but does not query Snowflake. PR
code receives no Snowflake credential.

After a merge to `main`, the same workflow runs `dbt build --target test`
against the isolated October 16 fixture. This executes the models and data
tests in Snowflake. The GitHub `ci` environment is limited to `main` and
contains a key for `NORTHBRIDGE_CI_TEST`. That Snowflake user has only the
`NORTHBRIDGE_DBT_TEST` role. It cannot deploy to DEV or PROD. The fixture is
static: this check proves the code works for that known case, not for every
future delivery.

The TEST key was generated with `python -m scripts.create_ci_test_key`.
Its public half was assigned to the Snowflake service user; its private half
is excluded from Git and stored as the `ci` environment secret
`NORTHBRIDGE_CI_TEST_KEY_B64` (base64 of the PEM file). Rotate the key by
creating a replacement, assigning the new public key to that user, updating
the environment secret and testing a connection before retiring the old key.

TEST was set up with [21_test_environment.sql](../snowflake/21_test_environment.sql).
The local TEST build passed 12 models and 34 data tests. A native Snowflake
dbt deployment and run also passed. TEST has no schedule and receives no
daily producer deliveries.

## Deploying code

The native dbt deployment command now requires an explicit environment:

```powershell
python -m scripts.deploy_dbt_project --target dev
python -m scripts.deploy_dbt_project --target test
```

It checks the Snowflake role and required RAW tables before uploading. The
native runner also requires `--target`. These commands are currently run by
an operator; the merge does not automatically deploy DEV. The daily tasks
continue to use the previously deployed DEV project until that happens.

PROD is deliberately gated. Its RAW tables, loader, grants, dbt project,
producer routing, task graph and own service identity still need to be built
and tested. Pointing a TEST job at a database named PROD would not produce a
working production pipeline. Do not copy the live DEV schedules into PROD.

## Release work still open

1. Make DEV deployment reproducible from a reviewed commit and record the
   deployed commit SHA. Verify its native dbt build before the next close.
2. Build independent PROD ingestion and tasks. Promote the *same* commit that
   passed TEST through a reviewed GitHub `production` environment.
3. Protect `main` with required checks and review. The environment names alone
   do not enforce this, and `main` is not protected today.
4. Rehearse a normal close, an input failure and rollback in PROD. For rollback,
   redeploy the prior reviewed commit; preserve RAW delivery history and assess
   any affected close before rerunning it.

The GitHub `production` environment exists but has no PROD deployment
credential or approval rule. This project should be described as an operating
DEV pipeline with isolated TEST integration, not as a completed PROD release.
