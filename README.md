# Northbridge daily close

A daily US-equity fund close built on Snowflake and dbt. Massive supplies real
closing prices and dividend announcements. A deterministic simulator supplies
trades, settlement confirmations, opening bank balances and fund-admin records.
The simulated records are marked as such; they are not independent broker or
bank evidence. The output is a **validated calculation**, not a published NAV.

## Daily path

| Step | What runs | Result |
| --- | --- | --- |
| Produce | [GitHub Actions](.github/workflows) runs `pipeline.produce_day` and `pipeline.produce_dividends` after a US market day | Dated, hashed deliveries from Massive and the simulator |
| Ingest | The loader registers delivery IDs and stages files in Snowflake. Snowpipe loads OMS and settlement events; checked `COPY` commands load prices and dividends | Immutable deliveries and row counts in `NORTHBRIDGE_DEV.RAW` |
| Gate | `DAILY_CLOSE_READY` compares expected and loaded rows, checks the dividend snapshot and requires a valid close for every held stock | A ready date, or a reason to wait |
| Build | `DAILY_CLOSE_BUILD` runs the deployed Snowflake dbt project | Typed staging views and incremental position, cash, dividend and NAV tables |
| Record | `DAILY_CLOSE_RECORD` checks both account NAVs and records one `VALIDATED` close | An auditable calculation in `RAW.DAILY_CLOSE_RUNS` |

The market producer is scheduled hourly from 00:17 to 04:17 New York time,
Tuesday through Saturday; dividends run from 00:25 to 04:25. The Snowflake
readiness task checks hourly from 02:00 to 07:00. A separate GitHub check
fails if the prior market day's close is not validated by 05:30; the dividend
delivery has a 05:35 check. The
reviewed [2026 US equity calendar](config/us_equity_calendar_2026.json) skips
market holidays and distinguishes them from settlement holidays.

GitHub's scheduler can be late. For the October 15, 2026 close, scheduled
producer runs started after Snowflake's former 05:00 final check;
[the incident record](incidents/2026-10-15-missed-producer.md)
documents the manual recovery. The readiness window now extends to 07:00.
`DAILY_CLOSE_DEADLINE` is a separate Snowflake task at 05:30. It fails in task
history if the close is missing and skips reviewed market holidays. It was
deployed on October 16; it does not send an external notification. A later
successful close does not make a missed deadline timely.

## Data and models

The current fund scenario starts with two fictional accounts on October 7,
2026. From October 14 the simulator rotates trades across 20 US equities. It
uses the previous validated close and stops if the required prior prices or NAV
are missing. Its settlement events are generated from its own trades; they do
not prove that an outside custodian settled anything.

The [dbt project](dbt) keeps source typing in `stg_*` views and daily results
in `fct_*` incremental tables. `fct_position_daily` carries signed shares and
market values; `fct_cash_daily` tracks calculated and unsettled cash;
`fct_nav_daily` combines cash, positions and open dividend amounts. Dividend
models use dated security mappings and the prior eligible position to book
long receivables or short liabilities on the ex-date. Cash movement on the pay
date is **modeled**. There is no independent payment confirmation, tax or
stock-borrow accounting.

Massive dividend events remain in RAW. The review queue separates ordinary
events from changed terms, unusual distributions and uncertain security
identity. As of October 16, 2026, three of the 20 simulated securities have
approved mappings; the others remain pending. A ticker match alone does not approve a
security. The dbt build stops if a held security has an unresolved relevant
event rather than silently changing the booked amount.

## Reliability and access

- Delivery IDs and file hashes make retries repeatable. A changed price close
  or conflicting same-version trade stops for review.
- The readiness gate waits for Snowpipe row counts; a registered file is not
  assumed to have loaded. Empty settlement deliveries are explicit.
- dbt merges by business key and date. A validated date is not rebuilt by a
  later scheduled check.
- The GitHub loader uses a restricted Snowflake service role and private key;
  dbt uses a separate role. The loader can read validated closes but cannot
  write them. Secrets are kept outside Git. The development warehouse has a
  resource monitor.

The [Snowflake SQL](snowflake) contains the RAW, access and task definitions.
`pipeline.recover_file` is an operator path for a failed Snowpipe file, after
checking copy history and confirming no RAW rows loaded. It is not part of the
normal schedule.

## Run and verify

The scheduled workflow is the normal producer. For a reviewed market date,
use `workflow_dispatch` on `daily-producer.yml` and `daily-dividends.yml` to
retry a delivery. A manual dispatch defaults to preparation only; choose
`submit=true` to load it. The readiness task can then build the close. Inspect
`RAW.DAILY_DELIVERIES`, Snowflake task history and `RAW.DAILY_CLOSE_RUNS` for
the outcome. `VALIDATED` means checks passed, not that NAV was published.

Pull requests and pushes to `main` run the Python tests and parse the dbt
project in [CI](.github/workflows/ci.yml). To run the Python checks locally:

```powershell
.\.venv\dbt\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

To deploy a reviewed dbt change, use `python -m scripts.deploy_dbt_project`
with the dbt service key configured. To run a reviewed Snowflake SQL file from
the project terminal, use `python scripts/snow_admin.py --file <path>` with the
admin connection configured. These are deployment commands, not daily jobs.

## Current boundary

This is a working daily calculation path, not a fully independent fund
accounting platform. It still needs independent broker and bank evidence,
payment reconciliation, a reviewed NAV publication decision, and reliable
producer scheduling beyond GitHub Actions. The 2026 market calendar must be
reviewed before running dates in 2027.
