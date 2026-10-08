# Daily ingestion

The two-year backfill is the starting history. Each new US equity session adds
one price package, one simulated OMS package, and any simulated settlements
due that day. The files keep their original delivery IDs and checksums, so a
retry can inspect the same evidence instead of making a new trade history.

`scripts/ingest_market_day.py` is the entry point for this part of the job:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/ingest_market_day.py --day 2026-09-23 --next-session 2026-09-24
```

The scheduler supplies the US market date and the next US market session. It
must use a market calendar; adding one calendar day is wrong before weekends
and exchange holidays. The job reads `MASSIVE_API_KEY` from its environment.
For a one-off run in a terminal, it asks for the key without echoing it.
It reuses a completed provider download, resumes a partial one, and rejects
ambiguous downloads. It then prepares the checked price CSV, generates OMS
fills using the last *provider* close, and generates confirmations from earlier
fills due today. Finally it loads prices through the price loader and sends
OMS and settlement files through Snowpipe. `--no-load` checks and prepares
files without contacting Snowflake.

This is one entry point over existing modules, not a second implementation of
price parsing, simulation, or Snowpipe. A saved DEV price correction is kept
out of the simulator's previous-close choice. Repeating a saved day uses the
same file bytes and delivery IDs; a changed saved file raises an error.

## What still prevents unattended closes

The entry point covers **ingestion**, not the whole close. Today a person
still has to supply the market calendar dates, configure the Massive secret in
the job environment, verify/register the close request, and trigger the
request-specific Snowflake Task. The current request-registration script uses
an interactive admin login, and the Task root expects a supplied request ID.
Neither belongs in an unattended job. The next build step is a limited service
identity and a Snowflake-owned ready-request queue, followed by a scheduled
Task that selects one verified request and checks its deployed dbt code hash.
Only then should this be described as a fully automatic daily close.

The 23 September 2026 Massive snapshot is saved as
`data/historical_prices/f6f568cfa2d94f1996eee84b6fad1949`. Its 20 checked
bars loaded to RAW under delivery `daily-prices-dc2c458f1ae07e95b7ec829b`.
The verified input selection `98e072ac531920d74204970d` produced a saved
candidate close: 1,004 account-day NAV rows and 19,614 position rows through
23 September. It is a restated build made after the historical date, not proof
of what the fund knew at that date's original cutoff. Three older source loads
still have count evidence but no original delivery receipt.
