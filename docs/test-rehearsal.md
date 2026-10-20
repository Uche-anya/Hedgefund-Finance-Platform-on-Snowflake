# TEST delivery rehearsal: October 6, 2026

This is a separate first-day scenario in `NORTHBRIDGE_TEST`. The October 16
fixture used by CI remains available. No TEST task runs on a schedule.

| Input | TEST result |
| --- | ---: |
| Massive unadjusted closes, October 5 | 12,621 rows |
| Massive unadjusted closes, October 6 | 12,579 rows |
| Massive dividend snapshot, October 6 | 8,646 events |
| Fictional opening bank and fund-admin records | 2 accounts each |
| Fictional OMS executions via Snowpipe | 4 rows |
| Fictional settlement delivery | 0 rows, explicitly `EMPTY` |
| Fictional bank statement | 2 balances |

The scenario is `sim-test-20261006`, with October 5 as its opening date.
The first trades settle October 7, so the October 6 settlement delivery is
correctly empty. `scripts/ingest_first_day.py` prepares the first-day fund
records from the saved October 5 price file and sends all deliveries to TEST.
It requires `NORTHBRIDGE_ENV=test` and the `NORTHBRIDGE_INGEST_TEST` role.
The TEST key is local and excluded from Git.

`pipeline.check_raw` reported all seven required source checks ready and
confirmed every held ticker had a close. The TEST dbt build completed with
`PASS=47 WARN=0 ERROR=0`. Both account bank reconciliations were `MATCH`:

| Account | October 6 NAV (USD) |
| --- | ---: |
| SIM-ACCOUNT-01 | 4,999,979.50 |
| SIM-ACCOUNT-02 | 5,000,037.08 |

`scripts/record_close.py` wrote one `VALIDATED` TEST close after checking
those outputs. Repeating the delivery reported files already loaded or
submitted; repeating the close record reported already validated. A separate
scenario with no fund inputs made readiness exit with `RAW is not ready for the
close`, and no close row was recorded for it. The original October 16 TEST dbt
fixture was rebuilt afterward and passed.

This proves the manual TEST path from saved provider files through the close
record. It does not prove a scheduled Snowflake task graph or an unattended
producer. Those need their own rehearsal before PROD scheduling.
