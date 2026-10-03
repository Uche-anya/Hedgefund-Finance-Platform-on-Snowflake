# First-day account positions

`oms_first_day_positions` adds signed trade quantities for each scenario, date,
fund, account and instrument. Buys add shares; sells subtract them.
The output includes the ticker and currency for later valuation.

This lesson explicitly starts with zero holdings, so the closing quantity equals
the net trade quantity. Apple is 10 + 8 - 3 = 15. Amazon is -5 + 2 = -3.
These are trade-date positions, not settled balances. Execution prices do not
enter the share-count calculation.

The model is a table because it lives under the project's marts folder. A build
replaces its result; it does not append another set of positions.

The input-scope test restricts this lesson to the saved scenario, account and
January 6 date. The execution test rejects repeated execution IDs before they
can double-count a trade. Existing staging tests reject unsupported versions
and statuses. Corrections, opening balances and multiple days need later work.

Output tests check required columns, one position per instrument/account/date,
and the independently calculated 15/-3 result, including missing or extra stocks.

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "+oms_first_day_positions oms_executions_preserve_rows"
```

The plus sign selects the upstream staging model too, so its tests run before
the positions table is built. The raw-to-staging row-count test is explicitly
selected because the helper uses cautious indirect test selection.

```sql
SELECT business_date, account_id, market_ticker,
       opening_quantity, net_trade_quantity, closing_quantity
FROM NORTHBRIDGE_DEV.DBT_DEV.OMS_FIRST_DAY_POSITIONS
ORDER BY market_ticker;
```
