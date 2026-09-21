# First price load

The holdings build succeeded in the user's supplied output: three models,
20 data tests and one hook (PASS=24, ERROR=0). The next slice starts with prices.

## Source

Use the saved EODHD market snapshot at
`data/market/0a35a13d137e4627ace8d7a9d668f3ce`.
`market_prices.verify_market` verified all saved response and CSV hashes and
recomputed the normalized CSV from the provider JSON. A byte-for-byte upload
copy is in `data/snowflake_upload/market_2025-01-06_08/closing_prices.csv`.
It has six rows: Apple and Amazon, each on January 6, 7 and 8, 2025.

The source is eodhd_demo, with unadjusted close prices in USD. These are real
saved historical observations, not the synthetic prices used in later lessons.
Prices and raw responses stay in ignored local data storage under the existing
private-learning usage restriction. No new API request was made.

## Manual steps

1. Run `08_closing_prices.sql` in Snowsight. Expect ten columns from DESCRIBE.
2. Ingestion > Add Data > Load files into a Stage. Upload only the prepared CSV.
   Select NORTHBRIDGE_DEV > RAW > MARKET_SAMPLE_20250106_08, with no subfolder.
3. Run `09_load_closing_prices.sql` in order. LIST should show one file.
   COPY should load six rows, and the count should be six. The final query selects
   January 6 only and should return two prices, matching the holdings date.

## Row meaning and lineage

One raw row is one received price observation for an instrument, date and currency.
The four file columns remain text; later dbt models will convert and validate them.
price_basis records that we selected the provider's unadjusted close field.
Other columns identify source, market snapshot, filename, file row and load time.
The market snapshot folder's ID is its delivery_id. It differs from the trade
delivery ID: these were separate source deliveries. Later, holdings join to
prices by instrument and date under the supported USD policy, not by delivery ID.

The loader assigns fixed source metadata for this verified snapshot. It is not
a general daily loader and does not verify uploaded bytes against the manifest.
The local CSV was validated, but transformed COPY is not a general CSV-width
validator. FORCE=FALSE uses Snowflake's finite load history, not permanent
business-key deduplication. Do not overwrite or rename a file to force a reload.

Giving the dbt role SELECT on this new table is required; its earlier grants
covered only executions and allocations. No additional write access is granted.

Local source verification passed. Table creation, upload, COPY and grants remain
UNVERIFIED against Snowflake. Price staging, date/currency/uniqueness checks,
missing-price blocking and position valuation are the next dbt step. Do not join
all three days of prices to holdings using only instrument: that triples rows.

References:
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
- https://docs.snowflake.com/en/user-guide/data-load-local-file-system-stage-ui
