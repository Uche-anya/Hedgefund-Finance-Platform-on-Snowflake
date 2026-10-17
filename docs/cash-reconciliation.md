# Daily cash check

The daily simulated bank statement compares its closing balances with dbt's
calculated cash. The statement is a separate delivery. It is not copied from
`FCT_CASH_DAILY` or the settlement table.

The bank simulator starts with the $5 million October 7 opening bank record.
It posts each trade on its scheduled settlement date, using the saved OMS
execution. For October 16 it gives $4,994,888.65 and $4,978,139.30. Those
match the separately calculated cash, which uses settlement confirmations.
The simulator stops when a booked dividend reaches its pay date because we do
not yet have a separate bank payment event. Both sides still depend on
fictional trading activity. A match is not confirmation from a real bank.

To prepare a daily statement from the saved opening and trade events:

```powershell
python -m pipeline.produce_bank 2026-10-16
```

The scheduled workflow retries before the Snowflake close window and uses
`--submit` to stage the saved JSONL file and load `RAW.DAILY_BANK_STATEMENTS`.
The delivery registry records its row count and file hash. The dbt view
`DBT_DEV.FCT_CASH_RECONCILIATION` compares bank and modeled cash by date,
scenario and account. Its statuses are `MATCH`, `BREAK`, missing bank or model
cash, duplicate bank row, and bad bank balance.

The Snowflake READY task waits for one complete bank delivery. After dbt runs,
the RECORD task refuses to validate the close unless both accounts have
`MATCH`. The 5:30 a.m. close deadline then reports any unresolved run. A cash
break is a review item, not an automatic adjustment to NAV.

The October 16 TEST build passed. A one-cent change produced `BREAK`, and
removing an account produced `MISSING_BANK_STATEMENT`; both changes were rolled
back. The bank readiness procedure returned `READY` for October 16 and
`WAITING_BANK` for October 15. The example CSV is kept in `examples/` for
reproducing the first delivery.
