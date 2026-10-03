# Remaining work

The detailed status and release criteria are in [PROJECT_AUDIT.md](PROJECT_AUDIT.md).

The multi-day replay is the current completed milestone. Keep its saved inputs
and independent accounting checks as a reference while adding each feature.

1. **Separate ingestion from administration.** Provision tables once, then give
   an ingestion service only the access it needs. Remove personal MFA from the
   scheduled run. Parameterise delivery IDs and dates before accepting new days.
2. **Add independent broker statements.** Produce a separate simulated statement
   feed with intentional disagreements. Reconcile positions and cash, keeping
   missing reports distinct from confirmed mismatches.
3. **Schedule and monitor runs.** Add a Snowflake task graph around ingestion
   readiness, dbt checks and reports. Exercise retries, failed inputs and recovery.
   A historical replay schedule is not a live market-data feed.
4. **Add continuous event ingestion.** Upload simulator events to Snowflake
   internal named stages and use Snowpipe for file ingestion. Small files arriving
   repeatedly are micro-batches.
5. **Extend accounting.** Integrate ECB FX, corporate actions, fees and opening
   positions. Model each additional asset type before claiming it can be valued.
6. **Add anomaly detection.** Start with transparent trade-quality rules, then
   compare Isolation Forest using earlier data for training and later data for
   evaluation. Keep intentionally generated anomalies labelled as synthetic;
   model scores alone do not establish fraud or a reconciliation-break cause.

Live daily operation also needs a configured market-data credential, entitlement
checks, secrets management, alerting and a deployment environment. The existing
saved Massive snapshot supports reproducible development without fresh API calls.
