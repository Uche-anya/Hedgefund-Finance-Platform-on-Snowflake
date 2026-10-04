# Snowflake SQL index

The numbered SQL files show the order in which the development platform grew.
They now fall into four groups. Do not run the whole directory as one migration:
several early files load fixed learning deliveries, while later files create
operational controls.

## 1. Development bootstrap and saved-data loads

| Files | Purpose |
| --- | --- |
| `01`-`05` | Create the development database and load the first CSV example |
| `06`-`07` | Create dbt access and key-pair access |
| `08`-`13` | Load closing prices, execution terms and assembled price history |
| `14`-`18` | Load OMS, settlement and multi-day replay records |
| `19`-`25` | Load corporate actions, dividend evidence and broker positions |
| `27_ingest_key_access.sql` | Create the ingestion service identity |
| `28_reference_and_operations_sources.sql` | Add reference feeds and operations tables |

These files explain and reproduce the development account. The original
step-by-step instructions are preserved in
[LEGACY_BOOTSTRAP.md](LEGACY_BOOTSTRAP.md).

## 2. Operations and financial controls

| File | Purpose |
| --- | --- |
| `26_nav_publication.sql` | Append-only NAV publication objects |
| `31_run_control.sql` | Runs, attempts, selected inputs and events |
| `33_run_control_check.sql` | Read-only run-control verification |
| `37_separate_nav_publisher.sql` | Remove publication from the dbt runtime role |
| `38_delivery_readiness.sql` | Delivery registration and readiness gate |
| `43_nav_approval_gate.sql` | Candidate hashing and approval checks |
| `44_approve_nav_candidate.sql` | Controlled manual approval entry point |

## 3. Snowflake runtime, cost and governance

| File | Purpose |
| --- | --- |
| `29_performance_baseline.sql` | Capture query evidence before tuning |
| `30_development_cost_controls.sql` | Warehouse and monitor controls |
| `34_oms_snowpipe.sql` | Micro-batch OMS ingestion design |
| `35_governance_baseline.sql` | Roles and governance baseline |
| `39_native_dbt_check.sql` | Verify the Snowflake-native dbt project |
| `40_daily_task_graph.sql` | Suspended weekday close task graph |
| `41`-`42` | Task smoke test and result inspection |
| `45_task_owner_setup.sql` | One-time task ownership setup |

The task graph ends after calculation and audit. Approval remains a human action
through a separate role.

## 4. CI and production foundations

| File | Purpose |
| --- | --- |
| `46_ci_environment.sql` | Original CI role, warehouse and clone baseline |
| `47_production_foundation_check.sql` | Read-only verification of Terraform-managed production objects |

Terraform now owns the long-lived CI and production roles, OIDC users,
warehouses, monitors, production database and top-level schemas. SQL migrations
will own production RAW objects; dbt owns transformed relations.

## Generated access files

Scripts create SQL containing public keys for the dbt, ingestion, runner and
publisher service users. Those generated files are ignored by Git. Private keys
remain outside the repository.

## Current production rule

`NORTHBRIDGE_PROD` contains only the Terraform-managed foundation today. Before
enabling the production deployment workflow or task schedule, create an ordered
environment-aware RAW migration and complete the dry run in
[`docs/ROADMAP.md`](../docs/ROADMAP.md).
