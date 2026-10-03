# Cash effect of the simulated trades

`oms_trade_cash` creates one row per execution. It uses the agreed execution
price, not the historical closing price used for position valuation.

Gross trade amount = quantity * execution price.
Expected cash change is negative for a buy and positive for a sell.

The five amounts in execution order are -2434.80, +1120.40, -1948.40,
-448.52 and +729.93 USD. Together they produce a net expected outflow
of 2981.39 USD, before fees.

These are contractual amounts, not confirmed cash movements. All five reports
say settlement is due January 7, 2025. No actual settlement messages exist yet.
The model does not assume a starting cash balance or treat short-sale proceeds
as freely available cash. It excludes commissions, borrow fees and margin rules.

The current upstream tests restrict this lesson to its fixed scenario and
original active executions. Correction handling is not implemented.
Tests preserve the execution rows and compare each cash amount against values
independently calculated from the saved messages.

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "+oms_trade_cash oms_executions_preserve_rows"
```

```sql
SELECT market_ticker, side, quantity, execution_price,
       expected_cash_change, settlement_due
FROM NORTHBRIDGE_DEV.DBT_DEV.OMS_TRADE_CASH
ORDER BY executed_at;
```

The result is a table under DBT_DEV. Rebuilding replaces the result rather than
appending another set of cash obligations.
