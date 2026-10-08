# Two-year Snowflake path

The two-year scenario is `sim-equity-2024-2026-v2`. The trades and custodian
confirmations are fictional; the stock prices and corporate-action candidates
come from saved provider downloads. A scenario ID keeps those sources from
being mistaken for real fund activity.

## Ingestion

| Input | Snowflake landing | How it was loaded |
| --- | --- | --- |
| Five daily OMS files, 20 fills | `RAW.OMS_EVENTS` | Internal stage, `OMS_EVENTS_PIPE`, Snowpipe REST notification |
| Five daily settlement files, 20 confirmations | `RAW.SETTLEMENT_EVENTS` | Separate stage, `SETTLEMENT_EVENTS_PIPE`, Snowpipe REST notification |
| Remaining 493 dates, 1,972 rows per feed | Same two RAW tables | Bulk `COPY INTO` of the historical packages |
| 250,036 stock-price rows | `RAW.HISTORICAL_PRICES` | Historical bulk load |
| Corporate actions | `RAW.CORPORATE_ACTIONS` | Saved provider snapshot and review history |
| Opening subscriptions and dividend cash confirmations | Separate RAW event tables | Checked file deliveries |

`source_file` and `delivery_id` remain on the RAW rows. The read-only
`snowflake/52_two_year_ingestion_check.sql` query shows the five daily files
separately from the 493-date backfill. The Snowpipe definitions are in
`snowflake/34_oms_snowpipe.sql` and `48_settlement_snowpipe.sql`.

Snowpipe is for **new arrivals**. Loading almost 500 old tiny files through
individual pipe notifications would add overhead without changing the result.
The backfill used `COPY INTO`; both routes land in the same RAW contracts. The
current pipes use an internal stage and an explicit REST notification. They
do not automatically watch an S3 bucket.

## dbt calculation

1. `stg_oms_events`, `stg_settlement_events`, `stg_historical_prices`, and
   `stg_corporate_actions` type the separate RAW feeds. `dim_instrument`
   identifies the security valid on each date.
2. `fct_account_positions_daily` accumulates signed BUY/SELL shares
   across 500 market dates. It carries XOM's reviewed one-for-one successor
   into the new security ID, then applies the day's unadjusted closing price.
3. `fct_account_cash_daily` starts with two simulated administrator
   subscriptions, applies custodian settlement cash and confirmed dividend
   cash, and keeps unsettled trade receivables and payables separate.
4. `fct_account_dividends_daily` uses **previous-close shares** on each
   ex-dividend date. The four-row `reviewed_action_decisions` seed records
   two approvals and two holds; other candidates stay pending. A provider
   pay date does not turn an entitlement into received cash.
5. `fct_account_nav_daily` combines cash, open trades, signed market
   values and reviewed dividend balances. It shows pending candidate impact
   separately from reviewed NAV. This is **provisional**, not published fund
   performance.

The saved Python close remains an independent comparison. Three dbt tests
compare every position, cash and NAV account-day in its original 500-date
window; all pass. The 22 September extension is checked separately from RAW
receipts and the rebuilt dbt outputs.
The original 500-day calculation yielded 19,534 position-days and 1,000
account-days through 21 September 2026. The 22 September daily extension
increased these to 19,574 and 1,002. The query in
`snowflake/53_two_year_dbt_check.sql` prints those counts and load-check
totals. A sum of daily NAV balances is only a load check, not a fund NAV.

## Daily operation still to wire

The first extension check is `snowflake/57_next_day_source_check.sql`.
Before the extension, it found 20 required tickers but no 22 September price
or event rows. A one-day Massive download supplied 20 unadjusted bars;
`prepare_daily_prices.py` built a checked CSV; and `load_daily_prices.py`
loaded it as a READY delivery. Four fictional 22 September OMS fills and
their four 23 September custodian confirmations arrived through separate
Snowpipes. `snowflake/59_next_day_close_check.sql` shows all three READY
receipts and the two new provisional NAV rows. The 22 September trades remain
open at that close because their cash settles on the 23rd.
dbt includes only the pinned historical snapshot and READY daily-price
deliveries. The saved Python parity tests remain limited to their original
500 dates. The new date has not been approved or published.

The earlier `OPERATIONS.DAILY_CLOSE` task was tied to the short replay and has
been retired. A future
daily run needs an arriving OMS file, a separate custodian confirmation file,
a current closing-price delivery, receipt checks, and then a dbt run for the
new business date. It also needs operational review of corporate actions and
bank evidence before any NAV can be approved for publication. The current
two-year models rebuild history; incremental scheduling and BI publication
are separate deployment steps.

At this size, manual clustering, search optimization and dynamic tables would
add maintenance without solving an observed bottleneck. The relevant
Snowflake features already exercised are stages, file formats, Snowpipe,
bulk `COPY INTO`, RAW `VARIANT`, roles, warehouses, dbt on Snowflake, and
read-only reconciliation queries. Task scheduling is not yet live for this
scenario.
