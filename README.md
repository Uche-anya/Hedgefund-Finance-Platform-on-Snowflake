# Northbridge daily close

A daily US-equity fund close built on Snowflake and dbt. Massive supplies real
closing prices and dividend announcements. A deterministic simulator supplies
trades, settlement confirmations, opening bank balances and fund-admin records.
The simulated records are marked as such; they are not independent broker or
bank evidence. The output is a **validated calculation**, not a published NAV.

## Daily path

| Step | What runs | Result |
| --- | --- | --- |
| Produce | [GitHub Actions](.github/workflows) can run the market, dividend and simulated bank producers for a selected US market day | Dated, hashed deliveries from Massive and the simulator |
| Ingest | The loader registers delivery IDs and stages files in Snowflake. Snowpipe loads OMS and settlement events; checked `COPY` commands load prices and dividends | Immutable deliveries and row counts in `NORTHBRIDGE_DEV.RAW` |
| Gate | `DAILY_CLOSE_READY` checks delivery counts, dividend and bank inputs, and prices for held stocks | A ready date, or a reason to wait |
| Build | `DAILY_CLOSE_BUILD` runs the deployed Snowflake dbt project | Typed staging views and incremental position, cash, dividend and NAV tables |
| Record | `DAILY_CLOSE_RECORD` checks both account NAVs and bank cash matches before recording one `VALIDATED` close | An auditable calculation in `RAW.DAILY_CLOSE_RUNS` |

DEV automated schedules were stopped on October 18, 2026. Its GitHub
workflows are manual, and the Snowflake readiness root and deadline task are
suspended. PROD completed [manual October 16 and 19 closes](docs/prod-rehearsal.md)
with its own deliveries, service identities and dbt release. Its daily
producer and Snowflake task schedules are not active. There is currently no
unattended PROD close. The reviewed
[2026 US equity calendar](config/us_equity_calendar_2026.json) skips market
holidays and distinguishes them from settlement holidays.

The earlier DEV pilot showed that GitHub's scheduler can be late. For the October 15, 2026 close, scheduled
producer runs started after Snowflake's former 05:00 final check;
[the incident record](incidents/2026-10-15-missed-producer.md)
documents the manual recovery. The readiness window now extends to 07:00.
`DAILY_CLOSE_DEADLINE` was a separate Snowflake task at 05:30. It failed in
task history if the close was missing and skipped reviewed market holidays.
It did not send an external notification. A later successful close did not
make a missed deadline timely.

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
cash is compared with a separately loaded simulated bank statement in
[`fct_cash_reconciliation`](dbt/models/marts/fct_cash_reconciliation.sql).
The bank simulator rolls forward its previous balance using dated postings
from OMS trades, so a missing settlement can appear as a cash break. It is
still fictional bank evidence. The simulator stops at a booked dividend pay
date until bank payment evidence is added.
Dividend models use dated security mappings and the prior eligible position to book
long receivables or short liabilities on the ex-date. Cash movement on the pay
date is **modeled**. There is no independent payment confirmation, tax or
stock-borrow accounting.

Massive dividend events remain in RAW. The review queue separates ordinary
events from changed terms, unusual distributions and uncertain security
identity. As of October 16, 2026, three of the 20 simulated securities have
approved mappings in DEV; the PROD mappings remain pending. A ticker match alone does not approve a
security. The dbt build stops if a held security has an unresolved relevant
event rather than silently changing the booked amount.

## Reliability and access

- Delivery IDs and file hashes make retries repeatable. A changed price close
  or conflicting same-version trade stops for review.
- The readiness gate waits for Snowpipe row counts; a registered file is not
  assumed to have loaded. Empty settlement deliveries are explicit.
- dbt merges by business key and date. A validated date is not rebuilt by a
  later readiness check.
- The GitHub loader uses a restricted Snowflake service role and private key;
  dbt uses a separate role. The loader can read validated closes but cannot
  write them. Secrets are kept outside Git. The development warehouse has a
  resource monitor.

The [Snowflake SQL](snowflake/README.md) separates current deployment files
from earlier DEV and incident scripts.
`pipeline.recover_file` is an operator path for a failed Snowpipe file, after
checking copy history and confirming no RAW rows loaded. It is not part of the
  normal delivery path.

## Run and verify

For a reviewed DEV market date, run the producers from the project terminal
with `NORTHBRIDGE_ENV=dev` and the DEV credentials configured. For example:

```powershell
python -m pipeline.produce_day 2026-10-16
python -m pipeline.produce_dividends 2026-10-16
python -m pipeline.produce_bank 2026-10-16
```

These prepare local files. Add `--submit` to each command to deliver them to
Snowflake. The bank command needs the earlier trade and settlement inputs.
Run `python -m pipeline.check_dividend_deadline --business-date 2026-10-16`
and `python -m pipeline.check_close_deadline --business-date 2026-10-16` to
check a delivery and validated close manually.
The suspended readiness graph must be explicitly run for a DEV close. Inspect
`RAW.DAILY_DELIVERIES`, Snowflake task history and `RAW.DAILY_CLOSE_RUNS` for
the outcome. `VALIDATED` means checks passed, not that NAV was published.

Pull requests run Python tests and an offline dbt parse. The
[CI workflow](.github/workflows/ci.yml) also defines a pre-merge Snowflake
TEST build for reviewed internal pull requests; its `ci-pr` environment and
required branch check still need GitHub setup. After a push to `main`, CI
builds against the named
[Snowflake TEST fixture](config/ci_test_fixture.json). A separate
[TEST delivery rehearsal](docs/test-rehearsal.md) loaded a dated first day
through Snowpipe, dbt and bank reconciliation; it has no schedule. The [environment guide](docs/ci-cd.md)
records the DEV, TEST and PROD boundaries and what remains before PROD can
run. To run the Python checks locally:

```powershell
.\.venv\dbt\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

After a successful TEST build on `main`, CI deploys the same commit to DEV,
compiles it and records it in `DBT_DEV.CODE_RELEASES`. PROD promotion stays
disabled until its separate credential and review gate are configured. Each
release keeps its source under the commit SHA for restoration. The manual
[DEV release workflow](.github/workflows/release-dev.yml) remains for recovery.
To run a reviewed Snowflake SQL file from
the project terminal, use `python scripts/snow_admin.py --file <path>` with the
admin connection configured. These are deployment commands, not daily jobs.

## Verified example

The [October 16 acceptance queries](snowflake/history/26_acceptance_20261016.sql)
show 12,630 market prices, 7,133 dividend records, eight trades, eight
settlements and two bank balances delivered. Snowflake recorded one
`VALIDATED` close. The account NAVs were $5,001,300.80 and $4,999,487.75;
both bank cash comparisons were `MATCH`.

That bank delivery used the earlier balance-only format. The new transaction
ledger reproduced both balances in a dry run and passed a
[hosted producer run](https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/39062827080).
The [TEST incident script](snowflake/history/25_bank_ledger_test.sql) showed a $50
bank fee produce `BREAK`, followed by `MATCH` when the bank reversed its
error. The TEST changes were rolled back. This proves the calculation and
reconciliation checks; it does not prove an unattended close using the new
ledger delivery.

## Current boundary

This is a validated daily calculation path, not an unattended PROD pipeline or a fully independent fund
accounting platform. It still needs independent broker and bank evidence,
payment reconciliation, a reviewed NAV publication decision, and reliable
producer scheduling beyond GitHub Actions. The 2026 market calendar must be
reviewed before running dates in 2027.
