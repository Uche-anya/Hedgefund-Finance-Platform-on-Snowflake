# 22 September close input inventory

For the provisional 22 September 2026 close, run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/inventory_close_inputs.py --request config/daily_close_20260922.json
```

The script verifies saved file hashes and row counts. It writes the selected
delivery IDs to ignored `data/close_input_inventory/<request_id>.json`. The
request ID is a hash of the date, UTC cutoff, file selection, active dbt model
code and reviewed seed files. Running it twice with unchanged inputs produces
the same ID.

| Input | Selected deliveries | Saved rows |
| --- | ---: | ---: |
| OMS executions through 22 September | 499 | 1,996 |
| Custodian settlements through 22 September | 498 | 1,992 |
| Historical price baseline | 1 | 250,036 |
| 22 September prices | 1 | 20 |
| Opening fund-administrator events | 1 | 2 |
| Confirmed dividend-payment events | 1 | 2 |
| Corporate-action candidates | 1 | 3,271 |
| Corporate-action review records | 1 | 46 |

That is **1,003 selected deliveries**. The 23 September settlement file is
excluded: the 22 September trades are still open at that day's cutoff. The
old dates form a restated historical calculation, not a record of what was
known at each original historical close.

`file_sha256` identifies the saved data file. `receipt_sha256` is the hash the
existing Snowflake loader records in `OPERATIONS.DELIVERIES`. OMS, settlement
and daily-price loaders record the file hash; the administrator and dividend
loaders record the manifest hash. The original price baseline and
corporate-action load have no delivery receipt in that table yet. Their local
hash and row count are verified, but Snowflake RAW must be checked separately.

The inventory and the Snowflake comparison were run in development on 7 October
2026. Request `9ef0a376386be1f0b338ae65` is registered with 1,003 selected
inputs in `OPERATIONS.CLOSE_REQUESTS` and `OPERATIONS.CLOSE_INPUTS`. RAW row
counts and available receipts matched the selection. Three older loads have no
original delivery receipt: historical prices, corporate actions, and corporate
action reviews. They are marked `LEGACY_RAW_COUNT_ONLY`. The request therefore
remains a **CANDIDATE**, not a READY or approved close.

The dbt close was rebuilt twice with this request ID. Both builds passed 31
dbt operations and returned the same result fingerprints: 1,002 account-day NAV
rows and 19,574 account-security-day position rows through 22 September. This
is a repeatability check for the current input selection. It does not prove
that the three legacy RAW loads contain exactly the saved bytes, or that NAV is
independently reconciled to broker and bank records.

To reproduce the development check, run the inventory script above, then
`scripts/verify_close_inventory.py`, `scripts/register_close_request.py`, and
the dbt build with `--vars 'close_request_id: <request_id>'`. The Snowflake
comparison exits with a nonzero status while those three original receipts are
missing; the registration script records the limited evidence explicitly.

A corrected delivery or changed dbt code and tests generates a different
request ID. The controlled correction and saved result versions are described
in [close_correction_pilot.md](close_correction_pilot.md). The current dbt
tables are shared development outputs; the separate result ledger preserves
each candidate. An approval gate is still needed before the daily Task.
