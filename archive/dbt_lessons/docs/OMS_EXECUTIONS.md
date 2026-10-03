# OMS execution staging

`models/staging/stg_oms_executions.sql` reads RAW.OMS_EVENTS and creates
NORTHBRIDGE_DEV.DBT_DEV.STG_OMS_EXECUTIONS as a view.

The `oms_delivery_id` project variable selects the saved five-message lesson.
It is separate from the earlier CSV execution delivery. No joins or holdings
calculations are part of this model.

The received CTE extracts JSON fields as text and retains file metadata.
The final SELECT converts dates, timezone-aware timestamps and decimal amounts.
Raw text is retained beside converted values. Failed conversions become NULL,
which the not_null tests flag. Decimal inputs with more than nine fractional
digits are rejected rather than silently rounded.

`oms_executions.yml` checks required fields, message uniqueness and this lesson's
supported values. `valid_oms_execution_fields.sql` checks positive amounts,
date ordering, nonblank identifiers and consistent message/load metadata.
`oms_executions_preserve_rows.sql` checks the delivery is nonempty and that
the staging view keeps the received row count.

Event IDs identify messages. Execution IDs identify trades, which could later
have correction messages. This step accepts only ACTIVE version-1 reports;
corrections and cancellations need explicit handling before extending it.
The model does not deduplicate messages or validate permanent security IDs.

Run from the repository root:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "stg_oms_executions oms_executions_preserve_rows"
```

The row-count test is explicitly selected because it depends on both the raw
source and the model and the helper uses cautious indirect test selection.

Live build on September 24, 2026: one view, 25 data tests and one project hook
passed (PASS=27, WARN=0, ERROR=0). Only this selection was built.
