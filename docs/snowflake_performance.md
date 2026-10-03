# Snowflake performance and cost work

Measure the workload before changing warehouse size, clustering or model
materializations. The current dataset is small enough that a full dbt build is
expected to be cheap and fast.

Run the read-only baseline from the project root:

```powershell
python scripts/snow_admin.py --file snowflake/29_performance_baseline.sql
```

The output records three things:

1. `SHOW WAREHOUSES` confirms size, state, auto-suspend and auto-resume.
2. `INFORMATION_SCHEMA.TABLES` shows which raw and dbt tables hold most data.
3. `QUERY_HISTORY` groups the last six days by query tag and reports query
   count, duration, bytes scanned and rows produced.

Query tags separate dbt, ingestion and publication activity. Untagged queries
are shown as `UNTAGGED` rather than being hidden.

Do not add a clustering key just because a table is large relative to this
project. First show that repeated selective queries scan too much data. Do not
increase warehouse size unless elapsed time or queueing creates an operating
problem. Dynamic tables are useful only when their refresh behaviour replaces
a real scheduling or incremental-processing need.

## First measurement

The 3 October 2026 baseline found:

| Measurement | Result |
|---|---:|
| Largest table | 4.45 MB |
| Average successful dbt query | 0.273 seconds |
| Slowest successful dbt query | 1.803 seconds |
| Queued queries | 0 |
| Warehouse size | X-Small |
| Auto-suspend | 300 seconds |
| Resource monitor | None |

There is no evidence for a larger warehouse, clustering keys or dynamic tables.
Separate warehouses would also make this short sequential run pay more minimum
resume periods. Script `30_development_cost_controls.sql` therefore keeps one
X-Small warehouse, changes auto-suspend to 60 seconds, disables query
acceleration and attaches a five-credit monthly development monitor. Its 80
percent notification trigger requires Snowflake notification recipients to be
configured; the 100 percent trigger suspends the warehouse.

Separate ingestion and dbt warehouses become worthwhile when concurrent jobs,
different service levels or larger workloads need isolation. Until then, query
tags provide workload attribution without additional warehouse resumes.
