# Settlement exception report

The [late-confirmation lesson](../../../docs/late_settlement.md) advances the current
cutoff to January 8 and clears this exception. The one-row example below
describes the original January 7 report, retained in SETTLEMENT_REPORT_HISTORY.

`settlement_exceptions` is the operations review list derived from the
reconciliation table. It keeps mismatched and unexpected confirmations, plus
trades with no confirmation on or after their settlement due date.

The report excludes matched trades and trades not yet due. Date comparison uses
the scenario's UTC report cutoff, not the current computer date. Same-day
missing confirmation is a review item; this model does not label it overdue
or determine a contractual settlement deadline.

For the saved lesson it contains one row: BUY 2 AMZN.US, USD 448.52 expected
outflow, confirmation unknown, as of January 7, 2025 at 22:00 UTC. The other
four trades matched and require no review in this report.

The reason describes the observed discrepancy, not a root cause. The manifest's
missing-ID list is not consulted. There is no machine learning involved.
Delivery and event identifiers are retained so someone can inspect the inputs.

This is a rebuilt report, not a permanent case-management system. It does not
assign owners, send notifications or preserve prior open/closed case history.
If a later confirmation is included and matches, a rebuilt report will omit
that trade; the earlier raw records remain. Later deliveries and historical
report snapshots are separate work.

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "+settlement_exceptions oms_executions_preserve_rows settlements_preserve_rows"
```

```sql
SELECT instrument_id, side, expected_quantity, expected_currency,
       expected_cash_change, exception_type, review_reason, as_of
FROM NORTHBRIDGE_DEV.DBT_DEV.SETTLEMENT_EXCEPTIONS;
```
