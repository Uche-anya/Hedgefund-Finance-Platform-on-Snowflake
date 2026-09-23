# Part 16: the next day's NAV

We now combine next-day holdings, settled cash, unpaid trade obligations and
closing share prices. **NAV** is the net value of the fund after its obligations.

Our 9 January closing prices are explicitly invented teaching prices: Apple
USD 245 and Amazon USD 225. They are not downloaded historical observations.
The original opening still comes from the published 8 January hybrid example.

## Check the arithmetic

| Component | Calculation | USD value |
| --- | --- | ---: |
| Cash | Opening cash less confirmed Amazon payment | 8,248.05 |
| Apple holding | 13 shares times 245 | 3,185.00 |
| Amazon short | 3 shares owed times 225 | -675.00 |
| Unpaid Apple purchase | 3 shares bought at 240 | -720.00 |
| **NAV** | **8,248.05 + 3,185 - 675 - 720** | **10,038.05** |

The Amazon short value is a valuation of shares owed, not another cash payment.
We bought back two shares already; the remaining three are still short. We
subtract their value once.

The Apple purchase price of 240 determines the payable. The closing price of
245 determines what the shares are worth at the end of the day. These prices
serve different purposes.

If the USD 720 payable settles, cash falls by 720 and the payable disappears.
Those changes offset in NAV. Settlement alone does not create a profit or loss.
Tests check this relationship, and check that a USD 1 rise in Amazon's price
reduces NAV by USD 3 while we remain short three shares.

## Run the lesson

```powershell
$activity = python -m fund_pipeline.landing --business-date 2025-01-09 --bundle daily_cash
$prices = python -m fund_pipeline.landing --business-date 2025-01-09 --bundle daily_prices
python -m fund_pipeline.daily_nav --database data/gbp_publication_demo.sqlite --previous-date 2025-01-08 --business-date 2025-01-09 --delivery $activity --prices $prices
```

The command needs Part 10's existing demonstration publication. A fresh checkout
must prepare that opening publication or supply an appropriate one. Both new
deliveries are labelled synthetic by the landing command. Prices are preserved
with their own manifest and verified before valuation.

`fund_pipeline/daily_nav.py` calls the daily cash calculation, then reads holdings from that
same opening candidate ID. It does not select the latest opening publication a
second time, which could mix two versions if a correction were published during
the run. Today's holdings and cash use the same activity delivery.

Every nonzero holding needs a valid same-date price in the local cash currency.
Missing, stale, duplicate, non-finite and wrong-currency prices stop valuation.
No missing holding is silently valued at zero.

The report is saved under `data/daily_nav/`. It includes opening publication
lineage, activity and price fingerprints, quantity movements, cash obligations,
share values and NAV. Replaying the same opening and inputs yields the same
financial result and a separate report.

## What this result means

This is a USD daily NAV calculation, marked NOT RECONCILED OR APPROVED. The hand
calculation is a learning check; it is not an external administrator comparison.
It has not been translated into GBP, saved as a review candidate or published.

The existing opening limitations still apply: one original trade-batch publication,
one subsequent calendar day, no fees, corporate actions or partial settlements.
Complete daily history persistence and integration with reconciliation/publication
are later steps. The existing configured historical runner is unchanged.
