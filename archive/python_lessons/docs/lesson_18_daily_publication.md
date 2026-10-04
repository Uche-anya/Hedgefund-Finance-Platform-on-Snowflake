# Part 18: review and publish the next-day USD close

The next-day calculation can now become a saved candidate in the existing SQLite
review workflow. **Candidate** means a proposed result; **publication** records a
reviewed version that a later day can use as its opening.

    Calculate and reconcile -> save candidate -> review -> approve -> publish

Preparation stores the exact checked snapshot: holdings, cash, unpaid obligations,
NAV, all controls, opening publication/version, input fingerprints and code hashes.
It also stores every known execution ID, including trades that have already settled.

## Prepare the example

Use the activity, prices and reference delivery variables from Part 17, or land
them again:

```powershell
$activity = python -m fund_pipeline.landing --business-date 2025-01-09 --bundle daily_cash
$prices = python -m fund_pipeline.landing --business-date 2025-01-09 --bundle daily_prices
$references = python -m fund_pipeline.landing --business-date 2025-01-09 --bundle daily_references
$db = 'data/my_daily_usd_review.sqlite'
$candidate = python -m fund_pipeline.prepare_daily --database $db --opening-database data/gbp_publication_demo.sqlite --previous-date 2025-01-08 --business-date 2025-01-09 --delivery $activity --prices $prices --references $references
python -m fund_pipeline.publication --database $db show --candidate $candidate
```

There are two databases here. `--opening-database` supplies the published opening
from Part 10's demonstration; `--database` receives the new USD candidate. We keep
USD publications separate from GBP publications. The original USD balances inside
the translated opening are used; translated GBP cash is never treated as USD.

Review the seven comparisons, USD NAV, payable and opening lineage. The expected
known execution IDs are SIM-E001, SIM-E002, SIM-D2-E001 and SIM-D2-E002.

After reviewing the candidate, these are the learning-demo approval commands:

```powershell
python -m fund_pipeline.publication --database $db approve --candidate $candidate --by demo-reviewer --note 'Reviewed synthetic next-day USD controls and history' --expected-version 0
python -m fund_pipeline.publication --database $db publish --candidate $candidate
python -m fund_pipeline.publication --database $db current --as-of 2025-01-09
```

Expected version 0 means no publication exists for 9 January in that database.
If a version exists, review against its actual number. `demo-reviewer` is an
asserted local test identity, not authentication or approval under your name.

## What is blocked?

Preparation can save a failed candidate for inspection. Approval and publication
both independently check the frozen controls. The Apple-12 discrepancy blocks
both actions, as do overdue settlement obligations. Passing controls alone do not
create an approval. Publication without a recorded approval fails.

The existing version rules apply: retries of an already-published candidate return
its original version, corrections require a new candidate and review, and an old
approval cannot overwrite a more recently published version for the same date.

## Using this close tomorrow

For 10 January, the USD database can serve as both opening and destination:

    opening database = daily USD database
    previous date = 2025-01-09
    business date = 2025-01-10

Provide actual matching 10 January activity, prices and comparison deliveries.
The daily opening now reads its execution history directly from the frozen
candidate. It no longer rebuilds history from only one day's trade file. This
retains the USD 720 payable and prevents an old execution ID being reused.

Tests prepare and publish a synthetic 10 January close with no new trades, settle
the carried payable and confirm NAV is unchanged when prices do not move. They
also remove the previous day's activity folder to prove the frozen daily state
supplies the opening without rereading it. Original source files should still be
retained for audit; deletion is only a temporary test.

## Current limits

The daily workflow supports USD, consecutive calendar dates, full settlements and
the simple ledger already built. It does not yet translate the new day to GBP or
run through the configuration-based historical runner. Each `prepare_daily` call
creates a new review candidate; historical-run candidate reuse has not been added
to that explicit preparation entry point. [Part 19](lesson_19_daily_runner.md)
now adds a configured daily runner with candidate reuse keyed to the opening version.

An opening correction does not automatically invalidate or rebuild later dates.
Each candidate preserves the opening version it actually used. Reviewers must
check that lineage and prepare/review affected dates again when required.
No authenticated reviewers, scheduler, cross-source ID registry, fees, partial
settlements, corporate actions or trading-calendar policy are implied.
