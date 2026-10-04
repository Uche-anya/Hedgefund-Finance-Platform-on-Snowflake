# CI/CD design

The project uses three Snowflake environments.

| Environment | Purpose | Database | dbt target |
| --- | --- | --- | --- |
| Development | Interactive work and manual investigation | `NORTHBRIDGE_DEV` | `dev` |
| CI | An isolated copy used to test one pull request | `NORTHBRIDGE_CI_PR_<number>` | `ci` |
| Production | The scheduled daily pipeline | `NORTHBRIDGE_PROD` | `prod` |

Development is allowed to change while code is being written. CI proves that a
proposed change can build against realistic Snowflake objects. Production only
receives code that has passed review and CI.

## What runs now

`.github/workflows/ci.yml` runs the following checks on every pull request and
every push to `main`:

1. Install the pinned Python and dbt packages.
2. Run the Python unit tests.
3. Parse every project YAML file.
4. Run `dbt parse`, which checks the model graph and Jinja without opening a
   Snowflake connection.

The workflow also contains an optional live Snowflake job for pull requests. It
is deliberately gated by the repository variable `SNOWFLAKE_CI_ENABLED`. The
job stays skipped until the CI role and OIDC service user have been created.

When enabled, the live job:

1. Gets a short-lived GitHub OIDC token. No Snowflake password or private key is
   stored in GitHub.
2. Clones `NORTHBRIDGE_CI_BASE` to `NORTHBRIDGE_CI_PR_<number>`.
3. Deploys a temporary native dbt project object.
4. Runs `dbt build --exclude tag:fixture` inside Snowflake.
5. Drops the pull-request database even if the build fails.

A Snowflake clone starts as a metadata operation, so CI gets an isolated copy
without paying to duplicate all table storage immediately. New or changed
micro-partitions created by the test are billed normally.

## GitHub settings needed for the live job

Create a GitHub environment named `ci`, then add:

| Kind | Name | Value |
| --- | --- | --- |
| Repository secret | `SNOWFLAKE_ACCOUNT` | `gxmgyta-fq45953` |
| Repository variable | `SNOWFLAKE_CI_BASE_DATABASE` | `NORTHBRIDGE_CI_BASE` |
| Repository variable | `SNOWFLAKE_CI_ENABLED` | `true`, but only after Snowflake setup |

The Snowflake OIDC service user must trust this exact GitHub subject:

```text
repo:Uche-anya/Hedgefund-Finance-Platform-on-Snowflake:environment:ci
```

GitHub supplies that subject because the live job uses the `ci` environment.
Snowflake matches it to the service user and gives the job a short-lived login.

## dbt environment files

`dbt/env.yml` supplies the database, role and warehouse for Snowflake-native dbt
runs. `dbt/dbt_projects_profiles.yml` defines the corresponding `dev`, `ci` and
`prod` targets. Source definitions read `DBT_SOURCE_DATABASE`, so a CI model
cannot accidentally read from development while writing to its pull-request
database.

The local dbt CLI continues to use `dbt/profiles.yml` and the developer's key.
The small `.github/dbt/profiles.yml` file only gives `dbt parse` the shape of a
connection. Its placeholder values are never used to connect.

## Next deployment step

The next infrastructure change is to create the CI role, warehouse, base
database and OIDC service user. After the live pull-request build is proven, add
a separate production workflow that deploys on merges to `main`. The production
job will use its own GitHub environment, OIDC user and deployment role; the
daily Snowflake task will continue to run under the production runtime role.
