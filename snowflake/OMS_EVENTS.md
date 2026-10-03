# Load the five execution messages

Live load verified on September 23, 2026: five files loaded, zero load errors,
five distinct event IDs and five distinct execution IDs, all simulated.
Setup run: `data/admin_runs/a183ec1b6ff3422083d77355688ad405.json`.
Load run: `data/admin_runs/f2b6ad2bf4c64d74ae14e6b3699b2bcc.json`.

`14_oms_events.sql` creates the raw table, JSON file format and reusable stage.
`15_load_oms_events.sql` uploads and loads the saved January 6 lesson.

`34_oms_snowpipe.sql` adds the production-style Snowpipe object. It keeps
automatic notifications off because the source is a Snowflake internal stage.
The producer uploads a validated file and explicitly gives Snowpipe its path.

Run from the project folder:

```powershell
python scripts/snow_admin.py --file snowflake/14_oms_events.sql
python scripts/snow_admin.py --file snowflake/15_load_oms_events.sql
```

## Load one new simulator event through Snowpipe

Create the pipe once:

```powershell
python scripts/snow_admin.py --file snowflake/34_oms_snowpipe.sql
```

Then choose one saved simulator file:

```powershell
python scripts/load_oms_snowpipe.py data/simulator/<event-file>.jsonl
```

The loader validates the JSON, uploads it below a delivery-specific stage path,
calls Snowpipe and waits until the expected row count is present in
`RAW.OMS_EVENTS`. It writes a local audit record under `data/ingestion_runs`.
The delivery ID comes from the file hash, so an exact retry uses the same path.

`payload` is a VARIANT column: it holds the parsed JSON object, including
the fictional trade and its historical price reference. The original files
remain on disk; VARIANT does not preserve their original whitespace.

The other columns record the source, scenario, delivery, filename, row number
and load time. The scenario groups a simulation; the delivery groups an upload.
For this single-batch lesson they use the same identifier. Future scenarios
can span multiple deliveries.

The stage is reusable. Each delivery has its own folder. The COPY statement
names the five expected files and stops on a load error. FORCE = FALSE uses
Snowflake's file load history to skip files already loaded; this is not a
permanent event-ID deduplication mechanism.

The count query should return five rows, five distinct event IDs, five distinct
execution IDs and five simulated events. The final query shows the trade fields
without creating a dbt model yet.

This is a file-based load, not an active streaming pipeline. Broker statements
and FX remain separate next steps.
