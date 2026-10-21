# Northbridge daily close

A Snowflake and dbt pipeline for a two-account US equity fund. Massive supplies real daily prices and dividend announcements. A deterministic simulator supplies trades, settlements, opening balances and bank statements. Simulated records are labelled and kept separate from market data.

The output is a checked NAV calculation, **not a published fund NAV**. The PROD close has been run manually for two market days. Its unattended schedule is off.

## How a market day runs

| Step | Work | Check |
| --- | --- | --- |
| Produce | Fetch Massive prices and dividends; generate fund events and a bank statement | Date, source, delivery ID and file hash are recorded |
| Load | Stage files in Snowflake; Snowpipe loads OMS and settlement events; checked loads handle the other files | Expected and loaded row counts must agree |
| Ready | A Snowflake task checks required deliveries, held-stock prices and bank inputs | Incomplete days wait; a validated day is not rebuilt |
| Build | A Snowflake task runs the native dbt project | Staging views type RAW data; incremental tables calculate positions, cash, dividends and NAV |
| Record | A Snowflake task checks both account NAVs and bank cash matches | One `VALIDATED` row is written to `RAW.DAILY_CLOSE_RUNS` |

The proposed PROD producer is [`.github/workflows/prod-daily.yml`](.github/workflows/prod-daily.yml); the task graph is [`snowflake/prod/05_tasks.sql`](snowflake/prod/05_tasks.sql). Neither PROD daily schedule is active. The October 16 and 19 closes were run manually with PROD data and service identities.

## Data model

| Input | Used for |
| --- | --- |
| Massive unadjusted daily closes | Value held shares at the market close |
| Massive dividend announcements | Calculate long receivables and short liabilities on the ex-date |
| Simulated OMS trades and settlements | Roll positions and cash forward |
| Simulated opening and bank records | Start the accounts and compare calculated cash with reported cash |

RAW keeps the received payloads and delivery history. [`dbt/models/staging`](dbt/models/staging) parses the inputs; [`dbt/models/marts`](dbt/models/marts) builds daily position, cash, dividend, NAV and cash-reconciliation tables. The next trading day starts from the prior validated close. dbt tests check business keys and accounting relationships; the close recorder separately requires one NAV and one bank match per account.

Dividend terms come from Massive, but the resulting cash payment is modeled. A relevant dividend with unresolved security identity or changed terms stops the build for review. A ticker alone is not enough to approve an event.

## Environments and releases

DEV, TEST and PROD are separate databases in one Snowflake account. PRs run Python tests and parse dbt without Snowflake credentials. A merge to `main` builds the fixed TEST case in Snowflake, then deploys the tested commit to DEV. PROD promotion uses a separate release key and GitHub `production` reviewer gate. Source is stored under its commit SHA so a failed release can restore the last recorded good version.

The controlled [PROD release of `24440c6`](https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/39474263222) deployed and compiled successfully on October 20, 2026. Automatic PROD code promotion is switched off again. Code release does not run a daily close.

## Evidence

- [PROD close rehearsal](docs/prod-rehearsal.md): October 16 and 19 passed RAW readiness, dbt build and bank reconciliation. Each date has one `VALIDATED` close for two accounts.
- [October 16 acceptance queries](snowflake/history/26_acceptance_20261016.sql): checks for loaded inputs, the close registry and account results.
- [TEST delivery rehearsal](docs/test-rehearsal.md): a dated delivery through Snowpipe, dbt and bank reconciliation.
- [Missed producer incident](incidents/2026-10-15-missed-producer.md): GitHub started late; the deadline check reported the miss and the close was recovered manually.

Run local Python checks with:

```powershell
.\.venv\dbt\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

## Design choices and limits

- **Snowflake Tasks run the close; GitHub Actions delivers files.** Tasks can wait for Snowpipe and run dbt near the data. GitHub provides a simple external producer, but its scheduled starts can be late. A deadline failure reports a missed close; it cannot make the run timely.
- **Snowpipe handles the small event files.** The price and dividend downloads are checked batch loads. This matches the current file sizes; it is not a claim of live trading-data streaming.
- **Retries use delivery IDs and hashes.** Repeating the same delivery does not create a second close. Conflicting prices or trade versions stop for review rather than silently replacing history.
- **The fund side is simulated.** Generated settlements and bank statements exercise accounting and reconciliation logic. They are not independent broker, custodian or bank evidence. There is no confirmed dividend payment, tax or stock-borrow accounting, or NAV publication approval.
- **PROD is not unattended yet.** The producer switch is off and the PROD task graph is not running on a schedule. The reviewed 2026 US equity calendar also needs extending before 2027.
