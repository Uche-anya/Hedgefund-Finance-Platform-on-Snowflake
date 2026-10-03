# First-day position valuation

`portfolio_valuation` joins holdings to closing prices by instrument and date.
It uses USD unadjusted prices and computes quantity times close_price, keeping
the negative sign for short positions. It is a table because it lives in marts.
This is still the zero-opening-position example, not a multi-day holdings engine.

A left join retains holdings with no matching price. The close_price and
market_value not-null tests reject those rows; no missing price becomes zero.
Other tests check that every holding appears exactly once with the same quantity,
and compare the saved example against independently calculated values:
GROWTH / AAPL.US = 2450.00 USD; HEDGE / AMZN.US = -1138.05 USD.
These values exclude cash and settlement obligations and are not NAV or profit.

From the repository folder in PowerShell:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select +portfolio_valuation
```

The leading + includes upstream models and their checks, so the holdings and
prices are rebuilt with the current delivery variables before valuation.
The trade and price delivery IDs are separate provenance fields, not join keys.
All six price observations remain in staging; only matching dates enter valuation.

After a successful build, inspect in Snowsight:

```sql
SELECT valuation_date, portfolio, instrument, quantity, currency,
       close_price, market_value
FROM NORTHBRIDGE_DEV.DBT_DEV.PORTFOLIO_VALUATION
ORDER BY portfolio, instrument;
```

The user confirmed the price view build and its ten tests passed live.
The user confirmed the full live build passed on September 21, 2026:
5 models, 40 tests and 1 hook (PASS=46). A failed dbt test can leave a
created table behind; build success is required before treating it as checked.
