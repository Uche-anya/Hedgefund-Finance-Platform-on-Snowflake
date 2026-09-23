# Part 21: Friday's close can become Monday's opening

A **business calendar** defines which dates need a close. Our first calendar is
deliberately simple: Monday through Friday, with no holiday exclusions yet.
Its recorded policy name is `WEEKDAYS_ONLY_NO_HOLIDAYS`.

The next close after Friday 10 January 2025 is Monday 13 January. Saturday and
Sunday are not valuation dates under this policy. We still reject skipping a
weekday: Friday cannot jump straight to Tuesday without Monday's close.

## Run Monday

```powershell
python -m fund_pipeline.run_daily --config configs/daily_usd_2025-01-13.json
```

The example uses Friday's published version 1 in `data/daily_usd_pipeline.sqlite`.
It has its own simulated Monday activity, prices and reference deliveries. No
new trades or payments occur, and the teaching prices stay unchanged. Cash is
USD 7,528.05 and NAV is USD 10,103.05. The Monday result is saved for review only.

Fresh checkouts need the published Friday example and their own landed delivery
paths. The saved configuration refers to deliveries on this machine.

## Monday still needs Monday's inputs

Skipping weekend valuation dates is not permission to reuse Friday's prices.
The runner requires all three Monday deliveries: activity, closing prices and
comparison statements. Empty activity files with valid headers explicitly mean
there were no events; missing files do not mean no events.

We demonstrated that missing Monday prices and missing references stop the run.
A delivery labelled Monday but containing only Friday prices also stops with
`Missing closing price ... on 2025-01-13`. None of these failures creates a candidate.
The error and selected input locations remain in each failed run record.

## What about payments during the weekend?

Monday's settlement batch can include confirmations for obligations already open
on Friday, with actual settlement dates after Friday and through Monday:

    Friday close < actual settlement date <= Monday close

For example, a simulated Saturday payment can appear as:

```csv
business_date,settlement_id,execution_id,currency,amount,settled_on
2025-01-13,S1,OLD-BUY,USD,720.00,2025-01-11
```

Here `business_date` identifies Monday's processing batch; `settled_on` identifies
when the payment actually happened. The cash movement preserves that actual date.
This is a demonstration of handling a supplied event, not a claim that these
equity trades normally settle on weekends.

Tests use an opening of USD 1,000 cash, a USD 720 payable and a USD 50 receivable.
The payable settles Saturday and the receivable Sunday. Monday cash becomes
1,000 - 720 + 50 = USD 330, with no remaining obligations. Repeating a confirmation
row does not repeat the movement, and rerunning from the same opening gives the
same result.

Confirmations dated on/before Friday are rejected because they belong to an
already-closed period. Dates after Monday are rejected because they are in the
future for this close. A new Monday trade cannot settle before its trade date.
Late-arriving confirmations for an earlier closed period still require a future
correction/replay process.

If no confirmation arrives, an obligation remains unpaid. A Saturday/Sunday due
date is not silently shifted to Monday: the existing rule marks it overdue by
Monday. The approval gate continues to block overdue obligations.

## Code and limitations

`fund_pipeline/business_calendar.py` holds the shared date rule. Configuration, holdings and
cash processing all use it. The policy is stored in new run records and reports,
and the calendar code is included in daily candidate fingerprints, so a calendar
code change cannot silently reuse an earlier candidate.

This supersedes the consecutive-calendar-day restriction in the earlier lessons.
It is not an exchange calendar. Public/exchange holidays, early closes, time-zone
cutoffs and provider-specific settlement calendars remain future work. Weekday
holidays currently require inputs like any other weekday; missing data stops the
run rather than being silently skipped. Weekend trades and corporate actions are
not supported. No scheduler or automatic download has been installed.

The Monday demonstration had no open Friday obligations; the weekend payment
examples are tested separately with synthetic opening obligations. The original
published Friday close was preserved throughout.
