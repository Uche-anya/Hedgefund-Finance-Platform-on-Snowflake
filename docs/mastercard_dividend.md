# Mastercard dividend: entitlement and payment

The replay covers January 6 through February 7, 2025. It combines real saved
prices and a reviewed dividend with fictional trades and one fictional cash receipt.

| Account | Shares entering January 10 | Gross entitlement | February 7 confirmation |
| --- | ---: | ---: | --- |
| SIM-REPLAY-01 | -134 | USD -101.84 | None; payable stays outstanding |
| SIM-REPLAY-02 | 335 | USD 254.60 | USD 254.60 received |

## Scoped review: MA_JAN_2025_DATE_REVIEW

Recorded September 27, 2026. The
[issuer announcement](https://investor.mastercard.com/investor-news/investor-news-details/2024/Mastercard-Board-of-Directors-Announces-Quarterly-Dividend-and-12-Billion-Share-Repurchase-Program/)
supports USD 0.76 per share, a January 9 record date and February 7 payment date.
[Nasdaq's closure notice](https://classic.nasdaqtrader.com/TraderNews.aspx?id=ETA2025-1)
supports moving the affected ex-date to January 10. Massive instead supplies
January 10 as the record date. We retain that provider value and show January 9
in a separate reviewed column; raw records are unchanged.

For this scenario, MA.US represents Mastercard Class A common stock. Gross
eligibility uses the opening trade-date position on January 10, with zero holdings
before the replay. Later trades do not change the entitlement. This is a simulation
assumption, not verification of legal ownership, settlement claims, lending terms
or tax treatment. Other corporate actions are still outside this accounting lesson.

## What the models do

- `fct_dividend_accruals` fixes the expected amount per account and event.
- `fct_daily_cash` matches a confirmation by scenario, account, dividend ID,
  instrument, currency and full gross amount. It counts cash only when both
  settlement time and publication time are within the session cutoff. Confirmed
  cash replaces the receivable or payable.
- `fct_daily_nav` adds cash and outstanding dividend balances once. It retains
  `nav_before_dividends` for comparison.

`confirmed_dividend_cash` is cumulative confirmed dividend cash, not a daily flow.
The accrual table retains the original entitlement after payment; outstanding
balances live in the daily cash and NAV tables.

For account 02, February 7 changes dividend receivable from 254.60 to zero and
adds 254.60 to cash. The dividend contribution to NAV stays 254.60. Daily NAV can
still change as share prices move. For account 01 the 101.84 payable remains:
the scheduled payment date alone proves no cash movement.

This lesson accepts one full gross confirmation per account/event. Duplicate,
unknown, wrong-currency and wrong-amount payments fail validation. Partial
payments, tax withholding, reversals and lending adjustments need separate work.
The calendar scope test stops dates beyond February 7.

## Saved inputs and running

1. `python scripts/prepare_dividend_replay.py` checks the extended calendar and
   prices, preserves the January records, and appends six sessions with no trades.
2. `python simulation/dividend_payment.py` appends the fictional receipt for account
   02, settled February 7 at 18:00 UTC and published at 18:01 UTC. It deliberately
   leaves account 01 without confirmation.
3. `python scripts/run_replay.py` verifies the saved inputs, loads SQL 22, builds
   dbt and compares results to an independent Python calculation.

Current delivery: `sim-dividend-a48996d29c0473a090db3b9f`, under `data/replays/`.
It contains the entire January replay plus six sessions and one payment: 6,394
records, 23 sessions, 3,200 trades and 3,168 trade confirmations. The scenario ID
stays `sim-replay-406bbef8179cdbb0a3dd6df3`; the delivery ID changes because this
is a new package. dbt selects only this package, avoiding duplicate January trades.

The [NYSE calendar](https://www.nyse.com/publicdocs/ICE_NYSE_2025_Yearly_Trading_Calendar.pdf)
and pinned saved prices cover all six added sessions: January 31 and February 3-7.
All 120 additional closes were verified. The original January package remains saved.

## Inspect the change

```sql
select business_date, account_id, reported_settled_cash,
       confirmed_dividend_cash, dividend_receivable, short_dividend_payable,
       simplified_nav - nav_before_dividends as dividend_nav_contribution
from NORTHBRIDGE_DEV.DBT_DEV.FCT_DAILY_NAV
where business_date in ('2025-02-06', '2025-02-07')
order by account_id, business_date;
```

The earlier read-only query in SQL 21 remains an entitlement illustration.
Payment confirmations here are fictional test inputs, not evidence from a broker.

## Reconciliation report

Run `snowflake/23_dividend_reconciliation.sql` in Snowsight for the February 7
session cutoff. It compares each accrued dividend with confirmations known by
that cutoff. It is read-only and creates no additional dbt model.

Amounts are signed: positive means cash expected in, negative means cash expected
out. Outstanding amount equals expected amount minus confirmed amount. Account 02
should show MATCHED (254.60 expected and confirmed); account 01 should show
NO_CONFIRMATION (-101.84 expected, zero confirmed). The latter means evidence is
missing, not that a bank has confirmed failure or a lending payment is overdue.

The report also distinguishes an amount mismatch and multiple confirmations.
The existing dbt input checks reject unsupported or unmatched payment records;
this query reports on the known entitlements rather than replacing those checks.
Wrong-currency or unknown-action records need the input validation results.
Saved report results live in `data/dividend_reports/`, with the Snowflake query ID.
