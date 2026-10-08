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
| `ci` environment secret | `SNOWFLAKE_ACCOUNT` | `gxmgyta-fq45953` |
| Repository variable | `SNOWFLAKE_CI_BASE_DATABASE` | `NORTHBRIDGE_CI_BASE` |
| Repository variable | `SNOWFLAKE_CI_ENABLED` | `true`, but only after Snowflake setup |

The Snowflake OIDC service user must trust this exact GitHub subject:

```text
repo:Uche-anya@108993926/Hedgefund-Finance-Platform-on-Snowflake@1379734472:environment:ci
```

GitHub supplies that subject because the account uses immutable owner and
repository IDs in its OIDC claims and the live job selects the `ci`
environment. Snowflake matches it to the service user and gives the job a
short-lived login.

## dbt environment files

`dbt/env.yml` supplies the database, role and warehouse for Snowflake-native dbt
runs. `dbt/dbt_projects_profiles.yml` defines the corresponding `dev`, `ci` and
`prod` targets. Source definitions read `DBT_SOURCE_DATABASE`, so a CI model
cannot accidentally read from development while writing to its pull-request
database.

The local dbt CLI continues to use `dbt/profiles.yml` and the developer's key.
The small `.github/dbt/profiles.yml` file only gives `dbt parse` the shape of a
connection. Its placeholder values are never used to connect.

## Live proof

Pull request 1 ran the complete CI path on 4 October 2026. The local checks
passed, GitHub authenticated to Snowflake with OIDC, and dbt completed 64 build
results with no warnings or errors. The cleanup step then dropped
`NORTHBRIDGE_CI_PR_1` successfully.

## Next deployment step

The production deployment workflow is defined in
`.github/workflows/deploy-production.yml`. It is disabled until the Terraform
foundations have been applied and the repository variable
`SNOWFLAKE_PROD_DEPLOY_ENABLED` is set to `true`.

After it is enabled, a reviewed merge to `main` deploys the dbt source to the
native project in `NORTHBRIDGE_PROD.OPERATIONS`. Deployment does not execute
the daily build or resume a task. The daily Snowflake task remains a separate
operational control owned by `NORTHBRIDGE_DBT_PROD`.

The `production` GitHub environment only accepts deployments from `main`. Its
OIDC service user has the deployment role, while the daily task uses a separate
runtime role. This stops a deployment workflow from becoming the day-to-day
data processing identity. GitHub required reviewers should also be enabled
when the repository plan supports that environment protection rule. On the
current plan, the disabled deployment switch is the manual release gate.

## Terraform ownership

`terraform/snowflake` manages durable account foundations:

- CI and production roles
- GitHub OIDC service users
- warehouses and resource monitors
- the production database and top-level schemas
- grants for deployment and runtime

Terraform does not manage dbt relations, raw table DDL, task SQL or the data
inside `NORTHBRIDGE_CI_BASE`. The CI base is a reviewed Snowflake clone and has
a different lifecycle from long-lived infrastructure.

Terraform stores shared state in the `northbridge-snowflake` workspace in the
`northbridge-fund-anya` HCP Terraform organization. The local wrapper supplies
those names on each run.
Pull requests run `terraform fmt` and `terraform validate` without opening the
remote state or connecting to Snowflake.

The current CI infrastructure definitions are in `terraform/snowflake/ci.tf`.
The CI base database is a reviewed data snapshot, so its clone and refresh
still need a separate operational procedure.

The account setup and GitHub `ci` environment are active. Set
`SNOWFLAKE_CI_ENABLED` only after checking the Terraform grants and CI base,
because that switch allows pull requests to spend Snowflake credits.
