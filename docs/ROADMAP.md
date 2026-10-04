# Remaining work

The calculation platform is built and tested in development. The next phase is
turning that controlled replay into an operated daily service.

## Next milestone: production dry run

1. Convert the RAW setup scripts into an ordered, environment-aware migration.
2. Deploy RAW objects, the native dbt project and the suspended task graph to
   `NORTHBRIDGE_PROD`.
3. Land one complete test delivery through service identities.
4. Run the task graph manually and collect task, dbt and reconciliation evidence.
5. Approve and publish one test NAV through the separate approval path.
6. Test an exact retry, a missing delivery and recovery from one failed task.

## After the dry run

1. Add alerts and an operations dashboard.
2. Apply governance tags and complete the first access review.
3. Test recovery using Time Travel or a zero-copy clone.
4. Measure query time, bytes scanned and credits before changing table design.
5. Agree the weekday schedule and source cutoffs, then enable the root task.

## Later scope

- Replace fictional broker, bank and administrator feeds when real contracts are
  available.
- Add other asset classes only with matching reference, pricing and accounting
  data.
- Train an anomaly model only after reviewed exception history provides useful
  labels.

See [PROJECT_AUDIT.md](PROJECT_AUDIT.md) for the evidence and release criteria.
