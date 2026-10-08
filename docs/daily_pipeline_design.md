# Daily pipeline design

## Decision

Use one RAW contract and one dbt calculation for the historical backfill and
new business days. Loading differs: old files use bulk `COPY INTO`; arriving
OMS and custodian files use Snowpipe; daily market prices use the checked price
loader for now. These routes must produce the same RAW columns and delivery
receipts. We do not replay two years by pretending that 500 old files are 500
live Snowpipe notifications.

The current two-year v2 calculation is a **provisional equity close**. Market
prices and corporate-action candidates are real provider data. Trades,
custodian confirmations, fund subscriptions and dividend cash confirmations
are simulated. The simulated custodian feed is derived from the OMS file, so it
does not prove independent reconciliation. Broker and bank evidence is still
needed before an approved NAV or performance report.

There are currently two calculation paths. The active dbt event marts calculate
two-year positions, cash and provisional NAV in Snowflake. The Power BI serving
tables read a separate Python close ledger from `RAW.TWO_YEAR_REPORTING`.
Those are useful for cross-checking, but they must not both claim to be the
production NAV. The target is for the Snowflake/dbt close to be authoritative;
the Python ledger becomes a comparison tool. Move the serving tables to a
versioned dbt close only after the two paths reconcile on each account/date.

## The two modes

| Mode | What happens | What it proves |
| --- | --- | --- |
| Historical backfill | Load saved 2024–2026 files in bulk; validate delivery counts; build all dated positions, cash and provisional NAV through dbt | The 500-session history passes the same transformation and financial checks |
| New business day | Source services deliver new files; Snowpipe loads OMS and custodian files; the price loader loads that day's market bars; readiness checks the exact input set; a Task runs dbt | The platform can extend the history without a person starting dbt |

The five original daily Snowpipe pilots and the 22 September extension exercise
the new-arrival route. The remaining 493 dates were bulk loaded. We have **not**
run 500 separate historical Task executions. That would add cost without
improving the evidence from the full-history calculation. A small multi-day
replay is useful for testing retries, missing files and late events.

## Daily close contract

One close request has a scenario, business date, UTC cutoff, code version,
source-selection version and a stable request ID. It names the exact delivery
IDs and content hashes that dbt may read, including the historical baseline,
daily prices, OMS, custodian events, dividend payments, fund administrator
events, corporate-action load and review decisions. It also pins the reviewed
instrument mapping and the dbt code/seed revision. A new delivery for the
same date does not enter an existing request automatically. FX, Treasury,
broker and bank feeds are not active inputs to this two-year provisional NAV;
adding them later requires an explicit contract and reconciliation rule.

For the backfill, a close built today is a **restated historical view** using
the selected evidence now available. It is not proof of what the fund knew at
each old day's cutoff. To reproduce an "as known then" close, each source
needs a reliable publication/receipt timestamp and the selection must exclude
anything arriving after that historical cutoff. We should label the current
two-year history accordingly.

The state belongs in Snowflake, not in a laptop JSON file:

- `CLOSE_REQUESTS`: one immutable requested input set and its cutoff.
- `CLOSE_INPUTS`: the source name, delivery ID, hash and row count selected by
  that request. There can be many selected deliveries for a historical build.
- `CLOSE_ATTEMPTS`: every gate and dbt attempt, with start/end time, result,
  error and Snowflake query or dbt invocation ID.
- `CLOSE_OUTPUTS`: candidate output fingerprint and validation status. A later
  revision points to the close version it supersedes.

The earlier `OPERATIONS.DELIVERIES` table records what arrived. It is not a
selection table: `READY` means a delivery loaded cleanly, not that a particular
close approved it. Standard Snowflake table primary keys are not enforced, so
the writer and gate must also check for duplicate request and receipt rows.

## What each component owns

1. **Producer outside Snowflake:** creates immutable files and manifests. In
   production it must run on a managed service, not on a laptop. It keeps
   provider data distinct from simulated fund activity.
2. **Snowpipe and bulk COPY:** land source rows with `delivery_id`, filename,
   row number and load time. They do not calculate NAV or choose the accepted
   version of an event.
3. **Readiness gate:** verifies hashes, counts, expected tickers, event IDs,
   business dates and cutoff. It pins the close inputs and fails closed when a
   required source is absent or conflicting. A trade can remain unsettled at
   its trade-date close; the custodian event is checked when it is due and
   available under the chosen cutoff.
4. **dbt:** reads only deliveries selected for the close. It resolves event
   versions explicitly, applies dated security identities, and calculates
   positions, cash, entitlements and provisional NAV. Tests catch broken
   grains and financial identities. The selected-input filter belongs in the
   active close graph, not in a shared staging view used by unrelated runs.
   Keep full table rebuilds until runtime and credits justify incremental
   models.
5. **Snowflake Task:** checks for a ready request, executes the deployed dbt
   project and records the attempt. A failed or incomplete request does not
   release output. The dbt Task needs a user-managed warehouse.
6. **Review and serving:** reconcile the dbt close to the Python comparison
   ledger; later compare with independent broker and bank evidence, approve
   separately, then expose only approved versions to Power BI. The current
   two-year output does not pass that publication gate.

## Retry and correction rules

- Same delivery ID and same bytes: retry is a no-op after verifying the RAW
  count and receipt. Same ID with different bytes: reject it.
- Same close request and same selected inputs: rebuild may create a new
  *attempt*, but it must reproduce the same dated result and must not create a
  second publication.
- New data for an old business date: preserve RAW, create a new close version,
  recalculate affected dates and compare it with the previous version. Do not
  silently change a previously approved result.
- A new event ID for an existing execution ID is not automatically a new trade.
  An explicit correction version and supersession rule is required before it
  can replace the old execution. Do not use `SELECT DISTINCT` to hide a
  conflict.

## Build order from today's repository

1. Inventory every source actually read by the active two-year dbt graph and
   define the first complete 22 September input set, including dbt seeds and
   the separate Python ledger used by serving. The current checker pins only
   that day's OMS and prices, so it is a pilot gate, not this complete set.
2. Add Snowflake close request/input/attempt tables and load that selection.
   Prove that repeated registration preserves one request and conflicting
   registration fails.
3. Change active close-graph source reads to use the selected set and cutoff.
   Run the 500-session baseline and 22 September extension twice; compare row
   counts and financial result fingerprints. Reconcile dbt and Python outputs
   before choosing the dbt result for serving.
4. Test a duplicate, missing price, late settlement and corrected historical
   event. Verify that the gate fails or creates a new close version as intended.
5. Measure full rebuild time and credits. Then deploy a **suspended** Task,
   execute it manually for a pilot day, inspect its run history and only then
   schedule it. Keep publication separate.

The request/input and attempt/result ledgers were piloted in development on
7 October 2026. The 22 September request pins 1,003 deliveries; dbt read that
selection and produced matching fingerprints on repeated builds. A simulated
one-cent price correction generated a separate saved result, with only the
expected account-day positions and NAV changing. Three historical loads lack
original receipts, so both versions remain CANDIDATE with limited evidence.
The shared dbt tables still hold only the latest build; the separate result
ledger preserves each candidate. `scripts/run_pinned_close.py` holds a Snowflake
row lock while it runs dbt, marks stranded attempts interrupted, and refuses a
blocked request or changed local dbt code. The unscheduled Task graph now records
a run owner on that same lock row, builds the fixed corrected request, and checks
or saves its versioned result. The local runner refuses an active Task owner.
The Task finalizer releases ownership if dbt fails. Two repeated runs matched
the saved result without adding rows; a forced failure was cleaned up and a
following run succeeded. The Task still needs a new-day request selector and a
deployment-to-request code pin before scheduling. Neither path publishes NAV.
See [close_correction_pilot.md](close_correction_pilot.md).
