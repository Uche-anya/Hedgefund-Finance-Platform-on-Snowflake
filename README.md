# Northbridge daily close

The aim is to run one fund close per business day. Market prices come from a
real data provider. Trades, settlements, and fund activity
are simulated because this portfolio project has no live broker or fund account.
Every record keeps its source, so the two kinds of data are distinguishable.

The old two-year data is saved under `data/`. This reset starts with daily
delivery checks and Snowpipe ingestion. The first cash and NAV calculation
covers 24 and 25 September 2024.

## Check one saved day

From the project directory, run:

```powershell
python -m pipeline.check_day 2024-09-25 --scenario sim-equity-2024-2026-v2 --prices data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv
```

The check reads that day's OMS and settlement manifests. A manifest names the
delivery, states how many records to expect, and stores a hash of the file.
The hash tells us if the file has changed since it was prepared. The check
also looks for that day's closing price for every stock traded that day.
It exits with an error if an input is missing or inconsistent.

September 24 is the first trade day in the saved daily scenario. The opening
package records cash on September 23, and there are no earlier saved trades.
`pipeline.first_day_settlement` checked those facts and wrote an empty,
zero-record settlement delivery. This is an explicit statement from our
simulator; a missing delivery is never treated as zero. To check the saved day:

```powershell
python -m pipeline.check_day 2024-09-24 --scenario sim-equity-2024-2026-v2 --prices data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv
```

The producer refuses to overwrite the delivery if run again. The empty
delivery has a hash and a manifest just like a nonempty one. It is still
simulated evidence, not an independent custodian statement.

This is a local check of saved backfill data. For a daily run, the producer
will put each delivery in a dated landing path. Snowpipe will copy landed
records into Snowflake RAW tables. We will use warehouse readiness checks
before scheduling dbt and publishing a NAV. A failed or late delivery must
stop publication; retrying the same delivery must not add its records twice.

## Snowflake RAW landing

Snowflake CLI is installed under `.venv/cli`. To test the personal admin
connection, run `.\.venv\cli\Scripts\python.exe scripts\snow_admin.py`. It reads the existing password
from Windows Credential Manager, asks for an MFA approval if needed, and keeps
the password out of the command line and config file. Run a SQL file with
`.\.venv\cli\Scripts\python.exe scripts\snow_admin.py --file snowflake/00_remove_legacy.sql`.
The loader uses a separate service user and key, with access only to ingestion
objects.

The cleanup ran on 8 October 2026. Its final inventory returned no tables,
and a separate schema check found only `RAW` remaining from the three project
schemas. Do not rerun it after new dbt models are built in `DBT_DEV`.
This removed old Snowflake data, not the saved two-year source files under
local `data/`.

`snowflake/01_daily_raw.sql` creates two RAW event tables, a delivery registry,
an internal stage, and two Snowpipe pipes. `snowflake/02_ingest_access.sql`
grants a loader role access to those objects. `snowflake/03_loader_user.sql`
creates the service user and assigns its public key. Run those files in that
order with an administrator role. The registry is a list of expected deliveries
and file hashes; it is not proof that Snowpipe finished.
`snowflake/04_check_day.sql` compares expected row counts with rows in RAW.
`snowflake/05_daily_prices.sql` adds the RAW price table and grants the loader
access to it.

The `01_daily_raw.sql`, `02_ingest_access.sql`, and `03_loader_user.sql` setup
ran on 8 October 2026. The three tables started empty, both pipes were present,
and the loader connected with its own key and `NORTHBRIDGE_INGEST_DEV` role.

`pipeline.load_day` checks the local files and plans stable stage paths. Run it
without `--submit` to see the paths without connecting:

```powershell
python -m pipeline.load_day 2024-09-24 --scenario sim-equity-2024-2026-v2 --prices data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv
```

With `--submit`, it registers the deliveries, uploads nonempty files to the
internal stage, and asks Snowpipe to load them. The empty settlement delivery
is recorded in the registry but has no event rows to load. A retry uses the
same path and delivery ID; a changed file cannot reuse that ID. This assumes
one producer owns each source and date. We still check RAW row counts before
calling a day complete. `python -m pipeline.check_raw 2024-09-24 --scenario
sim-equity-2024-2026-v2 --opening-date 2024-09-23` is the automated gate: it exits with an error if a
source is missing, registered twice, or has the wrong number of RAW rows.

The Python packages are installed in `.venv`. A new private key lives at
`.secrets/northbridge_loader.p8`; Git ignores it, and its Windows file access
is restricted. Only its public half appears in `03_loader_user.sql`. Set these
environment values in the terminal that runs the loader:

```powershell
$env:SNOWFLAKE_ACCOUNT = 'gxmgyta-fq45953'
$env:SNOWFLAKE_USER = 'NORTHBRIDGE_LOADER'
$env:SNOWFLAKE_ROLE = 'NORTHBRIDGE_INGEST_DEV'
$env:SNOWFLAKE_PRIVATE_KEY_FILE = (Resolve-Path '.secrets/northbridge_loader.p8').Path
```

Then add `--submit` to the `pipeline.load_day` command above and run
`python -m pipeline.check_raw 2024-09-24 --scenario sim-equity-2024-2026-v2 --opening-date 2024-09-23`.
The Snowpipe API uses the service user's default role; the setup SQL makes that
the loader role. This key is unencrypted for unattended local development; in
a hosted production deployment, keep it in a managed secret store. Corporate
actions need their own daily readiness rule because some days legitimately
have no actions.

## First loading check

The first submission for 24 September 2024 found an upload-path bug: `PUT`
appended the filename to a destination that already contained it. Snowpipe
registered the intended filename as failed and RAW stayed empty. The loader now
uploads to the parent directory. We recovered that one file with
`pipeline.recover_file`, which checks the registry and confirms RAW has no rows
before making an explicit `COPY`. The 24 September RAW check then passed with
four OMS rows and an explicitly empty settlement delivery. That recovery was a
manual COPY, not a successful Snowpipe load.

The next saved day, 25 September, used the corrected path. Snowflake copy
history showed `DAILY_OMS_PIPE` loaded four OMS rows and
`DAILY_SETTLEMENT_PIPE` loaded four settlement rows. A second submission
reported that both deliveries were already submitted, and both counts stayed
at four. These checks prove ingestion and retry behaviour for these two saved
days. They do not yet prove an unattended daily schedule, dbt, or NAV publication.

If a future pipe file fails, inspect `COPY_HISTORY` and the staged path first.
Snowpipe remembers failed filenames and will ignore a second request for the
same name. Only after confirming that RAW contains zero rows for the delivery,
an operator can run `python -m pipeline.recover_file <date> --scenario
<scenario> --source <oms|settlements>`. That command loads the file with a
one-time `COPY`; it is not part of the normal daily run.

## Real closing prices

The saved `assembled_prices` CSV came from Massive. `pipeline.prices` extracts
one market date into an immutable JSONL delivery and a manifest. It rejects
duplicate tickers, non-USD rows, non-Massive rows, adjusted prices, and missing
or nonpositive closes. The manifest records hashes of the source snapshot and
daily file. The loader stages that file and uses one `COPY` to put its rows in
`RAW.DAILY_PRICE_EVENTS`. The first three closes used a saved historical CSV.
`pipeline.massive_prices` can now fetch a new dated CSV from Massive's grouped
daily market endpoint and hand it to this same loader.

The 24 and 25 September 2024 deliveries were loaded on 9 October 2026: 498
real price rows per date. A repeat of 25 September found the existing delivery
and left the count at 498. The updated `pipeline.check_raw` gate now requires
one market delivery and one valid, unadjusted USD close for every nonzero
holding. On 25 September it checked positions from both loaded trade days;
eight stock tickers were involved. The four prices read back from Snowflake
were AAPL 226.37, AMZN 192.53, BAC 39.25 and KO 71.45.

To prepare or retry a saved day, set the loader environment variables above and
run:

```powershell
python -m pipeline.prices 2024-09-25 --prices data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv --submit
python -m pipeline.check_raw 2024-09-25 --scenario sim-equity-2024-2026-v2 --opening-date 2024-09-23
```

These are historical provider prices already saved locally. An unattended
daily API fetch, corporate actions, security mapping and NAV
publication remain separate work.

## First dbt position values

The first valuation layer starts with `stg_executions`, which
types the simulated trades and keeps the latest report per execution ID.
`stg_prices` types the Massive closes. `fct_position_daily` adds buys and
subtracts sells through each price date, then multiplies the resulting shares
by that day's close. A short position therefore has negative shares and a
negative market value. These are position values, not account NAV; cash and
liabilities are not included.

The dbt service user has its own key and role. It can read the five RAW
tables used by this pilot and create views or tables only in `DBT_DEV`. The private
key is ignored by Git. Set its path before running dbt:

```powershell
$env:NORTHBRIDGE_DBT_KEY_PATH = (Resolve-Path '.secrets/northbridge_dbt.p8').Path
.\.venv\dbt\Scripts\dbt.exe build --project-dir dbt --profiles-dir dbt --vars '{business_date: 2024-09-25, opening_date: 2024-09-23, scenario_id: sim-equity-2024-2026-v2}'
```

Run `pipeline.check_raw` first. A successful dbt build does not replace the
delivery readiness gate. The first build produced 12 position rows across 24
and 25 September 2024. For example, account `SIM-REPLAY-01` held 60 MSFT
shares on both days; their values were 25,750.20 and 25,926.60 USD using each
day's real close. The same account's 56-share UNH short had a negative value.

This pilot joins the simulator's reviewed set of tickers directly to prices.
Before using broader dates or securities, the daily path needs a reviewed
instrument map for symbol changes and corporate actions. It also needs a
scheduled readiness gate and NAV publication.

## First cash and NAV

The saved opening package has two bank balances of $5 million on 23 September
and two matching fund-admin subscriptions. Run `snowflake/07_opening_cash.sql`
once to create the RAW table and grant access. Then, with the loader settings
above, load and check it:

```powershell
python -m pipeline.opening 2024-09-23 --scenario sim-equity-2024-2026-v2 --submit
python -m pipeline.check_raw 2024-09-25 --scenario sim-equity-2024-2026-v2 --opening-date 2024-09-23
```

The bank amount is starting cash. The subscription checks it; we do not add
the subscription a second time. `stg_settlements` reads the simulated
confirmation amount with its sign: buys are negative cash and sells are
positive. `fct_cash_daily` moves that amount from unsettled trade cash into
calculated cash when settlement occurs. `fct_nav_daily` then adds calculated
cash, unsettled trade cash and the net value of stock positions. The latter
includes negative values for short positions.

The 25 September build completed with 28 passing dbt results. Account
`SIM-REPLAY-01` had $5,006,079.04 calculated cash, $2,044.19 unsettled trade
cash and -$8,472.71 net stock value, yielding $4,999,650.52 NAV. Account
`SIM-REPLAY-02` yielded $4,999,008.00. Query
`NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY` to see both days.

These are provisional pilot values. The settlement confirmations, opening bank
balance and fund-admin events are simulated. There is no independent daily
bank reconciliation, borrow-fee accrual, corporate-action accounting, or
publication lock yet. The pipeline has not been scheduled to fetch daily
market prices or run unattended.

## Run the next saved close

`pipeline.run_close` runs the 26 September pilot as one command. Use the
project's main `.venv` Python: it contains the Snowpipe SDK. Set both the
loader settings shown above and `NORTHBRIDGE_DBT_KEY_PATH`, then run:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_close 2024-09-26 --scenario sim-equity-2024-2026-v2 --opening-date 2024-09-23 --prices data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv --submit
```

Without `--submit`, the command checks the saved files locally. With it, the
controller submits OMS and settlement files to Snowpipe, loads the day's
saved Massive prices, waits for the RAW delivery gate, runs `dbt build`, and
checks that each opening account has one non-null NAV for that date. It writes
one attempt to `RAW.DAILY_CLOSE_RUNS`: `VALIDATED`, `WAITING_INPUTS`, or
`FAILED`. The full dbt output is kept under the ignored `data/close_runs/`
folder. A retry uses the same delivery IDs and does not load their rows again;
each attempt gets its own run log row.

The 26 September pilot validated with 4 OMS rows, 4 settlement rows and 498
price rows. Its NAVs were $4,998,968.43 and $4,999,577.67 for accounts 01
and 02. The first attempt failed because it was launched from the dbt-only
Python environment, which lacked the Snowpipe SDK. The retry from the main
environment succeeded, and both outcomes are visible in `DAILY_CLOSE_RUNS`.
`VALIDATED` means the calculations passed; it does not mean the NAV was
published. The market prices here came from a previously saved Massive CSV.
The API fetch was checked against a live Massive response for 2026-10-08.
Running the controller on a schedule remains open.

## Fetch a new market day

`pipeline.massive_prices` requests one unadjusted US stock market summary from
Massive. It saves `data/provider_prices/massive/<date>/prices.csv`, the provider
response and a manifest with the request ID, count and file hashes. The key
comes from `MASSIVE_API_KEY` in the process environment or Windows Credential
Manager; it is never saved with the delivery. To save it once on this Windows
machine, run the command below in your own terminal. It prompts without
echoing the key:

```powershell
.\.venv\Scripts\python.exe scripts/save_massive_key.py
```

If the delivery already exists, a retry checks its hash and uses
the saved file instead of requesting a different price snapshot.
For 2026-10-08, the live request saved 12,592 unadjusted closes. The CSV had
12,592 distinct tickers, its manifest hashes matched, and `pipeline.prices`
prepared all 12,592 rows. The full close for this date is described below.

With your key supplied privately to the terminal or job runner, check the
API delivery for a date your Massive plan allows:

```powershell
.\.venv\Scripts\python.exe -m pipeline.massive_prices YYYY-MM-DD
```

The fetch checks the provider's `adjusted=false` flag, count, duplicate
tickers and positive closes. The Snowflake RAW gate still checks that every
held stock has that day's close before dbt runs.

## October 2026 close using live prices

This is a new, isolated scenario. It opens two fictional accounts with $5m
each on 2026-10-07. `pipeline.sample_close` uses that day's saved Massive closes
as a reference to make four fictional trades on 2026-10-08. It does not use the
8 October close to invent earlier trades. All four are due to settle on
9 October, so the 8 October settlement delivery is explicitly empty.

```powershell
.\.venv\Scripts\python.exe -m pipeline.massive_prices 2026-10-07
.\.venv\Scripts\python.exe -m pipeline.massive_prices 2026-10-08
.\.venv\Scripts\python.exe -m pipeline.sample_close 2026-10-08 --opening-date 2026-10-07 --settlement-due 2026-10-09 --scenario sim-close-20261008 --reference data/provider_prices/massive/2026-10-07/prices.csv
.\.venv\Scripts\python.exe -m pipeline.run_close 2026-10-08 --scenario sim-close-20261008 --opening-date 2026-10-07 --prices data/provider_prices/massive/2026-10-08/prices.csv --submit
```

The last command needs the loader and dbt key environment variables shown
above. It loaded two opening bank records, two opening subscriptions and
12,592 real price rows. Snowpipe loaded four OMS events. The empty settlement
delivery was registered without sending a file to Snowpipe. The RAW gate passed
and dbt passed 29 build results. Account 01 ended at $5,000,063.30 NAV;
account 02 ended at $4,999,901.12. The first run ID was
`11f35956924a40d9a5ff30489994ecad`.

A second run reused all five deliveries and returned the same NAVs. Snowflake
recorded two `VALIDATED` attempts. The dbt price model now starts at the
scenario's opening date, so this October close does not create NAV rows for
the older market dates already present in RAW. The dbt marts are rebuilt for
one scenario per run; they are not a persistent history of every scenario.

This proves a live price fetch through a validated dev close. The trades,
opening records and empty settlement delivery are fictional. There is no
independent broker or bank reconciliation, NAV publication, or unattended
schedule yet.
