# dbt model inventory

The active dbt project contains the reusable fund accounting graph. Earlier
learning models and their tests live in `archive/dbt_lessons`.

`dim_instrument` supplies stable, effective-dated security IDs. The
`approved_corporate_actions` seed records the events operations has allowed into
accounting.

## Active models

| Layer | Model | One row represents | Materialization |
| --- | --- | --- | --- |
| Staging | `stg_activity_events` | One received replay record | View |
| Staging | `stg_historical_prices` | One ticker and valuation date in the selected snapshot | View |
| Staging | `stg_corporate_actions` | One reviewed corporate-action event | View |
| Staging | `stg_broker_positions` | One received broker position | View |
| Staging | `stg_fx_rates` | One ECB rate date | View |
| Staging | `stg_treasury_rates` | One Treasury rate date and tenor | View |
| Staging | `stg_fund_admin_events` | One investor-flow or expense event | View |
| Staging | `stg_bank_cash_statements` | One bank account closing balance | View |
| Mart | `fct_daily_positions` | One account, instrument and market date | Table |
| Mart | `fct_daily_valuations` | One valued account position on one market date | Table |
| Mart | `fct_settlement_obligations` | One trade obligation as known at one daily cutoff | Table |
| Mart | `fct_dividend_accruals` | One account and reviewed dividend event | Table |
| Mart | `fct_daily_cash` | One account, currency and daily cutoff | Table |
| Mart | `fct_daily_nav` | One account, currency and valuation date | Table |
| Mart | `fct_position_reconciliation` | One internal/broker account-security comparison | Table |
| Mart | `fct_daily_nav_reporting` | One account, date and reporting currency | Table |
| Mart | `fct_cash_yield_benchmark` | One account-day Treasury cash estimate | Table |
| Mart | `fct_bank_cash_reconciliation` | One internal/bank account-currency comparison | Table |

The active DAG therefore has eight staging views and ten mart tables. The
dividend reconciliation in `snowflake/23_dividend_reconciliation.sql` remains a
read-only operating report rather than another permanent model.

## Archived lessons

The original sample pipeline used CSV executions, allocations and two closing
prices. The later OMS lesson added five JSON executions, settlement reports and
exception history. They were useful for learning, but the current replay now
covers those concepts at a more realistic scale.

The archived files are deliberately preserved so their reasoning can still be
reviewed. dbt no longer parses or rebuilds them. Existing lesson objects in
Snowflake are left untouched; this consolidation does not delete raw data.

## Tests kept active

Routine tests protect source preservation, required fields, unique business keys,
price coverage, position continuity, settlement matching, dividend matching,
and the cash and NAV accounting identities. Exact counts and deliberate
exceptions live under `tests/acceptance` and carry the `fixture` tag.

Tests attached only to the sample and OMS lessons are excluded with those
lessons. The independent Python control remains part of `scripts/run_replay.py`
and checks every daily valuation and account balance against a separate Decimal
calculation.
