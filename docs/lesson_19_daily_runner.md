# Part 19: run the daily USD close with one command

We now have a runner for the carry-forward workflow:

```powershell
python run_daily.py --config configs/daily_usd_2025-01-09.json
```

It loads a published opening, applies the new day's activity, calculates NAV,
compares the simulated statements and saves a candidate. It records the attempt
under `data/daily_runs/`. Approval and publication remain separate commands.

The configuration selects the previous date, processing date, opening database,
destination USD database, activity, prices, references and run-record folder.
Paths are relative to the configuration file. Unknown, duplicate or missing fields
and nonconsecutive dates are rejected before processing.

The example points to existing saved deliveries on this machine. A fresh checkout
needs the earlier demonstration opening and deliveries, with paths adjusted.
The destination is `data/daily_usd_pipeline.sqlite`, separate from Part 18's
already-published demonstration database.

## What happens on a retry?

    Attempt A -> candidate X
    Same inputs and opening -> attempt B -> candidate X again
    Revised opening -> attempt C -> new candidate Y

Each attempt has its own run record. The reuse key includes processing dates,
the opening database and exact published opening version, all three input manifest
fingerprints, and calculation/validation code fingerprints. A new delivery or code
revision creates a new key, even if the resulting amounts happen to match.

This version reruns validation and reconciliation before looking for a reusable
candidate. It prevents duplicate saved successes; it does not skip calculation.
Failed candidates are kept for inspection but are not registered as reusable
successes. Missing or corrupted inputs still fail.

SQLite lookup, candidate insertion and reuse registration share one transaction.
Two overlapping attempts may both calculate, but only one successful candidate
is inserted for the same key. A lock timeout can fail a busy attempt; it can retry.

The runner uses a daily-specific key so it cannot accidentally reuse an earlier
single-batch candidate. Candidates from the explicit Part 18 preparation command
are preserved but are not automatically registered for runner reuse.

## Read the result

The command prints a candidate ID and run-record path. Run records contain dates,
configuration evidence, resolved locations, opening publication, manifest hashes,
individual controls and whether the candidate was reused.

| Status | Meaning |
| --- | --- |
| READY_FOR_REVIEW | Checks passed; no approval recorded |
| ALREADY_APPROVED | Reused candidate already has an approval record |
| ALREADY_PUBLISHED | Reused candidate has its original publication record |
| FAILED | Preparation or eligibility failed; inspect the error and controls |

ALREADY_PUBLISHED does not mean that version is still the current version. Use
`publication.py current` to read the latest published close. The runner neither
approves nor publishes, including during retries.

Inspect the result with:

```powershell
python publication.py --database data/daily_usd_pipeline.sqlite show --candidate YOUR_CANDIDATE_ID
```

Malformed configuration returns exit code 2. A failed pipeline returns 1; a
successful or reused eligible result returns 0. Failures during loading/calculation
appear at `prepare_candidate`; failed financial controls appear at `check_candidate`.

## Limits

The saved example is still historical, with synthetic next-day trades, prices
and statements. No scheduler, automatic delivery collection or GBP conversion is
added here. Dates still follow the consecutive-calendar-day lesson rule.

A newly published opening version changes the next run's key. It does not
automatically invalidate existing approvals or rebuild downstream published dates.
Reviewers still need to handle affected dates after corrections.

Run JSON and candidate storage are not one transaction. A killed process may leave
a RUNNING record even though its candidate was committed. A retry can reuse the
committed candidate, but automatic repair of the old log is future work.

The earlier `run_pipeline.py` command remains the fixed-batch GBP lesson. This
daily USD entry point uses `prepare_daily_candidate` and the same review database
rules, giving us a clear place to add scheduling later.
