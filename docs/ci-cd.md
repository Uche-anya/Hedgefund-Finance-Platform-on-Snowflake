# CI/CD for the daily close

The scheduled producer and Snowflake task graph run **data** for each market day.
CI/CD changes the **code and Snowflake objects** that those jobs run. A green
pull-request check is not proof that a daily close ran.

## What exists today

The live pipeline runs in `NORTHBRIDGE_DEV`. Pull requests run Python tests and
an offline dbt parse. The parse catches project/Jinja configuration errors; it
does not execute SQL, read RAW data, or verify Snowflake permissions. The daily
Snowflake task graph is deployed separately. The GitHub `production`
environment exists, but there is no production Snowflake database, deployment
identity, or production task graph. `main` is not yet protected by required
checks or review. We should not call the current workflow production CD.

## Release path

| Point | What runs | Pass condition |
| --- | --- | --- |
| Pull request | Python tests, offline dbt parse | Code is internally consistent; no Snowflake credential is exposed to PR code |
| Integration | Build the candidate dbt project in an isolated Snowflake CI schema using a controlled input fixture | dbt models and data tests pass against Snowflake; no write to the daily schema |
| Merge to `main` | Deploy the reviewed commit to development, then run a smoke build in a separate schema | The deployed commit and tested commit match |
| Production promotion | Approve the same commit in the GitHub `production` environment; test a release candidate with a production-only identity, then deploy outside the close window | Candidate build/test passes before the scheduled task can use the new version |
| Next market day | Scheduled producer, Snowpipe/COPY, readiness/build/record tasks, deadline check | One validated close per account and complete delivery evidence |

Integration and production deployment are **not implemented yet**. They need
separate Snowflake objects and credentials, not another job that points to
`NORTHBRIDGE_DEV`. The production environment should have its own RAW and dbt
schemas, service roles, warehouse/resource monitor and task graph. The dbt
profile, source database, deployment script and task SQL currently name DEV;
each must be made environment-specific before promotion is enabled.

The CI identity should write only to its test schema. The deploy identity
should own the dbt project object; it should not be the data-loader identity.
Use a short-lived GitHub OIDC identity for CI/deployment if configured in the
Snowflake account. Keep the Massive and loader credentials in the daily
producer's environment, separate from code deployment. Restrict production
promotion to `main`, require review, and make the passing integration check a
required branch check. GitHub environment names alone do not enforce these
rules.

Deploy the exact tested commit SHA. Record the SHA and dbt project version in
the release log. For rollback, redeploy the prior reviewed SHA and rerun the
affected date only after checking the delivery registry and close status;
never delete RAW deliveries to make a retry pass. Schema migrations need an
explicit compatibility and rollback review before promotion.

## Next implementation slice

1. Provision an isolated Snowflake CI schema and test identity. Run `dbt build`
   there on a controlled fixture in PRs from trusted branches. Forked PRs
   should remain credential-free.
2. Parameterize dbt sources, project profiles, deployment script and task SQL
   for DEV and PROD. Provision PROD separately; do not clone live schedules.
3. Add DEV deployment on `main` and a manual, approved PROD promotion for the
   same commit. Turn on required checks and branch protection only after the
   integration job is stable.
4. Prove one normal daily close and one failed-input incident in PROD before
   describing the release path as operational.
