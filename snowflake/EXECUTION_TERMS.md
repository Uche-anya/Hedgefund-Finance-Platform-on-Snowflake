# Trade prices and payment dates

Execution terms describe the agreed price, currency and settlement due date
for each existing trade. A due date is not confirmation that payment happened.
This step only lands raw records; dbt validation and obligations come next.

Use the existing saved delivery, not a newly generated scenario:
`data/landing/2025-01-06/18ae80085f1043789b5d604ee44dc216/execution_terms.csv`.
The upload copy is `data/snowflake_upload/2025-01-06/execution_terms.csv`.
Both are ignored local data. These are simulated trades whose execution prices
were set equal to the saved January 6 closing prices by build_hybrid.py.
Actual execution prices need not equal closing prices. The earlier $244 Apple
example was illustrative and is not part of this saved delivery.

1. Run all of `10_execution_terms.sql` in Snowsight to create the raw table
   and give the dbt role read access.
2. Upload only execution_terms.csv to NORTHBRIDGE_DEV.RAW.OMS_SAMPLE_20250106,
   using SYSADMIN. Leave the optional folder path blank.
3. Run all of `11_load_execution_terms.sql`. Expect a count of two and two
   displayed records. Payment is due January 7 for both trades.

Reuse the same OMS delivery ID: the file already belongs to that saved bundle.
The COPY filename pattern excludes executions.csv and allocations.csv in the
same stage. FORCE=FALSE uses Snowflake load history to skip already loaded files;
it is not a permanent duplicate-prevention guarantee. Business fields stay text
in RAW; loading successfully does not establish that financial rules passed.

Local verification checks the original manifest hashes, unchanged upload bytes,
and exactly one terms record per matching execution ID and business date.
Snowflake table creation and loading remain pending user execution.
