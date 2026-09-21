# Part 14: carry yesterday's holdings into today

**Opening holdings** are the shares we bring into a day. **Closing holdings**
are the shares left after applying that day's trades.

    Closing quantity = opening quantity + today's buys - today's sells

`build_positions.py` calculates the movement from one trade batch starting at
zero. We now add that movement to yesterday's published holdings.

## The example

We use the published 8 January holdings and two simulated 9 January trades:
buy 3 Apple shares and buy back 2 Amazon shares.

| Position | Opening | Today's movement | Closing |
| --- | ---: | ---: | ---: |
| GROWTH / Apple | 10 | +3 | 13 |
| HEDGE / Amazon | -5 | +2 | -3 |

Buying back shares sold short is called **covering the short**. Starting with
a short position of 5 and buying back 2 leaves a short position of 3.
Positions without trades stay unchanged. A new portfolio/instrument pair starts
at zero. Selling all a holding leaves zero; selling more produces a short position.
This arithmetic does not check borrowing permission or broker restrictions.

## Run it in PowerShell

```powershell
$delivery = python landing.py --business-date 2025-01-09 --bundle trades
python carry_positions.py --database data/gbp_publication_demo.sqlite --previous-date 2025-01-08 --business-date 2025-01-09 --delivery $delivery
```

The database is the labelled local demonstration from Part 10, published under
`demo-reviewer`. Unapproved candidates in the separate pipeline database cannot
be used as published opening balances. A fresh checkout needs to complete the
opening publication example or supply its own published close first.

The command saves a JSON report under `data/positions/`. It includes each opening
quantity, today's movement, closing quantity, opening candidate/version and the
new trade delivery's fingerprint. No share prices are needed to count shares.
Both new trades are simulated; no broker order is placed.

## Why a rerun does not buy another three shares

Every calculation starts from the same saved opening and applies today's batch
once. Yesterday's close is never updated in place. Repeating the calculation
creates another report with the same quantities. Existing trade checks ignore
exact repeated IDs within the batch and reject conflicting or unallocated trades.

The latest published version for the selected opening date is used, and its ID
and version are recorded. If that date is corrected and republished, a new run
uses the corrected opening; earlier reports remain unchanged. Automatic rebuilding
of later dates after a correction is future work.

## Boundaries of this lesson

- Dates must be consecutive calendar days; skipped dates are rejected. Trading
  calendars and weekend/holiday handling come later.
- Trade IDs are checked within today's batch. Cross-day duplicate tracking and
  corporate actions are not implemented.
- This report is HOLDINGS ONLY - NOT APPROVED. It does not calculate cash,
  settlement obligations, prices or NAV, and cannot supply a published third-day
  opening until we extend the full close.
- The existing USD/GBP runner is unchanged. This is a separate small step toward
  extending it to daily activity.

Read `carry_positions.py`: load a published opening, validate the new delivery,
calculate today's movement, then add the two quantities by portfolio and instrument.
