# First Snowflake integration

The user has activated a trial and is running setup manually in Snowsight.
The local Python pipeline remains our reference for checking financial results.

## Create the development database

Run `01_database.sql` in order in a Snowsight SQL file.
The final query should return SYSADMIN, NORTHBRIDGE_DEV and RAW.

- Database: the container for this project's schemas and tables.
- Schema: a named group of objects inside a database.
- RAW: where incoming source records will be loaded before dbt transformations.
- SYSADMIN: the built-in object administration role used for this initial setup.
- IF NOT EXISTS: permits rerunning setup without replacing an existing object.
  It does not verify the settings or ownership of an existing object.

This step creates no source tables and loads no data. Dedicated runtime roles,
raw trade tables, file loading and dbt follow. SYSADMIN is not the intended
scheduled pipeline role.

## Execution evidence

The supplied screenshot shows COMPUTE_WH as X-Small and suspended.
AUTO_SUSPEND=60 and AUTO_RESUME=TRUE were supplied to the user; their execution
has not been independently verified. Trial expiry and remaining balance have
not yet been recorded.

`01_database.sql`: UNVERIFIED against the live account until its execution
results are supplied. Local file creation and documentation review do not
prove Snowflake permissions or execution.

References:
- https://docs.snowflake.com/en/sql-reference/sql/create-database
- https://docs.snowflake.com/en/sql-reference/sql/create-schema

## Incoming executions table

Run `02_executions.sql` after database setup. Its final DESCRIBE statement
should list ten columns. Live execution remains UNVERIFIED.

One raw row represents one received execution record from a delivery file.
It is not yet a deduplicated trade. The first five columns match the existing
executions.csv contract, in the same order. Source fields remain text so an
invalid date or quantity can be retained for investigation. dbt must validate
and convert them before any financial calculations; those models are pending.
The original CSV and its manifest remain the evidence for the exact file bytes.

The loader will supply source_system (initially simulated_oms), delivery_id
from the saved delivery manifest, source_file, and source_row_number (Snowflake's
METADATA$FILE_ROW_NUMBER, preserved without renumbering). loaded_at records the
Snowflake insertion time, not the trade execution time. TIMESTAMP_LTZ displays
the instant in the session's time zone.

The logical identity of a received record is source_system + delivery_id +
source_file + source_row_number. No uniqueness is enforced by this DDL.
Loading retries and duplicate/conflicting execution IDs must be handled by
the upcoming loader and dbt checks before holdings are released.

This is a quantity-only source contract. Prices, currency and settlement terms
come from the separate execution_terms contract later. Orders and intraday
execution timestamps are not yet modeled. No data is inserted by this script.

Reference: https://docs.snowflake.com/en/sql-reference/sql/create-table

## Incoming allocations table

Run `03_allocations.sql`. DESCRIBE should list ten columns. Live execution is
UNVERIFIED until results are supplied. This script inserts no records.

One raw row is one received allocation record. The five source columns match
allocations.csv; the five lineage columns follow the executions table convention.
An execution may have several allocations, each with its own allocation_id.
For example, a buy of ten shares may allocate six to GROWTH and four to HEDGE.
Allocation quantity is positive; the linked execution supplies BUY or SELL.

For this first slice, execution IDs are assumed unique within a source system.
dbt must resolve repeated records before joining allocations to executions on
source_system + execution_id, validate matching business dates, reject unknown
execution IDs and conflicting duplicates, and require total allocated quantity
to equal executed quantity. These checks are not enforced by the raw table DDL.
Do not sum execution quantities after a one-to-many allocation join: that would
count the execution once for every allocation. Holdings use allocation quantities
with the execution's sign. Runtime roles, loading and dbt models remain pending.

## First manual file load

1. Run `04_sample_stage.sql` in Snowsight. The initial LIST should be empty.
2. Open Ingestion > Add Data > Load files into a Stage. Select both CSVs from
   `data/snowflake_upload/2025-01-06` and select
   NORTHBRIDGE_DEV > RAW > OMS_SAMPLE_20250106. Leave the path blank and upload.
3. Run LIST again. Expect one executions.csv and one allocations.csv (a .gz
   extension is also accepted). Do not upload both compressed and plain copies.
4. Run `05_load_sample.sql` statements in order. Stop on any error. The first
   grant lets SYSADMIN use COMPUTE_WH; subsequent commands run as SYSADMIN.
   Each COPY should load two rows. Inspect the count query and both detail queries.

A stage holds files; a file format describes how to read CSV; COPY INTO loads
records into a table. SKIP_HEADER ignores the column-name line. The first five
file fields map to source columns; constants and Snowflake file metadata fill
the provenance fields; loaded_at uses the table default. No holdings calculation
is done here: that belongs in dbt.

The prepared files are byte-for-byte copies of executions.csv and allocations.csv
from saved delivery `18ae80085f1043789b5d604ee44dc216`. Both hashes were checked
against its local manifest, and build_positions validated the allocations and
expected results: GROWTH holds 10 AAPL.US; HEDGE holds -5 AMZN.US from zero opening
holdings. All trade activity is simulated. No market prices are uploaded here.
If the upload folder is missing, copy only those two files from
`data/landing/2025-01-06/18ae80085f1043789b5d604ee44dc216` after verifying its manifest.

This is a manual bootstrap, not a daily loader. The delivery ID is deliberately
fixed. Uploading another delivery to this stage would mislabel its provenance.
The SQL does not verify uploaded bytes against the local manifest. Automated
manifest verification, schema validation and ingestion auditing remain pending.
CSV width enforcement is disabled for the transformed load; these exact local
files were validated, but arbitrary new files must not use this shortcut.

ON_ERROR=ABORT_STATEMENT stops a failing COPY. The two COPY statements are separate,
so the first can succeed while the second fails. Do not run downstream work until
both pass. FORCE=FALSE uses Snowflake's finite file-load history to skip files it
recognizes as already loaded; it is not a permanent business-key deduplication
guarantee. Do not rename or overwrite these files to force a retry.

Local verification passed. Stage creation, UI upload, COPY syntax/permissions,
rerun behavior and row contents in Snowflake remain UNVERIFIED until executed.

References:
- https://docs.snowflake.com/en/user-guide/data-load-local-file-system-stage-ui
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
- https://docs.snowflake.com/en/user-guide/querying-metadata

## Live evidence and dbt handoff

The user supplied a stage LIST screenshot showing both files and an allocations
query showing the expected two records with source metadata. They also confirmed
that the count query returned two executions and two allocations. Earlier
UNVERIFIED labels describe the status when scripts were first prepared; execution
row details and load retry behavior have not yet been independently verified.

The first dbt project is prepared in `../dbt`; see [its run guide](../dbt/README.md).
Offline parsing and dependency checks passed. Run `06_dbt_access.sql` manually
before connecting dbt. Its role grants and live dbt execution remain pending.
# Assembled historical prices

For the 503-ticker dataset, start with [the historical price setup](HISTORICAL_PRICES.md)
and `12_historical_prices.sql`. This prepares storage; loading is a separate step.
