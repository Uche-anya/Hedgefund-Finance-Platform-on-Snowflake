# Historical price staging

Live validation: the view built successfully on September 23, 2026. Its 24
directly selected tests passed, followed by the explicit row-preservation test
(25 data tests total). No build errors or warnings were reported.

stg_historical_prices is a view in NORTHBRIDGE_DEV.DBT_DEV. It selects the
assembled delivery named by historical_price_delivery_id in dbt_project.yml.
The earlier two-stock valuation models continue to use their original sample.

## What changes in staging

- Date text becomes a DATE, and prices and volume become NUMBER(38,9).
- Original date, price, volume and input row-number text is retained beside
  the parsed values. Malformed or unsupported numeric formats produce NULL,
  which fails the required-field tests. Prices allow nine decimal places;
  volumes also accept the positive scientific exponents in the saved bars.
- Blank instrument IDs and share-class FIGIs become NULL, meaning unknown.
  Provider-only ticker identities are not silently certified by this model.
- Every source row remains. Duplicate ticker/date rows fail a test instead of
  being silently dropped. Delivery and both local/Snowflake file references
  remain available for tracing a record.

The tests check required fields, supported source/currency/price basis/status,
price bounds, nonnegative volume, row references and uniqueness. The selected
reviewed snapshot also has explicit count and date-range expectations. A
separate test compares raw and staged counts and rejects empty deliveries.

Run the model and all its checks with:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "stg_historical_prices historical_prices_preserve_rows"
```

The explicit row-preservation selector includes the test whose raw source
dependency would otherwise be excluded by the helper's cautious selection.

Inspect in Snowsight:

```sql
SELECT valuation_date, universe_ticker, source_ticker,
       close_price, volume, identity_status
FROM NORTHBRIDGE_DEV.DBT_DEV.STG_HISTORICAL_PRICES
WHERE universe_ticker = 'AAPL'
ORDER BY valuation_date
LIMIT 10;
```

This is typed market data, not a holdings calculation. The shorter histories,
snapshot-membership bias, pending identity checks and need for corporate-action
handling still apply. The view's selected delivery is fixed until dbt rebuilds
it with another variable; this step does not implement daily ingestion.
