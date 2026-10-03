# Compare expected cash with settlement confirmations

The [late-confirmation lesson](../docs/late_settlement.md) adds a second delivery
and advances the cutoff to January 8. The four-match/one-missing results below
describe the original January 7 report, which is retained in history.

The four saved fictional custodian files were hash-checked and loaded with
`snowflake/16_settlement_events.sql`. The raw table stores full JSON and load
metadata. The reusable stage separates delivery folders. COPY uses FORCE=FALSE,
which skips files in load history; it is not permanent event-ID deduplication.
Load record: `data/admin_runs/423e6aedc3b34f77ad54b12311aeb7a4.json`.

`stg_settlements` extracts identifiers and converts amounts and timestamps.
Its tests require full, unique, simulated settlement confirmations. Partial
settlements, reversals and aggregation across multiple deliveries are not
implemented. Replays need event-ID checks across deliveries before expansion.

`oms_settlement_reconciliation` compares these confirmations with OMS_TRADE_CASH.
It uses a FULL OUTER JOIN on scenario and execution ID so neither an unmatched
trade nor an unexpected confirmation disappears. Account, fund, broker,
instrument, side, currency, quantity and cash amount must agree for MATCHED.

Statuses:

- MATCHED: the confirmation agrees with the expected trade details and amount.
- NO_CONFIRMATION: no confirmation available at the cutoff; payment failure is
  not established. Confirmed amount remains NULL rather than becoming zero.
- DETAILS_MISMATCH: a linked confirmation disagrees with the trade.
- UNEXPECTED_CONFIRMATION: a confirmation has no matching trade in this scope.

MATCHED describes agreement, not timeliness. Due date and actual settlement
date are retained separately; this step does not classify late settlement.

The cutoff variable is January 7, 2025 at 22:00 UTC. The historical replay uses
source publication time and settlement time, not the 2026 ingestion timestamp.
It does not reconstruct what a real warehouse actually knew in January 2025.
The fixed fixture-result test expects this cutoff and these selected deliveries.

Live build on September 24, 2026: four source files loaded with zero errors;
two staging views, two tables, 54 data tests and one hook passed (PASS=59).
The result has four MATCHED rows and one NO_CONFIRMATION: Amazon BUY 2,
expected cash -448.52 USD. No failure cause is assigned. The reconciliation SQL
does not consult the simulator manifest's deliberately missing trade list.

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "+oms_settlement_reconciliation oms_executions_preserve_rows settlements_preserve_rows"
```

```sql
SELECT instrument_id, side, expected_quantity,
       expected_cash_change, confirmed_cash_change, reconciliation_status
FROM NORTHBRIDGE_DEV.DBT_DEV.OMS_SETTLEMENT_RECONCILIATION
ORDER BY instrument_id, expected_quantity;
```

Both inputs are simulated, and the custodian fixtures derive from the OMS
fixtures. This demonstrates reconciliation logic, not independent real-world
confirmation. This remains file-based ingestion; no streaming service runs.
