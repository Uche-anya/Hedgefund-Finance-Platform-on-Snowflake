# Saved close and price correction pilot

On 7 October 2026 we tested a correction against the 22 September close in
`NORTHBRIDGE_DEV`. This is a development test, not a provider correction or an
approved NAV.

The original request (`61c294231f2d4a5b5512e9c8`) selected the saved Massive
price delivery. The second request (`5d1f1abedf4cbe14e6a6cef3`) selected a
new **simulated** delivery that changes Apple's closing price from $339.75 to
$339.76. Its manifest names the first price delivery in
`replaces_delivery_id`. Both requests selected the same other 1,002 deliveries
and the same dbt models, tests and seeds. RAW keeps both price files; dbt reads
only the one named by the request.

| Account | Apple position-value change | NAV change |
| --- | ---: | ---: |
| SIM-REPLAY-01 | +$3.01 | +$3.01 |
| SIM-REPLAY-02 | +$8.76 | +$8.76 |

Only the two Apple position rows and two NAV rows for 22 September changed.
Both builds passed 31 dbt operations. Each version has 1,002 NAV rows and
19,574 position rows stored in `OPERATIONS.CLOSE_RESULT_ROWS`. The corrected
version points to the original in `OPERATIONS.CLOSE_RESULTS`. Rebuilding the
corrected request returned `MATCHED`; it did not insert duplicate result rows.
Rebuilding the original request *after* the correction landed also returned
`MATCHED`, so the extra RAW price delivery did not alter the original close.
The first attempted corrected build failed because the source test accepted
only Massive prices. We allowed the explicitly named simulated source for the
development target, then rebuilt both versions with that same test contract.
The failed attempt remains in `OPERATIONS.CLOSE_ATTEMPTS`.

To inspect the stored comparison, run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/compare_close_versions.py 61c294231f2d4a5b5512e9c8 5d1f1abedf4cbe14e6a6cef3
```

The result ledger is a development implementation. Three older input loads
still have no original delivery receipts, so these requests remain
`CANDIDATE`. The result rows are saved separately, but the shared `DBT_DEV`
tables always contain the latest build. A genuine price correction would come
from the provider with its own source evidence; this one-cent file exists only
to exercise the mechanics.

## Snowflake Task pilot

`OPERATIONS.CLOSE_GATE` counted 1,003 selected inputs for each version: 1,000
verified, three older loads with missing receipts, and no mismatched loads.
The build gate was `BUILDABLE`; the publication gate remained `NOT_APPROVED`.
The corrected request was rebuilt through `run_pinned_close.py`, which holds a
Snowflake lock during dbt and returned `MATCHED` instead of saving duplicate
rows. Two simultaneous connections confirmed a second lock holder is blocked.
A labelled development fixture also went from `RUNNING` to `INTERRUPTED` under
the lock, proving the recovery update works after a runner stops early.

The deployed Snowflake dbt project ran the same pinned build successfully:
31 operations passed, producing 1,002 NAV and 19,574 position rows. A manual
`EXECUTE TASK` of the unscheduled `CLOSE_PILOT_GATE` root then ran its dbt child.
Snowflake Task history showed both steps `SUCCEEDED`. The shared dbt output
matched the saved candidate's totals and hashes. The root remains suspended;
the child is resumed only so a manual root run can trigger it.

The graph now has a capture step and a failure finalizer. It records an owner
on the same lock row used by the local runner, which refuses an active Task
owner. Capture compares a rerun to the saved totals and hashes, or saves a new
candidate and its rows in one transaction. Two manual runs returned `MATCHED`;
there is still one result header with 1,002 NAV and 19,574 position rows. A
labelled temporary Task owner blocked the local runner and was then cleared.
We deliberately made the dbt child fail once. The finalizer recorded `FAILED`
and cleared ownership; after restoring the normal dbt task, the next run
returned `MATCHED`. The first-time Task `SAVED` branch still needs a new valid
request to test it.

The root remains suspended with no schedule. The Task is fixed to the 22
September corrected request, and deployment code is not yet pinned by the
Snowflake Task itself. Three old delivery receipts are still missing, so this
is a candidate close, not an approved NAV.
