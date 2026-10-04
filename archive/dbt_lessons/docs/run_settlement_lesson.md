# Run the settlement lesson with one command

From the repository root:

```powershell
python scripts/run_settlement_lesson.py
```

The runner verifies both saved settlement deliveries against their manifest
hashes, loads the original four confirmations, loads the late confirmation,
then runs dbt to rebuild and test the reports. It uses the existing credential
helpers; it does not read or write passwords itself. The personal Snowflake
connection can still require MFA approval.

Every run gets a JSON record under `data/pipeline_runs/<run-id>/run.json`,
including input manifest hashes, step times, exit codes and overall status.
The child Snowflake helper also writes its own SQL-file run records. A failed
step stops the runner, so dbt is not run after a failed load. Earlier successful
steps are not rolled back; retries must therefore be safe.

This command replays the saved lesson; it does not generate new trades or
confirmations. Snowflake load history skips already loaded files, staging
tests detect duplicate event/trade identifiers across the selected deliveries,
and settlement_report_history inserts no rows for an already saved cutoff.
File-load history is not a permanent deduplication mechanism. The history
model assumes one writer; concurrent runs are not supported.

Expected after a successful retry: five staged confirmations, five matched
trades, no current exceptions, and five historical rows for each of the two
report cutoffs. The dbt tests check these results.

Prerequisites: the earlier OMS lesson is loaded, the January 7 report was
archived, both local settlement delivery folders exist, and the project uses
the January 8 cutoff. This is not a clean-install bootstrap or a daily scheduler.
It reuses the lesson SQL, including administrator setup grants. A production
scheduled job should separate provisioning and use a dedicated ingestion role
with unattended authentication.
