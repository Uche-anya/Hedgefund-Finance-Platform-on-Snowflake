# Part 6: compare our records with separate statements

**Reconciliation** means comparing records and investigating differences.
Our calculated holding is one record; the broker's statement is another.
Neither side is automatically correct when they disagree.

The broker and administrator in this lesson are fictional. Their reference
files are manually authored from the worked example below. The calculation
does not generate its own comparison values. This is independent fixture
preparation, not independent validation by a real third party or a separate
general-purpose accounting engine.

## Reference answers worked separately

| Statement | Hand calculation for 16 September | Expected |
| --- | --- | ---: |
| Broker: GROWTH / ALPHA | 100 shares bought - 30 sold | 70 shares |
| Broker: HEDGE / BETA | 0 opening shares - 20 shorted | -20 shares |
| Broker: settled GBP cash | 10,000 opening - 1,000 purchase + 330 sale + 400 short sale | 9,730 |
| Administrator: GBP NAV | 9,730 cash + 735 ALPHA value - 360 BETA obligation | 10,105 |

The source files live in `fixtures/references/2026-09-16/`. Broker positions
are explicitly on a trade-date basis: completed trades count even before
settlement. Broker cash is explicitly settled cash. All reference rows name
the NORTHBRIDGE fund and their statement date. We reject incompatible dates,
funds, currencies or bases rather than compare unlike numbers.

## Run the matching comparison

```powershell
$navDelivery = python -m fund_pipeline.landing --business-date 2026-09-14 --bundle nav
$referenceDelivery = python -m fund_pipeline.landing --business-date 2026-09-16 --bundle references
python -m fund_pipeline.reconcile --business-date 2026-09-14 --as-of 2026-09-16 --delivery "$navDelivery" --references "$referenceDelivery"
```

The trade batch is from 14 September, but the requested close and statements
are for 16 September. The reference fixture only covers that date.
You should see four PASS results and a path to a saved JSON report.
JSON is a structured text format; open the file to inspect the numbers and
delivery identifiers behind each check.

## Run the intentional 69-share mismatch

```powershell
python -m fund_pipeline.reconcile --business-date 2026-09-14 --as-of 2026-09-16 --delivery "$navDelivery" --references "$referenceDelivery" --demo-alpha-69
```

The demo copies the reference delivery into a temporary source directory,
changes only GROWTH/ALPHA from 70 to 69, and lands a new reference delivery.
The original source fixtures and saved statements remain unchanged. The report
labels the injected fault and identifies the original reference delivery.

Actual demonstrated output includes:

```text
broker_position GROWTH/ALPHA: FAIL | ours=70 reference=69 difference=1 shares | OUTSIDE_TOLERANCE
Reconciliation: FAIL | NOT APPROVED
```

This is a deliberately inconsistent broker test file, not a new trade. Our
holdings remain 70 and our NAV remains 10,105. The tool does not silently change
either side to make them agree. Its exit code is 1 for a failed comparison, so
a future scheduler can recognise the failure. A passing comparison returns 0.
Malformed inputs also stop the command with a nonzero exit; they do not create
a successful report. Structured ingestion-error reporting remains future work.

## Follow the ALPHA check through the code

1. `reconcile()` verifies the NAV and reference delivery manifests.
2. `calculate_nav()` derives our holdings, cash and NAV using the existing rules.
3. `read_reference()` validates broker rows and requires unique portfolio /
   instrument keys. We also check uniqueness of our calculated position keys.
4. `compare_values()` looks at every key found on either side. It subtracts the
   reference value from ours. For the demo, 70 - 69 = 1 share.
5. A nonzero share difference fails. The report records actual, expected,
   difference, tolerance, unit, entity, date, status and reason, with both input
   deliveries identified at report level. It is saved under `data/reconciliation/`.

Missing rows fail with MISSING_REFERENCE or MISSING_INTERNAL. Unknown values
stay null (missing) in the JSON; they are never converted to a zero balance.
Duplicate keys fail even when their values match.

## Tolerances and limits

A **tolerance** is the largest allowed absolute difference. Shares must match
exactly; cash and NAV allow one penny inclusive. These are initial teaching
thresholds, not production materiality agreed with a real fund. Comparisons use
Decimal values before display rounding.

PASS means these four comparisons matched. It does not mean approval to publish.
There are no investor access controls, approval records or publication workflow
yet. All outputs remain NOT APPROVED. Price correctness, fees, FX and full
broker/administrator integration still need additional controls and contracts.

Reference totals can share conceptual mistakes with our calculation because we
authored both. Tests also drop a trade from a copied input history while keeping
references intact, proving that discrepancies reach the position, cash and NAV
checks rather than being hidden by successful execution.

## Your exercise

Run the demo, then rerun the matching command without `--demo-alpha-69` using
the same original `$referenceDelivery`. Predict whether it will pass and why.
Open both saved reports and find the changed reference delivery ID, the one-share
difference and the intentional-fault label.
