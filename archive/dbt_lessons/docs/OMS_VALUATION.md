# First-day position valuation

Live build verified September 24, 2026: two views, two tables, 74 data tests
and one project hook passed (PASS=79, WARN=0, ERROR=0). The fixed-snapshot
valuation test confirmed both expected prices and market values below.

`oms_first_day_valuation` joins our account positions to the selected historical
price snapshot, then multiplies closing quantity by closing price.

For January 6, 2025 the saved Massive CSV has AAPL at USD 245.00 and AMZN at
USD 227.61. The expected signed values are 15 * 245 = 3675 and
-3 * 227.61 = -682.83. A negative value represents a short position, not a loss.
Cash, fees, borrowing costs and other assets/liabilities are not included.
This is neither profit nor total fund NAV.

The LEFT JOIN keeps positions visible when a price is missing; the resulting
NULL price fails a not_null test. Another test verifies that the price join
does not lose or multiply positions. There is no fallback to another day's
price, no zero-price substitution and no rounding to cents in the model.

The join requires matching universe ticker, source ticker, date and currency,
and an unadjusted price. This is deliberately scoped to this AAPL/AMZN lesson:
the upstream scope test fixes its scenario and date. These price rows have
provider_ticker_only identity status. The simulator's .US labels are not
permanent IDs, and this join must not be generalized to renamed or reused
tickers without a dated security mapping.

Price delivery, file and row metadata remain in the output for investigation.
Models under marts are materialized as tables by dbt_project.yml.

Build this model and its parents, including the raw-to-staging count tests:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "+oms_first_day_valuation oms_executions_preserve_rows historical_prices_preserve_rows"
```

Inspect the result:

```sql
SELECT valuation_date, account_id, market_ticker, currency,
       closing_quantity, close_price, market_value
FROM NORTHBRIDGE_DEV.DBT_DEV.OMS_FIRST_DAY_VALUATION
ORDER BY market_ticker;
```
