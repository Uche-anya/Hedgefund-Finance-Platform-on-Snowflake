# Project status and production gaps

Reviewed 4 October 2026. This is the current status of the repository and the
Snowflake account, based on the checks completed during the build.

## What is complete

- Four real reference sources are integrated: Massive daily equity prices,
  Massive corporate actions, ECB FX rates and US Treasury rates.
- Five fictional operating feeds model data a fund would normally receive from
  independent systems: OMS executions, settlement confirmations, broker
  positions, fund-administrator events and bank cash statements.
- The saved replay contains 3,200 trades across 20 equities, two accounts and 23
  valuation dates. It includes late and missing settlements, a reviewed dividend,
  position breaks and a bank-cash break.
- Snowflake RAW tables retain source payloads and delivery lineage. The dbt graph
  has 20 active models, 54 data tests and two controlled reference seeds.
- Instrument history uses stable security IDs and effective dates, including the
  SQ to XYZ ticker change and a separate XOM successor security.
- Positions, cash, settlement obligations, valuations, NAV, FX reporting,
  dividends and broker/bank reconciliations are calculated in Snowflake.
- An independent Python calculation agrees with 920 valuations and 46 daily NAV
  balances. The Python suite currently contains 235 tests.
- Run control records selected deliveries, attempts and status. NAV approval and
  publication use separate roles and an exact candidate hash.
- A suspended Snowflake task graph and native dbt project have been exercised in
  development. Tasks do not approve their own NAV output.
- Pull requests run local checks and an optional isolated Snowflake clone build.
- Terraform state is stored in HCP Terraform. Terraform manages the CI and
  production foundations: roles, OIDC service users, warehouses, monitors, the
  production database and its schemas.

This proves a production-style development replay. It is not evidence that a
real fund is operating on the platform.

## What remains before a daily production run

### 1. Deploy the production data plane

`NORTHBRIDGE_PROD` and its access roles exist, but production RAW tables, file
formats, stages, pipes, dbt project and task graph still need a reviewed release.
The production GitHub workflow is deliberately disabled until those objects and
their source credentials are ready.

### 2. Replace local producers with scheduled source hand-offs

The real reference downloads and fictional operating producers currently run
from a developer machine. A deployed service must create manifests, upload files
to controlled stage paths and register completed deliveries. Snowpipe can load
frequent OMS files; daily sources can use a scheduled load.

### 3. Choose the daily cutoff and activate scheduling

Agree the business timezone, source arrival deadlines, late-data policy and NAV
review window. Then enable the root task only after a monitored dry run in the
production environment.

### 4. Add operational monitoring

Alert on missing deliveries, failed task nodes, failed dbt tests, reconciliation
breaks, unapproved NAV candidates and unusual warehouse credit use. Record an
owner and a safe retry instruction for each alert.

### 5. Finish governance operations

Assign data owners, apply the existing classification design, document access
reviews and key rotation, and test Time Travel or clone-based recovery. Keep
publisher, transformation and ingestion duties separate.

### 6. Add accounting only when a source requires it

The current scope is USD listed equities. Stock borrow, margin, tax withholding,
options, futures and bonds need their own sources and accounting rules before the
platform can claim to support them. They are later product scope, not defects in
this equity close.

### 7. Add machine learning after operating history exists

The anomaly model is intentionally deferred. Reconciliation outcomes and rule
violations must first accumulate enough labelled history for time-based training
and evaluation. Synthetic labels must remain identified as synthetic.

## Cleanup decisions

The following files remain because they serve a clear purpose:

- `data_extraction` reproduces vendor downloads, identity reviews and price
  repairs.
- `fund_pipeline` supplies the independent calculation and the original local
  accounting implementation.
- `fixtures` provides small, committed inputs for tests and CI.
- numbered Snowflake SQL files document bootstrap, migration and operational
  checks. Their current role is indexed in `snowflake/README.md`.
- old Python and dbt lessons are under `archive`; they are excluded from the
  active dbt project.

Generated data, virtual environments, dbt output, Terraform plans/state, private
keys and credentials stay outside Git through `.gitignore`.

## Release definition

A credible production release requires all of the following:

- production objects deployed from reviewed code;
- service identities for ingestion, transformation and publication;
- a complete delivery manifest for one dry-run business date;
- dbt and independent control calculations passing;
- expected reconciliation exceptions reviewed;
- a NAV candidate approved and published by separate identities;
- task, failure, recovery and cost evidence retained;
- the schedule enabled only after the dry run is signed off.
