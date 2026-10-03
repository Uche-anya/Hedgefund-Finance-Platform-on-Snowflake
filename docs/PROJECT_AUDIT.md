# Project audit

Reviewed 1 October 2026. This document separates working features from the work
needed for a credible daily fund platform.

## What works now

- A pinned Massive price snapshot contains 250,036 rows for 503 tickers.
- Reviewed ticker changes are applied without changing the saved source files.
- Real corporate-action data is stored with review evidence and raw lineage.
- A saved simulation contains 3,200 trades across two accounts and 20 stocks.
- The replay covers 23 valuation dates and has settlement and dividend events.
- One instrument seed and eleven active dbt models calculate positions, valuation, obligations, cash, NAV and broker reconciliation.
- Dividend accrual, confirmation and reconciliation work for one reviewed
  Mastercard event.
- The acceptance build passes 45 data tests across 18 models. The complete
  Python suite passes 224 tests.
- An independent Decimal calculation matches 920 valuations and 46 NAV rows.
- dbt uses a dedicated key-pair user. Secrets and generated data are ignored by Git.

This is a reproducible development replay. It is not an official accounting
book, an unattended daily service or a live stream.

## Important gaps

### 1. Remaining reference data

The replay's 20 stocks now resolve through permanent internal security IDs and
effective-dated ticker history. The XOM holding-company transition proves the
mapping can distinguish two securities that used the same ticker. Account and
broker reference data still need controlled identifiers, and a replay spanning a
reorganisation will need an explicit position-conversion event.

### 2. Remaining reconciliation coverage

A separate prime-broker delivery now produces matched, missing, unexpected,
quantity-mismatch and late position outcomes. Its calculation and delivery are
separate from dbt, although it remains simulated rather than independent
real-world evidence. Cash-balance reconciliation is still outstanding.

### 3. Remaining NAV controls

The operational schema now preserves append-only run events, NAV publications
and restatements. The publisher role cannot update or delete those records, and
exact retries reuse the same run ID. The workflow still needs a real approver
identity and policy-driven materiality thresholds; the current exception note is
explicitly a simulated project control.

### 4. Daily run control

Delivery IDs are pinned in `dbt_project.yml`. A production run needs a run-control
record with business date, source deliveries, cutoffs, status, timestamps and
retry history. The loader must reject incomplete or conflicting deliveries and
allow an exact retry without duplicating records.

### 5. Remaining service-access work

dbt, raw ingestion and NAV publication now use separate key-pair roles. The
current replay and broker loader no longer uses the personal administrator or
MFA. Key rotation, expiry monitoring, emergency access and deployment-host
secret management still need an operating procedure.

### 6. Scheduling and monitoring

There is no Snowflake task graph, alerting, service-level objective or operations
dashboard. The task graph should check source readiness, validate contracts, run dbt, perform independent
reconciliation, publish only after approval and record every step. Alerts need
the failed step, business date, affected source and safe retry instruction.

### 7. Ingestion design

Local PUT/COPY commands are suitable for development. Production can retain
Snowflake internal named stages, but the producer must authenticate, upload each
file and notify Snowpipe or rely on a scheduled COPY. File manifests remain
necessary. Repeated JSON files are micro-batches, even if they arrive every
minute. Streaming is justified only when the business requires lower latency and
can operate it reliably.

### 8. Accounting coverage

The active NAV covers USD equities, trade settlement and one reviewed dividend.
It does not yet cover opening positions, every dividend, splits, tax withholding,
fees, stock borrow, margin, FX, subscriptions/redemptions, futures or other asset
types. Add each with a stated accounting rule and independent control total.

### 9. Data contracts and freshness

Required fields and pinned counts are tested, but sources have no automated
freshness rules or versioned external contract. Record expected arrival times,
schema versions, provider entitlements and late/missing delivery policy.

### 10. Deployment and reproducibility

There is no CI workflow, container, production dbt target or general Python
dependency file. Large generated datasets are correctly ignored, but a reviewer
needs either a small committed fixture or a documented download-and-build path.
The current working tree also contains several uncommitted milestones; these need
small, ordered commits before the portfolio is presented.

### 11. Performance and cost

The current volumes are small: 250,036 raw prices, 920 active valuations and 46
NAV rows. Full table rebuilds are reasonable today. Dynamic tables, clustering
keys and larger warehouses would add cost without evidence of a bottleneck.
First record query duration, bytes scanned and credits by run. Add incremental
processing or clustering only after query history shows a real problem. Configure
auto-suspend, a resource monitor and separate workload warehouses before daily use.

### 12. ML readiness

No ML model is implemented. Start after independent reconciliation creates useful
features and labels. Use transparent rules as a baseline, then compare an anomaly
model such as Isolation Forest on an earlier training period and later evaluation
period. Synthetic anomalies must stay labelled synthetic; a score is not proof
of fraud or the cause of a break.

### 13. Governance and recovery

Define data retention, Time Travel, cloning, access review, tagging and recovery
tests. There is no personal customer data in the current sample, so masking is
not a priority. Lineage and source hashes are already a useful foundation.

## Build order

1. Account and broker reference data.
2. Independent broker/custodian cash statements and reconciliation exceptions.
3. Production approval identities and NAV materiality policy.
4. Parameterised run control and ingestion-key rotation.
5. Snowflake Tasks orchestration, monitoring, CI and reproducible setup.
6. Internal-stage file ingestion with Snowpipe when the account setup is ready.
7. Remaining accounting rules, beginning with all relevant corporate actions.
8. Performance changes supported by Snowflake query-history evidence.
9. Anomaly detection after exception labels exist.

## Next milestone

Parameterise the daily run by business date and delivery manifest. The current
command uses least-privilege service identities, but its delivery IDs remain
pinned to the January replay configuration.

## Definition of a credible portfolio release

- A clean clone can run a documented small example without private files.
- CI runs Python and dbt checks against a safe test environment.
- Every published NAV points to immutable input and calculation versions.
- A correction produces a visible restatement rather than overwriting history.
- Independent statements create matched, missing and mismatched exceptions.
- Daily runs are idempotent, monitored and operated by service roles.
- Cost and performance decisions are backed by measurements.
- README claims match what the repository and live Snowflake build can prove.
