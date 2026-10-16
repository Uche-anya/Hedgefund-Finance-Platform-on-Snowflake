# October 15 close: producers started after the readiness window

The October 15 fund close missed its automatic input window. The market and
dividend producers were scheduled through 09:17 and 09:25 London time on
October 16. At 09:56, GitHub had created neither scheduled run. Both workflows
were active, their enablement variables were `true`, and Snowflake had no
October 15 delivery. The readiness task returned `WAITING_INPUTS` at its
earlier checks.

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

GitHub later created scheduled market and dividend runs at 10:01 and 10:06
London time:

- Market/fund: https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/38877606715
- Dividends: https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/38878214840

Those runs found the recovered close or dividend delivery and correctly
skipped new work. They arrived after Snowflake's final 10:00 readiness check.
Without manual recovery, the task graph would not have built the October 15
close in that window. The incident is delayed producer scheduling combined
with a readiness window that ends before a late delivery can be processed.
The data loading and Snowflake close path worked once invoked. The cron
expressions use supported syntax; the cause of GitHub's delay is unknown.

Follow-up: let Snowflake recheck readiness after the scheduled producer window
and raise an alert if the delivery still has not arrived. Evaluate an
independent producer trigger for the delivery deadline; repeated cron entries
on GitHub alone do not guarantee it. Keep manual dispatch as a documented
recovery path until a new close finishes unattended.
