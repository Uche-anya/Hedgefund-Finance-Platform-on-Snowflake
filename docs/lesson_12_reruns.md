# Part 12: rerun the work without duplicating its result

Imagine the scheduler starts our pipeline, but loses its connection just after
the result is saved. It tries again. We want a new record of the attempt, while
reusing the successful calculation it already saved.

    First attempt:   Run A -> Candidate X
    Same inputs:     Run B -> Candidate X (reused)
    Corrected inputs: Run C -> Candidate Y (new)

This is often called **idempotency**: repeating an operation does not duplicate
its intended effect. Here, that effect is saving a successful candidate. Every
attempt still has its own run record.

## How we decide whether the work is the same

We make an `input_key`, a fingerprint of:

- The trade batch date and valuation date.
- The output currency.
- All four input manifests, which include the saved file fingerprints.
- The calculation and validation source-code fingerprints.

A fingerprint is a short text representation of some bytes. Changing the bytes
changes the fingerprint. A revised FX delivery, reference delivery or calculation
file therefore gets a different key. We use whole manifests: a newly landed
delivery counts as new even if its numerical values are identical.

We still verify every input delivery before reuse. A corrupt file cannot hide
behind an earlier successful result. File fingerprints detect changes; they are
not provider authentication. Saved deliveries must remain unchanged during runs.

## Where the remembered result lives

The SQLite `candidate_reuse` table connects each key to one successful candidate.
Lookup, candidate creation and registration happen in the same database transaction.
A transaction commits these writes together or rolls them back together.

SQLite serialises overlapping writers, so two attempts cannot both register a
new successful result for one key. The existing finite lock timeout can still
make a busy attempt fail; retrying later is safe. This is a small local solution,
not a distributed scheduler implementation.

Failed financial checks and overdue settlement obligations are not registered as
reusable successes. Their candidates remain available for investigation. Repeating
the failed attempt may therefore save another failed candidate.

## Try it

Run the command in [Part 11](lesson_11_pipeline.md) twice. You should see:

```text
First:  Created new candidate
Second: Reused existing candidate
```

Both runs print the same candidate ID and different run-record paths. If the
candidate already exists from an earlier attempt using this code, both runs may
say reused. Open their JSON records: `candidate_reused` tells you which happened,
and `input_key` explains the match.

The first run after this upgrade creates a new registered candidate. Older
candidates are preserved but are not retroactively registered for reuse.

## Approval is still separate

The runner does not create or change approvals or publication versions. For a
reused candidate, its status says:

| Status | Meaning |
| --- | --- |
| READY_FOR_REVIEW | Checks passed; candidate has no approval |
| ALREADY_APPROVED | Candidate already has an approval record |
| ALREADY_PUBLISHED | Candidate already has a publication record |

ALREADY_PUBLISHED refers to that candidate's original publication; it does not
mean it is the latest published version. The `current` command remains the way
to read the latest version. A stale approval still cannot publish over a newer
version. If a new review is required for identical inputs, use the explicit
`publication.py prepare` workflow to create a fresh candidate for that review.

## Recovery and limits

The successful candidate and reuse registration commit together. Even if the
process then dies before completing its run JSON, a retry can find the candidate
in SQLite without needing the old log. The interrupted run record may still say
RUNNING; automatically resolving those records remains future work.

Reuse is scoped to the selected database. Another database has its own history.
Financial code changes force recalculation; edits only to the runner's messages
do not change the financial key. Each run separately records its runner checksum.

Read `prepare_candidate` in `publication.py`, then its call in `run_pipeline.py`.
The financial formulas are unchanged.
