# Environments and releases

Producer and Snowflake tasks process each market day's **data**. CI checks a
proposed **code** change. These are different runs: passing CI does not mean
a daily close was delivered or validated.

| Environment | Job | Current state |
| --- | --- | --- |
| `NORTHBRIDGE_DEV` | Develop and manually exercise the daily close | RAW deliveries and native dbt project exist; GitHub cron triggers were removed and Snowflake root/deadline tasks are suspended |
| `NORTHBRIDGE_TEST` | Check candidate code and rehearse deliveries | October 16 CI fixture plus a separate October 6 first-day delivery; no schedule |
| `NORTHBRIDGE_PROD` | Destination for approved code and the unattended daily close | Separate loader and release users; manual October 16 and 19 closes validated; schedules are off |

## What CI does

Pull requests run Python tests and parse the dbt project for DEV, TEST and
PROD. Parsing catches configuration errors but does not query Snowflake.
Pull request code does not receive a Snowflake key. The `ci-pr` environment
was left without credentials because it has no review protection.

After a merge to `main`, the integration job uses the existing `ci`
environment to build against the October 16 TEST fixture. It runs the models
and data tests in Snowflake, then gates the automatic DEV release. The TEST
role has no DEV or PROD access. All TEST builds share `DBT_TEST`, so the
workflow serializes them. The
fixed case does not prove every future delivery will work. Its date, opening
date and scenario are kept together in the fixture file; they do not choose
PROD's daily date.

`main` is not currently protected. A ruleset should require pull requests and
the `checks` status before merging. The live TEST build cannot be a required
pre-merge check in this design because it runs only after a push to `main`.
The TEST result still blocks DEV deployment. No branch ruleset has been
provisioned by this repository.

The TEST key was generated with `python -m scripts.create_ci_test_key`.
Its public half was assigned to the Snowflake service user; its private half
is excluded from Git and stored as the `ci` environment secret
`NORTHBRIDGE_CI_TEST_KEY_B64` (base64 of the PEM file). Rotate the key by
creating a replacement, assigning the new public key to that user, updating
the environment secret and testing a connection before retiring the old key.

TEST was set up with [21_test_environment.sql](../snowflake/history/21_test_environment.sql).
The local TEST build passed 12 models and 34 data tests. A native Snowflake
dbt deployment and run also passed. TEST has no schedule. The
[October 6 rehearsal](test-rehearsal.md) ran a separate dated delivery through
Snowpipe, readiness, dbt, bank reconciliation and one validated close. The
current CI job still checks dbt against the fixed October 16 fixture; it does
not run the complete delivery automatically.

## Deploying code

Python table, stage and pipe names come from
[`pipeline/environment.py`](../pipeline/environment.py). Set
`NORTHBRIDGE_ENV=dev`, `test` or `prod` before starting a producer process;
the manual DEV GitHub workflows explicitly select DEV. dbt profiles use matching
targets, and deployment takes `--target`. The same code can therefore point
at each environment's own objects. This is routing, not provisioning: TEST
has no scheduled daily run, and PROD has no task schedule yet.

The native dbt deployment command requires an explicit environment:

```powershell
python -m scripts.deploy_dbt_project --target dev
python -m scripts.deploy_dbt_project --target test
```

It checks the Snowflake role and required RAW tables before uploading. The
native runner also requires `--target`.

After a push to `main`, a successful TEST build now starts the DEV release
job in the same CI run. It checks that the tested commit is still the tip of
`main`, saves the dbt source under `DBT_SOURCE/commits/<SHA>/`, deploys it,
and compiles it in Snowflake. Compile resolves the deployed models without
rebuilding a daily NAV. The job records the commit SHA, CI run ID and stage
path in `NORTHBRIDGE_DEV.DBT_DEV.CODE_RELEASES`. The separate **Release dbt to
DEV** workflow remains available for a manual recovery or rehearsal.

The GitHub `development` environment is restricted to `main`. Its private
key belongs to `NORTHBRIDGE_RELEASE_DEV`, a Snowflake service user with only
the `NORTHBRIDGE_DBT_DEV` role. Generate a replacement locally with
`python -m scripts.create_dev_release_key`, assign its public key to that
user, and update the `NORTHBRIDGE_RELEASE_DEV_KEY_B64` environment secret.
This is a deliberate code release, separate from processing a day's data.

If deployment or compile fails after the release key is ready, the workflow
tries to redeploy and compile the last recorded good source. The workflow
still fails so the operator can investigate. To rehearse this in DEV, run the
workflow with `rehearse_failure` selected. It deploys the tested candidate,
then deliberately fails verification before recording it. The restore step
should redeploy the last recorded commit from its own stage folder. Expect a
failed GitHub run, a successful restore step, and a `RESTORE` row in
`CODE_RELEASES`. This tests the recovery path; it does not test how dbt
handles an invalid model. A failed restore needs operator attention before
the next daily close.

The [October 18 DEV rehearsal](https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/39151438430)
deployed candidate `71751bf`, stopped at the deliberate verification failure,
and restored `f6d7faa` from its saved commit folder. The restore compiled
successfully. The GitHub run is failed by design.

On October 18, 2026, unattended DEV processing was stopped: the repository's
`NORTHBRIDGE_DAILY_ENABLED` and `NORTHBRIDGE_DIVIDENDS_ENABLED` switches were
set to `false`, the five DEV GitHub cron triggers were removed, and
[`27_pause_dev_schedules.sql`](../snowflake/history/27_pause_dev_schedules.sql)
suspended `DAILY_CLOSE_READY` and `DAILY_CLOSE_DEADLINE`. BUILD and RECORD
remain started child tasks; they have no scheduled root run. DEV workflows
still support a reviewed manual dispatch. The earlier October 16 close remains
historical evidence of an unattended DEV pilot, not a production run.

PROD is deliberately gated. [01_raw.sql](../snowflake/prod/01_raw.sql)
created its own RAW tables, landing stage and Snowpipe pipes. Scoped grants
from [02_access.sql](../snowflake/prod/02_access.sql) and the read-only
roll-forward grants were applied. Separate PROD loader and release service
users use different keys. The [October 16 rehearsal](prod-rehearsal.md) loaded
real Massive data and fictional fund inputs, passed RAW readiness and dbt,
and recorded one validated close. The next October 19 market day also passed
with four settlement confirmations and two bank matches. The same CI-passed dbt commit was deployed
to a versioned PROD stage path and compiled. There is still **no unattended
PROD daily close**: the producer schedule and task graph are off, and a
scheduled next-day rehearsal remains open.

After DEV succeeds, the same CI run can promote that commit to PROD. This job
is still disabled by `SNOWFLAKE_PROD_DEPLOY_ENABLED=false`. Before enabling it,
the GitHub `production` environment needs a separate PROD release key and a
reviewer rule. The job rechecks that the commit is still the tip of `main`,
then deploys, compiles and records it. The standalone [Release dbt to
PROD](../.github/workflows/release-prod.yml) workflow remains a manual
recovery route. The fixed compile context is only a deployment check; it does
not calculate the next daily NAV.

## Release work still open

1. Protect `main` with a required pull request and the credential-free
   `checks` job. This has not been configured on GitHub.
2. Automate the proved TEST delivery rehearsal in CI or a controlled release
   gate, and test a late input arriving after readiness first says wait.
3. Configure and rehearse the automatic PROD promotion through the reviewed
   GitHub `production` environment, using its separate release credential.
4. Rehearse a scheduled next-day close, a late or missing input and rollback
   in PROD. For rollback,
   redeploy the prior reviewed commit; preserve RAW delivery history and assess
   any affected close before rerunning it.

The GitHub `production` environment exists but has no PROD deployment
credential or approval rule. The RAW objects alone do not make this an
operating production pipeline.

The proposed [PROD daily workflow](../.github/workflows/prod-daily.yml)
combines market, dividend and simulated bank deliveries in one job. It waits
for both Snowpipe event files before preparing bank cash. The job checks out
the last successful `production` deployment, so a new commit on `main` does
not change the running producer before the matching dbt code is deployed.
At 13:00 UTC on Tuesday through Saturday, the same workflow checks for
exactly one validated close for the preceding US market day. A missing close
fails that GitHub run. US market holidays are skipped by the reviewed
calendar; the calendar must be extended before 2027. The switch,
`NORTHBRIDGE_PROD_DAILY_ENABLED`, is off; the `production-data` environment
still needs its own loader key and Massive key. The proposed
[task graph](../snowflake/prod/05_tasks.sql) and its
[task-owner grants](../snowflake/prod/04_task_access.sql) are not applied.
Keep the graph suspended until a scheduled next-day delivery, missing-input
case and deadline check are rehearsed. GitHub may start scheduled workflows
late; the deadline check reports timeliness but does not repair a missed close.
