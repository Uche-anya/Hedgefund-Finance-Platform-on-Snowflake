# Part 2: keep the inputs behind a result

Suppose yesterday's close said GBP 10,090. Today someone changes a source price.
Reading the source folder again now gives a different answer. We need the exact
inputs used yesterday, as well as any later correction.

## Three terms

| Term | Meaning in this lesson |
| --- | --- |
| Landing | A place to save received files before calculating anything |
| Delivery | One received batch, identified by a unique ID |
| Manifest | A receipt listing the delivery's files, date, record counts and checksums |

A **checksum** is a fingerprint calculated from a file's bytes. If the bytes
change, the SHA-256 checksum will almost certainly change too. It helps detect
accidental edits or corruption; it does not prove that a price is correct.

## Run it in PowerShell

```powershell
$delivery = python -m fund_pipeline.landing --business-date 2026-09-14
Get-Content -LiteralPath "$delivery\manifest.json"
python -m fund_pipeline.daily_close --business-date 2026-09-14 --delivery "$delivery"
```

`$delivery` holds the new directory path printed by `fund_pipeline/landing.py`.
The close prints its delivery ID and should still show NAV of GBP 10,090.
Running the last command again uses the exact same saved delivery.

```text
fixtures/2026-09-14/           (our synthetic source files)
           |
           | copy unchanged bytes
           v
data/landing/2026-09-14/<delivery ID>/
    positions.csv
    prices.csv
    cash.csv
    manifest.json             (written last)
           |
           | verify date, required files and checksums
           v
fund_pipeline/daily_close.py                (calculate one complete snapshot)
```

## Walk one file through the code

1. `land_delivery()` creates a new directory. It never reuses an old delivery.
2. It copies `prices.csv` unchanged, then `describe_file()` counts records and
   calculates its checksum. The same happens for the other input files.
3. After all copies succeed, it writes the receipt to a temporary filename,
   then renames it to `manifest.json`. That final name means copying completed.
4. With `--delivery`, the close calls `verify_delivery()` before calculating.
   A missing manifest or changed file stops the close.

If copying fails, partial files remain for investigation. They have no completed
manifest, so they cannot be used through the delivery command. Retry by landing
a new delivery; do not repair or overwrite the partial folder.

## What a repeat means here

Receiving the same files twice produces two separate delivery receipts. Each
close reads exactly one full snapshot, so NAV is not doubled. We do not scan
all directories and add their positions together.

This is not yet trade-event deduplication. When we introduce trades, stable
event IDs and source versions will prevent a repeated trade changing holdings
twice. A corrected price creates a new delivery; approval and publication
versioning are still future work.

## Exercise

Keep the `$delivery` path. Change BETA's price in the **source fixture** from
18.00 to 19.00, then calculate from `$delivery` again. Predict the result first.
Land another delivery and calculate that one. Explain why the original still
returns GBP 10,090 while the new one returns GBP 10,070. Restore the fixture
price to 18.00 afterwards. Never edit the saved delivery to apply a correction.

## Limits of this step

- Inputs are still synthetic. This bundles three lesson files; real source
  systems will have separate deliveries and richer contracts.
- Source files must be finished and stable before copying. We have not built
  a transactionally consistent extract from a changing source database.
- Completed landing means copied successfully, not financially approved.
- Files are immutable by application convention: our writer never overwrites
  them. This is not filesystem access control or cloud retention enforcement.
  Someone able to edit both data and manifest could bypass the checksum check.
- The Part 1 command without `--delivery` remains a direct-fixture exercise.
- Financial outputs are printed, not persisted or published. Reproducing an
  old result across code changes will also require recording code versions.
- There is no scheduler, API download, Snowflake connection or ML model yet.

Run all checks with `python -m unittest discover -s tests -v`.
