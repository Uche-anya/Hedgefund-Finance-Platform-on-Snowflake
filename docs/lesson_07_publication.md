# Part 7: review a close, then publish one complete version

We can calculate a NAV and compare it with statements. Now we keep that exact
result for review and decide which version a local consumer should read.

| Step | Meaning |
| --- | --- |
| Prepare a candidate | Save the calculated close and the reconciliation that checked it |
| Review | Inspect holdings, cash, obligations, NAV and every comparison |
| Approve | Record the reviewer label, review note, time and expected current version |
| Publish | Make that approved candidate the next version for its valuation date |
| Read current | Return the latest committed published version, never an unapproved candidate |

This is a **local synthetic workflow**. No data is published to an external
service or audience. Reviewer names are recorded labels, not authenticated
identities. Anyone with filesystem/database access is outside this prototype's
security boundary; real authorisation is not implemented.

## Storage, without a new service

`fund_pipeline/publication.py` uses SQLite, a database built into Python, stored by default
at `data/publication.sqlite`. No database server or dependency installation is
needed. This local choice does not replace the planned Snowflake architecture.

There are three small tables:

- `candidates`: frozen JSON containing the close, controls, input delivery
  references and code-file fingerprints; plus a checksum for accidental changes.
- `approvals`: one recorded review per candidate, including expected current version.
- `publications`: date, version, candidate ID and publication time.

A **transaction** saves its changes together or rolls them back together.
Publication uses one transaction, so a reader gets a whole committed version.
We do not update individual holdings and cash balances in a live report.

Ordinary updates/deletes against these tables fail through SQLite triggers.
That protects history from accidental edits; it is not tamper-proof storage.
An administrator able to change the database schema can bypass that protection.

## Run the workflow in PowerShell

### 1. Save inputs and prepare a candidate

```powershell
$navDelivery = python -m fund_pipeline.landing --business-date 2026-09-14 --bundle nav
$referenceDelivery = python -m fund_pipeline.landing --business-date 2026-09-16 --bundle references
$candidate = python -m fund_pipeline.publication prepare --business-date 2026-09-14 --as-of 2026-09-16 --delivery "$navDelivery" --references "$referenceDelivery"
python -m fund_pipeline.publication show --candidate "$candidate"
```

The candidate is saved even if reconciliation fails, so its failed checks can
be reviewed. Invalid source data or a calculation error stops preparation.
For the normal example, confirm NAV 10,105 and all four comparisons PASS.
Check `current_version`: 0 means there is no published result for that date.

### 2. Record your review

After inspecting the saved candidate, use your chosen local reviewer label:

```powershell
python -m fund_pipeline.publication approve --candidate "$candidate" --by "your-name" --note "Reviewed synthetic holdings, cash, NAV and all four comparisons" --expected-version 0
```

The example uses 0 for the first publication. For a later reviewed candidate,
use the actual `current_version` shown during review. Do not mechanically
increment it to bypass a stale-review failure.

Failed reconciliation or overdue settlements block approval. An empty reviewer
or note also fails. Passing comparisons alone never creates an approval.

### 3. Publish and read the consumer result

```powershell
python -m fund_pipeline.publication publish --candidate "$candidate"
python -m fund_pipeline.publication current --as-of 2026-09-16
```

The result includes the full close, reviewer record, version and publication
time. The demonstrated first version contained NAV 10,105, cash 9,730,
ALPHA long assets 735 and BETA short obligations 360.

The reconciliation inside the frozen candidate still says NOT APPROVED: that
is its original calculation-time status. Later approval/publication lives in
separate records, so we never rewrite the historical calculation evidence.

## Follow one close through the code

1. `prepare()` calls `reconcile()`, which now returns the exact close it checked.
   The candidate stores that close and its controls together; there is no second
   calculation that could pick up different inputs.
2. `approve()` checks eligibility and compares the reviewer’s expected version
   with the current published version. It then saves the reviewer and note.
3. `publish()` requires that approval. Within a transaction it checks again that
   no other publication has advanced the version, then inserts the next version.
4. `current()` reads the highest committed version for that specific date and
   loads its frozen close. It does not rerun today's code against old inputs.

Code hashes help identify the implementation used, but are not archived source
code. Rebuilding old candidates after future code changes will also require
preserving the corresponding code version and environment.

## Corrections and competing runs

Suppose BETA's closing price changes from GBP 18 to GBP 19. A new input delivery
and separately corrected administrator fixture yield NAV 10,085. Prepare a new
candidate, review it against current version 1, approve it, and publish version 2.
Version 1 remains NAV 10,105; version 2 becomes the current consumer result.
This correction scenario is exercised in the tests.

If two candidates are approved against version 0 and one publishes version 1,
the other now has a stale approval. Publication rejects it. Prepare and review
a new candidate against the current version instead of silently overwriting it.

Retrying publication of the same candidate returns its existing version. It
does not create another version or make an old superseded candidate current.
`show --candidate <old ID>` still displays that candidate and its publication.

## Exercise

After publishing the matching candidate, run its `publish` command again.
Predict the version first. Then run `current` and verify the version stayed the
same. Explain why retrying a job should not manufacture a new financial revision.

## Tested boundaries and remaining work

Tests cover failed reconciliation, missing approval, blank review evidence,
overdue settlement, correction history, competing publication attempts, stale
review versions, repeated publication, immutable rows and rollback on an error
before commit. They also run the full command-line workflow in a temporary DB.

These tests do not establish authenticated reviewers, separation of duties,
Snowflake permissions, multi-host deployment, power-loss recovery, database
migrations or backups. Cross-date correction propagation is not implemented;
publication is versioned independently for each date in this one-fund prototype.
Data remains synthetic and all cloud integrations remain unverified.
