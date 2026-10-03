# Daily operation

This is the normal close after the platform has been deployed. Historical
replays use the same controls but set `run_mode` to `REPLAY` and select older
deliveries explicitly.

| Step | What happens | Control |
|---|---|---|
| 1. Land | Source files arrive in their dated storage paths. OMS events may arrive continuously through Snowpipe. | Files and raw rows keep source, delivery and load metadata. |
| 2. Register | Each completed source delivery is recorded in `OPERATIONS.DELIVERIES`. | Expected rows, loaded rows and manifest hash must agree. |
| 3. Wait | The close starts only when all deliveries selected for that business date are `READY`. | `selected_deliveries_are_ready` stops a missing, changed or incomplete delivery. |
| 4. Calculate | The Snowflake task executes the native dbt project. | dbt stages the raw records, rebuilds positions, cash, valuations, NAV and reconciliations, then runs the focused data tests. |
| 5. Review | `NAV_REVIEW_CANDIDATES` exposes the calculated NAV and a deterministic candidate hash. | A reviewer investigates reconciliation breaks and approves that exact hash. |
| 6. Publish | The publisher writes the approved candidate to the append-only publication ledger. | A changed candidate has a different hash and cannot reuse the earlier approval. |
| 7. Monitor | Operators inspect task history, run events, reconciliation exceptions and publication status. | Failures remain recorded; an exact retry appends a new attempt under the same run ID. |

## What has been proved

- All eight selected deliveries are registered and ready.
- The local controller completed the same February close twice under run ID
  `northbridge-run-37e9ee2c5c3e77ab20f13d57`. Attempts 1 and 2 both passed.
- The dbt build passed 64 results. Independent Python checks matched 920
  valuations and 46 NAV rows.
- The expected exceptions were reproduced: three position breaks, one late
  broker statement and one $25 bank-cash break.
- A deliberately missing bank delivery stopped the build.
- A NAV publication without a matching human approval stopped before writing.
- The native dbt project also ran successfully inside Snowflake.

## Task deployment state

`snowflake/40_daily_task_graph.sql` contains the weekday task graph and leaves
the root suspended. `snowflake/45_task_owner_setup.sql` is the one-time ownership
setup. The schedule should remain suspended until the operating time and daily
input hand-off are agreed.

The current graph deliberately ends after dbt and its audit row. The reviewer
and publisher remain separate because a scheduled calculation must not approve
its own result.
