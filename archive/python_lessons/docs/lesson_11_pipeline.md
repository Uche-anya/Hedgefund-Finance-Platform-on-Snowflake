# Part 11: one command for the saved-data pipeline

A **pipeline runner** calls our existing steps in order and records what happened.
It does not need to contain the financial formulas itself.

Our flow is:

    Check saved inputs
      -> calculate and reconcile USD
      -> translate and reconcile GBP
      -> save candidate
      -> check eligibility for review

`fund_pipeline/run_pipeline.py` calls `publication.prepare`, which already performs the middle
steps using one calculated snapshot. It then inspects the saved candidate. A failed
comparison remains available for investigation and makes the run fail. It never
approves or publishes a result.

## Run the historical example

From the project folder in PowerShell:

```powershell
python -m fund_pipeline.run_pipeline `
  --delivery data/landing/2025-01-06/18ae80085f1043789b5d604ee44dc216 `
  --references data/landing/2025-01-08/213ac7b4b9a84e009ae529b887ce0a0c `
  --fx-delivery data/fx/f5a7a63c62c44150b12ebbfdc7a09203 `
  --gbp-references data/landing/2025-01-08/7b49b33130d44197b9a57f1c4e7d2d0e `
  --business-date 2025-01-06 `
  --as-of 2025-01-08
```

`business-date` identifies our original trade batch. `as-of` is the date we value
the fund. These differ because this example follows one batch across several days.
The four paths explicitly select the saved input deliveries. The GBP comparison
delivery was prepared separately in Part 10; the runner does not manufacture a
fresh reference from its own calculated result.

Successful output says `READY_FOR_REVIEW`, gives a run-record path and a candidate
ID. The default candidate database is `data/gbp_pipeline.sqlite`. Inspect it with:

```powershell
python -m fund_pipeline.publication --database data/gbp_pipeline.sqlite show --candidate YOUR_CANDIDATE_ID
```

Approval and publication still follow Part 10 as separate actions.

## Read the run record

Each attempt has a new JSON file in `data/runs/`. JSON is a text format that stores
named fields, so both people and programs can read the result.

| Field | Meaning |
| --- | --- |
| `run_id` | Unique identifier for this attempt |
| `business_date`, `as_of` | Trade batch date and valuation date |
| `inputs`, `manifest_sha256` | Selected folders and fingerprints of verified manifests |
| `started_at`, `finished_at` | Start and finish times in UTC |
| `stage`, `steps` | Current/last stage and completed checks |
| `status` | RUNNING, FAILED or READY_FOR_REVIEW |
| `candidate_id` | Saved candidate, if preparation completed |
| `controls` | Individual financial comparison results, when available |
| `error` | Failure type and explanation, if the run failed |

The stages are `check_inputs`, `prepare_candidate` and `check_candidate`.
Calculation and reconciliation errors appear under `prepare_candidate` with their
error message; this lesson does not log separate timing for every financial step.

## Try a failure

Rerun the command with `--fx-delivery data/fx/missing_example`. It should report
`FAILED`, stop at `check_inputs`, and save an error record without a candidate.
The original successful run remains unchanged.

An **exit code** tells another program whether the command worked: this runner
returns 0 when ready for review and 1 on a caught failure. PowerShell exposes it
as `$LASTEXITCODE`. A future scheduler can use it to detect failed runs.

## What rerunning means

Each rerun creates a new attempt. Part 12 now reuses a successful candidate when
dates, delivery manifests and calculation code match. Otherwise preparation saves
a new candidate. See [Part 12: reruns](lesson_12_reruns.md). Earlier attempts and
publication versions are preserved.

Run records are replaced atomically: a reader sees a complete old or new JSON
record. They are not a transaction with SQLite. A process killed just after saving
a candidate may leave a RUNNING record without its candidate ID. Investigate the
database when investigating. Part 12 lets a retry reuse a committed successful
candidate even when its run log is incomplete. Disk/write failures can prevent the final record from
being saved; the command will fail rather than report success.

This is still a local historical replay. It does not download new data, select
deliveries automatically, handle a rolling multi-day trade ledger, or schedule
itself. Those are separate steps toward a daily production service. The existing
synthetic-reference and same-date ECB valuation limitations still apply.
