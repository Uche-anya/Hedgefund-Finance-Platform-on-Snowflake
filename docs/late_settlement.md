# A confirmation published after the report cutoff

Verified live on September 24, 2026: the final build passed 64 data tests
(PASS=71 including models and hook). The history contains five rows at each
cutoff, and the current exception report is empty. Two Python tests passed.
Load record: `data/admin_runs/02539f79e2964263b958544f02c6a0ce.json`.

The original report at January 7, 2025, 22:00 UTC contains four matching
settlements and one missing Amazon BUY 2 confirmation. We saved those five
rows before processing the late message.

`python -m simulation.late_settlement` creates only the missing confirmation.
It reports settlement on January 7 at 17:03 UTC, but publication on January 8
at 09:00 UTC. Its cash amount is -448.52 USD. This is fictional delayed
reporting, not an assertion that the payment occurred late.

Saved delivery: `data/simulator_settlements/2cfd3d50543c480dbbd15dae315c2cfa`.
The original four-message delivery is unchanged. The simulator preserves
trade linkage and uses stable event IDs so replay is not a new payment.

`snowflake/17_late_settlement.sql` uploads that one file to the existing stage
under a new delivery folder and loads it into RAW.SETTLEMENT_EVENTS.
The original four rows and the new row remain separately traceable.

Staging now reads the original delivery plus `settlement_late_delivery_id`.
Uniqueness tests span both selected deliveries. This is a two-delivery lesson,
not yet general ingestion of an unlimited number of delivery batches.

The reconciliation still filters publication time at `settlement_cutoff`.
We first rebuilt at the January 7 cutoff after loading the fifth message:
63 data tests passed, including the missing-confirmation expectation and the
comparison to saved history. The later message did not change that report.

The project cutoff then moves to January 8 at 10:00 UTC. At this cutoff, all
five confirmations are available, and the expected exception count is zero.
The scenario-specific tests now account for the known publication time.

## Saved reports

`settlement_report_history` is an incremental dbt model: it appends a new
scenario/cutoff report instead of replacing the entire table. A repeated build
of an already saved cutoff inserts no rows. `full_refresh=false` prevents an
ordinary full-refresh build from replacing this history. Raw source messages
also remain stored.

The history test checks five rows for each cutoff, four then five matches,
and one then zero missing confirmations. Another test compares the saved
current report to the live result and fails if an existing cutoff changes.
This is a single-writer lesson; it is not a concurrent case-management or
tamper-proof audit system. Revised historical reports need explicit versioning
before that use case is added.

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "+settlement_exceptions settlement_report_history settlement_history_matches_current oms_executions_preserve_rows settlements_preserve_rows"
```

```sql
SELECT as_of, reconciliation_status, confirmed_cash_change,
       settled_at, confirmation_published_at
FROM NORTHBRIDGE_DEV.DBT_DEV.SETTLEMENT_REPORT_HISTORY
WHERE execution_id = 'SIM-EXEC-bf8211379ba04580a5b707ada1183f9d'
ORDER BY as_of;
```

This historical replay uses simulated source publication times. It does not
claim that the warehouse actually received these messages in January 2025.
