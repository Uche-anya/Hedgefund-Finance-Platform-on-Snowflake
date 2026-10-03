# Snowflake governance for Northbridge

Governance is the set of controls that answers six questions:

1. Who can read, load, transform, approve and publish data?
2. Which source delivery and calculation produced a number?
3. Which data is confidential or regulated?
4. Who accessed or changed it?
5. How long is it retained and how is it recovered?
6. Who controls cost and production changes?

The aim is not to enable every Snowflake feature. Each control should address a
specific risk in the daily fund process.

## 1. Roles and separation of duties

An **account role** represents a job or service identity. A **database role**
packages access to objects inside one database. Users receive account roles;
database roles are granted to account roles.

The target structure is:

| Database role | Object access |
|---|---|
| `NORTHBRIDGE_DEV.RAW_LOADER` | Write approved RAW tables and stages |
| `NORTHBRIDGE_DEV.RAW_READER` | Read RAW tables |
| `NORTHBRIDGE_DEV.TRANSFORMER` | Read RAW and build controlled dbt schemas |
| `NORTHBRIDGE_DEV.OPERATIONS_WRITER` | Append run events and candidates |
| `NORTHBRIDGE_DEV.NAV_READER` | Read approved reporting views |

These database roles can be granted to functional account roles:

| Account role | Purpose |
|---|---|
| `NORTHBRIDGE_INGEST` | Source-file loading only |
| `NORTHBRIDGE_DBT_DEV` | Transformation only |
| `NORTHBRIDGE_RUNNER` | Run coordination only |
| `NORTHBRIDGE_NAV_REVIEWER` | Review candidates and exceptions |
| `NORTHBRIDGE_NAV_PUBLISHER` | Append an approved publication |
| `NORTHBRIDGE_REPORTING` | Read approved outputs only |

No service user should receive another service's functional role. In particular,
the dbt user should not also publish NAV. `NORTHBRIDGE_NAV_PUBLISHER_LOCAL` uses
its own key and receives the publisher role after registration. The old dbt grant
is then revoked by `snowflake/37_separate_nav_publisher.sql`.

## 2. Ownership and managed access

Ownership controls who may alter an object. It should not move between whichever
service last created a table. A platform owner should own schemas and deployment
objects. Runtime services receive only the privileges needed to do their work.

A **managed access schema** centralises grant decisions with the schema owner or
a role holding `MANAGE GRANTS`. Individual table owners cannot grant access on
their own objects. This prevents privilege drift.

Do not convert the current schemas blindly. First identify object owners and
future grants, create the target role hierarchy, and test dbt create/replace
behaviour. Use managed access when the production schemas are provisioned.

## 3. Data classification and protection

Classification describes the sensitivity and business purpose of data. Proposed
Northbridge tags are:

| Tag | Example values | Use |
|---|---|---|
| `DATA_CLASSIFICATION` | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED` | Sensitivity |
| `DATA_DOMAIN` | `TRADING`, `MARKET_DATA`, `FUND_ACCOUNTING`, `OPERATIONS` | Business ownership |
| `DATA_SOURCE` | `MASSIVE`, `OMS`, `BROKER`, `BANK`, `FUND_ADMIN` | Lineage and stewardship |
| `RETENTION_CLASS` | `RAW_EVIDENCE`, `WORKING`, `PUBLISHED_NAV` | Lifecycle policy |

Positions, trades, cash and unpublished NAV should be `CONFIDENTIAL`. API keys
and private keys never belong in tables or tags. The project currently has no
personal investor data, so masking every string column would add complexity
without addressing a real risk.

Use a **masking policy** when a role may query a column but should see a hidden
value, such as an investor tax identifier. Use a **row access policy** when the
same table serves several funds and a user may see only assigned fund rows.
Ordinary role grants remain simpler when an entire table is restricted.

## 4. Lineage, audit and reproducibility

Northbridge already records four forms of lineage:

- `source_file` and `source_row_number` identify the received record.
- `delivery_id` identifies the batch.
- manifests and SHA-256 hashes prove which local evidence was selected.
- `RUNS`, `RUN_INPUTS` and `RUN_EVENTS` connect inputs, code and attempts.

Snowflake query IDs and query tags add platform evidence. Enterprise accounts can
also use `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` for user, object and column-level
read/write history. Account Usage can be delayed, so it supports audit rather
than immediate pipeline control.

## 5. Financial approval governance

The daily calculation and the official publication are different decisions:

```text
dbt calculates candidate
    -> reconciliation controls pass
    -> reviewer investigates exceptions
    -> publisher records approved version
```

The same identity should not calculate, approve and publish. Publications and
restatements are append-only. A correction creates a new version with a reason
and a link to the superseded publication; it does not overwrite history.

## 6. Data quality governance

dbt tests are deployment and run gates. They should cover financial identities,
source contracts, uniqueness at the declared grain and required relationships.
They should not repeat every SQL expression.

Snowflake Data Metric Functions can monitor measures such as null counts,
duplicate counts and freshness on a schedule. They are an Enterprise feature and
consume serverless resources when scheduled. Use them for a few operational
service-level indicators after the account edition and cost are confirmed; keep
the accounting assertions in dbt.

## 7. Retention and recovery

Choose retention from the business purpose of each layer:

| Layer | Policy direction |
|---|---|
| Internal stages | Remove a file after its RAW load and manifest are verified, subject to replay requirements |
| RAW tables | Permanent, immutable evidence with an agreed retention period |
| dbt development outputs | Short retention; rebuildable |
| Published NAV and restatements | Long-lived controlled records |

Time Travel helps recover changed or deleted Snowflake data inside its retention
window. It is not a substitute for testing restores, preserving source evidence,
or maintaining a separate disaster-recovery plan.

## 8. Cost governance

The current X-Small warehouse, 60-second auto-suspend, resource monitor and query
tags are a sound start. Production should use separate warehouses for ingestion,
transformation and user reporting only when workload evidence justifies them.
Review credits by warehouse and query tag, and set budgets before enabling a
daily schedule.

## 9. Change governance

Terraform should provision stable security and platform objects. Versioned SQL or
Terraform can deploy database roles, managed schemas, warehouses, stages, pipes,
tasks, monitors and policies. dbt owns analytical transformations. GitHub Actions
checks proposed changes and deploys only after review.

Production changes should flow through development and test environments. A
human administrator should not be the routine deployment mechanism.

## Implementation order

1. Capture the current governance baseline without changing grants.
2. Design database roles and account-role inheritance.
3. Create a separate NAV publisher service identity and remove publication from dbt.
4. Provision future grants and managed access in the production schema design.
5. Add classification tags to important tables and columns.
6. Add access-history review if the Snowflake edition supports it.
7. Set retention and recovery rules and test a recovery exercise.
8. Add a small governance dashboard for grants, access, failed tasks and cost.
