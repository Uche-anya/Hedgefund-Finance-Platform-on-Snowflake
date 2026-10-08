# Daily operation: current state and target

The current two-year scenario is a historical calculation, not an unattended
production close. We loaded the five original daily OMS and custodian files
through Snowpipe and the remaining older dates through bulk `COPY INTO`.
We then loaded one new 22 September OMS file and its 23 September custodian
file through the same pipes, plus a checked 20-ticker daily price batch.
dbt rebuilt the 501-date position, cash, dividend and provisional NAV history.

| Step | Done in development | Needed for an unattended day |
| --- | --- | --- |
| Receive | Saved simulated OMS and custodian files; saved real price and action data | Source services deliver today's files and manifests to controlled paths |
| Load | Snowpipe pilot plus one later daily pair; historical bulk load for 493 older dates | Notify pipes or run a scheduled load for each new file |
| Check | RAW rows keep delivery IDs and file lineage | Require expected files, counts, date and freshness before calculation |
| Calculate | dbt rebuilt the two-year history and passed position, cash and NAV checks | Schedule a date-scoped build after sources are ready |
| Review | Dividend candidates remain approved or held explicitly | Review held actions and obtain broker and bank evidence |
| Publish | Two-year NAV is provisional | Add a separate human approval and publication path for this graph |

The short replay's Snowflake `DAILY_CLOSE` task has been retired. An unscheduled
DEV Task graph now runs the pinned two-year close request and checks or saves a
candidate result. It is fixed to the 22 September pilot request; it does not
choose a new business day or publish NAV. The old RAW and audit records remain
as history.

See [the Snowflake path](two_year_snowflake_path.md) for the exact source,
Snowpipe, dbt and parity evidence.
