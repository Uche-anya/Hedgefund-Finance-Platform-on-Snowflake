# Part 10: checking and approving the GBP close

We already translated our USD fund value into pounds. Now we check that result
before allowing it into the publication history.

## The separate calculation

The pipeline multiplies USD balances by a GBP-per-USD rate. Our learning reference
instead takes the separate USD comparison statements and converts through euros:

    GBP reference = USD reference / USD per EUR * GBP per EUR

For example, with a USD NAV of 10,000, USD per EUR of 1.25 and GBP per EUR of 1.00:

    10,000 / 1.25 * 1.00 = GBP 8,000

These are invented teaching numbers. Dividing by the GBP-per-USD rate instead
would give GBP 12,500, so getting the direction wrong matters.

We compare GBP NAV and settled cash within one penny. We also check rate direction
against the raw EUR observations within half of the twelfth decimal place, to allow
the documented rate rounding. Every existing USD position, cash and NAV check
must pass too. Missing FX stops preparation. Failed comparisons leave a candidate
available for inspection but block approval and publication.

This is separate arithmetic, not an independent administrator's statement. The
reference shares our USD fixture and FX source, so common source errors can still
pass. Individual GBP holdings and obligations are translated but do not yet have
separate external comparisons.

## Run it in PowerShell

Use the saved deliveries from Parts 8 and 9. This requires no new download.

```powershell
$nav = 'data/landing/2025-01-06/18ae80085f1043789b5d604ee44dc216'
$usd = 'data/landing/2025-01-08/213ac7b4b9a84e009ae529b887ce0a0c'
$fx = 'data/fx/f5a7a63c62c44150b12ebbfdc7a09203'
$db = 'data/my_gbp_review.sqlite'
$reference = python gbp_reference.py --references $usd --fx-delivery $fx --as-of 2025-01-08
$candidate = python publication.py --database $db prepare --delivery $nav --references $usd --fx-delivery $fx --gbp-references $reference --business-date 2025-01-06 --as-of 2025-01-08 --currency GBP
python publication.py --database $db show --candidate $candidate
```

A **candidate** is a saved result waiting for review. Read its `controls`, original
`local_close` in USD, reporting `close` in GBP and `fx_evidence`. Evidence includes
the selected rate/date, source manifest, file fingerprints and valuation policy.
A fingerprint lets us detect changed bytes; it does not authenticate a provider.
Use a separate database for this scenario.

After inspecting the result, a learning approval can be recorded as:

```powershell
python publication.py --database $db approve --candidate $candidate --by demo-reviewer --note 'Reviewed USD and GBP checks and same-date FX evidence; learning demonstration' --expected-version 0
python publication.py --database $db publish --candidate $candidate
python publication.py --database $db current --as-of 2025-01-08
```

`0` means no version has been published for that date. If one already exists,
review against the actual current version. Local reviewer names are asserted text,
not authenticated identities.

## What happens when a rate is corrected?

Save a new FX delivery, generate a new matching reference, then prepare and review
a new candidate. Publication advances to version 2 only after its own approval.
Version 1 keeps its original balances, rate and review. Re-publishing version 1
does not make it current again. An old reference cannot be paired with a new FX
delivery. Tests simulate a correction using explicitly labelled synthetic rates;
we do not claim the saved real ECB observations were revised.

Review and publication use the frozen candidate. They do not recalculate from
files that may have changed since preparation. Source monitoring and discovering
provider revisions are still future work.

Read `gbp_reference.py` first, then `reconcile_gbp.py`, then the small extension
to `publication.prepare`. SQLite still handles the same approval transactions
and version history from Part 7. This remains a local learning workflow.
