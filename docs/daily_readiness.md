# Daily close readiness

The 22 September 2026 provisional close now has a saved request in
`config/daily_close_20260922.json`. It names the scenario, business date,
UTC cutoff and the exact OMS and market-price manifests.

Run the check from the project root:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/check_daily_readiness.py --request config/daily_close_20260922.json
```

The check verifies file hashes and counts locally, then compares Snowflake
delivery receipts with every RAW trade and price row for that date. It rejects
missing rows, another delivery for the same day, repeated event or execution
IDs, repeated price tickers, changed closes and trades published after the
cutoff. It writes one local attempt record under `data/daily_close_checks/`.
It does not run dbt or approve NAV.

The request ID is calculated from the selected input bytes, date and cutoff.
Repeating the same request gives the same ID. A replacement file or changed
cutoff gives a new ID and must be reviewed as a new close request; the checker
does not silently replace an earlier result. The two-year dbt test
`two_year_execution_once.sql` also fails if an active execution or settlement
appears twice in the scenario.

For this first provisional gate, the required current-day inputs are OMS fills
and closing prices. A trade dated 22 September can settle on 23 September, so
the 23 September confirmation is **not** required for the 22 September close.
The full production gate still needs explicit due-settlement policy, corporate
action and reference-data version pins, a Snowflake-owned run ledger, and a
separate restatement process. A local attempt record is useful evidence but
cannot coordinate concurrent workers or make a Snowflake Task idempotent.

The checker passed against development Snowflake on 7 October 2026: four OMS
events and 20 price bars matched the saved 22 September request. The wider
historical selection is recorded separately in `close_input_inventory.md`.
The Task is not deployed or resumed. Do not use this gate to publish NAV.
