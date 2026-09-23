# Part 5: calculate the fund's net asset value

**NAV (net asset value)** is what the fund owns minus what it owes. We now
derive its holdings and cash from the trades, rather than supplying balances
as we did in Part 1.

## Our calculation after settlement

| Component | How we got it | GBP |
| --- | --- | ---: |
| Settled cash | 10,000 - 1,000 + 330 + 400 | 9,730 |
| ALPHA shares owned | (100 bought - 30 sold) times closing price 10.50 | 735 |
| BETA shares owed | 20 borrowed shares times closing price 18 | -360 |
| **NAV** | **9,730 + 735 - 360** | **10,105** |

The BETA short is an obligation, not an asset. Its negative signed value
already subtracts what we owe. The report shows that obligation as a positive
GBP 360 on a line labelled "Subtract short share obligations". These are two
ways of describing the same amount; we subtract it only once.

Before settlement we must also include trade receivables and payables:

```text
NAV = settled cash + receivables - payables
      + long share assets - short share obligations
```

| As-of date | Cash | Receivables | Payables | Long assets | Short obligations | NAV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 14 September | 10,000 | 730 | 1,000 | 735 | 360 | 10,105 |
| 15 September | 9,000 | 730 | 0 | 735 | 360 | 10,105 |
| 16 September | 9,730 | 0 | 0 | 735 | 360 | 10,105 |

The same NAV across these dates is intentional: the fixture supplies unchanged
closing prices and has no new trades, fees or other activity. Settlement only
changes outstanding amounts into cash. In a real daily series, prices can move.

## Run it in PowerShell

```powershell
$navDelivery = python -m fund_pipeline.landing --business-date 2026-09-14 --bundle nav
python -m fund_pipeline.fund_nav --business-date 2026-09-14 --as-of 2026-09-16 --delivery "$navDelivery"
```

Change `--as-of` to `2026-09-14` or `2026-09-15` to see the unsettled balances.
The business date identifies this one trade batch; as-of selects the valuation
date. This is a retrospective synthetic scenario, not a multi-day trading feed.

The `nav` bundle saves Part 4's five source files plus `closing_prices.csv`
from the same settlement fixture folder. Previous settlement deliveries remain
unchanged and do not suddenly acquire prices. Save a new NAV delivery to run
this lesson. Each closing price has an explicit valuation date, instrument,
currency and GBP-per-share amount. Execution prices and closing prices serve
different purposes: one determines the payment; the other values the holding.

## Follow ALPHA through the code

1. `verify_delivery()` verifies all six saved files before calculation.
2. `calculate_nav()` calls `calculate_cash()`, which already calls
   `build_positions()`. Existing trade, allocation and settlement checks apply.
3. That produces GROWTH's 70 ALPHA shares and the fund's cash/obligations.
4. `read_closing_prices()` selects ALPHA's price for the exact as-of date.
5. 70 times GBP 10.50 becomes GBP 735 of long assets. BETA contributes GBP 360
   of short obligations. The NAV formula combines them with the cash balances.

The NAV function returns only after all required prices are present. It does
not turn an unknown price into zero or silently take yesterday's price.
Even identical duplicate price keys fail to avoid an ambiguous join.

## Exercise: make the short more expensive

In the source `fixtures/settlement/2026-09-14/closing_prices.csv`, change only
BETA's 16 September price from 18.00 to 19.00. Predict the new NAV, then save a
new NAV delivery and calculate it for that date.

The short obligation increases by GBP 20, so NAV falls to GBP 10,085. Running
the original saved delivery still returns GBP 10,105. Restore the source price
afterwards. This tests reproducibility; approved restatement history comes later.

## What we have verified

The suite checks the hand-worked NAV, settlement invariance, missing/stale prices,
duplicate and invalid prices, repeated trade events, missing settlement
confirmations, allocation breaks and preserved inputs after a price change.

All reports remain **NOT APPROVED**. An overdue obligation is included and shown;
there is no automated approval decision. Prices are synthetic and assumed
approved within the exercise, not checked against a live market-data source.
Fees, FX, corporate actions, investor flows, cost basis and performance reporting
are still outside this slice. Calculation outputs are printed, not persisted.

The next control to build is reconciliation: compare our result with separately
prepared expected balances and investigate differences before publication.
