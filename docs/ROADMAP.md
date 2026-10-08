# Remaining work

The only active build path is the two-year backfill and its daily continuation
through one RAW contract and one Snowflake/dbt close calculation. The date-scoped
22 September source checker and a dbt execution-uniqueness test are in place.
The 22 September inventory has been pinned as a development CANDIDATE. A
simulated one-cent price correction produced a separate saved result version;
the two account NAV changes matched their position-value changes. The local
runner now checks a Snowflake input gate, uses a Snowflake row lock and recovers
stranded attempts. A manual, unscheduled Task graph claims the same close,
runs the deployed dbt project, then captures or checks the saved result. Two
successful reruns returned `MATCHED`; a forced dbt failure was recorded as
`FAILED`, released the run owner, and was followed by a successful retry.

1. Resolve or explicitly accept the three legacy receipt gaps. Keep the current
   request at CANDIDATE until its evidence and financial review are complete.
2. Exercise the first-time `SAVED` capture path with a new valid request. Test
   late, duplicate and missing deliveries; keep the simulated correction
   separate from a genuine provider correction.
3. Reconcile the dbt result to the Python ledger on each account and date.
   Move reporting to the dbt close after parity is established.
4. Test missing, repeated and late deliveries. Measure runtime and credits;
   keep full rebuilds until an incremental approach is justified.
5. Measure Task runtime and credits, pin the deployed dbt artifact to each
   request, then give the Task a new-day request selection instead of its fixed
   22 September pilot ID. Schedule it only after a new-day delivery is proved.
   Add independent broker and bank evidence before approval and publication.

At this data size, tune Snowflake from query and credit measurements rather
than adding clustering or dynamic tables by default.

See [PROJECT_AUDIT.md](PROJECT_AUDIT.md) for the current evidence and limits.
See [daily_readiness.md](daily_readiness.md) for the request and retry contract.
See [close_input_inventory.md](close_input_inventory.md) for the saved inputs.
See [daily_pipeline_design.md](daily_pipeline_design.md) for the backfill and
new-day architecture.
