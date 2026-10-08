# Northbridge equity close

Northbridge is a portfolio data-engineering project for a fictional equity fund.
It combines real market reference data with **labelled simulated fund activity**.
The current calculation covers 502 market sessions from 23 September 2024 to
23 September 2026. Its NAV is provisional: it is a calculated research result,
not a published fund NAV or evidence of a real fund.

## Project direction

The saved two-year history is the backfill for a daily equity-close pipeline.
New business-day deliveries must enter the same RAW contracts and the same
Snowflake/dbt calculation. Each close will pin its exact inputs and code
version, so a retry reproduces the same result and a late correction creates
a new close version. Snowpipe handles arriving OMS and settlement files; bulk
loading remains appropriate for the historical files. We will schedule the
close only after the input gate, dbt calculation and retry rules work together.

The Snowflake/dbt close is the intended source for reporting. The Python close
ledger is an independent check until the two calculations reconcile. The
current result remains provisional until independent evidence and an approval
path support publication. See [the daily pipeline design](docs/daily_pipeline_design.md).

## What currently runs

| Layer | Current implementation |
| --- | --- |
| Market reference | 250,036 saved Massive backfill price rows across 503 tickers, plus checked 22 and 23 September deliveries for the 20 traded tickers; saved corporate-action candidates and reviewed security identities |
| Fund activity | Fictional OMS executions, custodian confirmations, opening subscriptions and dividend cash evidence, identified by scenario `sim-equity-2024-2026-v2` |
| Snowflake landing | RAW tables with source and delivery lineage; the five-day Snowpipe pilot plus a new OMS file and its next-day settlement file, with 493 older dates per feed loaded by `COPY INTO` |
| dbt calculation | RAW-derived positions, settled cash, open-trade amounts, dividend balances and provisional NAV |
| Independent check | Saved Python close compared row by row with dbt positions, cash and NAV |

The 23 September candidate has 19,614 account-security-day positions and
1,004 account-day NAV rows. Its pinned dbt build passed; the saved Python parity
check covers the earlier history, not this new day. See
[the ingestion and calculation path](docs/two_year_snowflake_path.md) for the
exact route and its limits.

## Run the current dbt graph

From the repository root, with the Snowflake credentials configured:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select +fct_account_nav_daily --exclude tag:fixture --vars "close_request_id: 98e072ac531920d74204970d"
```

The `fixture` tests compare against a saved Python result. They are useful when
reproducing this particular historical scenario, but are not a generic daily
production gate. [The model inventory](dbt/MODEL_INVENTORY.md) names the active
tables and views.

## Current boundary

The earlier 23-day replay, its dbt graph and its Snowflake task were retired.
The immutable RAW deliveries and operating audit records remain as history.

The two-year graph is a **historical backfill plus a Snowpipe daily-arrival pilot**.
Its DEV Task graph has passed manual runs, but the root remains suspended. It is
not an automated daily close yet. A production run still needs scheduled source
hand-offs, a continuing closing-price delivery, a scheduled input gate, review of
held corporate actions, independent bank and broker evidence, and an approval
path. See [daily operations](docs/daily_operations.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `simulation/` | Fictional OMS and settlement producers |
| `data_extraction/` | Vendor downloads and reference-data review |
| `snowflake/` | RAW definitions, ingestion, governance and verification SQL |
| `dbt/` | Active transformations and tests |
| `fund_pipeline/` | Independent Python close and other local calculations |
| `scripts/` | Current ingestion, dbt and verification entry points |
| `docs/` | Design notes and current operating limits |

Generated datasets, secrets, private keys, dbt output and Terraform state are
excluded from Git. The fund trades and cash events are simulated; the market
reference data comes from saved provider downloads.
