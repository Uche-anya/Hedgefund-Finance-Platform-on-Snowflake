# Historical price load: prepare storage

Open 12_historical_prices.sql locally, copy it into a Snowsight SQL file with
the same name and run all statements. This prepares the table, file format,
internal stage and dbt read grant. Live execution is pending user confirmation.
The final DESCRIBE TABLE result should list 20 columns.

The first 16 columns receive the assembled CSV fields in order. CSV open, high
and low correspond to table open_price, high_price and low_price. Source values
are VARCHAR so dbt can later parse dates and decimals while retaining the
received text. Blank unverified security IDs remain blank at this raw layer.

Four additional fields record ingestion: delivery_id, source_file,
source_row_number and loaded_at. The future COPY statement will supply the
first three; Snowflake supplies loaded_at. input_file/input_row_number identify
the local file used during assembly, whereas source_file/source_row_number
will identify the staged CSV row loaded into Snowflake.

The stage stores uploaded files. The table stores rows loaded from those files.
The file format tells Snowflake to skip the CSV header, handle quoted fields
and retain empty values. Column-count mismatch checking is enabled, but
Snowflake ignores that setting for staged SELECT queries; a future transformed
COPY must also validate the 16-field input shape. No COPY is included yet.

Next input: data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv,
with 250,036 rows and 503 tickers. Upload/loading instructions come next.
The data retains five expected shorter histories and unverified identities;
loading it does not resolve these limitations or change existing dbt models.

Reference: [Snowflake file formats](https://docs.snowflake.com/en/sql-reference/sql/create-file-format)
and [staged-file transformation limits](https://docs.snowflake.com/en/user-guide/data-load-transform).

## Upload and load the verified delivery

The user supplied exit code 0 for setup. Script 13 is prepared for the exact
assembled delivery above. Its local SHA-256 matches the assembly manifest;
the header, all 16-field rows, total count, ticker count and unique ticker/date
pairs were checked before preparing the load.

```powershell
python scripts/snow_admin.py --file snowflake/13_load_historical_prices.sql
```

PUT uploads and compresses the local CSV into its delivery folder on the reused
stage. COPY loads only prices.csv.gz from that folder and adds the delivery ID
and Snowflake file metadata. The source business fields remain text. The final
queries check 250,036 rows, 503 tickers, no duplicate ticker/date groups, and
the expected coverage counts. SQL exit code 0 alone does not validate those
query results; inspect them before running downstream transformations.

The file path in PUT is specific to this workstation. OVERWRITE=FALSE preserves
an existing staged file. FORCE=FALSE uses Snowflake's finite file-load history;
it is not permanent deduplication. Do not rename the file or force-load it to
retry. This is a manual bootstrap, not the daily ingestion implementation.

Live load confirmed by user-supplied output: 250,036 rows, 503 tickers, zero
duplicate ticker/date groups and no COPY errors. The dates span 2024-09-23
through 2026-09-21. There are 498 full 500-row histories and five shorter ones.
