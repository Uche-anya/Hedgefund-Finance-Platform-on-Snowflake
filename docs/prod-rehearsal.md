# PROD close rehearsal: October 16, 2026

The first `NORTHBRIDGE_PROD` close was run manually. It has its own RAW
deliveries and service users; no DEV or TEST records were copied into it.

| Input | PROD result |
| --- | ---: |
| Massive closes, October 15 | 12,651 rows |
| Massive closes, October 16 | 12,630 rows |
| Massive dividend snapshot, October 16 | 7,258 events |
| Fictional opening bank and fund-admin records | 2 accounts each |
| Fictional OMS executions through Snowpipe | 4 rows |
| Fictional first-day settlements | 0 rows, marked `EMPTY` |
| Fictional bank statement | 2 balances |

The scenario is `sim-prod-20261016`, with an October 15 opening. The four
first-day trades are due to settle October 19. The loader used
`NORTHBRIDGE_INGEST_PROD`; the dbt build and close recorder used
`NORTHBRIDGE_RELEASE_PROD` with the `NORTHBRIDGE_DBT_PROD` role. Their keys
are separate and excluded from Git.

RAW readiness passed, including the Snowpipe row count and a close for each
held stock. `dbt build --target prod` finished with `PASS=47 WARN=0 ERROR=0`.
The local dbt files matched commit `c86d0b2`, which passed the main-branch
[CI run](https://github.com/Uche-anya/Hedgefund-Finance-Platform-on-Snowflake/actions/runs/39153226610).
The same dbt source was uploaded under that commit in the PROD stage, compiled
as a native Snowflake dbt project and recorded in `DBT_PROD.CODE_RELEASES`.

| Account | October 16 NAV (USD) | Bank comparison |
| --- | ---: | --- |
| SIM-ACCOUNT-01 | 5,000,034.95 | `MATCH` |
| SIM-ACCOUNT-02 | 4,999,875.92 | `MATCH` |

`RAW.DAILY_CLOSE_RUNS` has exactly one `VALIDATED` row for this date and
scenario. Running the recorder again returned `Close already validated`.
A scenario without fund deliveries failed the RAW gate and got no close.

This proves a manually operated PROD close, not unattended operation. The PROD
producer schedules, Snowflake task graph, deadline check, GitHub release
credential and production-environment reviewer are not active. Security
mappings are still pending review; a held-stock dividend on a later ex-date
will stop the dbt build until its identity and event are resolved. The next
day needs its own Massive deliveries and fictional bank statement.

## Next market day: October 19

The same PROD scenario used the October 16 validated close as its starting
point. The producer loaded 12,638 Massive closes, 6,717 dividend events,
8 fictional trades, 4 fictional settlement confirmations and 2 fictional
bank balances. RAW readiness passed. The dbt build again finished with
`PASS=47 WARN=0 ERROR=0`; the dividend ex-date coverage test found no
unresolved event affecting a held position that day.

| Account | October 19 NAV (USD) | Bank comparison |
| --- | ---: | --- |
| SIM-ACCOUNT-01 | 5,000,538.85 | `MATCH` |
| SIM-ACCOUNT-02 | 4,999,835.13 | `MATCH` |

The close recorder wrote a `VALIDATED` October 19 row. Both days were run
manually. This proves the roll-forward calculation and settlement movement,
but not the proposed PROD task schedule or unattended producer.
