# October 15 close: producer schedule did not fire

The October 15 fund close missed its automatic input window. At 09:56 London
time on October 16, neither GitHub producer workflow had a scheduled run for
the day. Both workflows were active, their enablement variables were `true`,
and Snowflake had no October 15 delivery. The Snowflake readiness task had
returned `WAITING_INPUTS` at its earlier checks.

At 09:56 London time, we manually dispatched the market/fund producer and the
dividend producer for October 15. These were `workflow_dispatch` runs, not
scheduled runs:

- Market/fund: https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/38877074806
- Dividends: https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/38877090509

Both completed. RAW row counts matched the registered deliveries: 8 OMS
trades, 8 settlements, 12,651 Massive prices and 7,592 Massive dividend
events. At 10:00 London time, `DAILY_CLOSE_READY` returned
`READY:2026-10-15`; `DAILY_CLOSE_BUILD` and `DAILY_CLOSE_RECORD` succeeded.
Snowflake recorded exactly one `VALIDATED` close. The two account NAVs were
$5,000,641.85 and $4,999,900.63.

The missed trigger is the incident. The data loading and Snowflake close path
worked once invoked. We have not established why GitHub created no scheduled
producer runs. The cron expressions use supported syntax, and a manual run on
the same deployed commit succeeded. Additional retries on the same scheduler
are not an independent recovery mechanism.

Follow-up: choose an independent trigger or scheduler for the producers, then
prove a new market close arrives without manual dispatch. Keep the current
manual dispatch as a documented recovery path until that test passes.
